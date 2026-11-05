"""Estoque: itens, entradas e saídas, lotes e validades (sai primeiro o que vence antes), estoque mínimo e histórico.

Mesmo formato do app em JavaScript: item {name, unit, qty, min, cost, barcode} e movimentos
{productId, kind: 'entrada'|'saida', qty, date, note, expiry, lot}. O saldo fica no próprio item (qty).
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import tempo, web
from ..dados.store import Conflito, novo_id
from ..web import exige, store

bp = Blueprint("estoque", __name__, url_prefix="/estoque")


def q2(n):
    try:
        return round(float(n or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def qtd(n):
    n = q2(n)
    return (str(int(n)) if n.is_integer() else f"{n:.2f}".rstrip("0")).replace(".", ",")


def lotes(item, movs):
    """Lotes ainda em estoque, por validade: as saídas consomem primeiro o que vence antes (PVPS)."""
    ent = sorted(({"expiry": m.get("expiry") or "", "lot": m.get("lot") or "", "qty": q2(m.get("qty")), "date": m.get("date") or "", "moveId": m["id"]}
                  for m in movs if m.get("productId") == item["id"] and m.get("kind") == "entrada"),
                 key=lambda l: (l["expiry"] or "9999", l["date"]))
    total = sum(l["qty"] for l in ent)
    usado = max(0.0, total - q2(item.get("qty")))
    for l in ent:
        u = min(l["qty"], usado)
        l["qty"] = q2(l["qty"] - u)
        usado -= u
    out = [l for l in ent if l["qty"] > 0]
    sem = q2(q2(item.get("qty")) - total)          # saldo cadastrado antes, sem lançamento de entrada
    if sem > 0:
        out.append({"expiry": "", "lot": "", "qty": sem, "date": "", "moveId": ""})
    return out


def proxima_validade(item, movs):
    return min((l["expiry"] for l in lotes(item, movs) if l["expiry"]), default="")


def dias_ate(iso):
    import datetime
    return (datetime.date.fromisoformat(iso) - datetime.date.fromisoformat(tempo.hoje())).days


@bp.app_template_filter("qtd")
def _qtd(n):
    return qtd(n)


@bp.app_template_global("validade")
def validade(iso):
    if not iso:
        return {"txt": "", "tag": ""}
    d = dias_ate(iso)
    return {"txt": tempo.data_br(iso), "tag": ("bad", "Vencido") if d < 0 else ("warn", "Vence hoje" if d == 0 else f"{d} dia(s)") if d <= 30 else ""}


@bp.route("/")
@exige("estoque")
def lista():
    st = store()
    itens, movs = st.listar("stock"), st.listar("stockMoves")
    q = (request.args.get("q") or "").strip().lower()
    lst = sorted([s for s in itens if not q or q in (s.get("name") or "").lower() or q in (s.get("barcode") or "").lower()], key=lambda s: (s.get("name") or "").lower())
    baixo = [s for s in itens if q2(s.get("qty")) <= q2(s.get("min"))]
    venc = [(s, e) for s in itens for e in [proxima_validade(s, movs)] if e and dias_ate(e) <= 30]
    return render_template("estoque.html", itens=[(s, proxima_validade(s, movs)) for s in lst], total=len(itens), baixo=baixo, venc=venc,
                           valor=sum(q2(s.get("qty")) * q2(s.get("cost")) for s in itens), q=request.args.get("q") or "")


@bp.route("/novo", methods=["GET", "POST"])
@bp.route("/<id>", methods=["GET", "POST"])
@exige("estoque")
def item(id=None):
    st = store()
    s = (st.get("stock", id) or abort(404)) if id else {"unit": "unidade", "min": 0}
    erro = ""
    if request.method == "POST":
        if web.nivel("estoque") < 2:
            abort(403)
        v = web.campos("name", "unit", "barcode", "cost", "qty", "min", "expiry")
        code = v["barcode"].strip()
        dup = code and next((x for x in st.listar("stock") if x["id"] != id and (x.get("barcode") or "").strip() == code), None)
        erro = ("Informe o nome" if not v["name"] else "Código de barras longo demais" if len(code) > 40
                else f"Este código já está no item \"{dup['name']}\"" if dup else "Custo inválido" if web.numero(v["cost"]) is None else "")
        if not erro:
            rec = {**s, "name": v["name"], "unit": v["unit"] or "unidade", "cost": web.numero(v["cost"]) or 0, "min": q2(web.numero(v["min"]) or 0), "barcode": code}
            ops = []
            if not id:
                rec.update(id=novo_id(), qty=q2(web.numero(v["qty"]) or 0))
                if rec["qty"]:
                    m = {"id": novo_id(), "productId": rec["id"], "kind": "entrada", "qty": rec["qty"], "date": tempo.hoje(), "expiry": v["expiry"], "lot": "", "note": "Estoque inicial"}
                    ops.append({"coll": "stockMoves", "op": "put", "id": m["id"], "rec": m, "v": 0})
            ops.insert(0, {"coll": "stock", "op": "put", "id": rec["id"], "rec": rec, "v": s.get("_v") or 0})
            r = st.aplicar(ops, [{"action": f"Item de estoque salvo: {rec['name']}", "user": web.nome_usuario()}])
            if r["conflicts"]:
                flash("Este item foi alterado em outro computador agora. Os dados atuais foram carregados.", "aviso")
                return redirect(request.url)
            flash("Item salvo.")
            return redirect(url_for("estoque.lista"))
        s = {**s, **v}
    movs = st.listar("stockMoves", "produto_id = ?", (id,)) if id else []
    return render_template("estoque_item.html", s=s, novo=not id, erro=erro, lotes=lotes(s, movs) if id else [])


@bp.route("/<id>/excluir", methods=["POST"])
@exige("estoque", 2)
def excluir(id):
    s = store().get("stock", id) or abort(404)
    store().excluir("stock", id, acao=f"Item de estoque excluído: {s.get('name')}", usuario=web.nome_usuario())
    flash("Item excluído.")
    return redirect(url_for("estoque.lista"))


@bp.route("/<id>/<kind>", methods=["GET", "POST"])
@exige("estoque", 2)
def movimento(id, kind):
    if kind not in ("entrada", "saida"):
        abort(404)
    st = store()
    s = st.get("stock", id) or abort(404)
    erro = ""
    v = {"qty": "1", "date": tempo.hoje(), "expiry": "", "lot": "", "note": ""}
    if request.method == "POST":
        v = web.campos("qty", "date", "expiry", "lot", "note")
        q = q2(web.numero(v["qty"]) or 0)
        erro = "Quantidade inválida" if q <= 0 else "Quantidade maior que o saldo" if kind == "saida" and q > q2(s.get("qty")) else ""
        if not erro:
            s["qty"] = q2(q2(s.get("qty")) + (q if kind == "entrada" else -q))
            m = {"id": novo_id(), "productId": s["id"], "kind": kind, "qty": q, "date": v["date"] or tempo.hoje(), "note": v["note"]}
            if kind == "entrada":
                m.update(expiry=v["expiry"], lot=v["lot"][:40])
            ops = [{"coll": "stock", "op": "put", "id": s["id"], "rec": s, "v": int(request.form.get("_v") or s["_v"])},
                   {"coll": "stockMoves", "op": "put", "id": m["id"], "rec": m, "v": 0}]
            if kind == "entrada" and request.form.get("expense"):
                f = {"id": novo_id(), "type": "despesa", "desc": f"Compra: {s['name']} ({qtd(q)} {s.get('unit', '')})", "value": round(q * q2(s.get("cost")), 2),
                     "due": m["date"], "paid": False, "paidDate": "", "category": "Materiais", "method": "Boleto", "patientId": "", "dentistId": ""}
                ops.append({"coll": "finance", "op": "put", "id": f["id"], "rec": f, "v": 0})
            r = st.aplicar(ops, [{"action": f"Estoque {kind}: {s['name']} ({qtd(q)})", "user": web.nome_usuario()}])
            if r["conflicts"]:
                # o saldo mudou em outro computador: desfaz o movimento e a despesa gravados no lote
                st.aplicar([{"coll": o["coll"], "op": "del", "id": o["id"]} for o in ops[1:]])
                flash("O saldo deste item mudou em outro computador agora. Confira e registre de novo.", "aviso")
                return redirect(url_for("estoque.movimento", id=id, kind=kind))
            flash(f"{'Entrada' if kind == 'entrada' else 'Saída'} registrada." + (f" Atenção: {s['name']} atingiu o estoque mínimo." if s["qty"] <= q2(s.get("min")) else ""),
                  "aviso" if s["qty"] <= q2(s.get("min")) else "message")
            return redirect(url_for("estoque.lista"))
    return render_template("estoque_movimento.html", s=s, kind=kind, erro=erro, v=v)


@bp.route("/historico")
@exige("estoque")
def historico():
    st = store()
    itens = st.mapa("stock")
    movs = sorted(st.listar("stockMoves"), key=lambda m: (m.get("date") or ""), reverse=True)[:500]
    return render_template("estoque_historico.html", movs=movs, itens=itens)


@bp.route("/movimento/<mid>", methods=["GET", "POST"])
@exige("estoque", 2)
def corrigir(mid):
    """Corrige ou exclui um lançamento, ajustando o saldo do item pela diferença."""
    st = store()
    m = st.get("stockMoves", mid) or abort(404)
    s = st.get("stock", m.get("productId"))
    erro = ""
    if request.method == "POST":
        excluir_ = bool(request.form.get("excluir"))
        v = web.campos("qty", "date", "expiry", "lot", "note")
        nova = 0.0 if excluir_ else q2(web.numero(v["qty"]) or 0)
        if not excluir_ and nova <= 0:
            erro = "Quantidade inválida"
        sinal = 1 if m.get("kind") == "entrada" else -1
        ops = []
        if not erro and s:
            saldo = q2(q2(s.get("qty")) + sinal * (nova - q2(m.get("qty"))))
            if saldo < 0:
                erro = f"O saldo de \"{s['name']}\" ficaria negativo ({qtd(saldo)}). Registre antes a entrada que falta."
            else:
                s["qty"] = saldo
                ops.append({"coll": "stock", "op": "put", "id": s["id"], "rec": s, "v": s["_v"]})
        if not erro:
            if excluir_:
                ops.append({"coll": "stockMoves", "op": "del", "id": mid})
            else:
                m.update(qty=nova, date=v["date"] or m.get("date"), note=v["note"])
                if m.get("kind") == "entrada":
                    m.update(expiry=v["expiry"], lot=v["lot"][:40])
                ops.append({"coll": "stockMoves", "op": "put", "id": mid, "rec": m, "v": m["_v"]})
            nome = (s or {}).get("name", "")
            r = st.aplicar(ops, [{"action": f"Lançamento de estoque {'excluído' if excluir_ else 'corrigido'}: {nome}", "user": web.nome_usuario()}])
            if r["conflicts"]:
                flash("O item mudou em outro computador agora. Confira e repita.", "aviso")
            else:
                flash("Lançamento excluído e saldo ajustado." if excluir_ else "Lançamento corrigido e saldo ajustado.")
            return redirect(url_for("estoque.historico"))
    return render_template("estoque_corrigir.html", m=m, s=s or {}, erro=erro)
