"""Regras das receitas (mesmas do app em JavaScript, src/medicamentos.js e src/app.js).

Tipos, separados automaticamente conforme os medicamentos:
  - simples: 1 via;
  - antimicrobiano (RDC 471/2021): 2 vias (1ª paciente, 2ª retida na farmácia), validade 10 dias; exige idade e sexo;
  - controle especial (Portaria 344/98, modelo da RDC 1.000/2025): 2 vias (1ª farmácia, 2ª paciente), até 3 substâncias
    por receita, validade 30 dias; exige CPF (ou "NÃO POSSUI") e endereço do paciente;
  - notificação A/B: só no talonário da Vigilância Sanitária — não é impressa pelo sistema.
"""
import re

TIPOS = {"simples": "Simples", "antimicrobiano": "Antimicrobiano", "controle": "Controle especial", "notificacao": "Notificação"}
USOS = {"oral": "Uso oral", "bucal": "Uso bucal (oral tópico)", "topico": "Uso tópico", "sublingual": "Uso sublingual", "outro": "Outro uso"}
RX_KIND = {"simples": "Receita simples · 1 via", "antimicrobiano": "Receita de antimicrobiano · 2 vias (RDC 471/2021)", "controle": "Receita de Controle Especial · 2 vias"}

UN = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze", "treze", "quatorze", "quinze",
      "dezesseis", "dezessete", "dezoito", "dezenove"]
DZ = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
CT = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos", "oitocentos", "novecentos"]
FEM = re.compile(r"^(c[aá]psulas?|dr[aá]geas?|ampolas?|bisnagas?|gotas?|unidades?|pastilhas?|seringas?|caixas?|cartelas?)\b", re.I)


def extenso(n, fem=False):
    if n == 100:
        return "cem"
    f = (lambda w: re.sub(r"entos$", "entas", re.sub(r"^dois$", "duas", re.sub(r"^um$", "uma", w)))) if fem else (lambda w: w)
    if n < 20:
        return f(UN[n])
    if n < 100:
        return DZ[n // 10] + (" e " + f(UN[n % 10]) if n % 10 else "")
    if n < 1000:
        return f(CT[n // 100]) + (" e " + extenso(n % 100, fem) if n % 100 else "")
    return str(n)


def qtd_extenso(q):
    """'21 cápsulas' → '21 (vinte e uma) cápsulas' (ajuda contra adulteração)."""
    m = re.match(r"^\s*(\d{1,3})\s+(.+)$", str(q or ""))
    if not m or not int(m.group(1)):
        return q
    n = int(m.group(1))
    return f"{n} ({extenso(n, bool(FEM.match(m.group(2))))}) {m.group(2)}"


def item_nome(i):
    return f"{i.get('g', '')}{' (' + i['brand'] + ')' if i.get('brandPrint') and i.get('brand') else ''}{' ' + i['a'] if i.get('a') else ''}"


def documentos(itens):
    """Separa os itens nas receitas exigidas: controle especial (até 3 por receita), antimicrobiano (com os simples
    na mesma receita) ou simples."""
    por = lambda t: [i for i in itens if i.get("tipo") == t]
    docs, ce, am, si = [], por("controle"), por("antimicrobiano"), por("simples")
    for k in range(0, len(ce), 3):
        docs.append({"kind": "controle", "items": ce[k:k + 3]})
    if am:
        docs.append({"kind": "antimicrobiano", "items": am + si})
    elif si:
        docs.append({"kind": "simples", "items": si})
    return docs


def grupos_uso(itens):
    """[(uso, [(número, item), ...]), ...] na ordem dos itens (o título do uso muda quando o uso muda)."""
    out, n = [], 0
    for i in itens:
        n += 1
        if not out or out[-1][0] != i.get("uso"):
            out.append((i.get("uso"), []))
        out[-1][1].append((n, i))
    return out
