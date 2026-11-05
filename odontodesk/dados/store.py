"""Leitura e gravação dos registros, no mesmo protocolo do app em JavaScript (server/store.js).

Regras que mantêm os dois apps sincronizados:
  - cada registro tem `versao`: só grava se ninguém mudou o registro desde que foi lido (senão: Conflito);
  - exclusão é lógica (`excluido = 1`), para os outros computadores saberem que sumiu;
  - toda gravação entra na tabela `alteracoes`; os computadores com o app em JavaScript leem essa
    tabela a cada 4 segundos e recebem a mudança feita aqui;
  - campos sem coluna própria ficam na coluna `dados` (JSON) e são preservados ao gravar.
"""
import json
import random
import string
import time

from .. import tempo
from .esquema import COLLS, SCHEMA, TABLE_TO_COLL, TYPES, ddl

MAXLEN = {"str": 255, "short": 40, "lstr": 1000, "hhmm": 5, "cep": 9, "uf": 2, "ref": 40}
TEXT_TYPES = {"ref", "str", "short", "lstr", "text", "hhmm", "cep", "uf"}


class Conflito(Exception):
    """O registro foi alterado (ou excluído) por outra pessoa depois de ser lido."""

    def __init__(self, coll, id, atual):
        super().__init__(f"{coll}/{id} alterado por outro computador")
        self.coll, self.id, self.atual = coll, id, atual


def novo_id():
    """Mesmo formato dos códigos criados pelo app em JavaScript (8 letras/números + 4 do relógio)."""
    alfa = string.ascii_lowercase + string.digits
    r = "".join(random.SystemRandom().choice(alfa) for _ in range(8))
    t = _base36(int(time.time() * 1000))[-4:]
    return r + t


def _base36(n):
    alfa = string.digits + string.ascii_lowercase
    s = ""
    while n:
        n, r = divmod(n, 36)
        s = alfa[r] + s
    return s or "0"


def agora():
    return tempo.agora_texto()


def _num(v):
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return int(f) if f.is_integer() else f


def to_col(tipo, v):
    if tipo == "date":
        return str(v)[:10] if v else None
    if tipo == "ref":
        return str(v)[:MAXLEN["ref"]] if v else None
    if tipo in MAXLEN and v is not None:
        return str(v)[:MAXLEN[tipo]]
    if tipo == "bool":
        return 1 if v else 0
    if tipo in ("dec", "int"):
        return _num(v)
    return None if v is None else str(v)


def from_col(tipo, v):
    if tipo == "date":
        return str(v)[:10] if v else ""
    if tipo in TEXT_TYPES:
        return "" if v is None else str(v)
    if tipo == "bool":
        return bool(int(v or 0))
    if tipo in ("dec", "int"):
        n = _num(v)
        return 0 if n is None else n
    return v


def _json(v):
    if v is None:
        return {}
    if isinstance(v, dict):
        return v
    if isinstance(v, (bytes, bytearray)):
        v = v.decode("utf-8")
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return {}


def to_row(coll, rec):
    s = SCHEMA[coll]
    row, extra = {}, {}
    for campo, (col, tipo) in s["cols"].items():
        row[col] = to_col(tipo, rec.get(campo))
    for k, v in rec.items():
        if k not in s["cols"] and k not in ("id", "_v", "_o"):
            extra[k] = v
    row["dados"] = json.dumps(extra, ensure_ascii=False, separators=(",", ":"))
    return row


def from_row(coll, row):
    s = SCHEMA[coll]
    rec = {"id": row["id"], **_json(row.get("dados"))}
    if s.get("single"):
        rec.pop("id", None)
    for campo, (col, tipo) in s["cols"].items():
        rec[campo] = from_col(tipo, row.get(col))
    rec["_v"] = int(row["versao"])
    if s.get("ordered"):
        rec["_o"] = int(row.get("ordem") or 0)
    return rec


class Store:
    def __init__(self, driver, computador="WEB-PYTHON"):
        self.db = driver
        self.computador = computador

    # ---------- estrutura ----------
    def criar_tabelas(self):
        """Cria as tabelas que faltarem (banco novo). Num banco já usado pelo app em JavaScript, não muda nada."""
        for sql in ddl(self.db.dialect):
            try:
                self.db.execute(sql)
            except Exception as e:  # índice já existe (MySQL)
                if not any(t in str(e) for t in ("Duplicate key name", "already exists")):
                    raise
        # colunas novas em bancos antigos
        T = TYPES[self.db.dialect]
        for s in SCHEMA.values():
            existentes = self._colunas(s["table"])
            for col, tipo in s["cols"].values():
                if col not in existentes:
                    self.db.execute(f"ALTER TABLE {s['table']} ADD COLUMN {col} {T[tipo]}")

    def _colunas(self, tabela):
        if self.db.dialect == "mysql":
            rows = self.db.query("SELECT COLUMN_NAME AS name FROM information_schema.COLUMNS "
                                 "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?", (tabela,))
        else:
            rows = self.db.query(f"PRAGMA table_info({tabela})")
        return {r["name"] for r in rows}

    def vazio(self):
        return int(self.db.query("SELECT COUNT(*) AS n FROM configuracoes WHERE excluido = 0")[0]["n"]) == 0

    # ---------- leitura ----------
    def get(self, coll, id=None):
        s = SCHEMA[coll]
        rows = self.db.query(f"SELECT * FROM {s['table']} WHERE id = ? AND excluido = 0", (s.get("single") or id,))
        return from_row(coll, rows[0]) if rows else None

    def listar(self, coll, where="", params=(), ordem=""):
        """Registros não excluídos. `where` e `ordem` usam os nomes das COLUNAS do banco (ex.: "data = ?")."""
        s = SCHEMA[coll]
        sql = f"SELECT * FROM {s['table']} WHERE excluido = 0"
        if where:
            sql += f" AND ({where})"
        if ordem:
            sql += f" ORDER BY {ordem}"
        elif s.get("ordered"):
            sql += " ORDER BY ordem"
        return [from_row(coll, r) for r in self.db.query(sql, params)]

    def mapa(self, coll):
        return {r["id"]: r for r in self.listar(coll)}

    def clinica(self):
        return self.get("clinic") or {}

    # ---------- gravação ----------
    def aplicar(self, ops, auditoria=(), computador=None, auditar_conflito=True):
        """Lote de gravações numa transação (igual a store.apply do JavaScript).
        ops: [{coll, op: 'put'|'del', id, rec, v, ordem}]   auditoria: [{action, user}]
        Retorna {results, conflicts}."""
        quem = computador or self.computador
        results, conflicts = [], []
        with self.db.transacao() as t:
            def next_seq(tabela, id, op):
                _, seq = t.execute("INSERT INTO alteracoes (tabela, registro_id, operacao, computador, data_hora) "
                                   "VALUES (?, ?, ?, ?, ?)", (tabela, id, op, quem, agora()))
                return seq
            for o in ops:
                s = SCHEMA.get(o["coll"])
                if not s:
                    continue
                id = s.get("single") or o["id"]
                if o["op"] == "del":
                    seq = next_seq(s["table"], id, "del")
                    t.execute(f"UPDATE {s['table']} SET excluido = 1, versao = versao + 1, seq = ? WHERE id = ?", (seq, id))
                    results.append({"coll": o["coll"], "id": id, "deleted": True})
                    continue
                row = to_row(o["coll"], o["rec"])
                if s.get("ordered"):
                    row["ordem"] = int(o.get("ordem") or 0)
                cols = list(row)
                sets = ", ".join(f"{c} = ?" for c in cols)
                vals = [row[c] for c in cols]
                seq = next_seq(s["table"], id, "put")
                v = o.get("v")
                if v:
                    n, _ = t.execute(f"UPDATE {s['table']} SET {sets}, versao = versao + 1, excluido = 0, seq = ? "
                                     f"WHERE id = ? AND versao = ? AND excluido = 0", (*vals, seq, id, v))
                    if n == 1:
                        results.append({"coll": o["coll"], "id": id, "v": v + 1})
                        continue
                    cur = t.query(f"SELECT * FROM {s['table']} WHERE id = ?", (id,))
                    if cur:  # outra pessoa alterou (ou excluiu) antes
                        conflicts.append({"coll": o["coll"], "id": id,
                                          "rec": None if int(cur[0]["excluido"]) else from_row(o["coll"], cur[0])})
                        continue
                cur = t.query(f"SELECT versao FROM {s['table']} WHERE id = ?", (id,))
                if cur:
                    nv = int(cur[0]["versao"]) + 1
                    t.execute(f"UPDATE {s['table']} SET {sets}, versao = ?, excluido = 0, seq = ? WHERE id = ?", (*vals, nv, seq, id))
                    results.append({"coll": o["coll"], "id": id, "v": nv})
                else:
                    t.execute(f"INSERT INTO {s['table']} (id, {', '.join(cols)}, versao, excluido, seq) "
                              f"VALUES (?, {', '.join('?' for _ in cols)}, 1, 0, ?)", (id, *vals, seq))
                    results.append({"coll": o["coll"], "id": id, "v": 1})
            for a in (auditoria if (auditar_conflito or not conflicts) else ()):
                a = {"action": a, "user": ""} if isinstance(a, str) else (a or {})
                t.execute("INSERT INTO auditoria (data_hora, acao, computador, usuario) VALUES (?, ?, ?, ?)",
                          (agora(), str(a.get("action") or "")[:500], quem, (str(a.get("user") or "")[:100] or None)))
        return {"results": results, "conflicts": conflicts}

    def salvar(self, coll, rec, acao=None, usuario="", ordem=None):
        """Grava um registro (novo ou alterado). Lança Conflito se outra pessoa mudou antes. Devolve o registro gravado."""
        s = SCHEMA[coll]
        rec = dict(rec)
        if not s.get("single") and not rec.get("id"):
            rec["id"] = novo_id()
        op = {"coll": coll, "op": "put", "id": rec.get("id"), "rec": rec, "v": rec.get("_v") or 0}
        if s.get("ordered"):
            op["ordem"] = rec.get("_o") if ordem is None else ordem
            if op["ordem"] is None:
                op["ordem"] = self._proxima_ordem(s["table"])
        r = self.aplicar([op], [{"action": acao, "user": usuario}] if acao else [], auditar_conflito=False)
        if r["conflicts"]:
            c = r["conflicts"][0]
            raise Conflito(coll, c["id"], c["rec"])
        rec["_v"] = r["results"][0]["v"]
        return rec

    def excluir(self, coll, id, acao=None, usuario=""):
        self.aplicar([{"coll": coll, "op": "del", "id": id}], [{"action": acao, "user": usuario}] if acao else [])

    def auditar(self, acao, usuario=""):
        self.aplicar([], [{"action": acao, "user": usuario}])

    def _proxima_ordem(self, tabela):
        r = self.db.query(f"SELECT COALESCE(MAX(ordem), -1) AS m FROM {tabela} WHERE excluido = 0")
        return int(r[0]["m"]) + 1

    # ---------- histórico ----------
    def auditoria(self, limite=200):
        rows = self.db.query("SELECT id, data_hora, acao, computador, usuario FROM auditoria ORDER BY id DESC LIMIT ?", (limite,))
        return [{"date": str(a["data_hora"]).replace(" ", "T"), "action": a["acao"], "computer": a["computador"] or "",
                 "user": a["usuario"] or ""} for a in rows]

    def alteracoes_desde(self, cursor=0):
        """Mesmo feed que os computadores leem (usado nos testes de convivência)."""
        rows = self.db.query("SELECT tabela, registro_id, operacao FROM alteracoes WHERE seq > ? ORDER BY seq", (cursor,))
        return [{"coll": TABLE_TO_COLL.get(r["tabela"]), "id": r["registro_id"], "op": r["operacao"]} for r in rows]

    def carregar_tudo(self):
        """Tudo de uma vez (exportação/backup)."""
        out = {}
        for c in COLLS:
            if SCHEMA[c].get("single"):
                out[c] = self.get(c)
            else:
                out[c] = self.listar(c)
        return out
