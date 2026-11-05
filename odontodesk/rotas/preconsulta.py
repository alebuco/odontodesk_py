"""Pré-consulta: o paciente preenche dados, motivo da consulta e anamnese pelo celular antes de chegar.

Mesmo protocolo do app em JavaScript: as perguntas vão dentro do link (#c=...) do formulário publicado no site
(Configurações → Pré-consulta) e as respostas voltam numa mensagem com o código #ODPC1:...#, que é importada aqui.
O site do formulário não guarda nenhum dado.
"""
import base64
import json
import re
import urllib.parse

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import br, tempo, web
from ..dados.store import Conflito, novo_id
from ..web import exige, store
from .documentos import contexto, preencher

bp = Blueprint("preconsulta", __name__)
CAMPOS = [("name", "Nome civil"), ("socialName", "Nome social"), ("birth", "Nascimento"), ("cpf", "CPF"), ("phone", "Telefone"), ("email", "E-mail"),
          ("cep", "CEP"), ("street", "Logradouro"), ("number", "Número"), ("complement", "Complemento"), ("district", "Bairro"), ("city", "Cidade"),
          ("uf", "UF"), ("address", "Endereço (texto)"), ("insurance", "Convênio"), ("guardian", "Responsável")]


def b64e(s):
    """Igual ao app: base64 do UTF-8, com + → . e / → ! e sem '=' (fica limpo dentro de links e mensagens)."""
    return base64.b64encode(s.encode("utf-8")).decode().replace("+", ".").replace("/", "!").rstrip("=")


def b64d(s):
    s = s.replace(".", "+").replace("!", "/")
    return base64.b64decode(s + "=" * (-len(s) % 4)).decode("utf-8")


def situacao(p):
    return (p.get("preConsulta") or {}).get("status") or ""


def link(p, consulta=None):
    """Prepara a pré-consulta no cadastro (código novo se já respondida) e devolve o link do formulário."""
    st = store()
    pc = p.get("preConsulta") or {}
    if not pc or pc.get("status") == "respondido":
        pc = {"token": novo_id(), "status": "pendente", "history": pc.get("history") or []}
    perguntas = st.listar("anamnesisModel")
    pc["qids"] = [m["id"] for m in perguntas]
    p["preConsulta"] = pc
    c = g.clinica
    wa = br.digitos(c.get("whatsapp"))
    if wa and len(wa) <= 11:
        wa = "55" + wa
    cfg = {"v": 1, "cl": c.get("name", ""), "wa": wa, "em": c.get("email") or "", "t": pc["token"], "n": web.nome_exibicao(p), "nc": p.get("name", ""),
           "ns": p.get("socialName") or "", "ph": p.get("phone") or "", "dt": f"{tempo.data_br(consulta['date'])} às {consulta['time']}" if consulta else "",
           "q": [[m.get("q", ""), "y" if m.get("type") == "yesno" else "t"] for m in perguntas]}
    return str(c.get("formUrl") or "").split("#")[0] + "#c=" + b64e(json.dumps(cfg, ensure_ascii=False, separators=(",", ":")))


def proxima_consulta(pid):
    hoje = tempo.hoje()
    ags = [a for a in store().listar("appointments", "paciente_id = ? AND data >= ?", (pid, hoje)) if a.get("status") not in ("cancelado", "faltou")]
    return min(ags, key=lambda a: (a["date"], a.get("time") or ""), default=None)


@bp.route("/pacientes/<pid>/pre-consulta")
@exige("pacientes")
def oferecer(pid):
    """Tela de envio (também aparece logo depois de agendar a primeira consulta)."""
    p = store().get("patients", pid) or abort(404)
    a = store().get("appointments", request.args.get("consulta")) if request.args.get("consulta") else proxima_consulta(pid)
    return render_template("preconsulta.html", p=p, a=a, situacao=situacao(p), pc=p.get("preConsulta") or {})


@bp.route("/pacientes/<pid>/pre-consulta/enviar", methods=["POST"])
@exige("pacientes", 2)
def enviar(pid):
    st = store()
    p = st.get("patients", pid) or abort(404)
    if not g.clinica.get("formUrl"):
        flash("Configure o endereço do formulário em Configurações → Pré-consulta.", "erro")
        return redirect(url_for("preconsulta.oferecer", pid=pid))
    via = request.form.get("via") or "copy"
    a = st.get("appointments", request.form.get("consulta")) if request.form.get("consulta") else proxima_consulta(pid)
    lnk = link(p, a)
    den = st.get("dentists", (a or {}).get("dentistId") or "") if a else None
    ctx = {**contexto(p, den), "data": tempo.data_br(a["date"]) if a else tempo.data_br(tempo.hoje()), "hora": (a or {}).get("time", ""), "link": lnk}
    texto = preencher(g.clinica.get("waPreConsulta") or "Olá {{paciente}}! Preencha o formulário de pré-consulta: {{link}}", ctx)
    if via == "whatsapp" and not br.digitos(p.get("phone")):
        flash("Paciente sem telefone cadastrado.", "erro")
        return redirect(url_for("preconsulta.oferecer", pid=pid))
    if via == "email" and not p.get("email"):
        flash("Paciente sem e-mail cadastrado.", "erro")
        return redirect(url_for("preconsulta.oferecer", pid=pid))
    agora = tempo.agora_iso_utc()
    p["preConsulta"].update(status="enviado", sentAt=agora, via=via)
    p["preConsulta"].setdefault("history", []).append({"date": agora, "event": f"Formulário enviado ({ {'whatsapp': 'WhatsApp', 'email': 'e-mail'}.get(via, 'link copiado') })"})
    try:
        st.salvar("patients", p, acao=f"Pré-consulta enviada ({via}): {p['name']}", usuario=web.nome_usuario())
    except Conflito:
        flash("O cadastro foi alterado em outro computador agora. Tente de novo.", "aviso")
        return redirect(url_for("preconsulta.oferecer", pid=pid))
    if via == "whatsapp":
        n = br.digitos(p["phone"])
        return redirect(f"https://wa.me/{'55' + n if len(n) <= 11 else n}?text={urllib.parse.quote(texto)}")
    if via == "email":
        return redirect(f"mailto:{p['email']}?subject={urllib.parse.quote('Pré-consulta — ' + g.clinica.get('name', ''))}&body={urllib.parse.quote(texto)}")
    return render_template("preconsulta_link.html", p=p, link=lnk, texto=texto)


def ler_resposta(texto):
    m = re.search(r"#ODPC1:([A-Za-z0-9.!]+)", str(texto or ""))
    if not m:
        return None
    try:
        r = json.loads(b64d(m.group(1)))
    except Exception:
        return None
    return r if isinstance(r, dict) and r.get("t") and isinstance(r.get("d"), dict) else None


def _por_token(t):
    return next((p for p in store().listar("patients") if (p.get("preConsulta") or {}).get("token") == t), None)


@bp.route("/pre-consulta/importar", methods=["GET", "POST"])
@exige("pacientes", 2)
def importar():
    erro, texto = "", request.form.get("mensagem") or ""
    if request.method == "POST":
        r = ler_resposta(texto)
        p = _por_token(r["t"]) if r else None
        if not r:
            erro = "Não encontrei o código da pré-consulta (#ODPC1:…) na mensagem."
        elif not p:
            erro = "Esta resposta não corresponde a nenhum paciente. Pode ser de um link antigo, substituído por um mais novo."
        else:
            return _revisar(p, r, texto)
    return render_template("preconsulta_importar.html", erro=erro, texto=texto)


def _respostas(p, r):
    qids = (p.get("preConsulta") or {}).get("qids") or []
    modelo = {m["id"]: m for m in store().listar("anamnesisModel")}
    out = []
    for i, a in enumerate(r.get("a") or []):
        q = modelo.get(qids[i]) if i < len(qids) else None
        if q:
            obs = r.get("o") or []
            out.append({"i": i, "q": q, "a": a, "o": str(obs[i]).strip() if i < len(obs) and obs[i] else ""})
    return out


def _revisar(p, r, texto):
    campos = []
    for k, rot in CAMPOS:
        novo = str(r["d"].get(k) or "").strip()
        if novo:
            atual = str(p.get(k) or "")
            campos.append({"k": k, "rotulo": rot, "atual": atual, "novo": novo, "diferente": atual != novo})
    resp = _respostas(p, r)
    alertas = [x for x in resp if x["q"].get("type") == "yesno" and x["a"] == "sim"]
    ja = situacao(p) == "respondido" and (p["preConsulta"].get("response") or {}).get("ts") == r.get("ts")
    return render_template("preconsulta_revisar.html", p=p, r=r, campos=campos, respostas=resp, alertas=alertas, ja=ja, texto=texto,
                           respondido=tempo.hora_local(r.get("ts")))


@bp.route("/pre-consulta/aplicar", methods=["POST"])
@exige("pacientes", 2)
def aplicar():
    r = ler_resposta(request.form.get("mensagem"))
    p = _por_token(r["t"]) if r else None
    if not p:
        abort(400)
    for k in request.form.getlist("campo"):
        if k in dict(CAMPOS) and str(r["d"].get(k) or "").strip():
            p[k] = str(r["d"][k]).strip()
    if br.cpf_valido(p.get("cpf")):
        p["cpf"] = br.cpf_formata(p["cpf"])
    if br.telefone_valido(p.get("phone")):
        p["phone"] = br.telefone_formata(p["phone"])
    if p.get("cep"):
        p["cep"] = br.cep_formata(p["cep"])
    if p.get("uf") and p["uf"] not in br.UFS:
        p["uf"] = ""
    if p.get("street") or p.get("city"):
        p["address"] = br.endereco_formata(p)
    resp = _respostas(p, r)
    an = dict(p.get("anamnesis") or {})
    for x in resp:
        an[x["q"]["id"]] = x["a"]
        an[x["q"]["id"] + "_obs"] = x["o"]
    an.update(_queixa=r.get("qx") or an.get("_queixa") or "", _updated=tempo.hoje(), _fonte="pré-consulta")
    p["anamnesis"] = an
    alertas = [x for x in resp if x["q"].get("type") == "yesno" and x["a"] == "sim"]
    if alertas and request.form.get("alertas"):
        txt = f"Pré-consulta {tempo.data_br(tempo.hoje())}: " + "; ".join(x["q"]["q"].rstrip("?") + (f" ({x['o']})" if x["o"] else "") for x in alertas)
        p["notes"] = (p.get("notes") + "\n" + txt) if p.get("notes") else txt
    agora = tempo.agora_iso_utc()
    p["preConsulta"].update(status="respondido", receivedAt=agora, response=r)
    p["preConsulta"].setdefault("history", []).append({"date": agora, "event": "Respostas importadas"})
    try:
        store().salvar("patients", p, acao=f"Pré-consulta importada: {p['name']}", usuario=web.nome_usuario())
    except Conflito:
        flash("O cadastro foi alterado em outro computador agora. Importe de novo.", "aviso")
        return redirect(url_for("preconsulta.importar"))
    flash("Pré-consulta importada para o cadastro e a anamnese.")
    return redirect(url_for("prontuario.anamnese", pid=p["id"]) if web.nivel("prontuario") else url_for("pacientes.ficha", id=p["id"]))
