"""Testes da etapa 3: procedimentos, modelos, configurações, próteses, estoque e usuários/perfis."""
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from odontodesk import seguranca, tempo  # noqa: E402
from test_web import Navegador, preparar  # noqa: E402


class Etapa3(unittest.TestCase):
    def setUp(self):
        self.app, self.st, self.d = preparar()
        self.n = Navegador(self.app)
        self.n.entrar("admin")
        self.p = self.st.salvar("patients", {"name": "Joana Lima", "anamnesis": {}, "gallery": [], "docs": []})

    # ---------- procedimentos ----------
    def test_procedimentos(self):
        self.n.post("/procedimentos/novo", {"source": "TUSS", "code": "8100", "name": "Consulta", "category": "Clínico", "price": "150,00"})
        self.assertIn("Código TUSS tem 8 dígitos (tem 4)", self.n.ultimo)
        self.n.post("/procedimentos/novo", {"source": "SUS", "code": "0307010031", "name": "Restauração", "category": "Dentística", "price": "80"})
        self.assertEqual(self.st.listar("procedures")[0]["code"], "03.07.01.003-1")   # formato SIGTAP
        self.n.post("/procedimentos/novo", {"source": "SUS", "code": "03.07.01.003-1", "name": "Outra", "category": "", "price": "1"})
        self.assertIn("já está em", self.n.ultimo)                                      # código repetido pede confirmação
        self.n.post("/procedimentos/novo", {"source": "", "code": "x", "name": "Clareamento", "category": "Estética", "price": "1.000,00"})
        cl = next(p for p in self.st.listar("procedures") if p["name"] == "Clareamento")
        self.assertEqual((cl["code"], cl["price"]), ("", 1000.0))
        self.n.post("/procedimentos/reajuste", {"pct": "10"}, de="/procedimentos/")
        self.assertEqual(sorted(p["price"] for p in self.st.listar("procedures")), [88.0, 1100.0])
        self.n.get("/procedimentos/?q=03070")
        self.assertIn("Restauração", self.n.ultimo)
        self.assertNotIn("Clareamento", self.n.ultimo)

    # ---------- modelos ----------
    def test_modelos_e_permissao(self):
        self.n.post("/modelos/novo", {"title": "Atestado", "body": "Atesto que {{paciente}}..."})
        t = self.st.listar("templates")[0]
        self.assertEqual(t["body"], "Atesto que {{paciente}}...")
        n2 = Navegador(self.app)
        n2.entrar("recepcao")          # documentos: só consulta
        self.assertIn("disabled", n2.get(f"/modelos/{t['id']}").get_data(as_text=True))
        r = n2.post(f"/modelos/{t['id']}", {"_v": "1", "title": "X", "body": "Y"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.st.get("templates", t["id"])["title"], "Atestado")

    # ---------- configurações ----------
    def test_configuracoes(self):
        cl = self.st.clinica()
        self.n.post("/configuracoes/clinica", {"_v": str(cl["_v"]), "name": "Instituto", "cnpj": "11.222.333/0001-80", "start": "08:00", "end": "18:00", "slot": "30"}, de="/configuracoes/")
        self.assertIn("CNPJ inválido", self.n.ultimo)
        self.n.post("/configuracoes/clinica", {"_v": str(cl["_v"]), "name": "Instituto Ciaco", "cnpj": "12abc34501de35", "phone": "2133334444", "start": "08:00",
                                                "end": "19:00", "slot": "20"}, de="/configuracoes/")
        cl = self.st.clinica()
        self.assertEqual((cl["name"], cl["cnpj"], cl["phone"], cl["slot"], cl["end"]), ("Instituto Ciaco", "12.ABC.345/01DE-35", "(21) 3333-4444", 20, "19:00"))
        self.assertEqual(len(cl["profiles"]), 4)   # o resto da configuração é preservado
        self.n.post("/configuracoes/dentista", {"name": "Dra. Bia", "cro": "CRO-RJ 2", "commission": "35"}, de="/configuracoes/")
        self.assertIn("Dra. Bia", [d["name"] for d in self.st.listar("dentists")])
        self.n.post("/configuracoes/anamnese", {"q": "É fumante?", "type": "yesno"}, de="/configuracoes/")
        q = self.st.listar("anamnesisModel")[0]
        self.n.post("/configuracoes/anamnese", {"remover": q["id"]}, de="/configuracoes/")
        self.assertEqual(self.st.listar("anamnesisModel"), [])
        self.n.post("/configuracoes/pre-consulta", {"_v": str(self.st.clinica()["_v"]), "whatsapp": "21999990000", "preMode": "perguntar", "formUrl": "https://alebuco.github.io/pre-consulta/", "waPreConsulta": "Olá"}, de="/configuracoes/")
        self.assertEqual(self.st.clinica()["formUrl"], "https://alebuco.github.io/pre-consulta/")
        dados = json.loads(self.n.get("/configuracoes/backup").get_data(as_text=True))
        self.assertEqual(dados["patients"][0]["name"], "Joana Lima")
        self.assertNotIn("_v", dados["patients"][0])

    # ---------- próteses ----------
    def _novo_trabalho(self, **extra):
        pr = self.st.salvar("prosthetists", {"name": "Carlos", "lab": "Lab Sorriso", "phone": "(21) 98888-0000", "days": 5})
        dados = {"patientId": self.p["id"], "dentistId": self.d["id"], "prosthetistId": pr["id"], "type": "Provisório", "teeth": "11", "shade": "A2",
                 "value": "300,00", "status": "andamento", "payDue": "2026-12-20", "toFin": "1",
                 "ph_id": ["", ""], "ph_name": ["Moldagem", "Instalação"], "ph_sent": ["", ""], "ph_due": ["", ""], "ph_received": ["", ""], "ph_note": ["", ""], **extra}
        self.n.post("/proteses/novo", dados)
        return self.st.listar("labWorks")[0], pr

    def test_proteses_fases_e_financeiro(self):
        w, pr = self._novo_trabalho()
        self.assertEqual([p["name"] for p in w["phases"]], ["Moldagem", "Instalação"])
        f = self.st.get("finance", w["financeId"])
        self.assertEqual((f["type"], f["value"], f["due"], f["paid"], f["category"]), ("despesa", 300.0, "2026-12-20", False, "Laboratório"))
        self.assertIn("A enviar", self.n.get("/proteses/").get_data(as_text=True))
        # enviar e receber as fases
        h = tempo.hoje()
        self.n.post(f"/proteses/{w['id']}/movimento", {"_v": "1", "sent": h, "due": tempo.soma_dias(h, 5)}, de=f"/proteses/{w['id']}/movimento")
        self.assertIn("No laboratório", self.n.get("/proteses/?filtro=lab").get_data(as_text=True))
        self.n.post(f"/proteses/{w['id']}/movimento", {"_v": "2", "received": tempo.soma_dias(h, -1)}, de=f"/proteses/{w['id']}/movimento")
        self.assertIn("antes do envio", self.n.ultimo)
        self.n.post(f"/proteses/{w['id']}/movimento", {"_v": "2", "received": h}, de=f"/proteses/{w['id']}/movimento")
        w = self.st.get("labWorks", w["id"])
        self.assertEqual((w["phases"][0]["sent"], w["phases"][0]["received"]), (h, h))
        self.assertIn("ordem de serviço", self.n.get(f"/proteses/{w['id']}/ordem").get_data(as_text=True).lower())
        # fase com recebimento antes do envio é recusada no formulário
        self.n.post(f"/proteses/{w['id']}", {"_v": str(w["_v"]), "patientId": self.p["id"], "prosthetistId": pr["id"], "type": "Provisório", "value": "300", "status": "andamento",
                                             "toFin": "1", "ph_id": [w["phases"][0]["id"]], "ph_name": ["Moldagem"], "ph_sent": ["2026-11-10"], "ph_due": [""],
                                             "ph_received": ["2026-11-01"], "ph_note": [""]})
        self.assertIn("recebimento antes do envio", self.n.ultimo)
        # pagar → financeiro baixado junto
        self.n.post(f"/proteses/{w['id']}", {"_v": str(w["_v"]), "patientId": self.p["id"], "prosthetistId": pr["id"], "type": "Provisório", "value": "300", "status": "andamento",
                                             "toFin": "1", "paid": "1", "paidDate": h, "ph_id": [p["id"] for p in w["phases"]], "ph_name": [p["name"] for p in w["phases"]],
                                             "ph_sent": [p["sent"] for p in w["phases"]], "ph_due": [p["due"] for p in w["phases"]],
                                             "ph_received": [p["received"] for p in w["phases"]], "ph_note": ["", ""]})
        f = self.st.get("finance", w["financeId"])
        self.assertEqual((f["paid"], f["paidDate"]), (True, h))
        # excluir o trabalho tira a conta a pagar
        self.n.post(f"/proteses/{w['id']}/excluir", {}, de=f"/proteses/{w['id']}")
        self.assertIsNone(self.st.get("finance", w["financeId"]))
        self.assertIsNone(self.st.get("labWorks", w["id"]))

    def test_protetico_com_trabalho_nao_e_excluido(self):
        w, pr = self._novo_trabalho()
        self.n.post(f"/proteses/proteticos/{pr['id']}", {"excluir": "1"}, de=f"/proteses/proteticos/{pr['id']}")
        self.assertIsNotNone(self.st.get("prosthetists", pr["id"]))

    # ---------- estoque ----------
    def test_estoque_lotes_e_saldo(self):
        self.n.post("/estoque/novo", {"name": "Resina A2", "unit": "seringa", "cost": "89,00", "qty": "3", "min": "2", "expiry": "2027-01-10", "barcode": "7891234567895"})
        s = self.st.listar("stock")[0]
        self.assertEqual((s["qty"], s["min"], s["cost"]), (3, 2, 89))
        self.assertEqual(self.st.listar("stockMoves")[0]["note"], "Estoque inicial")
        self.n.post(f"/estoque/{s['id']}/entrada", {"_v": "1", "qty": "5", "date": tempo.hoje(), "expiry": "2026-12-01", "lot": "L9", "note": "NF 123", "expense": "1"})
        s = self.st.get("stock", s["id"])
        self.assertEqual(s["qty"], 8)
        self.assertEqual(self.st.listar("finance")[0]["value"], 445.0)        # 5 × 89 vira despesa
        self.n.post(f"/estoque/{s['id']}/saida", {"_v": "2", "qty": "20", "date": tempo.hoje()})
        self.assertIn("maior que o saldo", self.n.ultimo)
        self.n.post(f"/estoque/{s['id']}/saida", {"_v": "2", "qty": "4", "date": tempo.hoje(), "note": "uso"})
        html = self.n.get(f"/estoque/{s['id']}").get_data(as_text=True)
        # PVPS: a saída consumiu primeiro o lote que vence antes (L9, dez/2026): ficam 1 do L9 e 3 de jan/2027
        self.assertRegex(html, r"01/12/2026.*L9.*1 seringa")
        self.assertRegex(html, r"10/01/2027.*3 seringa")
        # corrigir a entrada para baixo deixaria o saldo negativo
        ent = next(m for m in self.st.listar("stockMoves") if m.get("lot") == "L9")
        self.n.post(f"/estoque/movimento/{ent['id']}", {"excluir": "1"}, de=f"/estoque/movimento/{ent['id']}")
        self.assertIn("ficaria negativo", self.n.ultimo)                     # saldo 4 − entrada de 5 = −1: recusado
        self.assertEqual(self.st.get("stock", s["id"])["qty"], 4)
        self.n.get("/estoque/historico")
        self.assertIn("NF 123", self.n.ultimo)
        self.assertIn("Resina A2", self.n.get("/estoque/?q=7891234567895").get_data(as_text=True))   # busca pelo código de barras

    # ---------- usuários ----------
    def test_usuarios_e_perfis(self):
        self.n.post("/usuarios/novo", {"name": "Bia Souza", "login": "Bia", "profileId": "recepcao", "dentistId": "", "pass": "fraca"})
        self.assertIn("pelo menos 8", self.n.ultimo)
        self.n.post("/usuarios/novo", {"name": "Bia Souza", "login": "Bia", "profileId": "recepcao", "dentistId": "", "pass": "abcdef12"})
        self.assertIn("senha: abcdef12", self.n.ultimo)
        u = next(x for x in self.st.listar("users") if x["login"] == "bia")
        self.assertTrue(u["mustChange"])
        n2 = Navegador(self.app)
        n2.entrar("bia", "abcdef12")
        self.assertIn("Crie uma senha nova", n2.ultimo)                        # primeiro acesso: troca obrigatória
        n2.post("/trocar-senha", {"nova": "NovaSenha77", "nova2": "NovaSenha77"}, follow_redirects=True)
        self.assertFalse(self.st.get("users", u["id"])["mustChange"])
        # não dá para tirar o último administrador
        adm = next(x for x in self.st.listar("users") if x["login"] == "admin")
        self.n.post(f"/usuarios/{adm['id']}", {"name": "Admin", "login": "admin", "profileId": "recepcao", "active": "1"})
        self.assertIn("administrador", self.n.ultimo)                         # último administrador / próprio acesso
        self.assertEqual(self.st.get("users", adm["id"])["profileId"], "admin")
        # permissões: tirar o financeiro da recepção
        self.n.post("/usuarios/perfis", {"perm_recepcao_financeiro": "0"}, de="/usuarios/")
        self.assertEqual(self.st.clinica()["profiles"][2]["perms"]["financeiro"], 0)
        self.assertEqual(n2.get("/financeiro/").status_code, 403)
        # novo tipo de acesso copiando outro
        self.n.post("/usuarios/perfis/novo", {"name": "Gerente", "copy": "admin"}, de="/usuarios/")
        g = self.st.clinica()["profiles"][-1]
        self.assertEqual((g["name"], g["perms"]["config"]), ("Gerente", 2))
        # redefinir senha
        self.n.post(f"/usuarios/{u['id']}/senha", {}, de="/usuarios/")
        self.assertIn("Senha redefinida", self.n.ultimo)
        self.assertTrue(self.st.get("users", u["id"])["mustChange"])
        self.assertEqual(n2.get("/").status_code, 302)                          # sessão dela encerrada
        # código de recuperação
        self.n.post("/usuarios/seguranca", {"codigo": "1"}, de="/usuarios/")
        import re
        cod = re.search(r'recovery-code">([A-Z0-9-]+)<', self.n.ultimo).group(1)
        self.assertTrue(seguranca.confere_senha(cod.replace("-", ""), self.st.clinica()["recovery"]))
        # só o administrador vê usuários
        n3 = Navegador(self.app)
        n3.entrar("recepcao")
        self.assertEqual(n3.get("/usuarios/").status_code, 403)

    def test_bloqueio_por_inatividade(self):
        cl = self.st.clinica()
        cl["lockMinutes"] = 5
        self.st.salvar("clinic", cl)
        with self.n.c.session_transaction() as s:
            s["t"] = time.time() - 6 * 60
        r = self.n.get("/", follow_redirects=True)
        self.assertIn("sem uso", r.get_data(as_text=True))

    def test_paginas_abrem(self):
        for url in ["/procedimentos/", "/procedimentos/novo", "/modelos/", "/modelos/novo", "/configuracoes/", "/proteses/", "/proteses/novo", "/proteses/proteticos",
                    "/proteses/proteticos/novo", "/estoque/", "/estoque/novo", "/estoque/historico", "/usuarios/", "/usuarios/novo"]:
            self.assertEqual(self.n.get(url).status_code, 200, url)


if __name__ == "__main__":
    unittest.main()
