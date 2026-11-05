"""Trabalhos protéticos: fases (envio, previsão, recebimento), protéticos, situação e pagamento ao protético.

Mesmo formato do app em JavaScript: trabalho.phases = [{id, name, sent, due, received, note}], status
'andamento'|'concluido'|'cancelado', e o pagamento ao protético pode virar uma conta a pagar no financeiro (financeId).
"""
import urllib.parse

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import br, tempo, web
from ..dados.store import Conflito, novo_id
from ..web import exige, store
from .financeiro import data_fechamento, fechado, msg_fechado

bp = Blueprint("proteses", __name__, url_prefix="/proteses")

LAB_TYPES = {
    "Coroa metalocerâmica": ["Moldagem / escaneamento", "Prova da infraestrutura (coping)", "Prova da cerâmica (biscoito)", "Glaze / acabamento", "Cimentação"],
    "Coroa em zircônia": ["Moldagem / escaneamento", "Prova da infraestrutura", "Prova da cerâmica", "Glaze / acabamento", "Cimentação"],
    "Coroa em dissilicato (e.max)": ["Moldagem / escaneamento", "Prova", "Glaze / acabamento", "Cimentação"],
    "Coroa sobre implante": ["Moldagem de transferência", "Prova da infraestrutura", "Prova da cerâmica", "Instalação"],
    "Ponte fixa": ["Moldagem / escaneamento", "Prova da infraestrutura", "Prova da cerâmica", "Glaze / acabamento", "Cimentação"],
    "Faceta / lente de contato": ["Moldagem / escaneamento", "Enceramento diagnóstico (mock-up)", "Prova", "Cimentação"],
    "Inlay / onlay": ["Moldagem / escaneamento", "Prova", "Cimentação"],
    "Núcleo metálico fundido": ["Moldagem do conduto", "Prova / cimentação"],
    "Provisório": ["Moldagem", "Instalação"],
    "Prótese total (dentadura)": ["Moldagem anatômica", "Moldeira individual / moldagem funcional", "Plano de cera / registro", "Prova dos dentes", "Acrilização", "Instalação"],
    "Prótese parcial removível (PPR)": ["Moldagem anatômica", "Moldagem funcional", "Prova da armação metálica", "Plano de cera / registro", "Prova dos dentes", "Acrilização", "Instalação"],
    "Protocolo sobre implantes": ["Moldagem de transferência", "Prova da barra / infraestrutura", "Plano de cera / registro", "Prova dos dentes", "Acrilização / acabamento", "Instalação"],
    "Placa miorrelaxante": ["Moldagem", "Instalação / ajuste"],
    "Moldeira de clareamento": ["Moldagem", "Entrega"],
    "Aparelho ortodôntico removível": ["Moldagem", "Instalação"],
    "Outro": ["Moldagem / escaneamento", "Prova", "Instalação"],
}
FILTROS = [("andamento", "Em andamento"), ("lab", "No laboratório"), ("atrasados", "Atrasados"), ("clinica", "Na clínica / a enviar"),
           ("concluidos", "Concluídos"), ("cancelados", "Cancelados"), ("todos", "Todos")]


def fases_padrao(tipo):
    return [{"id": novo_id(), "name": n, "sent": "", "due": "", "received": "", "note": ""} for n in LAB_TYPES.get(tipo) or LAB_TYPES["Outro"]]


def situacao(w, hoje=None):
    """Onde o trabalho está: {key: lab|clinic|tosend|done|cancel, label, idx, phase, prev, late}"""
    hoje = hoje or tempo.hoje()
    ph = w.get("phases") or []
    if w.get("status") == "cancelado":
        return {"key": "cancel", "label": "Cancelado", "idx": -1}
    idx = next((i for i, p in enumerate(ph) if not p.get("received")), -1)
    if w.get("status") == "concluido" or (ph and idx < 0):
        return {"key": "done", "label": "Concluído", "idx": -1}
    if idx < 0:
        return {"key": "tosend", "label": "A enviar", "idx": -1}
    p = ph[idx]
    if p.get("sent"):
        late = bool(p.get("due")) and p["due"] < hoje
        return {"key": "lab", "late": late, "label": "Atrasado" if late else "No laboratório", "idx": idx, "phase": p}
    if idx > 0:
        return {"key": "clinic", "label": "Na clínica", "idx": idx, "phase": p, "prev": ph[idx - 1]}
    return {"key": "tosend", "label": "A enviar", "idx": idx, "phase": p}


def _rank(w):
    s = situacao(w)
    return {"lab": 0 if s.get("late") else 1, "clinic": 2, "tosend": 3, "done": 4}.get(s["key"], 5)


def _fin(w, fin):
    return fin.get(w.get("financeId")) if w.get("financeId") else None


def pago(w, fin):
    f = _fin(w, fin)
    return bool(f["paid"]) if f else bool(w.get("paid"))


def data_pago(w, fin):
    f = _fin(w, fin)
    return (f.get("paidDate") or "") if f else (w.get("paidDate") or "")


@bp.route("/")
@exige("proteses")
def lista():
    st = store()
    todos = st.listar("labWorks")
    fin = {f["id"]: f for f in st.listar("finance", "id IN (SELECT financeiro_id FROM trabalhos_proteticos WHERE excluido = 0)")} if todos else {}
    pac, pros = st.mapa("patients"), st.mapa("prosthetists")
    f, fp, fpay, q = request.args.get("filtro") or "andamento", request.args.get("protetico") or "", request.args.get("pagamento") or "", (request.args.get("q") or "").strip().lower()
    abertos = [w for w in todos if situacao(w)["key"] not in ("done", "cancel")]
    no_lab = [w for w in abertos if situacao(w)["key"] == "lab"]
    a_pagar = [w for w in todos if w.get("status") != "cancelado" and w.get("value") and not pago(w, fin)]

    def passa(w):
        s = situacao(w)
        k = s["key"]
        if f == "andamento" and k in ("done", "cancel"): return False
        if f == "lab" and k != "lab": return False
        if f == "atrasados" and not (k == "lab" and s.get("late")): return False
        if f == "clinica" and k not in ("clinic", "tosend"): return False
        if f == "concluidos" and k != "done": return False
        if f == "cancelados" and k != "cancel": return False
        if fp and w.get("prosthetistId") != fp: return False
        if fpay == "apagar" and (not w.get("value") or pago(w, fin) or w.get("status") == "cancelado"): return False
        if fpay == "pago" and not pago(w, fin): return False
        if q:
            p = pac.get(w.get("patientId")) or {}
            pr = pros.get(w.get("prosthetistId")) or {}
            if not any(q in (t or "").lower() for t in [p.get("name"), p.get("socialName"), w.get("type"), w.get("teeth"), pr.get("name"), pr.get("lab")]):
                return False
        return True
    lista = sorted([w for w in todos if passa(w)], key=lambda w: (_rank(w), (situacao(w).get("phase") or {}).get("due") or "9", ""))
    linhas = [{"w": w, "s": situacao(w), "pac": web.nome_exibicao(pac.get(w.get("patientId"))), "pros": pros.get(w.get("prosthetistId")) or {},
               "pago": pago(w, fin), "data_pago": data_pago(w, fin), "n": len(w.get("phases") or [])} for w in lista]
    return render_template("proteses.html", linhas=linhas, total=len(todos), n_lab=len(no_lab), n_atraso=len([w for w in no_lab if situacao(w).get("late")]),
                           n_clinica=len(abertos) - len(no_lab), a_pagar=sum(float(w.get("value") or 0) for w in a_pagar), filtros=FILTROS,
                           f=f, fp=fp, fpay=fpay, q=request.args.get("q") or "", proteticos=sorted(pros.values(), key=lambda x: x.get("name", "").lower()))


def _ler_fases():
    ids, nomes = request.form.getlist("ph_id"), request.form.getlist("ph_name")
    sent, due, rec, note = (request.form.getlist(k) for k in ("ph_sent", "ph_due", "ph_received", "ph_note"))
    fases = []
    for i, nome in enumerate(nomes):
        fases.append({"id": (ids[i] if i < len(ids) and ids[i] else novo_id()), "name": nome.strip(), "sent": sent[i] if i < len(sent) else "",
                      "due": due[i] if i < len(due) else "", "received": rec[i] if i < len(rec) else "", "note": (note[i] if i < len(note) else "").strip()})
    return fases


def _validar_fases(fases):
    for i, p in enumerate(fases):
        if not p["name"]:
            return f"Dê um nome para a fase {i + 1}"
        if p["received"] and not p["sent"]:
            return f"Fase \"{p['name']}\": informe também a data de envio"
        if p["sent"] and p["received"] and p["received"] < p["sent"]:
            return f"Fase \"{p['name']}\": recebimento antes do envio"
        if p["sent"] and p["due"] and p["due"] < p["sent"]:
            return f"Fase \"{p['name']}\": previsão antes do envio"
    return ""


def _form_ctx(w, novo, erro=""):
    st = store()
    fin = st.get("finance", w.get("financeId")) if w.get("financeId") else None
    tipos = list(LAB_TYPES) + ([w["type"]] if w.get("type") and w["type"] not in LAB_TYPES else [])
    return dict(w=w, novo=novo, erro=erro, fin=fin, pacientes=web.opcoes_pacientes(), dentistas=st.listar("dentists"),
                proteticos=sorted(st.listar("prosthetists"), key=lambda x: x.get("name", "").lower()), tipos=tipos, lab_types=LAB_TYPES,
                s=situacao(w) if not novo else None, pago=bool(fin["paid"]) if fin else bool(w.get("paid")),
                data_pago=(fin.get("paidDate") if fin else w.get("paidDate")) or "", vencimento=(fin.get("due") if fin else w.get("payDue")) or "",
                lancar=bool(fin) or (novo and g.clinica.get("labToFinance") is not False))


@bp.route("/novo", methods=["GET", "POST"])
@bp.route("/<id>", methods=["GET", "POST"])
@exige("proteses")
def trabalho(id=None):
    st = store()
    novo = not id
    w = (st.get("labWorks", id) or abort(404)) if id else {
        "patientId": request.args.get("paciente") or "", "dentistId": g.usuario.get("dentistId") or "", "type": "Coroa metalocerâmica", "teeth": "", "shade": "",
        "value": 0, "paid": False, "paidDate": "", "payDue": "", "status": "andamento", "notes": "", "phases": fases_padrao("Coroa metalocerâmica")}
    if novo and len(st.listar("prosthetists")) == 1:
        w["prosthetistId"] = st.listar("prosthetists")[0]["id"]
    if request.method == "GET":
        return render_template("protese_form.html", **_form_ctx(w, novo))
    if web.nivel("proteses") < 2:
        abort(403)
    v = web.campos("patientId", "dentistId", "prosthetistId", "type", "teeth", "shade", "value", "status", "paidDate", "payDue", "notes")
    pago_ = bool(request.form.get("paid"))
    lancar = bool(request.form.get("toFin"))
    fases = _ler_fases()
    rec = {**w, "patientId": v["patientId"], "dentistId": v["dentistId"], "prosthetistId": v["prosthetistId"], "type": v["type"], "teeth": v["teeth"],
           "shade": v["shade"], "value": web.numero(v["value"]) or 0, "status": v["status"] or "andamento", "notes": request.form.get("notes") or "", "phases": fases}
    erro = ("Selecione o paciente" if not v["patientId"] else "Selecione o protético (cadastre em \"Protéticos\")" if not v["prosthetistId"]
            else "Valor inválido" if web.numero(v["value"]) is None else _validar_fases(fases))
    lock = data_fechamento()
    data_pg = (v["paidDate"] or tempo.hoje()) if pago_ else ""
    fin = st.get("finance", w.get("financeId")) if w.get("financeId") else None
    manter = lancar and rec["value"] > 0 and rec["status"] != "cancelado"
    if not erro and lock:
        if fin and fechado(fin):
            if (not manter or rec["value"] != fin["value"] or not pago_ or data_pg != fin.get("paidDate")):
                erro = f"O pagamento deste trabalho está num período contábil fechado (até {tempo.data_br(lock)}): valor, situação e pagamento não podem mudar."
        elif pago_ and manter and data_pg <= lock:
            erro = msg_fechado(lock)
    if erro:
        return render_template("protese_form.html", **_form_ctx(rec, novo, erro))
    rec.update(paid=pago_, paidDate=data_pg, payDue=v["payDue"])
    if novo:
        rec.update(id=novo_id(), createdAt=tempo.hoje())
    else:
        rec["_v"] = int(request.form.get("_v") or w["_v"])
    pac = st.get("patients", rec["patientId"]) or {}
    pros = st.get("prosthetists", rec["prosthetistId"]) or {}
    ops = []
    if manter:
        fdata = {"type": "despesa", "desc": f"Prótese: {rec['type']}{' (' + rec['teeth'] + ')' if rec['teeth'] else ''} — {web.nome_exibicao(pac)} · {pros.get('name', '')}",
                 "value": rec["value"], "due": v["payDue"] or (fin or {}).get("due") or tempo.soma_dias(tempo.hoje(), 30), "paid": pago_, "paidDate": data_pg,
                 "category": "Laboratório", "dentistId": rec["dentistId"]}
        if fin:
            if not fechado(fin):
                ops.append({"coll": "finance", "op": "put", "id": fin["id"], "rec": {**fin, **fdata}, "v": fin["_v"]})
        else:
            f = {"id": novo_id(), "method": "Transferência", "patientId": "", **fdata}
            ops.append({"coll": "finance", "op": "put", "id": f["id"], "rec": f, "v": 0})
            rec["financeId"] = f["id"]
    elif fin:
        ops.append({"coll": "finance", "op": "del", "id": fin["id"]})
        rec["financeId"] = ""
    ops.append({"coll": "labWorks", "op": "put", "id": rec["id"], "rec": rec, "v": rec.get("_v") or 0})
    r = st.aplicar(ops, [{"action": f"Trabalho protético {'cadastrado' if novo else 'atualizado'}: {rec['type']} — {web.nome_exibicao(pac)}", "user": web.nome_usuario()}])
    if r["conflicts"]:
        flash("Este trabalho (ou a conta dele no financeiro) foi alterado em outro computador agora. Os dados atuais foram carregados.", "aviso")
        return redirect(url_for("proteses.trabalho", id=rec["id"]) if not novo else url_for("proteses.lista"))
    flash("Trabalho salvo.")
    return redirect(request.form.get("voltar") or url_for("proteses.lista"))


@bp.route("/<id>/excluir", methods=["POST"])
@exige("proteses", 2)
def excluir(id):
    st = store()
    w = st.get("labWorks", id) or abort(404)
    fin = st.get("finance", w.get("financeId")) if w.get("financeId") else None
    if fin and fechado(fin):
        flash(f"O pagamento deste trabalho está num período contábil fechado (até {tempo.data_br(data_fechamento())}) e não pode ser excluído.", "erro")
        return redirect(url_for("proteses.trabalho", id=id))
    ops = ([{"coll": "finance", "op": "del", "id": fin["id"]}] if fin else []) + [{"coll": "labWorks", "op": "del", "id": id}]
    pac = st.get("patients", w.get("patientId")) or {}
    st.aplicar(ops, [{"action": f"Trabalho protético excluído: {w.get('type')} — {web.nome_exibicao(pac)}", "user": web.nome_usuario()}])
    flash("Trabalho excluído." + (" A conta a pagar dele também saiu do financeiro." if fin else ""))
    return redirect(url_for("proteses.lista"))


@bp.route("/<id>/movimento", methods=["GET", "POST"])
@exige("proteses", 2)
def movimento(id):
    """Atalho da lista: enviar a fase atual ao laboratório ou receber de volta."""
    st = store()
    w = st.get("labWorks", id) or abort(404)
    s = situacao(w)
    p = s.get("phase")
    if not p:
        return redirect(url_for("proteses.lista"))
    tipo = "receive" if s["key"] == "lab" else "send"
    pros = st.get("prosthetists", w.get("prosthetistId")) or {}
    pac = st.get("patients", w.get("patientId")) or {}
    erro = ""
    if request.method == "POST":
        if tipo == "send":
            enviado, prev = request.form.get("sent") or "", request.form.get("due") or ""
            erro = "Informe a data de envio" if not enviado else "A previsão não pode ser antes do envio" if prev and prev < enviado else ""
            if not erro:
                p.update(sent=enviado, due=prev, note=(request.form.get("note") or "").strip())
        else:
            receb = request.form.get("received") or ""
            erro = "Informe a data de recebimento" if not receb else "O recebimento não pode ser antes do envio" if p.get("sent") and receb < p["sent"] else ""
            if not erro:
                p.update(received=receb, note=(request.form.get("note") or "").strip())
        if not erro:
            w["_v"] = int(request.form.get("_v") or w["_v"])
            try:
                st.salvar("labWorks", w, acao=f"Prótese {'enviada' if tipo == 'send' else 'recebida'}: {p['name']} — {web.nome_exibicao(pac)}", usuario=web.nome_usuario())
            except Conflito:
                flash("Este trabalho foi alterado em outro computador agora. Confira e repita.", "aviso")
                return redirect(url_for("proteses.lista"))
            if tipo == "receive" and situacao(w)["key"] == "done":
                flash("Última fase recebida: trabalho concluído.")
            else:
                flash("Envio registrado." if tipo == "send" else "Recebimento registrado.")
            if tipo == "send" and request.form.get("whatsapp") and br.digitos(pros.get("phone")):
                n = br.digitos(pros["phone"])
                n = "55" + n if len(n) <= 11 else n
                txt = (f"Olá {pros.get('name', '').split(' ')[0]}! Enviamos hoje o trabalho de {web.nome_exibicao(pac)}: {w.get('type')}"
                       f"{', dentes ' + w['teeth'] if w.get('teeth') else ''}{', cor ' + w['shade'] if w.get('shade') else ''}. Fase: {p['name']}."
                       f"{' Previsão de retorno: ' + tempo.data_br(p['due']) + '.' if p.get('due') else ''}{' Obs.: ' + p['note'] if p.get('note') else ''}")
                return redirect(f"https://wa.me/{n}?text={urllib.parse.quote(txt)}")
            return redirect(url_for("proteses.lista"))
    prev_padrao = p.get("due") or tempo.soma_dias(tempo.hoje(), int(pros.get("days") or 7))
    return render_template("protese_movimento.html", w=w, p=p, tipo=tipo, pros=pros, pac=web.nome_exibicao(pac), erro=erro, prev_padrao=prev_padrao)


@bp.route("/<id>/ordem")
@exige("proteses")
def ordem(id):
    st = store()
    w = st.get("labWorks", id) or abort(404)
    return render_template("imp_protese.html", w=w, s=situacao(w), pac=st.get("patients", w.get("patientId")) or {},
                           den=st.get("dentists", w.get("dentistId")) or {}, pros=st.get("prosthetists", w.get("prosthetistId")) or {})


# ---------- protéticos ----------
@bp.route("/proteticos")
@exige("proteses")
def proteticos():
    st = store()
    trabalhos = st.listar("labWorks")
    fin = st.mapa("finance") if trabalhos else {}
    linhas = []
    for x in sorted(st.listar("prosthetists"), key=lambda x: x.get("name", "").lower()):
        ws = [w for w in trabalhos if w.get("prosthetistId") == x["id"]]
        linhas.append({"x": x, "abertos": len([w for w in ws if situacao(w)["key"] not in ("done", "cancel")]), "total": len(ws),
                       "a_pagar": sum(float(w.get("value") or 0) for w in ws if w.get("status") != "cancelado" and w.get("value") and not pago(w, fin))})
    return render_template("proteticos.html", linhas=linhas)


@bp.route("/proteticos/novo", methods=["GET", "POST"])
@bp.route("/proteticos/<id>", methods=["GET", "POST"])
@exige("proteses")
def protetico(id=None):
    st = store()
    x = (st.get("prosthetists", id) or abort(404)) if id else {"days": 7}
    erro = ""
    if request.method == "POST":
        if web.nivel("proteses") < 2:
            abort(403)
        if request.form.get("excluir") and id:
            n = len(st.listar("labWorks", "protetico_id = ?", (id,)))
            if n:
                flash(f"Este protético tem {n} trabalho(s) cadastrado(s) e não pode ser excluído.", "erro")
                return redirect(url_for("proteses.protetico", id=id))
            st.excluir("prosthetists", id, acao=f"Protético excluído: {x.get('name')}", usuario=web.nome_usuario())
            flash("Protético excluído.")
            return redirect(url_for("proteses.proteticos"))
        v = web.campos("name", "lab", "phone", "email", "days", "notes")
        erro = "Informe o nome" if not v["name"] else br.telefone_erro(v["phone"])
        if not erro:
            rec = {**x, "name": v["name"], "lab": v["lab"], "phone": br.telefone_formata(v["phone"]) if v["phone"] else "", "email": v["email"],
                   "days": max(1, min(90, int(v["days"] or 7))), "notes": request.form.get("notes") or ""}
            if id:
                rec["_v"] = int(request.form.get("_v") or x["_v"])
            try:
                st.salvar("prosthetists", rec, acao=f"Protético {'atualizado' if id else 'cadastrado'}: {rec['name']}", usuario=web.nome_usuario())
            except Conflito:
                flash("Este cadastro foi alterado em outro computador. Os dados atuais foram carregados.", "aviso")
                return redirect(request.url)
            flash("Protético salvo.")
            return redirect(request.form.get("voltar") or url_for("proteses.proteticos"))
        x = {**x, **v}
    return render_template("protetico_form.html", x=x, novo=not id, erro=erro)
