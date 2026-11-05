"""Galeria do paciente: fotos, radiografias, PDFs e escaneamentos 3D (.stl), com visualizador 3D no navegador.

Mesmo formato do app em JavaScript: paciente.gallery = [{id, kind: 'img'|'stl'|'arquivo', name, file, thumb, size, date,
triangles, dims, ext, mime, pending}]. Os arquivos ficam nos anexos do banco (dados/anexos.py).
"""
import base64
import io
import json
import mimetypes
import re
import urllib.parse

from flask import Blueprint, Response, abort, flash, jsonify, redirect, render_template, request, url_for

from .. import tempo, web
from ..dados import malha
from ..dados.anexos import AnexoErro
from ..dados.store import Conflito, novo_id
from ..web import exige, store

bp = Blueprint("galeria", __name__)
MAX_ARQUIVO = 300 * 1024 * 1024
FILTROS = [("todos", "Todos"), ("img", "Imagens"), ("3d", "Modelos 3D / STL"), ("arq", "PDF e documentos")]


def anexos():
    from flask import current_app
    return current_app.config["ANEXOS"]


def _tipo(g):
    return "3d" if g.get("kind") == "stl" else "arq" if g.get("kind") == "arquivo" else "img"


AVISO_BAIXAR = '<text x="90" y="170" font-family="Arial" font-size="14" text-anchor="middle" fill="#92400e">a baixar</text>'


def icone(ext, pendente=False):
    ext = (ext or "arq").upper()[:4]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="180" height="180" viewBox="0 0 180 180"><rect width="180" height="180" fill="{"#f3f1ea" if pendente else "#eef5f4"}"/>'
           f'<path d="M58 30h46l24 24v96H58z" fill="#fff" stroke="#94a3b8" stroke-width="3"/><path d="M104 30v24h24" fill="none" stroke="#94a3b8" stroke-width="3"/>'
           f'<text x="93" y="118" font-family="Arial" font-size="22" font-weight="700" text-anchor="middle" fill="#0e8f86">{ext}</text>'
           + (AVISO_BAIXAR if pendente else "") + "</svg>")
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)


def miniatura(g):
    if g.get("pending"):
        return icone(g.get("ext") or ("img" if g.get("kind") == "img" else ""), True)
    return g.get("thumb") or g.get("data") or (icone(g.get("ext")) if g.get("kind") == "arquivo" else icone("STL" if g.get("kind") == "stl" else "IMG"))


def _imagem(dados, maximo, qualidade=85):
    from PIL import Image, ImageOps
    im = Image.open(io.BytesIO(dados))
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "L"):
        fundo = Image.new("RGB", im.size, (255, 255, 255))
        fundo.paste(im, mask=im.convert("RGBA").split()[-1])
        im = fundo
    im.thumbnail((maximo, maximo))
    out = io.BytesIO()
    im.convert("RGB").save(out, "JPEG", quality=qualidade, optimize=True)
    return out.getvalue()


def item_imagem(nome, dados, maximo=1600):
    """Foto: arquivo em tamanho de tela vai para os anexos; o cadastro guarda só a miniatura (igual ao app)."""
    gid = novo_id()
    cheio = _imagem(dados, maximo)
    anexos().gravar(f"{gid}.jpg", cheio)
    mini = "data:image/jpeg;base64," + base64.b64encode(_imagem(dados, 360)).decode()
    return {"id": gid, "kind": "img", "name": nome, "file": f"{gid}.jpg", "thumb": mini, "size": len(cheio), "date": tempo.hoje()}


def _paciente(pid):
    return store().get("patients", pid) or abort(404)


def _salvar_paciente(p, acao):
    try:
        store().salvar("patients", p, acao=acao, usuario=web.nome_usuario())
        return True
    except Conflito:
        flash("O cadastro do paciente foi alterado em outro computador agora. Confira e repita.", "aviso")
        return False


@bp.route("/pacientes/<pid>/galeria")
@exige("prontuario")
def galeria(pid):
    p = _paciente(pid)
    gal = p.get("gallery") or []
    f = request.args.get("filtro") or "todos"
    itens = [g for g in gal if f == "todos" or _tipo(g) == f]
    cont = {k: len([g for g in gal if k == "todos" or _tipo(g) == k]) for k, _ in FILTROS}
    return render_template("pront_galeria.html", p=p, aba="galeria", itens=itens, filtros=FILTROS, f=f, cont=cont, miniatura=miniatura,
                           n3d=cont["3d"], pendentes=len([g for g in gal if g.get("pending")]))


@bp.route("/pacientes/<pid>/galeria/enviar", methods=["POST"])
@exige("prontuario", 2)
def enviar(pid):
    p = _paciente(pid)
    novos, erros = [], []
    for arq in request.files.getlist("arquivos"):
        nome = (arq.filename or "arquivo").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        dados = arq.read()
        if not dados:
            continue
        if len(dados) > MAX_ARQUIVO:
            erros.append(f"{nome}: maior que {MAX_ARQUIVO // 1048576} MB")
            continue
        ext = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
        try:
            if ext == "stl":
                gid = novo_id()
                if not malha.eh_stl_binario(dados):
                    erros.append(f"{nome}: só STL binário é aceito aqui (o app do computador também abre STL em texto)")
                    continue
                r = anexos().gravar(f"{gid}.stl", dados)
                tri, dims = malha.medidas(r["canonical"] or dados)
                novos.append({"id": gid, "kind": "stl", "name": nome, "file": f"{gid}.stl", "size": len(dados), "date": tempo.hoje(),
                              "triangles": tri, "dims": dims, "thumb": ""})
            elif (arq.mimetype or "").startswith("image/") or ext in ("jpg", "jpeg", "png", "webp", "bmp", "gif", "tif", "tiff"):
                novos.append(item_imagem(nome, dados))
            else:
                gid = novo_id()
                ext = re.sub(r"[^a-z0-9]", "", ext)[:5] or "bin"
                anexos().gravar(f"{gid}.{ext}", dados)
                novos.append({"id": gid, "kind": "arquivo", "name": nome.rsplit(".", 1)[0] if "." in nome else nome, "ext": ext,
                              "mime": arq.mimetype or mimetypes.guess_type(nome)[0] or "application/octet-stream",
                              "file": f"{gid}.{ext}", "size": len(dados), "date": tempo.hoje()})
        except Exception as e:  # imagem corrompida, formato estranho
            erros.append(f"{nome}: não foi possível ler ({e})")
    if novos:
        p = _paciente(pid)  # relê: o upload pode ter demorado
        p["gallery"] = (p.get("gallery") or []) + novos
        if _salvar_paciente(p, f"{len(novos)} arquivo(s) adicionado(s) à galeria: {p['name']}"):
            flash(f"{len(novos)} arquivo(s) adicionado(s).")
        else:
            for g in novos:
                anexos().excluir(g["file"])
    for e in erros:
        flash(e, "erro")
    return redirect(url_for("galeria.galeria", pid=pid))


def _item(pid, gid):
    p = _paciente(pid)
    g = next((x for x in p.get("gallery") or [] if x.get("id") == gid), None) or abort(404)
    return p, g


@bp.route("/pacientes/<pid>/galeria/<gid>/arquivo")
@exige("prontuario")
def arquivo(pid, gid):
    """O arquivo em si (foto, PDF, STL). Só para quem pode ver o prontuário deste paciente."""
    p, g = _item(pid, gid)
    if g.get("pending") or not g.get("file"):
        abort(404)
    try:
        dados = anexos().ler(g["file"])
    except AnexoErro as e:
        abort(400, str(e))
    if dados is None:
        abort(404)
    mime = "model/stl" if g.get("kind") == "stl" else "image/jpeg" if g["file"].endswith(".jpg") else g.get("mime") or "application/octet-stream"
    nome = g.get("name") or g["file"]
    if g.get("kind") == "arquivo" and g.get("ext") and not nome.lower().endswith("." + g["ext"]):
        nome += "." + g["ext"]
    baixar = request.args.get("baixar") or g.get("kind") == "stl"
    disp = f"{'attachment' if baixar else 'inline'}; filename*=UTF-8''{urllib.parse.quote(nome)}"
    return Response(dados, mimetype=mime, headers={"Content-Disposition": disp, "Cache-Control": "private, max-age=3600"})


@bp.route("/pacientes/<pid>/galeria/<gid>")
@exige("prontuario")
def ver(pid, gid):
    p, g = _item(pid, gid)
    if g.get("kind") == "stl":
        return redirect(url_for("galeria.visualizador", pid=pid, ids=gid))
    return render_template("pront_galeria_item.html", p=p, aba="galeria", g=g)


@bp.route("/pacientes/<pid>/galeria/<gid>/excluir", methods=["POST"])
@exige("prontuario", 2)
def excluir(pid, gid):
    p, g = _item(pid, gid)
    p["gallery"] = [x for x in p["gallery"] if x.get("id") != gid]
    if _salvar_paciente(p, f"Arquivo removido da galeria: {g.get('name')} ({p['name']})"):
        if g.get("file"):
            anexos().excluir(g["file"])
        flash("Arquivo removido.")
    return redirect(url_for("galeria.galeria", pid=pid))


@bp.route("/pacientes/<pid>/3d")
@exige("prontuario")
def visualizador(pid):
    p = _paciente(pid)
    itens = [g for g in p.get("gallery") or [] if g.get("kind") == "stl" and not g.get("pending")]
    ids = [i for i in (request.args.get("ids") or "").split(",") if i] or [g["id"] for g in itens[:1]]
    modelos = [{"id": g["id"], "name": g.get("name"), "url": url_for("galeria.arquivo", pid=pid, gid=g["id"]), "color": g.get("color") or "",
                "triangles": g.get("triangles") or 0, "dims": g.get("dims") or [], "semMiniatura": not g.get("thumb"), "on": g["id"] in ids} for g in itens]
    return render_template("pront_3d.html", p=p, aba="galeria", modelos=modelos, modelos_json=json.dumps(modelos, ensure_ascii=False))


@bp.route("/pacientes/<pid>/3d/miniatura", methods=["POST"])
@exige("prontuario", 2)
def miniatura_3d(pid):
    """O navegador desenha a miniatura do modelo 3D (a primeira vez que é aberto) e manda para guardar."""
    gid, dado = request.form.get("id"), request.form.get("thumb") or ""
    if not dado.startswith("data:image/jpeg;base64,") or len(dado) > 200_000:
        abort(400)
    p, g = _item(pid, gid)
    if not g.get("thumb"):
        g["thumb"] = dado
        try:
            store().salvar("patients", p)
        except Conflito:
            pass
    return jsonify(ok=True)


@bp.route("/pacientes/<pid>/3d/captura", methods=["POST"])
@exige("prontuario", 2)
def captura(pid):
    """Imagem do visualizador 3D salva na galeria."""
    dado = request.form.get("imagem") or ""
    if not dado.startswith("data:image/") or "," not in dado:
        abort(400)
    p = _paciente(pid)
    nome = f"Captura 3D {tempo.agora().strftime('%d-%m-%Y %H-%M')}.jpg"
    p["gallery"] = (p.get("gallery") or []) + [item_imagem(nome, base64.b64decode(dado.split(",", 1)[1]))]
    ok = _salvar_paciente(p, f"Captura do modelo 3D salva na galeria: {p['name']}")
    return jsonify(ok=ok)
