"""Entrar, sair, trocar a senha e primeiro acesso (banco vazio)."""
import time

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from .. import seguranca, tempo, web
from ..web import store

bp = Blueprint("auth", __name__)
SESSAO_HORAS = 12


def _abrir_sessao(u):
    session.clear()
    session.update(u=u["id"], h=str(u.get("hash"))[:12], exp=time.time() + SESSAO_HORAS * 3600)
    session.permanent = False


@bp.route("/entrar", methods=["GET", "POST"])
def entrar():
    st = store()
    if st.vazio() or not st.listar("users"):
        return redirect(url_for("auth.primeiro_acesso"))
    erro = ""
    login = ""
    if request.method == "POST":
        login, senha = seguranca.normaliza_login(request.form.get("login")), request.form.get("senha") or ""
        espera = web.login_bloqueado(login)
        if not login or not senha:
            erro = "Informe usuário e senha"
        elif espera:
            erro = f"Muitas tentativas. Aguarde {espera} segundos."
        else:
            u = next((x for x in st.listar("users") if x.get("login") == login), None)
            boa = u and seguranca.confere_senha(senha, u)
            if not boa or not u.get("active"):
                web.login_falhou(login)
                erro = "Usuário desativado. Fale com o administrador." if boa else "Usuário ou senha incorretos."
            else:
                web.login_ok(login)
                _abrir_sessao(u)
                try:
                    u["lastLogin"] = tempo.agora_texto()[:16]
                    st.salvar("users", u)
                except Exception:
                    pass
                st.auditar(f"Entrou no sistema (web)", u["name"])
                if u.get("mustChange"):
                    return redirect(url_for("auth.trocar_senha"))
                prox = request.args.get("proximo") or ""
                return redirect(prox if prox.startswith("/") and not prox.startswith("//") else url_for("painel.inicio"))
    return render_template("entrar.html", erro=erro, login=login)


@bp.route("/sair", methods=["POST"])
def sair():
    if g.get("usuario"):
        store().auditar("Saiu do sistema (web)", g.usuario["name"])
    session.clear()
    return redirect(url_for("auth.entrar"))


@bp.route("/trocar-senha", methods=["GET", "POST"])
def trocar_senha():
    if not g.get("usuario"):
        return redirect(url_for("auth.entrar"))
    u, erro = g.usuario, ""
    if request.method == "POST":
        atual, nova, nova2 = (request.form.get(k) or "" for k in ("atual", "nova", "nova2"))
        if not u.get("mustChange") and not seguranca.confere_senha(atual, u):
            erro = "Senha atual incorreta"
        elif nova != nova2:
            erro = "As duas senhas novas não são iguais"
        else:
            erro = seguranca.problema_senha(nova, u.get("login"))
        if not erro:
            u.update(seguranca.hash_senha(nova))
            u["mustChange"] = False
            store().salvar("users", u, acao="Senha alterada", usuario=u["name"])
            _abrir_sessao(u)
            flash("Senha alterada.")
            return redirect(url_for("painel.inicio"))
    return render_template("trocar_senha.html", erro=erro, forcado=u.get("mustChange"))


@bp.route("/primeiro-acesso", methods=["GET", "POST"])
def primeiro_acesso():
    """Banco vazio (ou sem usuários): cadastra a clínica e o administrador."""
    st = store()
    if not st.vazio() and st.listar("users"):
        return redirect(url_for("auth.entrar"))
    erro = ""
    v = web.campos("clinica", "nome", "login", "senha", "senha2") if request.method == "POST" else {}
    if request.method == "POST":
        login = seguranca.normaliza_login(v["login"])
        if not v["nome"] or not login:
            erro = "Informe o nome e o usuário do administrador"
        elif v["senha"] != v["senha2"]:
            erro = "As duas senhas não são iguais"
        else:
            erro = seguranca.problema_senha(v["senha"], login)
        if not erro:
            cl = st.clinica()
            if not cl:
                cl = {"name": v["clinica"] or "Minha Clínica Odontológica", "cnpj": "", "phone": "", "email": "", "address": "", "city": "",
                      "start": "08:00", "end": "18:00", "slot": 30, "profiles": seguranca.perfis_padrao()}
                st.salvar("clinic", cl, acao="Banco de dados iniciado (OdontoDesk em Python)")
            u = {"name": v["nome"], "login": login, "profileId": "admin", "active": True, "mustChange": False, "dentistId": "",
                 "lastLogin": "", **seguranca.hash_senha(v["senha"])}
            u = st.salvar("users", u, acao=f"Administrador cadastrado: {v['nome']}", usuario=v["nome"])
            _abrir_sessao(u)
            return redirect(url_for("painel.inicio"))
    return render_template("primeiro_acesso.html", erro=erro, v=v, tem_clinica=not st.vazio())
