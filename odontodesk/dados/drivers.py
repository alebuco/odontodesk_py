"""Conexão com o banco.

Dois drivers com a mesma interface:
  - MySQL/MariaDB/TiDB (pacote PyMySQL) — produção
  - SQLite (vem com o Python) — testes e uso num computador só

Interface:
  query(sql, params)   -> lista de dicionários
  execute(sql, params) -> (linhas_afetadas, id_inserido)
  transacao()          -> bloco `with` que faz COMMIT no fim ou ROLLBACK se der erro
Os comandos usam `?` como marcador (como no app em JavaScript); o driver MySQL troca por `%s`.
"""
import re
import sqlite3
import threading
from contextlib import contextmanager


class SqliteDriver:
    dialect = "sqlite"
    flavor = "sqlite"

    def __init__(self, arquivo):
        self._db = sqlite3.connect(arquivo, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA busy_timeout=10000")
        self._lock = threading.RLock()
        self._em_tx = False

    def query(self, sql, params=()):
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, tuple(params)).fetchall()]

    def execute(self, sql, params=()):
        with self._lock:
            cur = self._db.execute(sql, tuple(params))
            return cur.rowcount, cur.lastrowid

    @contextmanager
    def transacao(self):
        with self._lock:
            if self._em_tx:          # transação dentro de transação: usa a de fora
                yield self
                return
            self._db.execute("BEGIN IMMEDIATE")
            self._em_tx = True
            try:
                yield self
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            finally:
                self._em_tx = False

    def close(self):
        self._db.close()


# TiDB Cloud (e outros bancos na nuvem) exigem conexão criptografada
NUVEM = re.compile(r"\.tidbcloud\.com$|\.aivencloud\.com$|\.psdb\.cloud$", re.I)


class MysqlDriver:
    """MySQL, MariaDB ou TiDB. Uma conexão por thread (o servidor web atende várias pessoas ao mesmo tempo)."""
    dialect = "mysql"

    def __init__(self, host, usuario, senha, banco, porta=3306, ssl=None, verificar_ssl=True):
        import pymysql  # instalado pelo requirements.txt
        self._pymysql = pymysql
        usar_ssl = ssl if ssl is not None else bool(NUVEM.search(str(host or "").strip()))
        self._args = dict(host=host, port=int(porta or 3306), user=usuario, password=senha or "", database=banco,
                          charset="utf8mb4", autocommit=True, connect_timeout=10, read_timeout=60, write_timeout=60,
                          cursorclass=pymysql.cursors.DictCursor)
        if usar_ssl:
            import ssl as _ssl
            ctx = _ssl.create_default_context()
            if not verificar_ssl:
                ctx.check_hostname = False
                ctx.verify_mode = _ssl.CERT_NONE
            self._args["ssl"] = ctx
        self._local = threading.local()
        v = self.query("SELECT VERSION() AS v")[0]["v"]
        self.version = v
        self.flavor = "tidb" if "tidb" in v.lower() else "mariadb" if "mariadb" in v.lower() else "mysql"

    def _conn(self):
        c = getattr(self._local, "conn", None)
        if c is None or not c.open:
            c = self._pymysql.connect(**self._args)
            self._local.conn = c
        return c

    @staticmethod
    def _sql(sql):
        return sql.replace("%", "%%").replace("?", "%s")

    def _run(self, fn):
        # conexões paradas são fechadas por provedores na nuvem (ex.: TiDB após ~5 min): reconecta uma vez
        try:
            return fn(self._conn())
        except (self._pymysql.err.OperationalError, self._pymysql.err.InterfaceError) as e:
            if getattr(self._local, "tx", False) or (e.args and e.args[0] not in (2006, 2013, 2014, 2055, 0)):
                raise
            self._local.conn = None
            return fn(self._conn())

    def query(self, sql, params=()):
        def f(c):
            with c.cursor() as cur:
                cur.execute(self._sql(sql), tuple(params))
                return [self._limpa(r) for r in cur.fetchall()]
        return self._run(f)

    def execute(self, sql, params=()):
        def f(c):
            with c.cursor() as cur:
                n = cur.execute(self._sql(sql), tuple(params))
                return n, cur.lastrowid
        return self._run(f)

    @staticmethod
    def _limpa(r):
        # datas e decimais do MySQL viram texto e número (como no app em JavaScript)
        import datetime
        import decimal
        out = {}
        for k, v in r.items():
            if isinstance(v, datetime.datetime):
                v = v.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(v, datetime.date):
                v = v.isoformat()
            elif isinstance(v, decimal.Decimal):
                v = float(v)
            out[k] = v
        return out

    @contextmanager
    def transacao(self):
        if getattr(self._local, "tx", False):
            yield self
            return
        c = self._conn()
        c.begin()
        self._local.tx = True
        try:
            yield self
            c.commit()
        except BaseException:
            try:
                c.rollback()
            finally:
                pass
            raise
        finally:
            self._local.tx = False

    def close(self):
        c = getattr(self._local, "conn", None)
        if c:
            c.close()


def criar_driver(cfg):
    """cfg = seção "banco" do config.json."""
    tipo = (cfg.get("tipo") or "mysql").lower()
    if tipo == "sqlite":
        return SqliteDriver(cfg.get("arquivo") or "odontodesk.db")
    return MysqlDriver(cfg.get("host"), cfg.get("usuario"), cfg.get("senha"), cfg.get("nome") or "odontodesk",
                       porta=cfg.get("porta") or 3306, ssl=cfg.get("ssl"), verificar_ssl=cfg.get("verificar_ssl", True))
