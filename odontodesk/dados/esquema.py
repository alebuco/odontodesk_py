"""Estrutura do banco do OdontoDesk.

É a MESMA usada pelo app em JavaScript (server/store.js): mesmas tabelas, mesmas colunas e o mesmo
formato da coluna `dados` (JSON com os campos que não têm coluna própria). Por isso os dois apps podem
usar o mesmo banco ao mesmo tempo.

Cada coleção tem:
  - table:   nome da tabela no banco
  - cols:    campo do registro -> (coluna, tipo)
  - ordered: True se a ordem dos registros importa (coluna `ordem`)
  - single:  id fixo, para tabelas de um registro só (configurações da clínica)
"""

SCHEMA = {
    "clinic": {"table": "configuracoes", "single": "clinica", "cols": {}},
    "dentists": {"table": "dentistas", "ordered": True, "cols": {
        "name": ("nome", "str"), "cro": ("cro", "str"), "commission": ("comissao", "dec")}},
    "patients": {"table": "pacientes", "index": ["nome", "cpf"], "cols": {
        "name": ("nome", "str"), "socialName": ("nome_social", "str"), "cpf": ("cpf", "str"),
        "birth": ("nascimento", "date"), "phone": ("telefone", "str"), "email": ("email", "str"),
        "address": ("endereco", "lstr"), "insurance": ("convenio", "str"), "guardian": ("responsavel", "str"),
        "notes": ("observacoes", "text"), "createdAt": ("criado_em", "date"),
        "cep": ("cep", "cep"), "street": ("logradouro", "str"), "number": ("numero", "short"),
        "complement": ("complemento", "str"), "district": ("bairro", "str"), "city": ("cidade", "str"), "uf": ("uf", "uf")}},
    "procedures": {"table": "procedimentos", "cols": {
        "name": ("nome", "lstr"), "category": ("categoria", "str"), "price": ("valor", "dec"),
        "code": ("codigo", "short"), "source": ("fonte", "short")}},
    "appointments": {"table": "agendamentos", "index": ["data", "paciente_id", "dentista_id"], "cols": {
        "date": ("data", "date"), "time": ("hora", "hhmm"), "duration": ("duracao", "int"),
        "patientId": ("paciente_id", "ref"), "dentistId": ("dentista_id", "ref"), "type": ("tipo", "short"),
        "status": ("status", "short"), "procId": ("procedimento_id", "ref"), "notes": ("observacoes", "text")}},
    "treatments": {"table": "tratamentos", "index": ["paciente_id"], "cols": {
        "patientId": ("paciente_id", "ref"), "dentistId": ("dentista_id", "ref"), "title": ("titulo", "str"),
        "status": ("status", "short"), "createdAt": ("criado_em", "date"), "discount": ("desconto", "dec")}},
    "finance": {"table": "financeiro", "index": ["vencimento", "data_pagamento", "paciente_id", "dentista_id"], "cols": {
        "type": ("tipo", "short"), "desc": ("descricao", "lstr"), "value": ("valor", "dec"), "due": ("vencimento", "date"),
        "paid": ("pago", "bool"), "paidDate": ("data_pagamento", "date"), "category": ("categoria", "str"),
        "method": ("forma_pagamento", "str"), "patientId": ("paciente_id", "ref"), "dentistId": ("dentista_id", "ref"),
        "treatmentId": ("tratamento_id", "ref")}},
    "stock": {"table": "estoque", "cols": {
        "name": ("nome", "str"), "unit": ("unidade", "short"), "qty": ("quantidade", "dec"), "min": ("minimo", "dec"),
        "cost": ("custo", "dec"), "barcode": ("codigo_barras", "short")}},
    "stockMoves": {"table": "estoque_movimentos", "index": ["produto_id"], "cols": {
        "productId": ("produto_id", "ref"), "kind": ("tipo", "short"), "qty": ("quantidade", "dec"), "date": ("data", "date"),
        "note": ("observacao", "lstr"), "expiry": ("validade", "date"), "lot": ("lote", "short")}},
    "prosthetists": {"table": "proteticos", "cols": {
        "name": ("nome", "str"), "lab": ("laboratorio", "str"), "phone": ("telefone", "str"), "email": ("email", "str"),
        "days": ("prazo_dias", "int"), "notes": ("observacoes", "text")}},
    "labWorks": {"table": "trabalhos_proteticos", "index": ["paciente_id", "protetico_id"], "cols": {
        "patientId": ("paciente_id", "ref"), "dentistId": ("dentista_id", "ref"), "prosthetistId": ("protetico_id", "ref"),
        "type": ("tipo", "str"), "teeth": ("dentes", "str"), "shade": ("cor", "short"), "value": ("valor", "dec"),
        "paid": ("pago", "bool"), "paidDate": ("data_pagamento", "date"), "status": ("situacao", "short"),
        "financeId": ("financeiro_id", "ref"), "createdAt": ("criado_em", "date"), "notes": ("observacoes", "text")}},
    "users": {"table": "usuarios", "cols": {
        "name": ("nome", "str"), "login": ("login", "short"), "profileId": ("perfil", "short"), "active": ("ativo", "bool"),
        "mustChange": ("trocar_senha", "bool"), "dentistId": ("dentista_id", "ref"), "hash": ("senha_hash", "str"),
        "salt": ("senha_sal", "short"), "iter": ("senha_iteracoes", "int"), "lastLogin": ("ultimo_acesso", "short")}},
    "evolutions": {"table": "evolucoes", "index": ["paciente_id", "data"], "cols": {
        "patientId": ("paciente_id", "ref"), "date": ("data", "date"), "dentistId": ("dentista_id", "ref"),
        "appointmentId": ("agendamento_id", "ref"), "text": ("anotacoes", "text"), "authorId": ("autor_id", "ref"),
        "authorName": ("autor", "str"), "createdAt": ("criado_em", "short"), "editedAt": ("alterado_em", "short")}},
    "prescriptions": {"table": "receitas", "index": ["paciente_id", "data"], "cols": {
        "patientId": ("paciente_id", "ref"), "dentistId": ("dentista_id", "ref"), "date": ("data", "date"),
        "kinds": ("tipos", "short"), "authorName": ("autor", "str"), "createdAt": ("criado_em", "short")}},
    "templates": {"table": "modelos_documentos", "ordered": True, "cols": {"title": ("titulo", "str"), "body": ("corpo", "text")}},
    "anamnesisModel": {"table": "anamnese_perguntas", "ordered": True, "cols": {"q": ("pergunta", "lstr"), "type": ("tipo", "short")}},
}
COLLS = list(SCHEMA)
TABLE_TO_COLL = {s["table"]: c for c, s in SCHEMA.items()}

TYPES = {
    "mysql": {"cep": "CHAR(9) NULL", "uf": "CHAR(2) NULL", "id": "VARCHAR(40)", "ref": "VARCHAR(40) NULL",
              "str": "VARCHAR(255) NULL", "short": "VARCHAR(40) NULL", "lstr": "VARCHAR(1000) NULL", "hhmm": "CHAR(5) NULL",
              "text": "TEXT NULL", "date": "DATE NULL", "int": "INT NULL", "dec": "DECIMAL(14,2) NULL",
              "bool": "TINYINT(1) NOT NULL DEFAULT 0", "json": "JSON NULL", "blob": "LONGBLOB NOT NULL", "bigint": "BIGINT"},
    "sqlite": {"cep": "TEXT", "uf": "TEXT", "id": "TEXT", "ref": "TEXT", "str": "TEXT", "short": "TEXT", "lstr": "TEXT",
               "hhmm": "TEXT", "text": "TEXT", "date": "TEXT", "int": "INTEGER", "dec": "REAL",
               "bool": "INTEGER NOT NULL DEFAULT 0", "json": "TEXT", "blob": "BLOB NOT NULL", "bigint": "INTEGER"},
}


def ddl(dialect):
    """Comandos CREATE TABLE/INDEX (iguais aos do app em JavaScript)."""
    T, my = TYPES[dialect], dialect == "mysql"
    tail = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci" if my else ""
    auto = "BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY" if my else "INTEGER PRIMARY KEY AUTOINCREMENT"
    id_cache = " /*T![auto_id_cache] AUTO_ID_CACHE=1 */" if my else ""  # TiDB: numeração sempre crescente
    dt = "DATETIME" if my else "TEXT"
    out = [
        f"CREATE TABLE IF NOT EXISTS alteracoes (seq {auto}, tabela VARCHAR(40) NOT NULL, registro_id VARCHAR(40) NOT NULL, "
        f"operacao VARCHAR(10) NOT NULL, computador VARCHAR(100) NULL, data_hora {dt} NOT NULL){tail}{id_cache}",
        f"CREATE TABLE IF NOT EXISTS auditoria (id {auto}, data_hora {dt} NOT NULL, acao VARCHAR(500) NOT NULL, "
        f"computador VARCHAR(100) NULL, usuario VARCHAR(100) NULL){tail}{id_cache}",
        f"CREATE TABLE IF NOT EXISTS anexos (nome VARCHAR(60) NOT NULL PRIMARY KEY, tamanho {T['bigint']} NOT NULL, partes INT NOT NULL, "
        f"criado_em {dt} NOT NULL, tamanho_armazenado {T['bigint']} NULL, compressao VARCHAR(10) NULL, sha256 CHAR(64) NULL){tail}",
        f"CREATE TABLE IF NOT EXISTS anexos_partes (nome VARCHAR(60) NOT NULL, parte INT NOT NULL, conteudo {T['blob']}, "
        f"PRIMARY KEY (nome, parte)){tail}{' ROW_FORMAT=DYNAMIC' if my else ''}",
    ]
    for s in SCHEMA.values():
        cols = [f"id {T['id']} NOT NULL PRIMARY KEY"] + [f"{col} {T[tp]}" for col, tp in s["cols"].values()]
        if s.get("ordered"):
            cols.append("ordem INT NOT NULL DEFAULT 0")
        cols += [f"dados {T['json']}", "versao INT NOT NULL DEFAULT 1", f"excluido {T['bool']}", f"seq {T['bigint']} NOT NULL DEFAULT 0"]
        out.append(f"CREATE TABLE IF NOT EXISTS {s['table']} ({', '.join(cols)}){tail}")
        for col in ["seq"] + s.get("index", []):
            out.append(f"CREATE INDEX idx_{s['table']}_{col} ON {s['table']} ({col})" if my
                       else f"CREATE INDEX IF NOT EXISTS idx_{s['table']}_{col} ON {s['table']} ({col})")
    return out
