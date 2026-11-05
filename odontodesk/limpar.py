"""Limpar dados de exemplo e de teste, mantendo os dados reais (mesma regra do src/limpar.js do app em JavaScript).

Reconhece o que veio de "Começar com dados de exemplo" (pacientes, lançamentos, estoque, protético, dentistas) e deixa o
administrador marcar pacientes e lançamentos de teste. Excluir um paciente exclui os registros dele e os arquivos da galeria.
"""
import re
import unicodedata

LINKED = ["appointments", "treatments", "finance", "evolutions", "prescriptions", "labWorks"]
SEED_PAT = {"carla mendes": "11999990001", "diego ferreira": "11999990002", "eduarda rocha": "11999990003"}
SEED_FIN = {"aluguel do consultorio": 3500, "compra de resina composta": 640}
SEED_STOCK = ["luvas de procedimento (cx 100)", "resina composta a2", "anestesico lidocaina 2%", "mascaras descartaveis (cx 50)"]
SEED_DENT = {"dra. ana souza": "CRO-SP 00000", "dr. bruno lima": "CRO-SP 00001"}
LABEL = {"appointments": "agendamento", "treatments": "plano", "finance": "lançamento", "evolutions": "evolução", "prescriptions": "receita",
         "labWorks": "prótese", "stock": "item de estoque", "stockMoves": "movimento de estoque", "prosthetists": "protético", "dentists": "dentista"}


def norm(s):
    s = unicodedata.normalize("NFD", "" if s is None else str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", s).strip()


def _dig(s):
    return re.sub(r"\D", "", "" if s is None else str(s))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def eh_paciente_exemplo(p):
    n = norm(p.get("name"))
    return n in SEED_PAT and _dig(p.get("phone")) == SEED_PAT[n]


def eh_lancamento_exemplo(f):
    n = norm(f.get("desc"))
    return n in SEED_FIN and _num(f.get("value")) == SEED_FIN[n]


def _bloqueio(a):
    return a.get("type") == "bloqueio" and norm(a.get("notes")) == "almoco" and a.get("time") == "12:00" and not a.get("patientId")


def _dentista(d):
    n = norm(d.get("name"))
    return n in SEED_DENT and str(d.get("cro") or "") == SEED_DENT[n]


def _data(d):
    return "/".join(reversed(str(d).split("-"))) if d else ""


def _dinheiro(v):
    s = f"{float(v or 0):,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def plano(db):
    cont = {}
    for c in LINKED:
        for r in db.get(c) or []:
            if r.get("patientId"):
                k = cont.setdefault(r["patientId"], {})
                k[c] = k.get(c, 0) + 1
    pacientes = [{"id": p["id"], "name": p.get("name", ""), "phone": p.get("phone") or "", "example": eh_paciente_exemplo(p),
                  "detail": cont.get(p["id"], {}), "sel": eh_paciente_exemplo(p)} for p in db.get("patients") or []]
    pacientes.sort(key=lambda x: (not x["example"], norm(x["name"])))
    outros = []
    for f in db.get("finance") or []:
        if not f.get("patientId"):
            ex = eh_lancamento_exemplo(f)
            outros.append({"coll": "finance", "id": f["id"], "example": ex, "sel": ex, "date": f.get("due") or "",
                           "label": f"{'Despesa' if f.get('type') == 'despesa' else 'Receita'}: {f.get('desc') or '—'} · {_dinheiro(f.get('value'))}"
                                    f" · venc. {_data(f.get('due'))}{' · pago' if f.get('paid') else ''}"})
    for a in db.get("appointments") or []:
        if _bloqueio(a):
            outros.append({"coll": "appointments", "id": a["id"], "label": f'Agenda: bloqueio "Almoço" {_data(a.get("date"))} 12:00', "example": True, "sel": True, "date": a.get("date") or ""})
    for s in db.get("stock") or []:
        if norm(s.get("name")) in SEED_STOCK:
            outros.append({"coll": "stock", "id": s["id"], "label": f"Estoque: {s.get('name')}", "example": True, "sel": True, "date": ""})
    for x in db.get("prosthetists") or []:
        if norm(x.get("lab")) == "laboratorio exemplo":
            outros.append({"coll": "prosthetists", "id": x["id"], "label": f"Protético: {x.get('name')} ({x.get('lab')})", "example": True, "sel": True, "date": ""})
    for d in db.get("dentists") or []:
        if _dentista(d):
            outros.append({"coll": "dentists", "id": d["id"], "label": f"Dentista: {d.get('name')} ({d.get('cro')})", "example": True, "sel": True, "date": ""})
    outros.sort(key=lambda o: (not o["example"], o["coll"], o["date"]))
    return {"patients": pacientes, "others": outros}


def operacoes(db, pacientes=(), outros=()):
    """O que excluir: ({coll: [ids]}, [arquivos de anexo], [avisos do que ficou]). Dentista/protético só sai se
    nada que fica estiver ligado a ele."""
    pids = set(pacientes)
    dele, arquivos, ficou = {}, [], []
    removidos = set()

    def tira(c, pred):
        for r in db.get(c) or []:
            if (c, r["id"]) not in removidos and pred(r):
                removidos.add((c, r["id"]))
                dele.setdefault(c, []).append(r["id"])

    for p in db.get("patients") or []:
        if p["id"] in pids:
            arquivos += [g["file"] for g in p.get("gallery") or [] if g.get("file")]
            arquivos += [d["signed"]["file"] for d in p.get("docs") or [] if (d.get("signed") or {}).get("file")]
    tira("patients", lambda p: p["id"] in pids)
    for c in LINKED:
        tira(c, lambda r: r.get("patientId") in pids)
    sel = {}
    for o in outros:
        coll, id = o if isinstance(o, tuple) else (o["coll"], o["id"])
        sel.setdefault(coll, set()).add(id)
    for c in ("finance", "appointments"):
        if c in sel:
            tira(c, lambda r: r["id"] in sel[c])
    if "stock" in sel:
        tira("stockMoves", lambda m: m.get("productId") in sel["stock"])
        tira("stock", lambda s: s["id"] in sel["stock"])
    fica = lambda c: [r for r in db.get(c) or [] if (c, r["id"]) not in removidos]
    for id in sel.get("prosthetists", ()):
        if any(w.get("prosthetistId") == id for w in fica("labWorks")):
            ficou.append("protético com trabalhos de pacientes que ficaram")
            continue
        tira("prosthetists", lambda x: x["id"] == id)
    for id in sel.get("dentists", ()):
        usado = any(r.get("dentistId") == id for c in LINKED for r in fica(c)) or any(u.get("dentistId") == id for u in db.get("users") or [])
        if usado:
            d = next((x for x in db.get("dentists") or [] if x["id"] == id), None)
            ficou.append(f"{d.get('name') if d else 'dentista'} (tem registros que ficaram)")
            continue
        tira("dentists", lambda d: d["id"] == id)
    return dele, arquivos, ficou
