"""Pacientes: lista, cadastro e ficha (dados, consultas e pagamentos)."""
import unicodedata

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import br, tempo, web
from ..dados.store import Conflito
from ..web import exige, store

bp = Blueprint("pacientes", __name__, url_prefix="/pacientes")
CAMPOS = ("name", "usesSocial", "socialName", "cpf", "birth", "phone", "email", "insurance", "guardian",
          "cep", "street", "number", "complement", "district", "city", "uf", "notes")


def _sem_acento(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


@bp.route("/")
@exige("pacientes")
def lista():
    q = (request.args.get("q") or "").strip()
    ps = store().listar("patients", ordem="nome")
    if q:
        qn, qd = _sem_acento(q), br.digitos(q)
        ps = [p for p in ps if qn in _sem_acento(p.get("name")) or qn in _sem_acento(p.get("socialName"))
              or (qd and (qd in br.digitos(p.get("cpf")) or qd in br.digitos(p.get("phone"))))]
    return render_template("pacientes.html", pacientes=ps, q=q, total=len(ps))


def _validar(v, id_atual=None):
    erros = {}
    if not v["name"]:
        erros["name"] = "Informe o nome"
    if v["usesSocial"] == "s" and not v["socialName"]:
        erros["socialName"] = "Informe o nome social"
    if br.cpf_erro(v["cpf"]):
        erros["cpf"] = br.cpf_erro(v["cpf"])
    elif v["cpf"]:
        d = br.digitos(v["cpf"])
        outro = next((p for p in store().listar("patients", "cpf IS NOT NULL AND cpf <> ''") if br.digitos(p.get("cpf")) == d and p["id"] != id_atual), None)
        if outro:
            erros["cpf"] = f"CPF já cadastrado para {outro['name']}"
    if br.telefone_erro(v["phone"]):
        erros["phone"] = br.telefone_erro(v["phone"])
    if br.cep_erro(v["cep"]):
        erros["cep"] = br.cep_erro(v["cep"])
    if v["birth"] and v["birth"] > tempo.hoje():
        erros["birth"] = "Data de nascimento no futuro"
    return erros


def _aplicar(p, v):
    p.update(name=v["name"], socialName=v["socialName"] if v["usesSocial"] == "s" else "", cpf=br.cpf_formata(v["cpf"]) if v["cpf"] else "",
             birth=v["birth"], phone=br.telefone_formata(v["phone"]) if v["phone"] else "", email=v["email"], insurance=v["insurance"],
             guardian=v["guardian"], cep=br.cep_formata(v["cep"]) if v["cep"] else "", street=v["street"], number=v["number"],
             complement=v["complement"], district=v["district"], city=v["city"], uf=v["uf"], notes=v["notes"])
    p["address"] = br.endereco_formata(p)
    return p


@bp.route("/novo", methods=["GET", "POST"])
@exige("pacientes", 2)
def novo():
    v = web.campos(*CAMPOS) if request.method == "POST" else {"insurance": "Particular", "usesSocial": "n"}
    erros = {}
    if request.method == "POST":
        erros = _validar(v)
        if not erros:
            p = _aplicar({"createdAt": tempo.hoje(), "anamnesis": {}, "gallery": [], "docs": []}, v)
            p = store().salvar("patients", p, acao=f"Paciente cadastrado: {p['name']}", usuario=web.nome_usuario())
            flash("Paciente cadastrado.")
            return redirect(url_for("pacientes.ficha", id=p["id"]))
    return render_template("paciente_form.html", v=v, erros=erros, novo=True, ufs=br.UFS)


@bp.route("/<id>/editar", methods=["GET", "POST"])
@exige("pacientes", 2)
def editar(id):
    p = store().get("patients", id) or abort(404)
    if request.method == "POST":
        v = web.campos(*CAMPOS)
        erros = _validar(v, id)
        if not erros:
            p["_v"] = int(request.form.get("_v") or p["_v"])
            try:
                store().salvar("patients", _aplicar(p, v), acao=f"Paciente atualizado: {v['name']}", usuario=web.nome_usuario())
            except Conflito:
                flash("Este cadastro foi alterado em outro computador enquanto você editava. Os dados atuais foram carregados: confira e salve de novo.", "aviso")
                return redirect(url_for("pacientes.editar", id=id))
            flash("Cadastro atualizado.")
            return redirect(url_for("pacientes.ficha", id=id))
    else:
        v = {k: p.get(k, "") for k in CAMPOS}
        v["usesSocial"] = "s" if p.get("socialName") else "n"
        erros = {}
    return render_template("paciente_form.html", v=v, erros=erros, novo=False, p=p, ufs=br.UFS)


@bp.route("/<id>")
@exige("pacientes")
def ficha(id):
    st = store()
    p = st.get("patients", id) or abort(404)
    aba = request.args.get("aba") or "dados"
    ctx = {"p": p, "aba": aba}
    if aba == "consultas" and web.nivel("agenda") >= 1:
        dent = st.mapa("dentists")
        ctx["consultas"] = [{**a, "dentista": (dent.get(a.get("dentistId")) or {}).get("name", "")}
                            for a in st.listar("appointments", "paciente_id = ?", (id,), ordem="data DESC, hora DESC")]
    if aba == "pagamentos" and web.nivel("financeiro") >= 1:
        lanc = st.listar("finance", "paciente_id = ?", (id,), ordem="vencimento")
        ctx["lancamentos"] = lanc
        ctx["pago"] = sum(f["value"] for f in lanc if f["paid"] and f["type"] == "receita")
        ctx["aberto"] = sum(f["value"] for f in lanc if not f["paid"] and f["type"] == "receita")
    if p.get("birth"):
        h, b = tempo.hoje(), p["birth"]
        ctx["idade"] = int(h[:4]) - int(b[:4]) - ((h[5:] < b[5:]) and 1 or 0)
    return render_template("paciente.html", **ctx)
