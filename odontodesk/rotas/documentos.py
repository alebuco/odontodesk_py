"""Aba Documentos do paciente: receitas (simples, antimicrobiano, controle especial) e documentos gerados a partir
dos modelos (atestado, contrato, termo...). Mesmo formato do app em JavaScript: paciente.docs = [{id, title, text, date,
dentistId, signed?}] e a tabela receitas (prescriptions)."""
import json
import re

from flask import Blueprint, Response, abort, flash, g, jsonify, redirect, render_template, request, url_for

from .. import br, receitas, tempo, web
from ..dados.anexos import AnexoErro
from ..dados.store import Conflito, novo_id
from ..web import exige, store

bp = Blueprint("documentos", __name__)


def anexos():
    from flask import current_app
    return current_app.config["ANEXOS"]


def _paciente(pid):
    return store().get("patients", pid) or abort(404)


def nome_completo(p):
    return f"{p['socialName']} (nome civil: {p['name']})" if p.get("socialName") else p.get("name", "")


def contexto(p, dentista):
    d = dentista or {}
    c = g.clinica
    return {"paciente": web.nome_exibicao(p), "nome_civil": p.get("name", ""), "nome_social": p.get("socialName", ""), "paciente_completo": nome_completo(p),
            "cpf": p.get("cpf", ""), "telefone": p.get("phone", ""), "nascimento": tempo.data_br(p.get("birth")), "dentista": d.get("name", ""), "cro": d.get("cro", ""),
            "clinica": c.get("name", ""), "cnpj": c.get("cnpj", ""), "cidade": c.get("city", ""), "endereco": br.endereco_formata(p) or p.get("address", ""),
            "cep": p.get("cep", ""), "endereco_clinica": c.get("address", ""), "data": tempo.data_br(tempo.hoje()), "hora": ""}


def preencher(texto, ctx):
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(ctx.get(m.group(1), "")), texto or "")


@bp.route("/pacientes/<pid>/documentos")
@exige("prontuario")
def documentos(pid):
    p = _paciente(pid)
    st = store()
    rx = sorted(st.listar("prescriptions", "paciente_id = ?", (pid,)), key=lambda r: (r.get("date") or "") + (r.get("createdAt") or ""), reverse=True)
    return render_template("pront_documentos.html", p=p, aba="documentos", receitas=rx, modelos=st.listar("templates"), dentistas=st.listar("dentists"),
                           docs=list(reversed(p.get("docs") or [])), dentista_padrao=g.usuario.get("dentistId") or "")


# ====================== DOCUMENTOS A PARTIR DOS MODELOS ======================
@bp.route("/pacientes/<pid>/documentos/novo", methods=["GET", "POST"])
@exige("prontuario", 2)
def documento_novo(pid):
    p = _paciente(pid)
    st = store()
    if request.method == "POST":
        titulo, texto = (request.form.get("title") or "").strip(), request.form.get("text") or ""
        if not titulo or not texto.strip():
            flash("Informe o título e o texto.", "erro")
            return redirect(url_for("documentos.documentos", pid=pid))
        d = {"id": novo_id(), "title": titulo, "text": texto, "date": tempo.hoje(), "dentistId": request.form.get("dentistId") or ""}
        p["docs"] = (p.get("docs") or []) + [d]
        p["_v"] = int(request.form.get("_v") or p["_v"])
        try:
            st.salvar("patients", p, acao=f"Documento gerado: {titulo} ({p['name']})", usuario=web.nome_usuario())
        except Conflito:
            flash("O cadastro do paciente foi alterado em outro computador agora. Gere o documento de novo.", "aviso")
            return redirect(url_for("documentos.documentos", pid=pid))
        flash("Documento salvo.")
        return redirect(url_for("documentos.documentos", pid=pid, imprimir=d["id"]))
    t = st.get("templates", request.args.get("modelo") or "") or abort(404)
    den = st.get("dentists", request.args.get("dentista") or "") if request.args.get("dentista") else None
    texto = preencher(t.get("body"), contexto(p, den))
    return render_template("pront_documento_form.html", p=p, aba="documentos", t=t, texto=texto, dentista=(den or {}).get("id", ""))


def _doc(pid, did):
    p = _paciente(pid)
    d = next((x for x in p.get("docs") or [] if x.get("id") == did), None) or abort(404)
    return p, d


@bp.route("/pacientes/<pid>/documentos/<did>/imprimir")
@exige("prontuario")
def documento_imprimir(pid, did):
    p, d = _doc(pid, did)
    return render_template("imp_documento.html", titulo=d.get("title"), texto=d.get("text"), emitido=tempo.agora().strftime("%d/%m/%Y %H:%M"))


@bp.route("/pacientes/<pid>/documentos/<did>/excluir", methods=["POST"])
@exige("prontuario", 2)
def documento_excluir(pid, did):
    p, d = _doc(pid, did)
    p["docs"] = [x for x in p["docs"] if x.get("id") != did]
    try:
        store().salvar("patients", p, acao=f"Documento excluído: {d.get('title')} ({p['name']})", usuario=web.nome_usuario())
    except Conflito:
        flash("O cadastro do paciente foi alterado em outro computador agora. Confira e repita.", "aviso")
        return redirect(url_for("documentos.documentos", pid=pid))
    if (d.get("signed") or {}).get("file"):
        anexos().excluir(d["signed"]["file"])
    flash("Documento excluído.")
    return redirect(url_for("documentos.documentos", pid=pid))


@bp.route("/pacientes/<pid>/assinado/<path:arquivo>")
@exige("prontuario")
def assinado(pid, arquivo):
    """PDF assinado (gerado no app do computador) de um documento ou receita deste paciente."""
    p = _paciente(pid)
    donos = [d.get("signed") or {} for d in p.get("docs") or []] + [r.get("signed") or {} for r in store().listar("prescriptions", "paciente_id = ?", (pid,))]
    if not any(s.get("file") == arquivo for s in donos):
        abort(404)
    try:
        dados = anexos().ler(arquivo)
    except AnexoErro as e:
        abort(400, str(e))
    if dados is None:
        abort(404)
    return Response(dados, mimetype="application/pdf", headers={"Content-Disposition": f"inline; filename={arquivo}"})


# ====================== RECEITAS ======================
@bp.route("/receitas/catalogo.json")
@exige("prontuario")
def catalogo():
    """Lista CMED/ANVISA importada no app do computador (anexo medcatalogo.json), se houver."""
    try:
        dados = anexos().ler("medcatalogo.json")
    except Exception:
        dados = None
    return Response(dados or b'{"itens":[]}', mimetype="application/json", headers={"Cache-Control": "private, max-age=3600"})


def _idade(nasc):
    if not nasc:
        return ""
    h = tempo.hoje()
    return str(int(h[:4]) - int(nasc[:4]) - (1 if h[5:] < nasc[5:10] else 0))


@bp.route("/pacientes/<pid>/receitas/nova", methods=["GET", "POST"])
@exige("prontuario", 2)
def receita_nova(pid):
    p = _paciente(pid)
    st = store()
    if request.method == "POST":
        try:
            rx = json.loads(request.form.get("dados") or "{}")
        except ValueError:
            abort(400)
        erros = validar_receita(rx, p)
        if erros:
            return jsonify(ok=False, erros=erros), 400
        den = st.get("dentists", rx["dentistId"]) or {}
        c = g.clinica
        itens = [{k: v for k, v in i.items() if k != "posOpts"} for i in rx["items"]]
        cpf_nao = bool(rx.get("cpfNaoPossui"))
        rec = {"id": rx.get("id") or novo_id(), "patientId": pid, "dentistId": rx["dentistId"], "date": rx.get("date") or tempo.hoje(),
               "layout": rx.get("layout") or "duas", "items": itens, "kinds": ",".join(dict.fromkeys(d["kind"] for d in receitas.documentos(itens))),
               "sexo": rx.get("sexo") or "", "idade": str(rx.get("idade") or ""),
               "cpf": "NÃO POSSUI" if cpf_nao else br.cpf_formata(rx.get("cpf") or p.get("cpf") or ""), "cpfNaoPossui": cpf_nao,
               "snap": {"clinic": {k: c.get(k, "") for k in ("name", "address", "city", "phone", "email", "cnpj")},
                        "dentist": {"name": den.get("name", ""), "cro": den.get("cro", "")},
                        "patient": {"name": nome_completo(p), "address": br.endereco_formata(p) or p.get("address", "")}},
               "authorId": g.usuario["id"], "authorName": g.usuario["name"], "createdAt": tempo.agora_iso_utc()}
        existente = st.get("prescriptions", rec["id"])
        if existente:
            rec["_v"] = existente["_v"]
        st.salvar("prescriptions", rec, acao=f"Receita emitida: {web.nome_exibicao(p)} ({', '.join(i['g'] for i in itens)})", usuario=web.nome_usuario())
        # guarda no cadastro o que foi informado
        mudou = False
        if rx.get("sexo") and p.get("sex") != rx["sexo"]:
            p["sex"] = rx["sexo"]
            mudou = True
        if rx.get("cpf") and not cpf_nao and br.cpf_valido(rx["cpf"]) and not p.get("cpf"):
            p["cpf"] = br.cpf_formata(rx["cpf"])
            mudou = True
        if mudou:
            try:
                st.salvar("patients", p)
            except Conflito:
                pass
        if g.clinica.get("rxLayout") != rec["layout"]:
            cl = st.clinica()
            cl["rxLayout"] = rec["layout"]
            try:
                st.salvar("clinic", cl)
            except Conflito:
                pass
        return jsonify(ok=True, imprimir=url_for("documentos.receita_imprimir", rid=rec["id"]), voltar=url_for("documentos.documentos", pid=pid))
    base = st.get("prescriptions", request.args.get("repetir")) if request.args.get("repetir") else None
    inicial = {"dentistId": (base or {}).get("dentistId") or g.usuario.get("dentistId") or (st.listar("dentists")[:1] or [{}])[0].get("id", ""),
               "date": tempo.hoje(), "layout": (base or {}).get("layout") or g.clinica.get("rxLayout") or "duas",
               "items": [{**i, "id": novo_id()} for i in (base or {}).get("items", [])],
               "sexo": (base or {}).get("sexo") or p.get("sex") or "", "idade": (base or {}).get("idade") or _idade(p.get("birth")),
               "cpf": p.get("cpf") or "", "cpfNaoPossui": bool((base or {}).get("cpfNaoPossui"))}
    perguntas = {q["id"]: q["q"] for q in st.listar("anamnesisModel")}
    alergia = " \n ".join([p.get("notes") or ""] + [f"{perguntas.get(k.replace('_obs', ''), '')} {v}" for k, v in (p.get("anamnesis") or {}).items()
                                                     if (not k.startswith("_") or k == "_queixa") and isinstance(v, str)])
    dent = [{"id": d["id"], "name": d.get("name", ""), "cro": d.get("cro", "")} for d in st.listar("dentists")]
    clinica_ok = bool(g.clinica.get("address") and g.clinica.get("phone"))
    endereco = br.endereco_formata(p) or p.get("address", "")
    return render_template("pront_receita.html", p=p, aba="documentos",
                           cfg=json.dumps({"rx": inicial, "dentistas": dent, "alergia": alergia, "clinicaOk": clinica_ok, "endereco": endereco,
                                           "catalogo": url_for("documentos.catalogo"), "salvar": request.path, "proprios": g.clinica.get("medsCustom") or []},
                                          ensure_ascii=False))


def validar_receita(rx, p):
    """As mesmas conferências do app (refeitas aqui no servidor)."""
    erros = []
    itens = [i for i in rx.get("items") or [] if str(i.get("g", "")).strip() or str(i.get("pos", "")).strip()]
    rx["items"] = itens
    if not itens:
        return ["Inclua ao menos um medicamento"]
    for k, i in enumerate(itens, 1):
        if not str(i.get("g", "")).strip():
            erros.append(f"Item {k}: informe o medicamento")
        elif not str(i.get("qtd", "")).strip():
            erros.append(f"{i['g']}: informe a quantidade")
        elif not str(i.get("pos", "")).strip():
            erros.append(f"{i['g']}: informe a posologia")
        if i.get("tipo") not in receitas.TIPOS:
            i["tipo"] = "simples"
        if i.get("tipo") == "notificacao":
            erros.append(f"{i.get('g')} exige Notificação de Receita (talonário da Vigilância Sanitária): retire da receita.")
        if i.get("uso") not in receitas.USOS:
            i["uso"] = "oral"
    den = store().get("dentists", rx.get("dentistId") or "")
    if not den:
        erros.append("Selecione o dentista.")
    elif not den.get("cro"):
        erros.append(f"Cadastre o CRO de {den['name']} (Configurações → Dentistas).")
    docs = receitas.documentos([i for i in itens if i.get("tipo") != "notificacao"])
    if any(d["kind"] != "simples" for d in docs) and not (g.clinica.get("address") and g.clinica.get("phone")):
        erros.append("Antimicrobianos e controle especial exigem endereço completo e telefone da clínica (Configurações → Clínica).")
    if any(i.get("tipo") == "controle" for i in itens):
        if not rx.get("cpfNaoPossui") and not br.cpf_valido(rx.get("cpf") or p.get("cpf") or ""):
            erros.append("Receita de controle especial: informe um CPF válido ou marque \"não possui\".")
        if not (br.endereco_formata(p) or p.get("address")):
            erros.append("Receita de controle especial: cadastre o endereço completo do paciente na ficha.")
    if any(i.get("tipo") == "antimicrobiano" for i in itens):
        if not str(rx.get("idade") or "").strip():
            erros.append("Antimicrobiano: informe a idade do paciente.")
        if rx.get("sexo") not in ("F", "M"):
            erros.append("Antimicrobiano: informe o sexo do paciente.")
    return erros


@bp.route("/receitas/<rid>/imprimir")
@exige("prontuario")
def receita_imprimir(rid):
    rx = store().get("prescriptions", rid) or abort(404)
    return render_template("imp_receita.html", rx=rx, S=rx.get("snap") or {}, docs=receitas.documentos(rx.get("items") or []), R=receitas,
                           data_extenso=_data_extenso(rx.get("date")), cidade=((rx.get("snap") or {}).get("clinic", {}).get("city") or "").split("/")[0].split("-")[0].strip())


def _data_extenso(iso):
    if not iso:
        return ""
    a, m, d = iso[:10].split("-")
    return f"{int(d)} de {tempo.MESES[int(m) - 1]} de {a}"
