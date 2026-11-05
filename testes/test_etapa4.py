"""Testes da etapa 4a: anexos (compressão e convivência com o app em JavaScript), galeria e visualizador 3D, documentos,
receitas, pré-consulta e limpeza de dados de exemplo."""
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, ".."))
sys.path.insert(0, AQUI)

import _brotli_node  # noqa: E402

_brotli_node.instalar()

from odontodesk import limpar, receitas  # noqa: E402
from odontodesk.dados import malha  # noqa: E402
from odontodesk.dados.anexos import Anexos  # noqa: E402
from odontodesk.dados.drivers import SqliteDriver  # noqa: E402
from odontodesk.dados.store import Store  # noqa: E402
from odontodesk.rotas import preconsulta as pc  # noqa: E402
from test_convivencia import JS, TEM_JS  # noqa: E402
from test_web import Navegador, preparar  # noqa: E402

STL_REAL = os.path.join(JS, "exemplos-stl", "mandibula.stl")


def stl_cubo():
    """Um cubo (12 triângulos) em STL binário."""
    v = [(x, y, z) for x in (0, 10) for y in (0, 10) for z in (0, 10)]
    faces = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    out = b"cubo".ljust(80, b"\0") + struct.pack("<I", len(faces))
    for f in faces:
        out += struct.pack("<3f", 0, 0, 0) + b"".join(struct.pack("<3f", *v[i]) for i in f) + b"\0\0"
    return out


def png(w=40, h=30):
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 30)).save(b, "PNG")
    return b.getvalue()


class Anexos_(unittest.TestCase):
    def setUp(self):
        self.st = Store(SqliteDriver(":memory:"), "T")
        self.st.criar_tabelas()
        self.ax = Anexos(self.st)

    def test_ida_e_volta(self):
        txt = ("Relatório " * 20000).encode()
        r = self.ax.gravar("a.txt", txt)
        self.assertEqual(r["compression"], "br")
        self.assertLess(r["stored"], len(txt) // 10)
        self.assertEqual(self.ax.ler("a.txt"), txt)
        cubo = stl_cubo()
        r = self.ax.gravar("c.stl", cubo)
        self.assertEqual(r["compression"], "mesh")
        self.assertEqual(r["sha256"], hashlib.sha256(r["canonical"] or cubo).hexdigest())
        self.assertEqual(malha.medidas(self.ax.ler("c.stl"))[0], 12)
        self.ax.excluir("c.stl")
        self.assertIsNone(self.ax.meta("c.stl"))

    def test_nome_invalido(self):
        with self.assertRaises(Exception):
            self.ax.gravar("../x.jpg", b"1")


@unittest.skipUnless(TEM_JS, "Node.js ou o app em JavaScript não encontrados")
class AnexosConvivencia(unittest.TestCase):
    def js(self, acao, arg=None):
        r = subprocess.run(["node", os.path.join(AQUI, "js", "convivencia.js"), JS, self.arquivo, acao] + ([json.dumps(arg)] if arg is not None else []),
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.arquivo = os.path.join(self.dir, "c.db")
        self.js("init")
        self.st = Store(SqliteDriver(self.arquivo), "PY")
        self.ax = Anexos(self.st)

    def tearDown(self):
        self.st.db.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_python_grava_js_le_e_vice_versa(self):
        stl = open(STL_REAL, "rb").read() if os.path.exists(STL_REAL) else stl_cubo()
        for nome, dados in (("py.stl", stl), ("py.jpg", png())):
            r = self.ax.gravar(nome, dados)
            saida = os.path.join(self.dir, "saida")
            m = self.js("fileGet", {"name": nome, "path": saida})
            self.assertEqual(open(saida, "rb").read(), r["canonical"] or dados)
            self.assertEqual(m["meta"]["sha256"], r["sha256"])
        entrada = os.path.join(self.dir, "entrada")
        for nome, dados in (("js.stl", stl), ("js.txt", ("texto " * 30000).encode())):
            open(entrada, "wb").write(dados)
            meta = self.js("filePut", {"name": nome, "path": entrada})
            lido = self.ax.ler(nome)
            self.assertEqual(hashlib.sha256(lido).hexdigest(), meta["sha256"])
            if nome.endswith(".txt"):
                self.assertEqual(lido, dados)


class Paginas4(unittest.TestCase):
    def setUp(self):
        self.app, self.st, self.d = preparar()
        self.n = Navegador(self.app)
        self.n.entrar("admin")
        self.p = self.st.salvar("patients", {"name": "Joana Lima", "phone": "(21) 99999-1234", "anamnesis": {}, "gallery": [], "docs": []})

    # ---------- galeria ----------
    def test_galeria_e_3d(self):
        url = f"/pacientes/{self.p['id']}/galeria"
        tok = self.n.token(self.n.get(url).get_data(as_text=True))
        r = self.n.c.post(url + "/enviar", data={"_csrf": tok, "arquivos": [(io.BytesIO(png(2400, 1200)), "foto.png"), (io.BytesIO(stl_cubo()), "arcada.stl"),
                                                                             (io.BytesIO(b"%PDF-1.4 teste"), "exame.pdf")]},
                          content_type="multipart/form-data")
        self.assertIn(r.status_code, (200, 302))
        gal = self.st.get("patients", self.p["id"])["gallery"]
        self.assertEqual(sorted(x["kind"] for x in gal), ["arquivo", "img", "stl"])
        img = next(x for x in gal if x["kind"] == "img")
        self.assertTrue(img["thumb"].startswith("data:image/jpeg;base64,"))
        from PIL import Image
        foto = self.n.c.get(f"{url}/{img['id']}/arquivo")
        self.assertEqual(Image.open(io.BytesIO(foto.data)).size, (1600, 800))
        stl = next(x for x in gal if x["kind"] == "stl")
        self.assertEqual(stl["triangles"], 12)
        self.assertEqual(self.n.c.get(f"{url}/{stl['id']}/arquivo").data[80:84], struct.pack("<I", 12))
        self.assertIn("stl-viewer.js", self.n.get(f"/pacientes/{self.p['id']}/3d?ids={stl['id']}").get_data(as_text=True))
        pdf = next(x for x in gal if x["kind"] == "arquivo")
        self.assertIn("attachment", self.n.c.get(f"{url}/{pdf['id']}/arquivo?baixar=1").headers.get("Content-Disposition", ""))
        self.n.post(f"{url}/{stl['id']}/excluir", de=url)
        self.assertEqual(len(self.st.get("patients", self.p["id"])["gallery"]), 2)
        self.assertIsNone(self.app.config["ANEXOS"].meta(stl["file"]))
        # recepção só consulta o prontuário: vê a galeria, mas não envia nem exclui
        n2 = Navegador(self.app)
        n2.entrar("recepcao")
        self.assertEqual(n2.get(url).status_code, 200)
        n2.post(f"{url}/{img['id']}/excluir", de=url)
        self.assertEqual(len(self.st.get("patients", self.p["id"])["gallery"]), 2)

    # ---------- documentos ----------
    def test_documento_com_modelo(self):
        t = self.st.salvar("templates", {"title": "Atestado", "body": "Atesto que {{paciente}} esteve em {{clinica}} em {{data}}."})
        url = f"/pacientes/{self.p['id']}/documentos/novo?modelo={t['id']}"
        html = self.n.get(url).get_data(as_text=True)
        self.assertIn("Atesto que Joana Lima esteve em Instituto Teste", html)
        self.n.post(url, {"title": "Atestado", "text": "Atesto que Joana Lima compareceu.", "dentistId": self.d["id"]})
        docs = self.st.get("patients", self.p["id"])["docs"]
        self.assertEqual(len(docs), 1)
        imp = self.n.get(f"/pacientes/{self.p['id']}/documentos/{docs[0]['id']}/imprimir").get_data(as_text=True)
        self.assertIn("Atesto que Joana Lima compareceu.", imp)

    # ---------- receitas ----------
    def _rx(self, itens, **k):
        url = f"/pacientes/{self.p['id']}/receitas/nova"
        tok = self.n.token(self.n.get(url).get_data(as_text=True))
        rx = {"dentistId": self.d["id"], "date": "2026-11-05", "layout": "duas", "items": itens, **k}
        return self.n.c.post(url, data={"_csrf": tok, "dados": json.dumps(rx)})

    def test_receitas(self):
        amox = {"id": "1", "g": "Amoxicilina", "a": "500 mg", "qtd": "21 cápsulas", "pos": "1 cápsula de 8/8 h por 7 dias", "uso": "oral", "tipo": "antimicrobiano"}
        dipi = {"id": "2", "g": "Dipirona", "a": "500 mg", "qtd": "10 comprimidos", "pos": "se dor", "uso": "oral", "tipo": "simples"}
        r = self._rx([amox, dipi])
        self.assertEqual(r.status_code, 400)
        erros = " ".join(r.get_json()["erros"])
        self.assertIn("endereço completo e telefone da clínica", erros)
        self.assertIn("informe a idade", erros)
        cl = self.st.clinica()
        self.st.salvar("clinic", {**cl, "address": "Rua A, 1 - Centro", "phone": "(21) 3333-4444", "city": "Rio de Janeiro/RJ"})
        r = self._rx([amox, dipi], idade="40", sexo="F")
        self.assertTrue(r.get_json()["ok"], r.get_data(as_text=True))
        rx = self.st.listar("prescriptions")[0]
        self.assertEqual(rx["kinds"], "antimicrobiano")
        imp = self.n.get(r.get_json()["imprimir"]).get_data(as_text=True)
        self.assertIn("21 (vinte e uma) cápsulas", imp)
        self.assertIn("1ª via", imp)
        self.assertEqual(self.st.get("patients", self.p["id"])["sex"], "F")
        # controle especial: CPF e endereço do paciente
        diaz = {"id": "3", "g": "Diazepam", "a": "5 mg", "qtd": "10 comprimidos", "pos": "1 à noite", "uso": "oral", "tipo": "controle"}
        erros = " ".join(self._rx([diaz]).get_json()["erros"])
        self.assertIn("CPF válido", erros)
        self.assertIn("endereço completo do paciente", erros)
        r = self._rx([{**diaz, "tipo": "notificacao"}])
        self.assertIn("Notificação de Receita", " ".join(r.get_json()["erros"]))

    def test_regras_receita(self):
        self.assertEqual(receitas.qtd_extenso("2 frascos"), "2 (dois) frascos")
        self.assertEqual(receitas.qtd_extenso("200 ml"), "200 (duzentos) ml")
        docs = receitas.documentos([{"tipo": "controle"}] * 4 + [{"tipo": "simples"}])
        self.assertEqual([(d["kind"], len(d["items"])) for d in docs], [("controle", 3), ("controle", 1), ("simples", 1)])

    # ---------- pré-consulta ----------
    def test_pre_consulta(self):
        perg = [self.st.salvar("anamnesisModel", {"q": "Tem alergia a algum medicamento?", "type": "yesno"}),
                self.st.salvar("anamnesisModel", {"q": "Toma algum remédio?", "type": "text"})]
        cl = self.st.clinica()
        self.st.salvar("clinic", {**cl, "formUrl": "https://alebuco.github.io/pre-consulta/", "whatsapp": "21988887777",
                                  "waPreConsulta": "Olá {{paciente}}! {{link}}"})
        r = self.n.post(f"/pacientes/{self.p['id']}/pre-consulta/enviar", {"via": "copy"}, de=f"/pacientes/{self.p['id']}/pre-consulta")
        lnk = re.search(r"https://alebuco\.github\.io/pre-consulta/#c=[A-Za-z0-9.!]+", self.n.ultimo).group(0)
        cfg = json.loads(pc.b64d(lnk.split("#c=")[1]))
        self.assertEqual((cfg["n"], cfg["wa"], len(cfg["q"])), ("Joana Lima", "5521988887777", 2))
        p = self.st.get("patients", self.p["id"])
        self.assertEqual(p["preConsulta"]["status"], "enviado")
        if TEM_JS:   # o formulário do site (JavaScript) lê o link do Python
            js = "const b64d=(s)=>{s=s.replace(/\\./g,'+').replace(/!/g,'/');while(s.length%4)s+='=';return decodeURIComponent(escape(atob(s)));};" \
                 "process.stdout.write(b64d(process.argv[1]))"
            self.assertEqual(json.loads(subprocess.run(["node", "-e", js, lnk.split("#c=")[1]], capture_output=True, text=True).stdout)["n"], "Joana Lima")
        # resposta como o site gera (b64e do JavaScript)
        resp = {"v": 1, "t": p["preConsulta"]["token"], "ts": "2026-11-05T13:00:00.000Z", "qx": "Dor no dente",
                "d": {"name": "Joana Lima", "cpf": "52998224725", "birth": "1985-03-02", "phone": "21999991234", "email": "joana@exemplo.com"},
                "a": ["sim", "Losartana"], "o": ["Penicilina", ""]}
        texto = json.dumps(resp, ensure_ascii=False)
        if TEM_JS:
            js = "const b64e=(s)=>btoa(unescape(encodeURIComponent(s))).replace(/\\+/g,'.').replace(/\\//g,'!').replace(/=+$/,'');process.stdout.write(b64e(process.argv[1]))"
            cod = subprocess.run(["node", "-e", js, texto], capture_output=True, text=True).stdout
            self.assertEqual(cod, pc.b64e(texto))
        else:
            cod = pc.b64e(texto)
        msg = f"*Pré-consulta*\nPaciente: Joana Lima\n\nCódigo para o sistema da clínica (não apague):\n#ODPC1:{cod}#"
        self.n.post("/pre-consulta/importar", {"mensagem": msg})
        self.assertIn("Penicilina", self.n.ultimo)
        self.assertIn('value="cpf"', self.n.ultimo)
        self.n.post("/pre-consulta/aplicar", {"mensagem": msg, "campo": ["cpf", "birth", "email"], "alertas": "1"}, de="/pre-consulta/importar")
        p = self.st.get("patients", self.p["id"])
        self.assertEqual((p["cpf"], p["birth"], p["email"]), ("529.982.247-25", "1985-03-02", "joana@exemplo.com"))
        self.assertEqual(p["anamnesis"][perg[0]["id"]], "sim")
        self.assertEqual(p["anamnesis"][perg[0]["id"] + "_obs"], "Penicilina")
        self.assertEqual(p["anamnesis"]["_queixa"], "Dor no dente")
        self.assertIn("Tem alergia a algum medicamento (Penicilina)", p["notes"])
        self.assertEqual(p["preConsulta"]["status"], "respondido")
        self.n.post("/pre-consulta/importar", {"mensagem": "sem código"})
        self.assertIn("Não encontrei o código", self.n.ultimo)

    def test_primeira_consulta_oferece_pre_consulta(self):
        r = self.n.post("/agenda/nova", {"date": "2026-12-01", "time": "09:00", "duration": "30", "type": "consulta", "patientId": self.p["id"],
                                         "dentistId": self.d["id"], "status": "agendado"})
        self.assertIn("/pre-consulta", r.headers["Location"])
        r = self.n.post("/agenda/nova", {"date": "2026-12-08", "time": "09:00", "duration": "30", "type": "retorno", "patientId": self.p["id"],
                                         "dentistId": self.d["id"], "status": "agendado"})
        self.assertNotIn("/pre-consulta", r.headers["Location"])

    # ---------- limpar ----------
    def test_limpar(self):
        ex = self.st.salvar("patients", {"name": "Carla Mendes", "phone": "(11) 99999-0001", "gallery": [{"id": "g1", "file": "g1.jpg", "kind": "img"}]})
        self.app.config["ANEXOS"].gravar("g1.jpg", png())
        self.st.salvar("appointments", {"patientId": ex["id"], "date": "2026-11-10", "time": "10:00", "type": "consulta", "dentistId": self.d["id"]})
        self.st.salvar("finance", {"patientId": ex["id"], "type": "receita", "desc": "Consulta", "value": 100, "due": "2026-11-10"})
        alug = self.st.salvar("finance", {"type": "despesa", "desc": "Aluguel do consultório", "value": 3500, "due": "2026-11-05"})
        real = self.st.salvar("finance", {"type": "despesa", "desc": "Aluguel do consultório", "value": 4200, "due": "2026-11-05"})
        dex = self.st.salvar("dentists", {"name": "Dra. Ana Souza", "cro": "CRO-SP 00000"})
        n2 = Navegador(self.app)
        n2.entrar("recepcao")
        self.assertEqual(n2.get("/configuracoes/limpar/").status_code in (302, 403), True)
        html = self.n.get("/configuracoes/limpar/").get_data(as_text=True)
        self.assertIn(f'value="{ex["id"]}" checked', html)
        self.assertNotIn(f'value="{self.p["id"]}" checked', html)
        self.assertIn(f'value="finance:{alug["id"]}" checked', html)
        self.assertNotIn(f'value="finance:{real["id"]}" checked', html)
        self.n.post("/configuracoes/limpar/", {"paciente": [ex["id"]], "outro": [f"finance:{alug['id']}", f"dentists:{dex['id']}"]})
        self.assertIsNotNone(self.st.get("patients", ex["id"]))            # sem a confirmação nada sai
        self.n.post("/configuracoes/limpar/", {"paciente": [ex["id"]], "outro": [f"finance:{alug['id']}", f"dentists:{dex['id']}"], "confirmar": "EXCLUIR"},
                    follow_redirects=True)
        self.assertIsNone(self.st.get("patients", ex["id"]))
        self.assertEqual([f["id"] for f in self.st.listar("finance")], [real["id"]])
        self.assertEqual(self.st.listar("appointments"), [])
        self.assertIsNone(self.st.get("dentists", dex["id"]))
        self.assertIsNotNone(self.st.get("patients", self.p["id"]))
        self.assertIsNone(self.app.config["ANEXOS"].meta("g1.jpg"))

    def test_limpar_mantem_dentista_em_uso(self):
        db = {"patients": [], "dentists": [{"id": "d", "name": "Dr. Bruno Lima", "cro": "CRO-SP 00001"}],
              "appointments": [{"id": "a", "patientId": "p", "dentistId": "d"}], "users": []}
        dele, _, ficou = limpar.operacoes(db, [], [("dentists", "d")])
        self.assertEqual(dele, {})
        self.assertIn("Dr. Bruno Lima", ficou[0])


@unittest.skipUnless(TEM_JS, "Node.js ou o app em JavaScript não encontrados")
class LimparIgualAoJS(unittest.TestCase):
    def test_mesmo_plano(self):
        db = {"patients": [{"id": "1", "name": "Carla  Mendes", "phone": "(11) 99999-0001"}, {"id": "2", "name": "Diego Ferreira", "phone": "x"},
                           {"id": "3", "name": "Ana"}],
              "finance": [{"id": "f1", "desc": "Compra de resina composta", "value": 640, "due": "2026-01-02", "type": "despesa"},
                          {"id": "f2", "desc": "Luz", "value": "80", "due": "2026-01-03", "paid": True}, {"id": "f3", "patientId": "1", "value": 1}],
              "appointments": [{"id": "a1", "type": "bloqueio", "notes": "Almoço", "time": "12:00", "date": "2026-01-01"}],
              "stock": [{"id": "s1", "name": "Resina composta A2"}], "prosthetists": [{"id": "x", "name": "Seu Zé", "lab": "Laboratório Exemplo"}],
              "dentists": [{"id": "d1", "name": "Dra. Ana Souza", "cro": "CRO-SP 00000"}]}
        js = f"const L=require({json.dumps(os.path.join(JS, 'src', 'limpar.js'))});process.stdout.write(JSON.stringify(L.plan(JSON.parse(process.argv[1]))))"
        esperado = json.loads(subprocess.run(["node", "-e", js, json.dumps(db)], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(limpar.plano(db), esperado)


if __name__ == "__main__":
    unittest.main()
