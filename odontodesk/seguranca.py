"""Senhas, perfis e permissões — as mesmas regras do app em JavaScript.

Senhas: PBKDF2-SHA256 com sal aleatório, 210.000 iterações, em base64 (os campos hash/salt/iter do usuário).
Uma senha criada num app funciona no outro.
Permissões: cada perfil tem um nível por módulo: 0 = sem acesso, 1 = só consulta, 2 = completo.
O perfil "admin" (Administrador) tem acesso completo a tudo.
"""
import base64
import hashlib
import hmac
import os
import re
import unicodedata

PBKDF2_ITER = 210000
PASS_MIN = 8

MODULES = [
    ("painel", "Painel"), ("agenda", "Agenda"), ("pacientes", "Pacientes (cadastro)"),
    ("prontuario", "Prontuário (anamnese, odontograma e financeiro, documentos, galeria, histórico)"),
    ("financeiro", "Financeiro (geral e do paciente)"), ("procedimentos", "Procedimentos e preços"), ("proteses", "Próteses"),
    ("estoque", "Estoque"), ("documentos", "Modelos de documentos"), ("config", "Configurações da clínica"),
]


def _todos(v):
    return {k: v for k, _ in MODULES}


def perfis_padrao():
    return [
        {"id": "admin", "name": "Administrador", "fixed": True, "perms": _todos(2)},
        {"id": "dentista", "name": "Dentista", "perms": {"painel": 2, "agenda": 2, "pacientes": 2, "prontuario": 2, "financeiro": 0,
                                                       "procedimentos": 1, "proteses": 2, "estoque": 2, "documentos": 2, "config": 0}},
        {"id": "recepcao", "name": "Recepção", "perms": {"painel": 2, "agenda": 2, "pacientes": 2, "prontuario": 1, "financeiro": 2,
                                                        "procedimentos": 1, "proteses": 2, "estoque": 2, "documentos": 1, "config": 0}},
        {"id": "auxiliar", "name": "Auxiliar (ASB/TSB)", "perms": {"painel": 1, "agenda": 1, "pacientes": 1, "prontuario": 1, "financeiro": 0,
                                                                  "procedimentos": 1, "proteses": 2, "estoque": 2, "documentos": 0, "config": 0}},
    ]


def hash_senha(senha, sal_b64=None, iter=PBKDF2_ITER):
    sal = base64.b64decode(sal_b64) if sal_b64 else os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", unicodedata.normalize("NFC", str(senha)).encode("utf-8"), sal, int(iter), 32)
    return {"hash": base64.b64encode(h).decode(), "salt": base64.b64encode(sal).decode(), "iter": int(iter)}


def confere_senha(senha, usuario):
    if not usuario or not usuario.get("hash") or not usuario.get("salt"):
        return False
    h = hash_senha(senha, usuario["salt"], usuario.get("iter") or PBKDF2_ITER)["hash"]
    return hmac.compare_digest(h.encode(), str(usuario["hash"]).encode())


def problema_senha(senha, login=""):
    senha = str(senha or "")
    if len(senha) < PASS_MIN:
        return f"A senha precisa ter pelo menos {PASS_MIN} caracteres"
    if not re.search(r"[a-zA-Z]", senha) or not re.search(r"\d", senha):
        return "Use letras e números na senha"
    if login and str(login).lower() in senha.lower():
        return "A senha não pode conter o nome de usuário"
    return ""


def normaliza_login(s):
    s = unicodedata.normalize("NFD", str(s or "").strip().lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9._-]", "", s)


def perfis(clinica):
    p = (clinica or {}).get("profiles")
    return p if isinstance(p, list) and p else perfis_padrao()


def eh_admin(usuario):
    return bool(usuario) and usuario.get("profileId") == "admin"


def nivel(usuario, clinica, modulo):
    """0, 1 ou 2. `_todos` = páginas que todos veem; `_admin` = só o administrador."""
    if not usuario:
        return 0
    if modulo == "_todos":
        return 2
    if modulo == "_admin":
        return 2 if eh_admin(usuario) else 0
    if eh_admin(usuario):
        return 2
    perfil = next((p for p in perfis(clinica) if p.get("id") == usuario.get("profileId")), None)
    try:
        return int(((perfil or {}).get("perms") or {}).get(modulo) or 0)
    except (TypeError, ValueError):
        return 0
