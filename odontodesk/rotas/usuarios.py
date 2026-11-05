"""Usuários e acessos (só o administrador): usuários, senhas provisórias, tipos de acesso (perfis), bloqueio por
inatividade e código de recuperação. Mesmo formato do app em JavaScript (usuarios + clinic.profiles)."""
import secrets
import string

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import seguranca, tempo, web
from ..dados.store import Conflito, novo_id
from ..web import exige, store

bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")
NIVEIS = [(0, "Sem acesso"), (1, "Só consulta"), (2, "Completo")]
BLOQUEIO = [(0, "Nunca"), (5, "5 minutos"), (10, "10 minutos"), (20, "20 minutos"), (30, "30 minutos"), (60, "1 hora")]


def senha_provisoria():
    r = secrets.SystemRandom()
    return "".join(r.choice(string.ascii_lowercase.replace("l", "").replace("o", "")) for _ in range(6)) + str(r.randint(10, 99))


def codigo_recuperacao():
    a = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    c = "".join(secrets.choice(a) for _ in range(20))
    return "-".join(c[i:i + 5] for i in range(0, 20, 5))


def _admins_ativos(users):
    return [u for u in users if u.get("active") and u.get("profileId") == "admin"]


@bp.route("/")
@exige("_admin")
def lista():
    st = store()
    users = sorted(st.listar("users"), key=lambda u: (not u.get("active"), (u.get("name") or "").lower()))
    perfis = seguranca.perfis(g.clinica)
    return render_template("usuarios.html", users=users, perfis=perfis, modulos=seguranca.MODULES, niveis=NIVEIS, dent=st.mapa("dentists"),
                           por_perfil={p["id"]: len([u for u in users if u.get("profileId") == p["id"] and u.get("active")]) for p in perfis},
                           bloqueio=BLOQUEIO, lock=int(g.clinica.get("lockMinutes") if g.clinica.get("lockMinutes") is not None else 20))


@bp.route("/novo", methods=["GET", "POST"])
@bp.route("/<id>", methods=["GET", "POST"])
@exige("_admin")
def usuario(id=None):
    st = store()
    todos = st.listar("users")
    u = (st.get("users", id) or abort(404)) if id else {"profileId": "recepcao", "active": True}
    erro = ""
    if request.method == "POST":
        v = web.campos("name", "login", "profileId", "dentistId", "pass")
        login = seguranca.normaliza_login(v["login"])
        ativo = True if not id else bool(request.form.get("active"))
        outros_admins = [x for x in _admins_ativos(todos) if x["id"] != id]
        if not v["name"]:
            erro = "Informe o nome"
        elif not login:
            erro = "Informe o usuário"
        elif any(x["id"] != id and x.get("login") == login for x in todos):
            erro = f"O usuário \"{login}\" já existe"
        elif v["profileId"] not in [p["id"] for p in seguranca.perfis(g.clinica)]:
            erro = "Escolha o tipo de acesso"
        elif id and u.get("profileId") == "admin" and (v["profileId"] != "admin" or not ativo) and not outros_admins:
            erro = "É preciso manter pelo menos um administrador ativo"
        elif id == g.usuario["id"] and (not ativo or v["profileId"] != "admin"):
            erro = "Você não pode tirar o próprio acesso de administrador"
        elif not id:
            erro = seguranca.problema_senha(v["pass"], login)
        if not erro:
            rec = dict(u) if id else {"id": novo_id(), "lastLogin": "", "mustChange": True, **seguranca.hash_senha(v["pass"])}
            rec.update(name=v["name"], login=login, profileId=v["profileId"], dentistId=v["dentistId"], active=ativo)
            perfil = next((p["name"] for p in seguranca.perfis(g.clinica) if p["id"] == rec["profileId"]), "")
            try:
                st.salvar("users", rec, acao=f"Usuário {'alterado' if id else 'criado'}: {rec['name']} ({perfil})", usuario=web.nome_usuario())
            except Conflito:
                flash("Este usuário foi alterado em outro computador agora. Os dados atuais foram carregados.", "aviso")
                return redirect(request.url)
            if not id:
                return render_template("senha_provisoria.html", u=rec, senha=v["pass"])
            flash("Usuário salvo.")
            return redirect(url_for("usuarios.lista"))
        u = {**u, **v, "login": login or v["login"], "active": ativo}
    senha = senha_provisoria() if not id else ""
    return render_template("usuario_form.html", u=u, novo=not id, erro=erro, perfis=seguranca.perfis(g.clinica), dentistas=st.listar("dentists"),
                           senha=request.form.get("pass") or senha, eu=id == g.usuario["id"])


@bp.route("/<id>/excluir", methods=["POST"])
@exige("_admin")
def excluir(id):
    st = store()
    u = st.get("users", id) or abort(404)
    if id == g.usuario["id"]:
        flash("Você não pode excluir o próprio usuário.", "erro")
    elif u.get("profileId") == "admin" and u.get("active") and len(_admins_ativos(st.listar("users"))) <= 1:
        flash("É preciso manter pelo menos um administrador ativo.", "erro")
    else:
        st.excluir("users", id, acao=f"Usuário excluído: {u.get('name')}", usuario=web.nome_usuario())
        flash("Usuário excluído. O histórico de ações continua registrado.")
    return redirect(url_for("usuarios.lista"))


@bp.route("/<id>/senha", methods=["POST"])
@exige("_admin")
def redefinir(id):
    u = store().get("users", id) or abort(404)
    if id == g.usuario["id"]:
        return redirect(url_for("auth.trocar_senha"))
    senha = senha_provisoria()
    u.update(seguranca.hash_senha(senha))
    u["mustChange"] = True
    store().salvar("users", u, acao=f"Senha redefinida pelo administrador: {u['name']}", usuario=web.nome_usuario())
    web.login_ok(u.get("login"))
    return render_template("senha_provisoria.html", u=u, senha=senha, redefinida=True)


# ---------- tipos de acesso (perfis) ----------
def _salvar_perfis(perfis, acao):
    cl = store().clinica()
    cl["profiles"] = perfis
    try:
        store().salvar("clinic", cl, acao=acao, usuario=web.nome_usuario())
        return True
    except Conflito:
        flash("As configurações foram alteradas em outro computador agora. Confira e salve de novo.", "aviso")
        return False


@bp.route("/perfis", methods=["POST"])
@exige("_admin")
def perfis_salvar():
    """Salva a tabela de permissões (todas as áreas de todos os tipos de acesso)."""
    perfis = [dict(p, perms=dict(p.get("perms") or {})) for p in seguranca.perfis(g.clinica)]
    mudou = []
    for p in perfis:
        if p.get("fixed") or p["id"] == "admin":
            continue
        for k, nome in seguranca.MODULES:
            val = request.form.get(f"perm_{p['id']}_{k}")
            if val in ("0", "1", "2") and int(val) != int(p["perms"].get(k) or 0):
                p["perms"][k] = int(val)
                mudou.append(f"{p['name']}: {nome.split(' (')[0]} → {dict(NIVEIS)[int(val)]}")
    if mudou and _salvar_perfis(perfis, "Tipos de acesso alterados: " + "; ".join(mudou)[:450]):
        flash(f"{len(mudou)} permissão(ões) alterada(s).")
    elif not mudou:
        flash("Nenhuma permissão mudou.")
    return redirect(url_for("usuarios.lista") + "#perfis")


@bp.route("/perfis/novo", methods=["POST"])
@exige("_admin")
def perfil_novo():
    nome = (request.form.get("name") or "").strip()
    perfis = seguranca.perfis(g.clinica)
    if not nome:
        flash("Informe o nome do tipo de acesso.", "erro")
    elif any(p["name"].lower() == nome.lower() for p in perfis):
        flash("Já existe um tipo de acesso com esse nome.", "erro")
    else:
        base = next((p for p in perfis if p["id"] == request.form.get("copy")), None)
        perfis = perfis + [{"id": novo_id(), "name": nome, "perms": dict((base or {}).get("perms") or {k: 0 for k, _ in seguranca.MODULES})}]
        if _salvar_perfis(perfis, f"Tipo de acesso criado: {nome}"):
            flash("Tipo de acesso criado. Ajuste as permissões na tabela.")
    return redirect(url_for("usuarios.lista") + "#perfis")


@bp.route("/perfis/<pid>", methods=["POST"])
@exige("_admin")
def perfil(pid):
    perfis = seguranca.perfis(g.clinica)
    p = next((x for x in perfis if x["id"] == pid), None)
    if not p or p.get("fixed") or pid == "admin":
        abort(404)
    if request.form.get("excluir"):
        n = len([u for u in store().listar("users") if u.get("profileId") == pid])
        if n:
            flash(f"{n} usuário(s) usam este tipo de acesso. Mude o tipo deles antes de excluir.", "erro")
        elif _salvar_perfis([x for x in perfis if x["id"] != pid], f"Tipo de acesso excluído: {p['name']}"):
            flash("Tipo de acesso excluído.")
    else:
        nome = (request.form.get("name") or "").strip()
        if not nome or any(x is not p and x["name"].lower() == nome.lower() for x in perfis):
            flash("Nome vazio ou já usado.", "erro")
        else:
            p["name"] = nome
            if _salvar_perfis(perfis, f"Tipo de acesso renomeado: {nome}"):
                flash("Tipo de acesso renomeado.")
    return redirect(url_for("usuarios.lista") + "#perfis")


@bp.route("/seguranca", methods=["POST"])
@exige("_admin")
def seguranca_salvar():
    cl = store().clinica()
    if request.form.get("codigo"):
        cod = codigo_recuperacao()
        cl["recovery"] = seguranca.hash_senha("".join(c for c in cod.upper() if c.isalnum()))
        store().salvar("clinic", cl, acao="Novo código de recuperação gerado", usuario=web.nome_usuario())
        return render_template("codigo_recuperacao.html", codigo=cod)
    try:
        minutos = int(request.form.get("lock") or 0)
    except ValueError:
        minutos = 20
    cl["lockMinutes"] = minutos
    store().salvar("clinic", cl, acao=f"Bloqueio por inatividade: {dict(BLOQUEIO).get(minutos, minutos)}", usuario=web.nome_usuario())
    flash("Bloqueio por inatividade salvo.")
    return redirect(url_for("usuarios.lista") + "#seguranca")
