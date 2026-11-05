"""Convivência com o app em JavaScript: os dois gravam e leem o mesmo banco.

Precisa do Node.js e da pasta do OdontoDesk em JavaScript (variável ODONTODESK_JS; padrão: ../odontodesk).
Sem eles, o teste é pulado.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, ".."))

from odontodesk.dados.drivers import SqliteDriver  # noqa: E402
from odontodesk.dados.store import Store  # noqa: E402

JS = os.environ.get("ODONTODESK_JS") or os.path.abspath(os.path.join(AQUI, "..", "..", "odontodesk"))
TEM_JS = shutil.which("node") and os.path.exists(os.path.join(JS, "server", "store.js")) and os.path.exists(os.path.join(JS, "testes", "driver-sqlite.js"))


@unittest.skipUnless(TEM_JS, "Node.js ou a pasta do OdontoDesk em JavaScript não encontrados")
class Convivencia(unittest.TestCase):
    def js(self, acao, arg=None):
        r = subprocess.run(["node", os.path.join(AQUI, "js", "convivencia.js"), JS, self.arquivo, acao] + ([json.dumps(arg)] if arg is not None else []),
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.arquivo = os.path.join(self.dir, "conv.db")
        self.js("init")                       # o app em JavaScript cria as tabelas
        self.st = Store(SqliteDriver(self.arquivo), "WEB-PYTHON")
        self.st.criar_tabelas()               # não muda nada num banco já criado

    def tearDown(self):
        self.st.db.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_js_grava_python_le_e_altera_js_recebe(self):
        self.js("apply", {"ops": [{"coll": "patients", "op": "put", "id": "p1", "v": 0, "rec": {
            "id": "p1", "name": "Paciente do JS", "cpf": "529.982.247-25", "birth": "1980-05-06", "anamnesis": {"q": "sim"}, "gallery": [{"id": "g", "file": "g.jpg"}]}}],
            "audit": [{"action": "js gravou", "user": "Ana"}]})
        p = self.st.get("patients", "p1")
        self.assertEqual((p["name"], p["birth"], p["anamnesis"], p["_v"]), ("Paciente do JS", "1980-05-06", {"q": "sim"}, 1))
        cursor = self.js("load")["cursor"]
        p["phone"] = "(21) 99999-0000"
        self.st.salvar("patients", p, acao="py alterou", usuario="Bia")
        self.st.salvar("appointments", {"date": "2026-11-05", "time": "09:30", "duration": 30, "patientId": "p1", "type": "consulta", "status": "agendado"})
        ch = self.js("changes", {"cursor": cursor, "auditCursor": 0})
        recs = {r["coll"]: r["rec"] for r in ch["records"]}
        self.assertEqual(recs["patients"]["phone"], "(21) 99999-0000")
        self.assertEqual(recs["patients"]["gallery"][0]["file"], "g.jpg")    # campos que o Python não mexe são preservados
        self.assertEqual(recs["patients"]["_v"], 2)
        self.assertEqual(recs["appointments"]["time"], "09:30")
        self.assertIn("py alterou", [a["action"] for a in ch["audit"]])

    def test_conflito_entre_os_dois_apps(self):
        p = self.st.salvar("patients", {"name": "Ana"})
        r = self.js("apply", {"ops": [{"coll": "patients", "op": "put", "id": p["id"], "v": 1, "rec": {**p, "notes": "do JS"}}]})
        self.assertEqual(r["results"][0]["v"], 2)
        r = self.js("apply", {"ops": [{"coll": "patients", "op": "put", "id": p["id"], "v": 1, "rec": {**p, "notes": "atrasado"}}]})
        self.assertEqual(r["conflicts"][0]["rec"]["notes"], "do JS")    # o JS também respeita a versão gravada pelo Python
        self.assertEqual(self.st.get("patients", p["id"])["notes"], "do JS")

    def test_fechamento_do_periodo_e_o_mesmo_campo(self):
        self.st.salvar("clinic", {"name": "C", "finClosings": [{"id": "k", "until": "2026-10-31"}]})
        dados = self.js("load")["data"]
        self.assertEqual(dados["clinic"]["finClosings"][0]["until"], "2026-10-31")


if __name__ == "__main__":
    unittest.main()
