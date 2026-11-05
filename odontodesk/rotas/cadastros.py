"""Procedimentos e preços, Modelos de documentos e Configurações (clínica, pré-consulta, dentistas, anamnese, backup)."""
import json
import re

from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for

from .. import br, tempo, web
from ..dados.store import Conflito, novo_id
from ..web import exige, store

bp = Blueprint("cadastros", __name__)
FONTES = [("", "Sem código (procedimento próprio)"), ("TUSS", "TUSS — terminologia da ANS (8 dígitos)"),
          ("SUS", "SUS — tabela SIGTAP (10 dígitos)"), ("Outros", "Outros (convênio, tabela própria…)")]


def _sigtap(d):
    return f"{d[:2]}.{d[2:4]}.{d[4:6]}.{d[6:9]}-{d[9:]}"


def codigo_normalizado(fonte, bruto):
    """Mesmas regras do app: TUSS 8 dígitos; SUS (SIGTAP) 10 dígitos no formato 03.07.01.003-1."""
    bruto = str(bruto or "").strip()
    if not fonte:
        return "", ""
    if not bruto:
        return "", "Informe o código"
    d = br.digitos(bruto)
    if fonte == "TUSS":
        return (d, "") if len(d) == 8 else (bruto, f"Código TUSS tem 8 dígitos (tem {len(d)})")
    if fonte == "SUS":
        return (_sigtap(d), "") if len(d) == 10 else (bruto, f"Código SIGTAP tem 10 dígitos, ex.: 03.07.01.003-1 (tem {len(d)})")
    return bruto[:40], ""


# ====================== PROCEDIMENTOS ======================
@bp.route("/procedimentos/")
@exige("procedimentos")
def procedimentos():
    q, fonte, sem_valor = (request.args.get("q") or "").strip().lower(), request.args.get("fonte") or "todos", bool(request.args.get("sem_valor"))
    qd = br.digitos(q)
    todos = store().listar("procedures")
    lista = [p for p in todos if (fonte == "todos" or (not p.get("source") if fonte == "sem" else p.get("source") == fonte))
             and (not sem_valor or not float(p.get("price") or 0) > 0)
             and (not q or q in (p.get("name") or "").lower() or q in (p.get("category") or "").lower() or q in (p.get("code") or "").lower()
                  or (qd and qd in br.digitos(p.get("code"))))]
    lista.sort(key=lambda p: ((p.get("category") or "Outros").lower(), (p.get("name") or "").lower()))
    LIM = 400
    mostrar = lista[:LIM]
    cats = []
    for p in mostrar:
        c = p.get("category") or "Outros"
        if not cats or cats[-1][0] != c:
            cats.append((c, []))
        cats[-1][1].append(p)
    cnt = lambda f: len([p for p in todos if f(p)])
    fontes = [("todos", f"Todas as fontes ({len(todos)})"), ("TUSS", f"TUSS ({cnt(lambda p: p.get('source') == 'TUSS')})"),
              ("SUS", f"SUS / SIGTAP ({cnt(lambda p: p.get('source') == 'SUS')})"), ("Outros", f"Outros ({cnt(lambda p: p.get('source') == 'Outros')})"),
              ("sem", f"Sem código ({cnt(lambda p: not p.get('source'))})")]
    return render_template("procedimentos.html", cats=cats, total=len(lista), limite=LIM, q=request.args.get("q") or "", fonte=fonte, fontes=fontes,
                           sem_valor=sem_valor, n_sem_valor=cnt(lambda p: not float(p.get("price") or 0) > 0))


def _proc_form(p, novo):
    erros, v = {}, {"source": p.get("source") or "", "code": p.get("code") or "", "name": p.get("name") or "", "category": p.get("category") or "",
                     "price": web.numero_campo(p.get("price")) if p.get("price") not in (None, "") else ""}
    if request.method == "POST":
        v = web.campos("source", "code", "name", "category", "price")
        cod, erro = codigo_normalizado(v["source"], v["code"])
        if not v["name"]:
            erros["name"] = "Informe o nome"
        if erro:
            erros["code"] = erro
        if web.numero(v["price"]) is None:
            erros["price"] = "Valor inválido"
        dup = cod and next((x for x in store().listar("procedures") if x["id"] != p.get("id") and x.get("source") == v["source"] and x.get("code") == cod), None)
        if dup and not request.form.get("mesmo_assim") and not erros:
            erros["_dup"] = f"O código {cod} ({v['source']}) já está em \"{dup['name']}\"."
        if not erros:
            rec = {**p, "name": v["name"], "category": v["category"], "price": web.numero(v["price"]) or 0, "source": v["source"], "code": cod}
            if not novo:
                rec["_v"] = int(request.form.get("_v") or p["_v"])
            try:
                store().salvar("procedures", rec, acao=f"Procedimento salvo: {(cod + ' ') if cod else ''}{rec['name']}", usuario=web.nome_usuario())
            except Conflito:
                flash("Este procedimento foi alterado em outro computador. Os dados atuais foram carregados.", "aviso")
                return redirect(request.url)
            flash("Procedimento salvo.")
            return redirect(url_for("cadastros.procedimentos"))
    categorias = sorted({x.get("category") for x in store().listar("procedures") if x.get("category")})
    return render_template("procedimento_form.html", v=v, erros=erros, novo=novo, p=p, fontes=FONTES, categorias=categorias)


@bp.route("/procedimentos/novo", methods=["GET", "POST"])
@exige("procedimentos", 2)
def procedimento_novo():
    return _proc_form({}, True)


@bp.route("/procedimentos/<id>", methods=["GET", "POST"])
@exige("procedimentos")
def procedimento_editar(id):
    p = store().get("procedures", id) or abort(404)
    if request.method == "POST" and web.nivel("procedimentos") < 2:
        abort(403)
    return _proc_form(p, False)


@bp.route("/procedimentos/<id>/excluir", methods=["POST"])
@exige("procedimentos", 2)
def procedimento_excluir(id):
    p = store().get("procedures", id) or abort(404)
    store().excluir("procedures", id, acao=f"Procedimento excluído: {p.get('name')}", usuario=web.nome_usuario())
    flash("Procedimento excluído. Orçamentos já feitos não mudam.")
    return redirect(url_for("cadastros.procedimentos"))


@bp.route("/procedimentos/reajuste", methods=["POST"])
@exige("procedimentos", 2)
def procedimentos_reajuste():
    pct = web.numero(request.form.get("pct"))
    if pct is None or not pct or abs(pct) > 500:
        flash("Informe o percentual (ex.: 5 ou -10).", "erro")
        return redirect(url_for("cadastros.procedimentos"))
    k = 1 + pct / 100
    ops = []
    for p in store().listar("procedures"):
        if float(p.get("price") or 0) > 0:
            p["price"] = round(float(p["price"]) * k, 2)
            ops.append({"coll": "procedures", "op": "put", "id": p["id"], "rec": p, "v": p["_v"]})
    r = store().aplicar(ops, [{"action": f"Tabela de procedimentos reajustada em {str(pct).replace('.', ',')}%", "user": web.nome_usuario()}])
    flash(f"{len(r['results'])} valor(es) reajustado(s) em {str(pct).replace('.', ',')}%." + (f" {len(r['conflicts'])} estavam sendo alterados em outro computador e ficaram como estavam." if r["conflicts"] else ""))
    return redirect(url_for("cadastros.procedimentos"))


# ====================== MODELOS DE DOCUMENTOS ======================
VARIAVEIS = "{{paciente}} {{nome_civil}} {{nome_social}} {{paciente_completo}} {{cpf}} {{nascimento}} {{telefone}} {{endereco}} {{cep}} {{dentista}} {{cro}} {{clinica}} {{cnpj}} {{cidade}} {{data}}"


@bp.route("/modelos/")
@exige("documentos")
def modelos():
    return render_template("modelos.html", modelos=store().listar("templates"), variaveis=VARIAVEIS)


@bp.route("/modelos/novo", methods=["GET", "POST"])
@bp.route("/modelos/<id>", methods=["GET", "POST"])
@exige("documentos")
def modelo(id=None):
    t = (store().get("templates", id) or abort(404)) if id else {}
    erro = ""
    if request.method == "POST":
        if web.nivel("documentos") < 2:
            abort(403)
        titulo, corpo = (request.form.get("title") or "").strip(), request.form.get("body") or ""
        if not titulo:
            erro = "Informe o título"
        else:
            rec = {**t, "title": titulo, "body": corpo}
            if id:
                rec["_v"] = int(request.form.get("_v") or t["_v"])
            try:
                store().salvar("templates", rec, acao=f"Modelo salvo: {titulo}", usuario=web.nome_usuario())
            except Conflito:
                flash("Este modelo foi alterado em outro computador. Os dados atuais foram carregados.", "aviso")
                return redirect(request.url)
            flash("Modelo salvo.")
            return redirect(url_for("cadastros.modelos"))
        t = {**t, "title": titulo, "body": corpo}
    return render_template("modelo_form.html", t=t, novo=not id, erro=erro, variaveis=VARIAVEIS)


@bp.route("/modelos/<id>/excluir", methods=["POST"])
@exige("documentos", 2)
def modelo_excluir(id):
    t = store().get("templates", id) or abort(404)
    store().excluir("templates", id, acao=f"Modelo excluído: {t.get('title')}", usuario=web.nome_usuario())
    flash("Modelo excluído.")
    return redirect(url_for("cadastros.modelos"))


# ====================== CONFIGURAÇÕES ======================
@bp.route("/configuracoes/")
@exige("config")
def configuracoes():
    st = store()
    return render_template("configuracoes.html", c=g.clinica, dentistas=st.listar("dentists"), perguntas=st.listar("anamnesisModel"),
                           erros={}, banco=_banco_info(), slots=["15", "20", "30", "60"])


def _banco_info():
    d = store().db
    if d.dialect == "mysql":
        a = getattr(d, "_args", {})
        return f"MySQL/TiDB · {a.get('host')}:{a.get('port')} · banco {a.get('database')} · usuário {a.get('user')}{' · SSL' if a.get('ssl') else ''}"
    return "SQLite (arquivo local, para testes)"


def _salvar_clinica(campos, acao):
    cl = store().clinica()
    cl.update(campos)
    cl["_v"] = int(request.form.get("_v") or cl.get("_v") or 0)
    try:
        store().salvar("clinic", cl, acao=acao, usuario=web.nome_usuario())
        return True
    except Conflito:
        flash("As configurações foram alteradas em outro computador agora. Os dados atuais foram carregados: confira e salve de novo.", "aviso")
        return False


@bp.route("/configuracoes/clinica", methods=["POST"])
@exige("config", 2)
def config_clinica():
    v = web.campos("name", "cnpj", "phone", "email", "city", "address", "start", "end", "slot", "waConfirm", "waBirthday", "waReturn")
    erros = {}
    if not v["name"]:
        erros["name"] = "Informe o nome da clínica"
    if br.doc_erro(v["cnpj"]):
        erros["cnpj"] = br.doc_erro(v["cnpj"])
    if br.telefone_erro(v["phone"]):
        erros["phone"] = br.telefone_erro(v["phone"])
    if v["start"] and v["end"] and v["end"] <= v["start"]:
        erros["end"] = "O fim precisa ser depois do início"
    if erros:
        st = store()
        c = {**g.clinica, **v}
        return render_template("configuracoes.html", c=c, dentistas=st.listar("dentists"), perguntas=st.listar("anamnesisModel"), erros=erros,
                               banco=_banco_info(), slots=["15", "20", "30", "60"])
    v["cnpj"] = br.doc_formata(v["cnpj"]) if v["cnpj"] else ""
    v["phone"] = br.telefone_formata(v["phone"]) if v["phone"] else ""
    v["slot"] = int(v["slot"] or 30)
    if _salvar_clinica(v, "Dados da clínica atualizados"):
        flash("Dados da clínica salvos.")
    return redirect(url_for("cadastros.configuracoes"))


@bp.route("/configuracoes/pre-consulta", methods=["POST"])
@exige("config", 2)
def config_pre():
    v = web.campos("whatsapp", "preMode", "formUrl", "waPreConsulta")
    if br.telefone_erro(v["whatsapp"]):
        flash(f"WhatsApp da clínica: {br.telefone_erro(v['whatsapp'])}", "erro")
    elif v["formUrl"] and not re.match(r"^https?://", v["formUrl"], re.I):
        flash("O endereço do formulário deve começar com https://", "erro")
    else:
        v["whatsapp"] = br.telefone_formata(v["whatsapp"]) if v["whatsapp"] else ""
        if _salvar_clinica(v, "Configurações de pré-consulta atualizadas"):
            flash("Configurações de pré-consulta salvas.")
    return redirect(url_for("cadastros.configuracoes") + "#prec")


@bp.route("/configuracoes/dentista", methods=["POST"])
@bp.route("/configuracoes/dentista/<id>", methods=["POST"])
@exige("config", 2)
def config_dentista(id=None):
    d = (store().get("dentists", id) or abort(404)) if id else {}
    if request.form.get("excluir") and id:
        store().excluir("dentists", id, acao=f"Dentista excluído: {d.get('name')}", usuario=web.nome_usuario())
        flash("Dentista excluído. Agendamentos existentes ficam sem dentista.")
        return redirect(url_for("cadastros.configuracoes") + "#dentistas")
    nome = (request.form.get("name") or "").strip()
    if not nome:
        flash("Informe o nome do dentista.", "erro")
    else:
        com = web.numero(request.form.get("commission")) or 0
        rec = {**d, "name": nome, "cro": (request.form.get("cro") or "").strip(), "commission": max(0, min(100, com))}
        try:
            store().salvar("dentists", rec, acao=f"Dentista salvo: {nome}", usuario=web.nome_usuario())
            flash("Dentista salvo.")
        except Conflito:
            flash("Este dentista foi alterado em outro computador. Confira e salve de novo.", "aviso")
    return redirect(url_for("cadastros.configuracoes") + "#dentistas")


@bp.route("/configuracoes/anamnese", methods=["POST"])
@exige("config", 2)
def config_anamnese():
    if request.form.get("remover"):
        q = store().get("anamnesisModel", request.form["remover"])
        if q:
            store().excluir("anamnesisModel", q["id"], acao=f"Pergunta de anamnese removida: {q.get('q')}", usuario=web.nome_usuario())
            flash("Pergunta removida. As respostas antigas continuam guardadas nos pacientes.")
    else:
        q = (request.form.get("q") or "").strip()
        if q:
            store().salvar("anamnesisModel", {"q": q, "type": "text" if request.form.get("type") == "text" else "yesno"},
                           acao="Pergunta de anamnese adicionada", usuario=web.nome_usuario())
            flash("Pergunta adicionada.")
    return redirect(url_for("cadastros.configuracoes") + "#anamnese")


@bp.route("/configuracoes/backup")
@exige("config", 2)
def config_backup():
    """Cópia completa dos dados em JSON (mesmo formato do "Exportar dados" do app do computador, sem os anexos)."""
    dados = store().carregar_tudo()
    for c, v in dados.items():
        for r in (v if isinstance(v, list) else [v] if v else []):
            r.pop("_v", None)
            r.pop("_o", None)
    users = [{k: x for k, x in u.items() if k not in ("hash", "salt", "iter")} for u in dados.get("users") or []] if not web.eh_admin() else dados.get("users")
    dados["users"] = users
    if dados.get("clinic"):
        dados["clinic"].pop("google", None)
        if not web.eh_admin():
            dados["clinic"].pop("recovery", None)
    store().auditar("Backup dos dados exportado (web)", web.nome_usuario())
    return Response(json.dumps(dados, ensure_ascii=False), mimetype="application/json",
                    headers={"Content-Disposition": f"attachment; filename=odontodesk-backup-{tempo.hoje()}.json"})
