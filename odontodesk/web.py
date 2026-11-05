"""Peças comuns das páginas: usuário logado, permissões, proteção dos formulários (CSRF) e formatos."""
import functools
import re
import secrets
import time

from flask import abort, current_app, flash, g, redirect, request, session, url_for

from . import br, seguranca, tempo


def store():
    return current_app.config["STORE"]


# ---------- formatos ----------
def dinheiro(v):
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        v = 0.0
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-R$ " if v < 0 else "R$ ") + s


def numero(v):
    """Aceita 1.234,56 / 1234,56 / 1234.56 → 1234.56"""
    s = str(v or "").strip().replace("R$", "").replace(" ", "")
    if not s:
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def numero_campo(v):
    return f"{float(v or 0):.2f}".replace(".", ",") if v not in (None, "") else ""


def mes_nome(ym):
    nomes = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    a, m = ym.split("-")
    return f"{nomes[int(m) - 1]} de {a}"


def registrar_filtros(app):
    app.jinja_env.filters["dinheiro"] = dinheiro
    app.jinja_env.filters["data"] = tempo.data_br
    app.jinja_env.filters["tel"] = br.telefone_formata
    app.jinja_env.filters["numero_campo"] = numero_campo
    app.jinja_env.filters["mes_nome"] = mes_nome
    # funções usadas também dentro das macros (que não recebem o contexto da página)
    app.jinja_env.globals.update(csrf=csrf_token, nivel=nivel, eh_admin=eh_admin, nome_exibicao=nome_exibicao)


# ---------- usuário e permissões ----------
def nome_exibicao(p):
    return (p or {}).get("socialName") or (p or {}).get("name") or ""


def carregar_usuario():
    g.clinica = store().clinica()
    g.usuario = None
    uid = session.get("u")
    if not uid:
        return
    u = store().get("users", uid)
    # trocar a senha (aqui ou no app do computador) encerra as sessões abertas
    if not u or not u.get("active") or str(u.get("hash"))[:12] != session.get("h") or session.get("exp", 0) < time.time():
        session.clear()
        return
    g.usuario = u


def nivel(modulo):
    return seguranca.nivel(g.get("usuario"), g.get("clinica"), modulo)


def eh_admin():
    return seguranca.eh_admin(g.get("usuario"))


def exige(modulo, minimo=1):
    """Decorador: a página exige login e o nível mínimo no módulo."""
    def deco(fn):
        @functools.wraps(fn)
        def w(*a, **k):
            if not g.get("usuario"):
                return redirect(url_for("auth.entrar", proximo=request.full_path))
            if g.usuario.get("mustChange"):
                return redirect(url_for("auth.trocar_senha"))
            if nivel(modulo) < minimo:
                if minimo >= 2 and nivel(modulo) >= 1:
                    flash("Seu acesso a esta área é só de consulta. Nada foi alterado.", "erro")
                    return redirect(request.referrer or url_for("painel.inicio"))
                abort(403)
            return fn(*a, **k)
        return w
    return deco


def nome_usuario():
    return (g.get("usuario") or {}).get("name", "")


# ---------- proteção dos formulários ----------
def csrf_token():
    t = session.get("csrf")
    if not t:
        t = session["csrf"] = secrets.token_urlsafe(24)
    return t


def conferir_csrf():
    if request.method == "POST":
        enviado = request.form.get("_csrf") or request.headers.get("X-CSRF")
        if not enviado or not secrets.compare_digest(enviado, session.get("csrf", "")):
            abort(400, "Formulário expirado. Volte e tente de novo.")


# ---------- tentativas de login ----------
_falhas = {}


def login_bloqueado(login):
    f = _falhas.get(login)
    return int(f["ate"] - time.time()) + 1 if f and f["ate"] > time.time() else 0


def login_falhou(login):
    f = _falhas.setdefault(login, {"n": 0, "ate": 0})
    f["n"] += 1
    if f["n"] >= 5:
        f["ate"] = time.time() + min(15, 2 ** (f["n"] - 5)) * 60


def login_ok(login):
    _falhas.pop(login, None)


# ---------- ajudas para formulários ----------
def campos(*nomes):
    return {n: (request.form.get(n) or "").strip() for n in nomes}


def opcoes_pacientes():
    ps = store().listar("patients", ordem="nome")
    return [{"id": p["id"], "name": nome_exibicao(p) + (f" ({p['name']})" if p.get("socialName") else "")} for p in ps]


def so_digitos_ou_vazio(v):
    return re.sub(r"\D", "", v or "")
