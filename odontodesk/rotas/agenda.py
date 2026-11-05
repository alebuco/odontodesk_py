"""Agenda: dia e semana, por dentista; marcar, alterar, mudar a situação e excluir consultas."""
import datetime

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import tempo, web
from ..dados.store import Conflito
from ..web import exige, store

bp = Blueprint("agenda", __name__, url_prefix="/agenda")
STATUS = [("agendado", "Agendado"), ("confirmado", "Confirmado"), ("atendido", "Atendido"), ("faltou", "Faltou"), ("cancelado", "Cancelado")]
TIPOS = [("consulta", "Consulta"), ("retorno", "Retorno"), ("encaixe", "Encaixe"), ("bloqueio", "Bloqueio de horário")]
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def _min(hhmm):
    h, m = (hhmm or "00:00").split(":")[:2]
    return int(h) * 60 + int(m)


def _hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def horarios(clinica):
    ini, fim = _min(clinica.get("start") or "08:00"), _min(clinica.get("end") or "18:00")
    passo = int(clinica.get("slot") or 30) or 30
    return [_hhmm(m) for m in range(ini, fim, passo)], passo


def _enriquecer(ags):
    st = store()
    pac, dent, proc = st.mapa("patients"), st.mapa("dentists"), st.mapa("procedures")
    out = []
    for a in ags:
        out.append({**a, "paciente": web.nome_exibicao(pac.get(a.get("patientId"))) if a.get("patientId") else "",
                    "dentista": (dent.get(a.get("dentistId")) or {}).get("name", ""),
                    "procedimento": (proc.get(a.get("procId")) or {}).get("name", ""),
                    "status_nome": dict(STATUS).get(a.get("status"), a.get("status"))})
    return out


@bp.route("/")
@exige("agenda")
def ver():
    hoje = tempo.hoje()
    data = request.args.get("data") or hoje
    modo = request.args.get("modo") or "dia"
    st = store()
    dentistas = st.listar("dentists")
    dentista = request.args.get("dentista")
    if dentista is None:
        dentista = g.usuario.get("dentistId") or ""
    filtro, params = "", ()
    if dentista:
        filtro, params = "(dentista_id = ? OR dentista_id IS NULL OR dentista_id = '')", (dentista,)
    d = datetime.date.fromisoformat(data)
    ctx = {"data": data, "modo": modo, "dentistas": dentistas, "dentista": dentista, "hoje": hoje,
           "anterior": tempo.soma_dias(data, -7 if modo == "semana" else -1), "proximo": tempo.soma_dias(data, 7 if modo == "semana" else 1),
           "dia_semana": DIAS[d.weekday()]}
    if modo == "semana":
        seg = d - datetime.timedelta(days=d.weekday())
        dias = [(seg + datetime.timedelta(days=i)).isoformat() for i in range(7)]
        w = f"data >= ? AND data <= ?" + (f" AND {filtro}" if filtro else "")
        ags = _enriquecer(st.listar("appointments", w, (dias[0], dias[-1], *params), ordem="data, hora"))
        ctx["semana"] = [{"data": x, "nome": DIAS[i], "consultas": [a for a in ags if a["date"] == x]} for i, x in enumerate(dias)]
    else:
        ags = _enriquecer(st.listar("appointments", "data = ?" + (f" AND {filtro}" if filtro else ""), (data, *params), ordem="hora"))
        slots, passo = horarios(g.clinica)
        por_slot = {s: [] for s in slots}
        fora = []
        for a in ags:
            m = _min(a.get("time"))
            alvo = next((s for s in slots if _min(s) <= m < _min(s) + passo), None)
            (por_slot[alvo] if alvo else fora).append(a)
        ctx.update(slots=slots, por_slot=por_slot, fora=fora, total=len([a for a in ags if a.get("type") != "bloqueio"]))
    return render_template("agenda.html", **ctx)


def _conflitos(rec):
    """Outras consultas do mesmo dentista que se sobrepõem a este horário."""
    if rec.get("type") == "bloqueio" or not rec.get("dentistId"):
        return []
    ini = _min(rec["time"])
    fim = ini + int(rec.get("duration") or 30)
    out = []
    for a in store().listar("appointments", "data = ? AND dentista_id = ?", (rec["date"], rec["dentistId"])):
        if a["id"] == rec.get("id") or a.get("status") in ("cancelado", "faltou"):
            continue
        ai = _min(a.get("time"))
        if ai < fim and ini < ai + int(a.get("duration") or 30):
            out.append(a)
    return out


def _form_ctx(v, erros, novo, a=None):
    st = store()
    return dict(v=v, erros=erros, novo=novo, a=a, pacientes=web.opcoes_pacientes(), dentistas=st.listar("dentists"),
                procedimentos=st.listar("procedures", ordem="nome"), status=STATUS, tipos=TIPOS)


def _ler_form():
    v = web.campos("date", "time", "duration", "type", "patientId", "dentistId", "procId", "status", "notes")
    v["duration"] = int(v["duration"] or 30)
    return v


def _validar(v):
    erros = {}
    if not v["date"]:
        erros["date"] = "Informe a data"
    if not v["time"]:
        erros["time"] = "Informe o horário"
    if v["type"] != "bloqueio" and not v["patientId"]:
        erros["patientId"] = "Selecione o paciente"
    return erros


@bp.route("/nova", methods=["GET", "POST"])
@exige("agenda", 2)
def nova():
    if request.method == "POST":
        v = _ler_form()
        erros = _validar(v)
        if not erros:
            rec = {**v}
            if v["type"] == "bloqueio":
                rec.update(patientId="", dentistId="", procId="")
            choques = _conflitos(rec)
            if choques and not request.form.get("mesmo_assim"):
                erros["_choque"] = choques
            else:
                rec = store().salvar("appointments", rec, acao=f"Agendamento criado ({tempo.data_br(rec['date'])} {rec['time']})", usuario=web.nome_usuario())
                flash("Consulta marcada." if rec["type"] != "bloqueio" else "Horário bloqueado.")
                return redirect(url_for("agenda.ver", data=rec["date"], dentista=request.args.get("dentista", "")))
        if erros.get("_choque"):
            erros["_choque"] = _enriquecer(erros["_choque"])
    else:
        v = {"date": request.args.get("data") or tempo.hoje(), "time": request.args.get("hora") or "08:00", "duration": int(g.clinica.get("slot") or 30),
             "type": "consulta", "status": "agendado", "dentistId": request.args.get("dentista") or g.usuario.get("dentistId") or "",
             "patientId": request.args.get("paciente") or ""}
        erros = {}
    return render_template("agendamento_form.html", **_form_ctx(v, erros, True))


@bp.route("/<id>", methods=["GET", "POST"])
@exige("agenda")
def editar(id):
    a = store().get("appointments", id) or abort(404)
    if request.method == "POST":
        if web.nivel("agenda") < 2:
            abort(403)
        v = _ler_form()
        erros = _validar(v)
        if not erros:
            rec = {**a, **v, "_v": int(request.form.get("_v") or a["_v"])}
            if v["type"] == "bloqueio":
                rec.update(patientId="", dentistId="", procId="")
            choques = _conflitos(rec)
            if choques and not request.form.get("mesmo_assim"):
                erros["_choque"] = _enriquecer(choques)
            else:
                try:
                    store().salvar("appointments", rec, acao="Agendamento atualizado", usuario=web.nome_usuario())
                except Conflito:
                    flash("Esta consulta foi alterada em outro computador enquanto você editava. Os dados atuais foram carregados.", "aviso")
                    return redirect(url_for("agenda.editar", id=id))
                flash("Consulta atualizada.")
                return redirect(url_for("agenda.ver", data=rec["date"]))
    else:
        v, erros = dict(a), {}
    return render_template("agendamento_form.html", **_form_ctx(v, erros, False, a))


@bp.route("/<id>/situacao", methods=["POST"])
@exige("agenda", 2)
def situacao(id):
    a = store().get("appointments", id) or abort(404)
    novo = request.form.get("status")
    if novo not in dict(STATUS):
        abort(400)
    a["status"] = novo
    try:
        store().salvar("appointments", a, acao=f"Consulta {dict(STATUS)[novo].lower()} ({tempo.data_br(a['date'])} {a['time']})", usuario=web.nome_usuario())
    except Conflito:
        flash("A consulta foi alterada em outro computador. Confira e tente de novo.", "aviso")
    return redirect(request.referrer or url_for("agenda.ver", data=a["date"]))


@bp.route("/<id>/excluir", methods=["POST"])
@exige("agenda", 2)
def excluir(id):
    a = store().get("appointments", id) or abort(404)
    store().excluir("appointments", id, acao="Agendamento excluído", usuario=web.nome_usuario())
    flash("Agendamento excluído.")
    return redirect(url_for("agenda.ver", data=a["date"]))
