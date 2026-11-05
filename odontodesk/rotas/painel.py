"""Painel (página inicial) e Sobre."""
from flask import Blueprint, g, render_template

from .. import tempo, web
from ..web import exige, store
from .financeiro import resumo_mes

bp = Blueprint("painel", __name__)


@bp.route("/")
@exige("_todos")
def inicio():
    st, hoje = store(), tempo.hoje()
    ctx = {}
    if web.nivel("agenda") >= 1:
        dent = st.mapa("dentists")
        pac = st.mapa("patients")
        ags = st.listar("appointments", "data = ?", (hoje,), ordem="hora")
        if g.usuario.get("dentistId") and not web.eh_admin():
            ags = [a for a in ags if a.get("dentistId") in ("", g.usuario["dentistId"])]
        ctx["consultas"] = [{**a, "paciente": web.nome_exibicao(pac.get(a.get("patientId"))), "dentista": (dent.get(a.get("dentistId")) or {}).get("name", "")}
                            for a in ags if a.get("type") != "bloqueio"]
    if web.nivel("pacientes") >= 1:
        md = hoje[5:]
        ctx["aniversarios"] = [p for p in st.listar("patients", "nascimento IS NOT NULL") if (p.get("birth") or "")[5:] == md]
    if web.nivel("pacientes") >= 1:
        from .preconsulta import proxima_consulta
        pend = [p for p in st.listar("patients") if (p.get("preConsulta") or {}).get("status") == "enviado"]
        ctx["pre_pendentes"] = [{"p": p, "a": proxima_consulta(p["id"])} for p in pend]
    if web.nivel("financeiro") >= 1:
        ctx["fin"] = resumo_mes(hoje[:7])
        venc = st.listar("finance", "pago = 0 AND vencimento < ?", (hoje,), ordem="vencimento")
        ctx["vencidos"] = venc
    return render_template("painel.html", **ctx)


@bp.route("/sobre")
@exige("_todos")
def sobre():
    from ..app import ETAPA
    return render_template("sobre.html", etapa=ETAPA)
