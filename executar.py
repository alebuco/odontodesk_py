"""Inicia o OdontoDesk em Python.

    python executar.py                 → usa o config.json desta pasta
    python executar.py --configurar    → pergunta os dados do banco e cria o config.json

Depois abra no navegador: http://localhost:8650 (ou o endereço mostrado).
"""
import getpass
import json
import os
import secrets
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.environ.get("ODONTODESK_PY_CONFIG") or os.path.join(AQUI, "config.json")


def perguntar(txt, padrao=""):
    r = input(f"{txt}{f' [{padrao}]' if padrao else ''}: ").strip()
    return r or padrao


def configurar():
    atual = {}
    if os.path.exists(CONFIG):
        with open(CONFIG, encoding="utf-8") as f:
            atual = json.load(f)
    b = atual.get("banco", {})
    print("Dados do banco (os mesmos do OdontoDesk do computador: Configurações → Banco de dados).")
    print("TiDB Cloud: Cluster → Connect → Public. A porta é 4000.\n")
    tipo = perguntar("Tipo (mysql ou sqlite)", b.get("tipo", "mysql"))
    if tipo == "sqlite":
        b = {"tipo": "sqlite", "arquivo": perguntar("Arquivo", b.get("arquivo", os.path.join(AQUI, "odontodesk.db")))}
    else:
        b = {"tipo": "mysql", "host": perguntar("Endereço do servidor", b.get("host", "")), "porta": int(perguntar("Porta", str(b.get("porta", 4000)))),
             "nome": perguntar("Banco", b.get("nome", "odontodesk")), "usuario": perguntar("Usuário", b.get("usuario", ""))}
        senha = getpass.getpass("Senha (Enter mantém a atual): ")
        b["senha"] = senha or atual.get("banco", {}).get("senha", "")
    cfg = {**atual, "banco": b, "chave_secreta": atual.get("chave_secreta") or secrets.token_hex(32),
           "computador": atual.get("computador") or "WEB-PYTHON", "fuso": atual.get("fuso") or "America/Sao_Paulo",
           "endereco": atual.get("endereco") or "127.0.0.1", "porta": atual.get("porta") or 8650, "https": atual.get("https", False)}
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    try:
        os.chmod(CONFIG, 0o600)
    except OSError:
        pass
    print(f"\nConfiguração salva em {CONFIG}")


def main():
    if "--configurar" in sys.argv or not os.path.exists(CONFIG):
        configurar()
    sys.path.insert(0, AQUI)
    from odontodesk.app import carregar_config, create_app
    cfg = carregar_config(CONFIG)
    app = create_app(cfg)
    host, porta = cfg.get("endereco") or "127.0.0.1", int(cfg.get("porta") or 8650)
    print(f"OdontoDesk em Python: abra http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{porta}")
    try:
        from waitress import serve
        serve(app, host=host, port=porta, threads=8)
    except ImportError:
        print("(waitress não instalado: usando o servidor de testes do Flask)")
        app.run(host=host, port=porta)


if __name__ == "__main__":
    main()
