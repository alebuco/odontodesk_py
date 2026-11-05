"""Prontuário do paciente: anamnese, evolução clínica, odontograma e planos de tratamento (orçamento e cobrança) e histórico.

Mesmas regras e mesmo formato de dados do app em JavaScript:
  - anamnese em paciente.anamnesis: {<id da pergunta>: 'sim'|'nao'|texto, <id>_obs, _queixa, _updated}
  - evolução: o autor corrige em até 24 h (a versão anterior vai para `history`); depois, só adendos (`addenda`)
  - plano de tratamento: itens {tooth, faces, procId, name, code, source, price, status, doneAt}; aprovar gera
    a entrada (paga) e as parcelas no financeiro, ligadas ao plano (treatmentId)
"""
import urllib.parse

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import br, tempo, web
from ..dados.store import Conflito, novo_id
from ..web import exige, store
from .financeiro import PAY, data_fechamento, msg_fechado

bp = Blueprint("prontuario", __name__)
EVO_HORAS = 24
UPPER = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28]
LOWER = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]
UPPER_D = [55, 54, 53, 52, 51, 61, 62, 63, 64, 65]
LOWER_D = [85, 84, 83, 82, 81, 71, 72, 73, 74, 75]
FACES = {"V": "Vestibular", "L": "Lingual/Palatina", "M": "Mesial", "D": "Distal", "O": "Oclusal/Incisal"}
PLAN_STATUS = {"orcamento": ("Orçamento", "warn"), "aprovado": ("Aprovado", "info"), "concluido": ("Concluído", "ok")}
TIPOS_CONSULTA = {"consulta": "Consulta", "retorno": "Retorno", "encaixe": "Encaixe", "bloqueio": "Bloqueio de horário"}


def _paciente(pid):
    return store().get("patients", pid) or abort(404)


def _salvar(coll, rec, acao, voltar):
    """Grava; se outra pessoa alterou antes, avisa e volta para a página (com os dados atuais)."""
    try:
        return store().salvar(coll, rec, acao=acao, usuario=web.nome_usuario())
    except Conflito:
        flash("Este registro foi alterado em outro computador enquanto você trabalhava. Os dados atuais foram carregados: confira e repita.", "aviso")
        raise _Volta(voltar)


class _Volta(Exception):
    def __init__(self, url):
        self.url = url


@bp.errorhandler(_Volta)
def _volta(e):
    return redirect(e.url)


# ====================== ANAMNESE ======================
@bp.route("/pacientes/<pid>/anamnese", methods=["GET", "POST"])
@exige("prontuario")
def anamnese(pid):
    p = _paciente(pid)
    perguntas = store().listar("anamnesisModel")
    if request.method == "POST":
        if web.nivel("prontuario") < 2:
            abort(403)
        an = {"_queixa": (request.form.get("_queixa") or "").strip()}
        for m in perguntas:
            an[m["id"]] = (request.form.get(m["id"]) or "").strip()
            if m.get("type") == "yesno":
                an[m["id"] + "_obs"] = (request.form.get(m["id"] + "_obs") or "").strip()
        an["_updated"] = tempo.hoje()
        p["anamnesis"] = an
        p["_v"] = int(request.form.get("_v") or p["_v"])
        _salvar("patients", p, f"Anamnese atualizada: {p['name']}", url_for("prontuario.anamnese", pid=pid))
        flash("Anamnese salva.")
        return redirect(url_for("prontuario.anamnese", pid=pid))
    return render_template("pront_anamnese.html", p=p, aba="anamnese", perguntas=perguntas, an=p.get("anamnesis") or {})


@bp.route("/pacientes/<pid>/anamnese/imprimir")
@exige("prontuario")
def anamnese_imprimir(pid):
    p = _paciente(pid)
    return render_template("imp_anamnese.html", p=p, perguntas=store().listar("anamnesisModel"), an=p.get("anamnesis") or {})


# ====================== EVOLUÇÃO CLÍNICA ======================
def pode_editar(e):
    return (g.usuario and e.get("authorId") == g.usuario["id"] and tempo.horas_desde(e.get("createdAt")) < EVO_HORAS
            and web.nivel("prontuario") >= 2)


def _consultas_do_paciente(pid):
    hoje = tempo.hoje()
    ags = [a for a in store().listar("appointments", "paciente_id = ?", (pid,))
           if a.get("type") != "bloqueio" and a.get("status") != "cancelado" and (a.get("date") or "") <= hoje]
    return sorted(ags, key=lambda a: (a["date"], a.get("time") or ""), reverse=True)[:40]


def _rotulo_consulta(a, dent, proc):
    return (f"{tempo.data_br(a['date'])} {a.get('time', '')} — {TIPOS_CONSULTA.get(a.get('type'), '')} com "
            f"{(dent.get(a.get('dentistId')) or {}).get('name', '—')}" + (f" · {proc[a['procId']]['name']}" if a.get("procId") in proc else ""))


@bp.route("/pacientes/<pid>/evolucao")
@exige("prontuario")
def evolucao(pid):
    p = _paciente(pid)
    st = store()
    q, fd = (request.args.get("q") or "").strip().lower(), request.args.get("dentista") or ""
    todas = st.listar("evolutions", "paciente_id = ?", (pid,))
    lista = [e for e in todas if (not fd or e.get("dentistId") == fd)
             and (not q or any(q in (t or "").lower() for t in [e.get("text")] + [a.get("text") for a in e.get("addenda") or []]))]
    lista.sort(key=lambda e: (e.get("date") or "", e.get("createdAt") or ""), reverse=True)
    dent, proc, ags = st.mapa("dentists"), st.mapa("procedures"), st.mapa("appointments")
    hoje = tempo.hoje()
    consulta_hoje = next((a for a in st.listar("appointments", "paciente_id = ? AND data = ?", (pid, hoje))
                          if a.get("type") != "bloqueio" and a.get("status") != "cancelado"), None)
    if consulta_hoje and any(e.get("appointmentId") == consulta_hoje["id"] for e in todas):
        consulta_hoje = None
    return render_template("pront_evolucao.html", p=p, aba="evolucao", lista=lista, total=len(todas), q=q, fd=fd, dent=dent, proc=proc, ags=ags,
                           consulta_hoje=consulta_hoje, pode_editar=pode_editar, dentistas=st.listar("dentists"))


def _evo_form_ctx(p, e, novo, erro=""):
    st = store()
    dent, proc = st.mapa("dentists"), st.mapa("procedures")
    ags = _consultas_do_paciente(p["id"])
    if e.get("appointmentId") and not any(a["id"] == e["appointmentId"] for a in ags):
        a = st.get("appointments", e["appointmentId"])
        if a:
            ags.insert(0, a)
    return dict(p=p, aba="evolucao", e=e, novo=novo, erro=erro, consultas=[(a["id"], _rotulo_consulta(a, dent, proc), a) for a in ags],
                dentistas=st.listar("dentists"), horas=EVO_HORAS)


@bp.route("/pacientes/<pid>/evolucao/nova", methods=["GET", "POST"])
@exige("prontuario", 2)
def evolucao_nova(pid):
    p = _paciente(pid)
    st = store()
    if request.method == "POST":
        v = web.campos("appointmentId", "date", "dentistId")
        texto = (request.form.get("text") or "").rstrip()
        erro = ("Escreva as anotações da consulta" if not texto.strip() else "Informe a data do atendimento" if not v["date"]
                else "A data do atendimento não pode ser no futuro" if v["date"] > tempo.hoje() else "")
        if erro:
            return render_template("pront_evolucao_form.html", **_evo_form_ctx(p, {**v, "text": texto}, True, erro))
        e = {"id": novo_id(), "patientId": pid, "date": v["date"], "dentistId": v["dentistId"], "appointmentId": v["appointmentId"], "text": texto,
             "authorId": g.usuario["id"], "authorName": g.usuario["name"], "createdAt": tempo.agora_iso_utc(), "editedAt": "", "addenda": [], "history": []}
        st.salvar("evolutions", e, acao=f"Evolução registrada: {web.nome_exibicao(p)} ({tempo.data_br(v['date'])})", usuario=web.nome_usuario())
        # consulta vinculada que ainda estava agendada/confirmada passa a "atendido"
        a = st.get("appointments", v["appointmentId"]) if v["appointmentId"] else None
        if a and a.get("status") in ("agendado", "confirmado") and a["date"] <= tempo.hoje():
            a["status"] = "atendido"
            try:
                st.salvar("appointments", a)
            except Conflito:
                pass
        flash("Evolução registrada.")
        return redirect(url_for("prontuario.evolucao", pid=pid))
    e = {"date": tempo.hoje(), "dentistId": "", "appointmentId": request.args.get("consulta") or "", "text": ""}
    a = st.get("appointments", e["appointmentId"]) if e["appointmentId"] else None
    if a:
        e.update(date=a["date"], dentistId=a.get("dentistId") or "")
    if not e["dentistId"] and g.usuario.get("dentistId"):
        e["dentistId"] = g.usuario["dentistId"]
    return render_template("pront_evolucao_form.html", **_evo_form_ctx(p, e, True))


def _evo(eid):
    e = store().get("evolutions", eid) or abort(404)
    return e, _paciente(e["patientId"])


@bp.route("/evolucao/<eid>/editar", methods=["GET", "POST"])
@exige("prontuario", 2)
def evolucao_editar(eid):
    e, p = _evo(eid)
    if not pode_editar(e):
        flash(f"Esta evolução não pode mais ser alterada (só o autor, nas primeiras {EVO_HORAS} horas). Use \"Adendo\".", "erro")
        return redirect(url_for("prontuario.evolucao", pid=p["id"]))
    if request.method == "POST":
        v = web.campos("appointmentId", "date", "dentistId")
        texto = (request.form.get("text") or "").rstrip()
        erro = ("Escreva as anotações da consulta" if not texto.strip() else "Informe a data do atendimento" if not v["date"]
                else "A data do atendimento não pode ser no futuro" if v["date"] > tempo.hoje() else "")
        if erro:
            return render_template("pront_evolucao_form.html", **_evo_form_ctx(p, {**e, **v, "text": texto}, False, erro))
        if (texto, v["date"], v["dentistId"], v["appointmentId"]) != (e.get("text"), e.get("date"), e.get("dentistId"), e.get("appointmentId")):
            e.setdefault("history", []).append({"at": tempo.agora_iso_utc(), "by": g.usuario["name"], "text": e.get("text"), "date": e.get("date")})
            e.update(text=texto, date=v["date"], dentistId=v["dentistId"], appointmentId=v["appointmentId"], editedAt=tempo.agora_iso_utc())
            e["_v"] = int(request.form.get("_v") or e["_v"])
            _salvar("evolutions", e, f"Evolução corrigida: {web.nome_exibicao(p)} ({tempo.data_br(v['date'])})", url_for("prontuario.evolucao", pid=p["id"]))
            flash("Evolução corrigida (a versão anterior ficou guardada).")
        return redirect(url_for("prontuario.evolucao", pid=p["id"]))
    return render_template("pront_evolucao_form.html", **_evo_form_ctx(p, e, False))


@bp.route("/evolucao/<eid>/excluir", methods=["POST"])
@exige("prontuario", 2)
def evolucao_excluir(eid):
    e, p = _evo(eid)
    if not pode_editar(e):
        flash(f"Só o autor pode excluir, e só nas primeiras {EVO_HORAS} horas.", "erro")
    else:
        store().excluir("evolutions", eid, acao=f"Evolução excluída: {web.nome_exibicao(p)} ({tempo.data_br(e.get('date'))})", usuario=web.nome_usuario())
        flash("Evolução excluída.")
    return redirect(url_for("prontuario.evolucao", pid=p["id"]))


@bp.route("/evolucao/<eid>/adendo", methods=["GET", "POST"])
@exige("prontuario", 2)
def evolucao_adendo(eid):
    e, p = _evo(eid)
    erro = ""
    if request.method == "POST":
        texto = (request.form.get("text") or "").strip()
        if not texto:
            erro = "Escreva o adendo"
        else:
            e.setdefault("addenda", []).append({"id": novo_id(), "text": texto, "at": tempo.agora_iso_utc(), "authorId": g.usuario["id"], "authorName": g.usuario["name"]})
            e["_v"] = int(request.form.get("_v") or e["_v"])
            _salvar("evolutions", e, f"Adendo na evolução: {web.nome_exibicao(p)} ({tempo.data_br(e.get('date'))})", url_for("prontuario.evolucao_adendo", eid=eid))
            flash("Adendo acrescentado.")
            return redirect(url_for("prontuario.evolucao", pid=p["id"]))
    return render_template("pront_adendo.html", p=p, aba="evolucao", e=e, erro=erro)


@bp.route("/evolucao/<eid>/versoes")
@exige("prontuario")
def evolucao_versoes(eid):
    e, p = _evo(eid)
    return render_template("pront_versoes.html", p=p, aba="evolucao", e=e)


@bp.route("/pacientes/<pid>/evolucao/imprimir")
@exige("prontuario")
def evolucao_imprimir(pid):
    p = _paciente(pid)
    lista = sorted(store().listar("evolutions", "paciente_id = ?", (pid,)), key=lambda e: (e.get("date") or "", e.get("createdAt") or ""))
    return render_template("imp_evolucao.html", p=p, lista=lista, dent=store().mapa("dentists"))


# ====================== ODONTOGRAMA E PLANOS DE TRATAMENTO ======================
def _plano(tid):
    t = store().get("treatments", tid) or abort(404)
    t.setdefault("items", [])
    return t, _paciente(t["patientId"])


def _totais(plan):
    sub = round(sum(float(i.get("price") or 0) for i in plan["items"]), 2)
    total = round(max(0.0, sub - float(plan.get("discount") or 0)), 2)
    feito = round(sum(float(i.get("price") or 0) for i in plan["items"] if i.get("status") == "realizado"), 2)
    return sub, total, feito


def _estado_faces(plan):
    """{dente: {face: 'plan'|'done'}} para pintar o odontograma."""
    out = {}
    for it in plan["items"]:
        for tn in it.get("teeth") or [it.get("tooth")]:
            if not tn:
                continue
            fs = out.setdefault(str(tn), {})
            for f in (it.get("faces") or list(FACES)):
                if fs.get(f) != "done":
                    fs[f] = "done" if it.get("status") == "realizado" else "plan"
    return out


def _proc_label(p):
    return (f"{p['code']} — " if p.get("code") else "") + p.get("name", "")


@bp.route("/pacientes/<pid>/tratamentos")
@exige("prontuario")
def tratamentos(pid):
    p = _paciente(pid)
    st = store()
    planos = sorted(st.listar("treatments", "paciente_id = ?", (pid,)), key=lambda t: t.get("createdAt") or "", reverse=True)
    plan = next((t for t in planos if t["id"] == request.args.get("plano")), planos[0] if planos else None)
    ctx = dict(p=p, aba="tratamentos", planos=planos, plan=plan, dentistas=st.listar("dentists"))
    if plan:
        plan.setdefault("items", [])
        dent = plan.get("dentition") or "permanente"
        sub, total, feito = _totais(plan)
        procs = sorted(st.listar("procedures"), key=lambda x: x.get("name", "").lower())
        ctx.update(arcadas=[a for a, ok in ((UPPER, dent != "decidua"), (UPPER_D, dent != "permanente"), (None, True),
                                            (LOWER_D, dent != "permanente"), (LOWER, dent != "decidua")) if ok],
                   faces=_estado_faces(plan), sub=sub, total=total, feito=feito, procs=[(x["id"], _proc_label(x)) for x in procs],
                   status=PLAN_STATUS.get(plan.get("status"), ("—", "")), dentista=(st.get("dentists", plan.get("dentistId")) or {}).get("name", "—"),
                   whatsapp=_whatsapp_orcamento(p, plan, total), FACES=FACES)
    return render_template("pront_tratamentos.html", **ctx)


def _whatsapp_orcamento(p, plan, total):
    n = br.digitos(p.get("phone"))
    if not n:
        return ""
    if len(n) <= 11:
        n = "55" + n
    linhas = "\n".join(f"• {i.get('name')}{' (dente ' + str(i['tooth']) + ')' if i.get('tooth') else ''}: {web.dinheiro(i.get('price'))}" for i in plan["items"])
    desc = f"\nDesconto: -{web.dinheiro(plan.get('discount'))}" if float(plan.get("discount") or 0) else ""
    txt = f"Olá {web.nome_exibicao(p).split(' ')[0]}! Segue o orçamento do seu tratamento na {g.clinica.get('name', '')}:\n\n{linhas}{desc}\n\n*Total: {web.dinheiro(total)}*"
    return f"https://wa.me/{n}?text={urllib.parse.quote(txt)}"


@bp.route("/pacientes/<pid>/tratamentos/novo", methods=["POST"])
@exige("prontuario", 2)
def plano_novo(pid):
    p = _paciente(pid)
    n = len(store().listar("treatments", "paciente_id = ?", (pid,)))
    t = {"id": novo_id(), "patientId": pid, "createdAt": tempo.hoje(), "status": "orcamento", "discount": 0, "items": [],
         "title": (request.form.get("title") or "").strip() or f"Plano de tratamento {n + 1}",
         "dentistId": request.form.get("dentistId") or "", "dentition": request.form.get("dentition") or "permanente"}
    store().salvar("treatments", t, acao=f"Plano de tratamento criado: {p['name']}", usuario=web.nome_usuario())
    return redirect(url_for("prontuario.tratamentos", pid=pid, plano=t["id"]))


def _volta_plano(plan):
    return url_for("prontuario.tratamentos", pid=plan["patientId"], plano=plan["id"])


@bp.route("/tratamentos/<tid>/item", methods=["POST"])
@exige("prontuario", 2)
def plano_item(tid):
    plan, p = _plano(tid)
    proc = store().get("procedures", request.form.get("procId") or "")
    if not proc:
        flash("Escolha um procedimento.", "erro")
        return redirect(_volta_plano(plan))
    dente = (request.form.get("tooth") or "").strip()
    faces = [f for f in (request.form.get("faces") or "").split(",") if f in FACES] if dente else []
    plan["items"].append({"id": novo_id(), "tooth": int(dente) if dente.isdigit() else "", "faces": faces, "procId": proc["id"], "name": proc.get("name", ""),
                          "code": proc.get("code") or "", "source": proc.get("source") or "", "price": proc.get("price") or 0, "status": "planejado"})
    plan["_v"] = int(request.form.get("_v") or plan["_v"])
    _salvar("treatments", plan, None, _volta_plano(plan))
    return redirect(_volta_plano(plan))


@bp.route("/tratamentos/<tid>/itens", methods=["POST"])
@exige("prontuario", 2)
def plano_itens(tid):
    """Salva situação e valor de todos os itens e o desconto (botão "Salvar alterações")."""
    plan, p = _plano(tid)
    feitos = []
    for it in plan["items"]:
        stt = request.form.get(f"st_{it['id']}")
        if stt in ("planejado", "realizado") and stt != it.get("status"):
            it["status"] = stt
            if stt == "realizado":
                it["doneAt"] = tempo.hoje()
                feitos.append(it.get("name"))
        pr = request.form.get(f"pr_{it['id']}")
        if pr is not None and web.numero(pr) is not None:
            it["price"] = web.numero(pr)
    if request.form.get("discount") is not None and web.numero(request.form.get("discount")) is not None:
        plan["discount"] = web.numero(request.form.get("discount"))
    plan["_v"] = int(request.form.get("_v") or plan["_v"])
    acao = f"Procedimento realizado: {', '.join(feitos)} ({p['name']})" if feitos else None
    _salvar("treatments", plan, acao, _volta_plano(plan))
    flash("Plano salvo.")
    return redirect(_volta_plano(plan))


@bp.route("/tratamentos/<tid>/item/<iid>/remover", methods=["POST"])
@exige("prontuario", 2)
def plano_item_remover(tid, iid):
    plan, p = _plano(tid)
    plan["items"] = [i for i in plan["items"] if i.get("id") != iid]
    plan["_v"] = int(request.form.get("_v") or plan["_v"])
    _salvar("treatments", plan, None, _volta_plano(plan))
    return redirect(_volta_plano(plan))


@bp.route("/tratamentos/<tid>/excluir", methods=["POST"])
@exige("prontuario", 2)
def plano_excluir(tid):
    plan, p = _plano(tid)
    store().excluir("treatments", tid, acao="Plano excluído", usuario=web.nome_usuario())
    flash("Plano de tratamento excluído.")
    return redirect(url_for("prontuario.tratamentos", pid=p["id"]))


@bp.route("/tratamentos/<tid>/concluir", methods=["POST"])
@exige("prontuario", 2)
def plano_concluir(tid):
    plan, p = _plano(tid)
    plan["status"] = "concluido"
    for i in plan["items"]:
        if i.get("status") != "realizado":
            i.update(status="realizado", doneAt=tempo.hoje())
    _salvar("treatments", plan, f"Plano concluído: {p['name']}", _volta_plano(plan))
    flash("Plano concluído.")
    return redirect(_volta_plano(plan))


@bp.route("/tratamentos/<tid>/aprovar", methods=["GET", "POST"])
@exige("prontuario", 2)
def plano_aprovar(tid):
    plan, p = _plano(tid)
    sub, total, feito = _totais(plan)
    if plan.get("status") != "orcamento" or not plan["items"]:
        return redirect(_volta_plano(plan))
    erro = ""
    v = {"entry": "0,00", "n": "1", "first": tempo.hoje(), "method": "Pix"}
    if request.method == "POST":
        v = web.campos("entry", "n", "first", "method")
        entrada = min(web.numero(v["entry"]) or 0.0, total)
        n = max(1, min(48, int(v["n"] or 1)))
        lock, hoje = data_fechamento(), tempo.hoje()
        if entrada > 0 and lock and hoje <= lock:
            erro = msg_fechado(lock)
        elif not v["first"]:
            erro = "Informe o 1º vencimento"
        if not erro:
            resto = round(total - entrada, 2)
            parc = int(resto / n * 100) / 100
            base = {"type": "receita", "category": "Tratamento", "method": v["method"], "patientId": p["id"], "dentistId": plan.get("dentistId") or "", "treatmentId": plan["id"]}
            ops = []
            if entrada > 0:
                f = {**base, "id": novo_id(), "desc": f"{plan['title']} — entrada ({p['name']})", "value": entrada, "due": hoje, "paid": True, "paidDate": hoje}
                ops.append({"coll": "finance", "op": "put", "id": f["id"], "rec": f, "v": 0})
            for i in range(n):
                if resto <= 0:
                    break
                val = round(resto - parc * (n - 1), 2) if i == n - 1 else parc
                f = {**base, "id": novo_id(), "desc": f"{plan['title']} — parcela {i + 1}/{n} ({p['name']})", "value": val,
                     "due": tempo.soma_meses(v["first"], i), "paid": False, "paidDate": ""}
                ops.append({"coll": "finance", "op": "put", "id": f["id"], "rec": f, "v": 0})
            plan.update(status="aprovado", approvedAt=hoje)
            ops.append({"coll": "treatments", "op": "put", "id": plan["id"], "rec": plan, "v": plan["_v"]})
            r = store().aplicar(ops, [{"action": f"Orçamento aprovado: {p['name']} ({web.dinheiro(total)})", "user": web.nome_usuario()}])
            if r["conflicts"]:
                flash("O plano foi alterado em outro computador agora. Confira e aprove de novo.", "aviso")
                # desfaz os lançamentos gravados neste lote
                store().aplicar([{"coll": "finance", "op": "del", "id": o["id"]} for o in ops if o["coll"] == "finance"])
                return redirect(_volta_plano(plan))
            flash("Orçamento aprovado e cobranças lançadas no financeiro.")
            return redirect(_volta_plano(plan))
    return render_template("pront_aprovar.html", p=p, aba="tratamentos", plan=plan, total=total, v=v, erro=erro, formas=PAY)


@bp.route("/tratamentos/<tid>/orcamento")
@exige("prontuario")
def plano_orcamento(tid):
    plan, p = _plano(tid)
    sub, total, feito = _totais(plan)
    d = store().get("dentists", plan.get("dentistId")) or {}
    return render_template("imp_orcamento.html", p=p, plan=plan, sub=sub, total=total, dentista=d.get("name", "—"),
                           com_codigo=any(i.get("code") for i in plan["items"]))


# ====================== HISTÓRICO ======================
@bp.route("/pacientes/<pid>/historico")
@exige("prontuario")
def historico(pid):
    p = _paciente(pid)
    st = store()
    dent, proc = st.mapa("dentists"), st.mapa("procedures")
    nome_d = lambda i: (dent.get(i) or {}).get("name", "—")
    ev = []
    for a in st.listar("appointments", "paciente_id = ?", (pid,)):
        ev.append((a["date"], f"{a.get('time', '')} — {TIPOS_CONSULTA.get(a.get('type'), '')} com {nome_d(a.get('dentistId'))}"
                   + (f" · {proc[a['procId']]['name']}" if a.get("procId") in proc else ""), ("status", a.get("status"))))
    for t in st.listar("treatments", "paciente_id = ?", (pid,)):
        for i in t.get("items") or []:
            if i.get("status") == "realizado":
                ev.append((i.get("doneAt") or t.get("createdAt") or "", f"Procedimento realizado: {i.get('name')}" + (f" (dente {i['tooth']})" if i.get("tooth") else ""), ("ok", "Realizado")))
    for d in p.get("docs") or []:
        ev.append((d.get("date") or "", f"Documento: {d.get('title')}", None))
    for r in st.listar("prescriptions", "paciente_id = ?", (pid,)):
        ev.append((r.get("date") or "", "Receita: " + ", ".join(i.get("g", "") for i in r.get("items") or []), ("", "Receita")))
    for e in st.listar("evolutions", "paciente_id = ?", (pid,)):
        txt = " ".join((e.get("text") or "").split())
        ev.append((e.get("date") or "", f"Evolução{' — ' + nome_d(e['dentistId']) if e.get('dentistId') else ''}: {txt[:90]}{'…' if len(txt) > 90 else ''}", ("info", "Evolução")))
    for h in (p.get("preConsulta") or {}).get("history") or []:
        ev.append(((h.get("date") or "")[:10], f"Pré-consulta: {h.get('event')}", None))
    ev.sort(key=lambda x: x[0] or "", reverse=True)
    return render_template("pront_historico.html", p=p, aba="historico", ev=ev)
