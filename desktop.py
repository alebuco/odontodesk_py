"""OdontoDesk em Python como aplicativo de computador (janela própria, sem barra de endereço).

    pythonw desktop.py      (Windows: sem a janela preta; o atalho criado por instalar_atalho.bat faz isso)
    python3 desktop.py      (Linux)

Liga o sistema só neste computador (endereço 127.0.0.1, ninguém de fora acessa) e abre numa aba do Brave (se estiver
instalado) ou numa janela própria do Edge/Chrome. Fechadas as abas do OdontoDesk, o sistema desliga sozinho em 5 minutos.
No config.json: "navegador": "edge" ou "chrome" para preferir outro; "janela": "aba" para abrir sempre como aba. Usa o mesmo config.json do executar.py
(o mesmo banco: o que for gravado aqui aparece no app do computador, no servidor e no celular).
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser

AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.environ.get("ODONTODESK_PY_CONFIG") or os.path.join(AQUI, "config.json")
PORTA = 8651
ULTIMO_USO = [time.time()]
WIN = os.name == "nt"
DADOS = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.local/share"), "OdontoDesk-Python")
os.makedirs(DADOS, exist_ok=True)
LOG = os.path.join(DADOS, "odontodesk.log")


def aviso(msg):
    """Mostra uma mensagem mesmo sem console (pythonw)."""
    print(msg)
    if WIN:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, "OdontoDesk", 0x40)
            return
        except Exception:
            pass
    for cmd in (["zenity", "--info", "--text", msg], ["notify-send", "OdontoDesk", msg]):
        if shutil.which(cmd[0]):
            subprocess.run(cmd)
            return


def ja_rodando(porta):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/entrar", timeout=2) as r:
            return b"OdontoDesk" in r.read()
    except Exception:
        return False


def porta_livre(porta):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", porta)) != 0


def navegador(preferido=""):
    """(caminho, modo): o Brave abre como aba (no Brave que você já usa); Edge/Chrome abrem em janela própria."""
    if WIN:
        bases = [os.environ.get(k, "") for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
        cands = [("brave", r"BraveSoftware\Brave-Browser\Application\brave.exe"), ("edge", r"Microsoft\Edge\Application\msedge.exe"),
                 ("chrome", r"Google\Chrome\Application\chrome.exe")]
        achados = [(n, os.path.join(b, rel)) for n, rel in cands for b in bases if b and os.path.exists(os.path.join(b, rel))]
    else:
        nomes = [("brave", "brave-browser"), ("brave", "brave"), ("edge", "microsoft-edge"), ("chrome", "google-chrome"),
                 ("chrome", "google-chrome-stable"), ("chrome", "chromium"), ("chrome", "chromium-browser")]
        achados = [(n, shutil.which(x)) for n, x in nomes if shutil.which(x)]
    achados.sort(key=lambda x: x[0] != preferido)
    return achados[0] if achados else (None, None)


def iniciar_servidor(porta):
    sys.path.insert(0, AQUI)
    from odontodesk.app import carregar_config, create_app
    cfg = carregar_config(CONFIG)
    cfg = {**cfg, "https": False}   # aqui é só 127.0.0.1
    if not cfg.get("computador") or cfg.get("computador") == "WEB-PYTHON":
        cfg["computador"] = (os.environ.get("COMPUTERNAME") or socket.gethostname() or "DESKTOP")[:40] + "-PY"
    app = create_app(cfg)
    app.config["DESKTOP"] = True               # as páginas avisam a cada minuto que continuam abertas
    app.before_request(lambda: ULTIMO_USO.__setitem__(0, time.time()))
    app.add_url_rule("/_vivo", "vivo", lambda: ("", 204))
    try:
        from waitress import create_server
        srv = create_server(app, host="127.0.0.1", port=porta, threads=8)
        threading.Thread(target=srv.run, daemon=True).start()
    except ImportError:                          # sem waitress: servidor do próprio Flask
        from werkzeug.serving import make_server
        srv = make_server("127.0.0.1", porta, app, threaded=True)
        srv.close = srv.shutdown
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    for _ in range(100):
        if not porta_livre(porta):
            return srv
        time.sleep(0.1)
    return srv


def main():
    if not os.path.exists(CONFIG):
        aviso("Falta configurar o banco de dados.\n\nAbra o Prompt de Comando nesta pasta e rode:\n  python executar.py --configurar\n\n"
              f"Pasta: {AQUI}")
        return
    porta, srv = PORTA, None
    if ja_rodando(porta):
        pass                                     # já aberto: só abre outra janela
    else:
        while not porta_livre(porta):
            porta += 1
        srv = iniciar_servidor(porta)
    url = f"http://127.0.0.1:{porta}/"
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    nome, exe = navegador(cfg.get("navegador") or "brave")
    if not exe:
        webbrowser.open(url)
    elif nome == "brave" or cfg.get("janela") == "aba":
        subprocess.Popen([exe, url])                                  # nova aba no navegador já aberto
    else:
        perfil = os.path.join(DADOS, "janela")
        subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={perfil}", "--no-first-run", "--no-default-browser-check",
                          "--window-size=1366,860", "--disable-features=Translate"])
    if srv:
        esperar_fechar(int(os.environ.get("ODONTODESK_DESKTOP_LIMITE") or 300))
        srv.close()


def esperar_fechar(limite=300):
    """Fica ligado enquanto houver alguma tela do OdontoDesk aberta: cada página avisa a cada minuto (/_vivo).
    Fechadas todas as abas/janelas, desliga depois de 5 minutos."""
    while time.time() - ULTIMO_USO[0] < limite:
        time.sleep(5)


if __name__ == "__main__":
    if sys.stdout is None or "pythonw" in os.path.basename(sys.executable).lower():
        sys.stdout = sys.stderr = open(LOG, "a", encoding="utf-8", buffering=1)
    try:
        main()
    except Exception:
        traceback.print_exc()
        aviso("Não foi possível abrir o OdontoDesk.\n\n" + traceback.format_exc()[-800:] + f"\n\nDetalhes em {LOG}")
