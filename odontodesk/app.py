"""OdontoDesk em Python — aplicação web (Flask).

Abra pelo navegador do computador, do celular ou do tablet. Os dados ficam no mesmo banco do app em
JavaScript (TiDB/MySQL), então os dois podem ser usados ao mesmo tempo durante a transição.
"""
import datetime
import json
import os
import secrets

from flask import Flask, g, render_template, request

from . import tempo, web
from .dados.drivers import criar_driver
from .dados.store import Store

VERSAO = "0.3.0"
ETAPA = "Etapas 1 a 3: atendimento, prontuário, financeiro, procedimentos, próteses, estoque, modelos, configurações e usuários"


def carregar_config(caminho=None):
    caminho = caminho or os.environ.get("ODONTODESK_PY_CONFIG") or os.path.join(os.getcwd(), "config.json")
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def create_app(config=None, store=None):
    cfg = config if config is not None else carregar_config()
    tempo.configurar(cfg.get("fuso"))
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=cfg.get("chave_secreta") or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=bool(cfg.get("https")),
        MAX_CONTENT_LENGTH=20 * 1024 * 1024,
        TESTING=bool(cfg.get("testes")),
    )
    if store is None:
        store = Store(criar_driver(cfg.get("banco") or {}), cfg.get("computador") or "WEB-PYTHON")
        store.criar_tabelas()
    app.config["STORE"] = store
    app.config["VERSAO"] = VERSAO
    web.registrar_filtros(app)

    from .rotas import agenda, auth, cadastros, estoque, financeiro, pacientes, painel, prontuario, proteses, usuarios
    for bp in (auth.bp, painel.bp, pacientes.bp, agenda.bp, financeiro.bp, prontuario.bp, cadastros.bp, proteses.bp, estoque.bp, usuarios.bp):
        app.register_blueprint(bp)

    @app.before_request
    def antes():
        web.conferir_csrf()
        web.carregar_usuario()

    @app.after_request
    def seguranca_http(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self' 'unsafe-inline'")
        if g.get("usuario"):
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    @app.context_processor
    def contexto():
        return {"usuario": g.get("usuario"), "clinica": g.get("clinica") or {}, "nivel": web.nivel, "eh_admin": web.eh_admin,
                "csrf": web.csrf_token, "versao": VERSAO, "hoje": tempo.hoje(), "nome_exibicao": web.nome_exibicao,
                "ano": datetime.date.today().year}

    @app.errorhandler(403)
    def proibido(e):
        return render_template("erro.html", titulo="Sem acesso", msg="Seu perfil não tem acesso a esta área."), 403

    @app.errorhandler(404)
    def nao_achou(e):
        return render_template("erro.html", titulo="Não encontrado", msg="Esta página ou registro não existe (ou foi excluído)."), 404

    @app.errorhandler(400)
    def ruim(e):
        return render_template("erro.html", titulo="Não foi possível concluir", msg=getattr(e, "description", "") or "Pedido inválido."), 400

    return app
