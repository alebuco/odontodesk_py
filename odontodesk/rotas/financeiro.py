"""Financeiro: fluxo de caixa do mês, lançamentos, baixa, recibo, CSV e fechamento do período contábil.

Fechamento do período (igual ao app em JavaScript, campo `finClosings` da clínica): lançamentos PAGOS até a data
do fechamento ficam só para consulta. Ninguém altera, exclui ou lança pagamento com data dentro do período.
Contas em aberto continuam valendo. Só o administrador fecha ou reabre.
"""
import calendar
import csv
import io

from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for

from .. import tempo, web
from ..dados.store import Conflito, novo_id
from ..web import exige, store

bp = Blueprint("financeiro", __name__, url_prefix="/financeiro")
PAY = ["Dinheiro", "Pix", "Cartão de débito", "Cartão de crédito", "Boleto", "Transferência", "Convênio"]
CATS_R = ["Tratamento", "Consulta", "Convênio", "Outras receitas"]
CATS_D = ["Aluguel", "Materiais", "Laboratório", "Salários", "Comissões", "Impostos", "Água/Luz/Internet", "Marketing", "Manutenção", "Outras despesas"]
FILTROS = [("todos", "Todos do mês"), ("receitas", "Receitas"), ("despesas", "Despesas"), ("aberto", "Em aberto no mês"), ("vencidos", "Todos os vencidos")]


# ---------- período contábil ----------
def fechamentos(clinica=None):
    return list(((clinica if clinica is not None else g.clinica) or {}).get("finClosings") or [])


def data_fechamento(clinica=None):
    return max((c.get("until") or "" for c in fechamentos(clinica)), default="")


def fechado(f, lock=None):
    lock = data_fechamento() if lock is None else lock
    return bool(lock and f and f.get("paid") and f.get("paidDate") and f["paidDate"] <= lock)


def msg_fechado(lock):
    return f"Período contábil fechado até {tempo.data_br(lock)}. Use uma data de pagamento a partir de {tempo.data_br(tempo.soma_dias(lock, 1))}."


# ---------- resumo ----------
def resumo_mes(m):
    st = store()
    ini, fim = m + "-01", f"{m}-{calendar.monthrange(int(m[:4]), int(m[5:]))[1]:02d}"
    lanc = st.listar("finance", "(vencimento >= ? AND vencimento <= ?) OR (pago = 1 AND data_pagamento >= ? AND data_pagamento <= ?)", (ini, fim, ini, fim))
    pagos = [f for f in lanc if f["paid"] and (f.get("paidDate") or "").startswith(m)]
    soma = lambda l, t: round(sum(f["value"] for f in l if f["type"] == t), 2)
    previstos = [f for f in lanc if not f["paid"] and (f.get("due") or "").startswith(m)]
    r = {"lanc": lanc, "pagos": pagos, "rec": soma(pagos, "receita"), "desp": soma(pagos, "despesa"),
         "prev_r": soma(previstos, "receita"), "prev_d": soma(previstos, "despesa")}
    r["saldo"] = round(r["rec"] - r["desp"], 2)
    r["projetado"] = round(r["saldo"] + r["prev_r"] - r["prev_d"], 2)
    return r


def resumo_periodo(de, ate):
    lanc = store().listar("finance")
    dentro = lambda d: d and (not de or d >= de) and d <= ate
    pagos = [f for f in lanc if f["paid"] and dentro(f.get("paidDate"))]
    abertos = [f for f in lanc if not f["paid"] and f.get("due") and f["due"] <= ate]
    soma = lambda l, t: round(sum(f["value"] for f in l if f["type"] == t), 2)
    return {"pagos": sorted(pagos, key=lambda f: f["paidDate"]), "rec": soma(pagos, "receita"), "desp": soma(pagos, "despesa"),
            "n": len(pagos), "open_r": soma(abertos, "receita"), "open_d": soma(abertos, "despesa"), "n_open": len(abertos)}


@bp.route("/")
@exige("financeiro")
def mes():
    hoje = tempo.hoje()
    m = request.args.get("mes") or hoje[:7]
    filtro = request.args.get("filtro") or "todos"
    st = store()
    r = resumo_mes(m)
    lanc = r["lanc"]
    lista = {"receitas": [f for f in lanc if f["type"] == "receita"], "despesas": [f for f in lanc if f["type"] == "despesa"],
             "aberto": [f for f in lanc if not f["paid"]],
             "vencidos": st.listar("finance", "pago = 0 AND vencimento < ?", (hoje,))}.get(filtro, lanc)
    lista = sorted(lista, key=lambda f: f.get("due") or "")
    pac = st.mapa("patients")
    dent = st.listar("dentists")
    comissoes = []
    for d in dent:
        base = sum(f["value"] for f in r["pagos"] if f["type"] == "receita" and f.get("dentistId") == d["id"])
        if base > 0:
            comissoes.append({"d": d, "base": base, "valor": round(base * float(d.get("commission") or 0) / 100, 2)})
    cats = {}
    for f in r["pagos"]:
        if f["type"] == "despesa":
            cats[f.get("category") or "Outras"] = cats.get(f.get("category") or "Outras", 0) + f["value"]
    a, mm = map(int, m.split("-"))
    ant = f"{a - (mm == 1)}-{12 if mm == 1 else mm - 1:02d}"
    prox = f"{a + (mm == 12)}-{1 if mm == 12 else mm + 1:02d}"
    lock = data_fechamento()
    return render_template("financeiro.html", m=m, r=r, lista=lista, filtro=filtro, filtros=FILTROS, pac=pac, comissoes=comissoes,
                           cats=sorted(cats.items(), key=lambda x: -x[1]), ant=ant, prox=prox, lock=lock, fechado=fechado, hoje=hoje)


@bp.route("/csv")
@exige("financeiro")
def exportar_csv():
    m = request.args.get("mes") or tempo.hoje()[:7]
    st = store()
    pac, dent = st.mapa("patients"), st.mapa("dentists")
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["Tipo", "Vencimento", "Descrição", "Paciente", "Dentista", "Categoria", "Forma", "Pago", "Data pagamento", "Valor"])
    for f in sorted(resumo_mes(m)["lanc"], key=lambda f: f.get("due") or ""):
        w.writerow([f["type"], tempo.data_br(f.get("due")), f.get("desc"), (pac.get(f.get("patientId")) or {}).get("name", ""),
                    (dent.get(f.get("dentistId")) or {}).get("name", ""), f.get("category"), f.get("method"), "Sim" if f["paid"] else "Não",
                    tempo.data_br(f.get("paidDate")), f"{f['value']:.2f}".replace(".", ",")])
    return Response("﻿" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=financeiro-{m}.csv"})


def _ler_form():
    v = web.campos("type", "category", "desc", "value", "due", "patientId", "dentistId", "method", "repeat", "paidDate")
    v["paid"] = bool(request.form.get("paid"))
    return v


def _validar(v):
    erros = {}
    if not v["desc"]:
        erros["desc"] = "Informe a descrição"
    if web.numero(v["value"]) is None:
        erros["value"] = "Valor inválido"
    if not v["due"]:
        erros["due"] = "Informe o vencimento"
    lock = data_fechamento()
    if v["paid"] and not v["paidDate"]:
        v["paidDate"] = tempo.hoje()
    if v["paid"] and lock and v["paidDate"] <= lock:
        erros["paidDate"] = msg_fechado(lock)
    return erros


def _form_ctx(v, erros, novo, f=None, so_leitura=False):
    return dict(v=v, erros=erros, novo=novo, f=f, so_leitura=so_leitura, pacientes=web.opcoes_pacientes(), dentistas=store().listar("dentists"),
                cats=CATS_R + CATS_D, formas=PAY, lock=data_fechamento())


@bp.route("/novo", methods=["GET", "POST"])
@exige("financeiro", 2)
def novo():
    if request.method == "POST":
        v = _ler_form()
        erros = _validar(v)
        if not erros:
            n = max(1, min(60, int(v["repeat"] or 1)))
            valor = web.numero(v["value"])
            ops = []
            for i in range(n):
                rec = {"id": novo_id(), "type": v["type"], "category": v["category"], "desc": f"{v['desc']} ({i + 1}/{n})" if n > 1 else v["desc"],
                       "value": valor, "due": tempo.soma_meses(v["due"], i), "patientId": v["patientId"], "dentistId": v["dentistId"],
                       "method": v["method"], "paid": v["paid"] if i == 0 else False, "paidDate": v["paidDate"] if (i == 0 and v["paid"]) else ""}
                ops.append({"coll": "finance", "op": "put", "id": rec["id"], "rec": rec, "v": 0})
            store().aplicar(ops, [{"action": f"Lançamento salvo: {v['desc']}", "user": web.nome_usuario()}])
            flash("Lançamento salvo." if n == 1 else f"{n} lançamentos salvos (um por mês).")
            return redirect(request.form.get("voltar") or url_for("financeiro.mes", mes=v["due"][:7]))
    else:
        v = {"type": request.args.get("tipo") or "receita", "due": tempo.hoje(), "method": "Pix", "patientId": request.args.get("paciente") or "",
             "category": "Tratamento" if request.args.get("paciente") else "", "repeat": "1", "paidDate": tempo.hoje(), "value": ""}
        erros = {}
    return render_template("lancamento_form.html", **_form_ctx(v, erros, True))


@bp.route("/<id>", methods=["GET", "POST"])
@exige("financeiro")
def editar(id):
    f = store().get("finance", id) or abort(404)
    if fechado(f):
        return render_template("lancamento_form.html", **_form_ctx({**f, "value": web.numero_campo(f["value"])}, {}, False, f, so_leitura=True))
    if request.method == "POST":
        if web.nivel("financeiro") < 2:
            abort(403)
        v = _ler_form()
        erros = _validar(v)
        if not erros:
            rec = {**f, "type": v["type"], "category": v["category"], "desc": v["desc"], "value": web.numero(v["value"]), "due": v["due"],
                   "patientId": v["patientId"], "dentistId": v["dentistId"], "method": v["method"], "paid": v["paid"],
                   "paidDate": v["paidDate"] if v["paid"] else "", "_v": int(request.form.get("_v") or f["_v"])}
            try:
                store().salvar("finance", rec, acao=f"Lançamento salvo: {rec['desc']}", usuario=web.nome_usuario())
            except Conflito:
                flash("Este lançamento foi alterado em outro computador enquanto você editava. Os dados atuais foram carregados.", "aviso")
                return redirect(url_for("financeiro.editar", id=id))
            flash("Lançamento salvo.")
            return redirect(request.form.get("voltar") or url_for("financeiro.mes", mes=rec["due"][:7]))
    else:
        v, erros = {**f, "value": web.numero_campo(f["value"]), "paidDate": f.get("paidDate") or tempo.hoje()}, {}
    return render_template("lancamento_form.html", **_form_ctx(v, erros, False, f))


@bp.route("/<id>/excluir", methods=["POST"])
@exige("financeiro", 2)
def excluir(id):
    f = store().get("finance", id) or abort(404)
    if fechado(f):
        flash(msg_fechado(data_fechamento()), "erro")
        return redirect(url_for("financeiro.editar", id=id))
    store().excluir("finance", id, acao=f"Lançamento excluído: {f.get('desc')}", usuario=web.nome_usuario())
    flash("Lançamento excluído.")
    return redirect(url_for("financeiro.mes", mes=(f.get("due") or tempo.hoje())[:7]))


@bp.route("/<id>/baixar", methods=["POST"])
@exige("financeiro", 2)
def baixar(id):
    f = store().get("finance", id) or abort(404)
    lock, hoje = data_fechamento(), tempo.hoje()
    if lock and hoje <= lock:
        flash(msg_fechado(lock), "erro")
    elif not f["paid"]:
        f.update(paid=True, paidDate=hoje)
        try:
            store().salvar("finance", f, acao=f"Baixa: {f.get('desc')} ({web.dinheiro(f['value'])})", usuario=web.nome_usuario())
            flash("Lançamento baixado.")
        except Conflito:
            flash("O lançamento foi alterado em outro computador. Confira e tente de novo.", "aviso")
    return redirect(request.referrer or url_for("financeiro.mes"))


@bp.route("/<id>/recibo")
@exige("financeiro")
def recibo(id):
    f = store().get("finance", id) or abort(404)
    p = store().get("patients", f.get("patientId")) if f.get("patientId") else None
    d = store().get("dentists", f.get("dentistId")) if f.get("dentistId") else None
    return render_template("recibo.html", f=f, p=p or {}, d=d or {})


# ---------- períodos contábeis (só o administrador) ----------
@bp.route("/periodos", methods=["GET", "POST"])
@exige("_admin")
def periodos():
    hoje = tempo.hoje()
    lock = data_fechamento()
    de = tempo.soma_dias(lock, 1) if lock else ""
    fim_mes_anterior = tempo.soma_dias(hoje[:8] + "01", -1)
    ate = request.values.get("ate") or (fim_mes_anterior if fim_mes_anterior > lock else hoje)
    erro = ""
    if ate > hoje:
        erro = "A data não pode ser futura"
    elif lock and ate <= lock:
        erro = f"Escolha uma data depois de {tempo.data_br(lock)} (último fechamento)"
    resumo = None if erro else resumo_periodo(de, ate)
    if request.method == "POST" and not erro:
        cl = store().clinica()
        lista = list(cl.get("finClosings") or [])
        lista.append({"id": novo_id(), "from": de, "until": ate, "at": tempo.agora().isoformat(timespec="seconds"), "by": web.nome_usuario(),
                      "rec": resumo["rec"], "desp": resumo["desp"], "n": resumo["n"], "openR": resumo["open_r"], "openD": resumo["open_d"]})
        cl["finClosings"] = lista
        try:
            store().salvar("clinic", cl, acao=f"Período contábil fechado: {tempo.data_br(de) if de else 'início'} a {tempo.data_br(ate)} "
                                              f"(recebido {web.dinheiro(resumo['rec'])}, pago {web.dinheiro(resumo['desp'])}, {resumo['n']} lançamento(s))",
                           usuario=web.nome_usuario())
        except Conflito:
            flash("As configurações da clínica foram alteradas em outro computador agora. Confira e feche de novo.", "aviso")
            return redirect(url_for("financeiro.periodos"))
        flash(f"Período fechado até {tempo.data_br(ate)}. O novo período começa em {tempo.data_br(tempo.soma_dias(ate, 1))}.")
        return redirect(url_for("financeiro.mes"))
    lista = sorted(fechamentos(), key=lambda c: c.get("until") or "", reverse=True)
    return render_template("periodos.html", lock=lock, de=de, ate=ate, erro=erro, resumo=resumo, lista=lista, hoje=hoje)


@bp.route("/periodos/<id>/reabrir", methods=["POST"])
@exige("_admin")
def reabrir(id):
    cl = store().clinica()
    lista = list(cl.get("finClosings") or [])
    ultimo = max(lista, key=lambda c: c.get("until") or "", default=None)
    if not ultimo or ultimo.get("id") != id:
        flash("Só o último fechamento pode ser reaberto.", "erro")
        return redirect(url_for("financeiro.periodos"))
    cl["finClosings"] = [c for c in lista if c.get("id") != id]
    store().salvar("clinic", cl, acao=f"Período contábil REABERTO: {tempo.data_br(ultimo.get('from')) or 'início'} a {tempo.data_br(ultimo['until'])}",
                   usuario=web.nome_usuario())
    flash("Período reaberto.")
    return redirect(url_for("financeiro.periodos"))


@bp.route("/periodos/<id>/imprimir")
@exige("_admin")
def imprimir_periodo(id):
    c = next((x for x in fechamentos() if x.get("id") == id), None) or abort(404)
    return render_template("periodo_impressao.html", c=c, r=resumo_periodo(c.get("from") or "", c["until"]))
