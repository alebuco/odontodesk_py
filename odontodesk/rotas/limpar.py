"""Configurações → Limpar dados de exemplo e de teste (só o administrador)."""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from .. import limpar, web
from ..web import exige, store

bp = Blueprint("limpar", __name__, url_prefix="/configuracoes/limpar")
COLLS = ["patients", "dentists", "finance", "appointments", "stock", "stockMoves", "prosthetists"] + limpar.LINKED


def _db():
    st = store()
    return {c: st.listar(c) for c in dict.fromkeys(COLLS)} | {"users": st.listar("users")}


@bp.route("/", methods=["GET", "POST"])
@exige("config", 2)
def limpar_dados():
    if not web.eh_admin():
        abort(403)
    db = _db()
    if request.method == "POST":
        pac = request.form.getlist("paciente")
        outros = [tuple(x.split(":", 1)) for x in request.form.getlist("outro") if ":" in x]
        dele, arquivos, ficou = limpar.operacoes(db, pac, outros)
        total = sum(len(v) for v in dele.values())
        if not total:
            flash("Nada foi marcado para excluir.", "aviso")
            return redirect(url_for("limpar.limpar_dados"))
        if request.form.get("confirmar") != "EXCLUIR":
            flash('Para confirmar, digite EXCLUIR no campo indicado.', "erro")
            return redirect(url_for("limpar.limpar_dados"))
        resumo = ", ".join(f"{len(v)} {limpar.LABEL.get(c, 'paciente' if c == 'patients' else c)}{'(s)' if len(v) > 1 else ''}"
                           for c, v in dele.items())
        ops = [{"coll": c, "op": "del", "id": id} for c, ids in dele.items() for id in ids]
        store().aplicar(ops, [{"action": f"Dados de exemplo/teste excluídos: {resumo}", "user": web.nome_usuario()}])
        anexos = current_app.config.get("ANEXOS")
        for f in arquivos:
            try:
                anexos.excluir(f)
            except Exception:
                pass
        flash(f"Excluído: {resumo}." + (f" Ficou: {'; '.join(ficou)}." if ficou else ""))
        return redirect(url_for("limpar.limpar_dados"))
    pl = limpar.plano(db)
    return render_template("limpar.html", plano=pl, label=limpar.LABEL)
