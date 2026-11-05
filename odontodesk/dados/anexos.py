"""Anexos (fotos, PDFs, escaneamentos 3D) guardados no banco — mesmo formato do app em JavaScript (server/store.js).

Tabelas: `anexos` (nome, tamanho, partes, compressão, SHA-256) e `anexos_partes` (o conteúdo em pedaços).
Compressão: 'mesh' para STL binário (malha indexada, sem perda), 'br' (brotli) para outros arquivos grandes
que compactam bem; fotos (JPG/PNG) ficam como estão. Na leitura, o SHA-256 confere a integridade.
"""
import hashlib
import re

from . import malha
from .store import agora

NOME_OK = re.compile(r"^[a-z0-9]+\.[a-z0-9]{1,5}$", re.I)


class AnexoErro(Exception):
    pass


def _brotli():
    import brotli  # pacote "Brotli" (requirements.txt)
    return brotli


class Anexos:
    def __init__(self, store):
        self.st = store
        self.db = store.db
        self._parte = None

    def tamanho_parte(self):
        """¼ do limite do servidor, entre 512 KB e 8 MB (no TiDB, no máximo 2 MB) — igual ao app em JavaScript."""
        if self._parte:
            return self._parte
        p = 4 * 1024 * 1024
        if self.db.dialect == "mysql":
            try:
                p = min(8 * 1048576, max(512 * 1024, int(self.db.query("SELECT @@max_allowed_packet AS p")[0]["p"]) // 4))
            except Exception:
                p = 1048576
            if getattr(self.db, "flavor", "") == "tidb":
                p = min(p, 2 * 1048576)
        self._parte = p
        return p

    def meta(self, nome):
        r = self.db.query("SELECT nome, tamanho, partes, tamanho_armazenado, compressao, sha256 FROM anexos WHERE nome = ?", (nome,))
        if not r:
            return None
        m = r[0]
        return {"name": nome, "size": int(m["tamanho"]), "parts": int(m["partes"]), "stored": int(m["tamanho_armazenado"] or m["tamanho"]),
                "compression": m["compressao"] or "", "sha256": m["sha256"] or ""}

    def ler(self, nome):
        m = self.meta(nome)
        if not m:
            return None
        partes = []
        for i in range(m["parts"]):
            r = self.db.query("SELECT conteudo FROM anexos_partes WHERE nome = ? AND parte = ?", (nome, i))
            if not r:
                raise AnexoErro(f"Anexo {nome} incompleto no banco (parte {i + 1} de {m['parts']})")
            partes.append(bytes(r[0]["conteudo"]))
        dados = b"".join(partes)
        if m["compression"] == "br":
            dados = _brotli().decompress(dados)
        elif m["compression"] == "mesh":
            dados = malha.descompactar(dados)
        if m["sha256"] and hashlib.sha256(dados).hexdigest() != m["sha256"]:
            raise AnexoErro(f"Anexo {nome} corrompido (verificação SHA-256 falhou)")
        return dados

    def gravar(self, nome, dados):
        """Grava (substitui) um anexo. Devolve {size, stored, sha256, compression, canonical}."""
        if not NOME_OK.match(nome):
            raise AnexoErro("Nome de anexo inválido")
        dados = bytes(dados)
        guardar, comp, canon = dados, "", None
        if nome.lower().endswith(".stl") and malha.eh_stl_binario(dados):
            try:
                r = malha.compactar(dados)
                if r and len(r[0]) < len(dados) * 0.9:
                    guardar, canon = r
                    comp = "mesh"
            except Exception as e:  # malha estranha: guarda como veio
                print("malha", nome, e)
        sha = hashlib.sha256(canon or dados).hexdigest()  # do arquivo que a leitura devolve
        if not comp and len(dados) > 64 * 1024 and not re.search(r"\.(jpe?g|png|webp|zip|gz)$", nome, re.I):
            z = _brotli().compress(dados, quality=5)
            if len(z) < len(dados) * 0.92:
                guardar, comp = z, "br"
        tam = self.tamanho_parte()
        partes = max(1, -(-len(guardar) // tam))
        with self.db.transacao() as t:
            t.execute("DELETE FROM anexos_partes WHERE nome = ?", (nome,))
            t.execute("DELETE FROM anexos WHERE nome = ?", (nome,))
            for i in range(partes):
                t.execute("INSERT INTO anexos_partes (nome, parte, conteudo) VALUES (?, ?, ?)", (nome, i, guardar[i * tam:(i + 1) * tam]))
            t.execute("INSERT INTO anexos (nome, tamanho, partes, criado_em, tamanho_armazenado, compressao, sha256) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (nome, len(dados), partes, agora(), len(guardar), comp or None, sha))
        return {"size": len(dados), "stored": len(guardar), "sha256": sha, "compression": comp, "canonical": canon}

    def excluir(self, nome):
        with self.db.transacao() as t:
            t.execute("DELETE FROM anexos_partes WHERE nome = ?", (nome,))
            t.execute("DELETE FROM anexos WHERE nome = ?", (nome,))
