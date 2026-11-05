"""Máscaras e validação de documentos brasileiros: CPF, CNPJ (inclusive o alfanumérico), telefone e CEP.
Mesmas regras de src/br.js do app em JavaScript."""
import re

DDD = {11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28, 31, 32, 33, 34, 35, 37, 38, 41, 42, 43, 44, 45, 46, 47, 48, 49,
       51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68, 69, 71, 73, 74, 75, 77, 79, 81, 82, 83, 84, 85, 86, 87, 88, 89,
       91, 92, 93, 94, 95, 96, 97, 98, 99}
UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
       "RS", "RO", "RR", "SC", "SP", "SE", "TO"]


def digitos(s):
    return re.sub(r"\D", "", str(s or ""))


def _alnum(s):
    return re.sub(r"[^0-9A-Z]", "", str(s or "").upper())


# ---------- CPF ----------
def cpf_formata(v):
    d = digitos(v)[:11]
    if len(d) <= 3:
        return d
    if len(d) <= 6:
        return f"{d[:3]}.{d[3:]}"
    if len(d) <= 9:
        return f"{d[:3]}.{d[3:6]}.{d[6:]}"
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


def cpf_valido(v):
    d = digitos(v)
    if len(d) != 11 or d == d[0] * 11:
        return False

    def dv(n):
        s = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        r = (s * 10) % 11
        return 0 if r == 10 else r
    return dv(9) == int(d[9]) and dv(10) == int(d[10])


def cpf_erro(v):
    d = digitos(v)
    if not d:
        return ""
    if len(d) < 11:
        return f"CPF incompleto ({len(d)} de 11 dígitos)"
    return "" if cpf_valido(d) else "CPF inválido"


# ---------- CNPJ (numérico e alfanumérico, IN RFB 2.229/2024) ----------
def cnpj_formata(v):
    d = _alnum(v)[:14]
    if len(d) <= 2:
        return d
    if len(d) <= 5:
        return f"{d[:2]}.{d[2:]}"
    if len(d) <= 8:
        return f"{d[:2]}.{d[2:5]}.{d[5:]}"
    if len(d) <= 12:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:]}"
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def cnpj_valido(v):
    d = _alnum(v)
    if not re.fullmatch(r"[0-9A-Z]{12}\d{2}", d) or re.fullmatch(r"(\d)\1{13}", d):
        return False

    def dv(n):
        s = sum((ord(d[n - 1 - i]) - 48) * (2 + (i % 8)) for i in range(n))
        r = s % 11
        return 0 if r < 2 else 11 - r
    return dv(12) == int(d[12]) and dv(13) == int(d[13])


def doc_tipo(v):
    d = _alnum(v)
    return "cnpj" if re.search(r"[A-Z]", d) or len(d) > 11 else "cpf"


def doc_formata(v):
    return cnpj_formata(v) if doc_tipo(v) == "cnpj" else cpf_formata(v)


def doc_erro(v):
    d = _alnum(v)
    if not d:
        return ""
    if doc_tipo(d) == "cnpj":
        if len(d) < 14:
            return f"CNPJ incompleto ({len(d)} de 14 caracteres)"
        return "" if cnpj_valido(d) else "CNPJ inválido"
    if len(d) < 11:
        return f"Incompleto: CPF tem 11 dígitos e CNPJ, 14 ({len(d)} digitado{'s' if len(d) > 1 else ''})"
    return "" if cpf_valido(d) else "CPF inválido"


# ---------- telefone ----------
# Fixo:    (DD) NNNN-NNNN   → 10 dígitos, número começa com 2 a 5
# Celular: (DD) 9NNNN-NNNN  → 11 dígitos, número começa com 9
def telefone_digitos(v):
    """Aceita número colado com +55 / 55 / 0 na frente."""
    d = digitos(v)
    if len(d) > 11 and d.startswith("55"):
        d = d[2:]
    if len(d) > 10 and d.startswith("0"):
        d = d.lstrip("0")
    return d[:11]


def telefone_formata(v):
    d = telefone_digitos(v)
    if not d:
        return ""
    if len(d) <= 2:
        return f"({d}"
    ddd, n = d[:2], d[2:]
    if len(n) <= 4:
        return f"({ddd}) {n}"
    if len(d) <= 10:
        return f"({ddd}) {n[:4]}-{n[4:]}"   # fixo (ou digitando)
    return f"({ddd}) {n[:5]}-{n[5:]}"        # celular


def telefone_tipo(v):
    d = telefone_digitos(v)
    if len(d) == 11 and d[2] == "9":
        return "celular"
    if len(d) == 10 and d[2] in "2345":
        return "fixo"
    return ""


def telefone_erro(v):
    d = telefone_digitos(v)
    if not d:
        return ""
    if len(d) < 10:
        return "Telefone incompleto"
    if int(d[:2]) not in DDD:
        return f"DDD {d[:2]} não existe"
    if len(d) == 11 and d[2] != "9":
        return "Celular deve começar com 9"
    if len(d) == 10 and d[2] not in "2345":
        return "Celular precisa de 9 dígitos após o DDD" if d[2] == "9" else "Fixo deve começar com 2, 3, 4 ou 5"
    return ""


def telefone_valido(v):
    return bool(digitos(v)) and not telefone_erro(v)


# ---------- CEP ----------
def cep_formata(v):
    d = digitos(v)[:8]
    return f"{d[:5]}-{d[5:]}" if len(d) > 5 else d


def cep_erro(v):
    d = digitos(v)
    return "" if not d or len(d) == 8 else "CEP deve ter 8 dígitos"


def endereco_formata(a):
    l1 = ", ".join(x for x in [a.get("street"), a.get("number")] if x)
    local = "/".join(x for x in [a.get("city"), a.get("uf")] if x)
    partes = [x for x in [l1, a.get("complement"), ", ".join(x for x in [a.get("district"), local] if x)] if x]
    out = " - ".join(partes)
    if len(digitos(a.get("cep"))) == 8:
        out += (" - " if out else "") + "CEP " + cep_formata(a.get("cep"))
    return out
