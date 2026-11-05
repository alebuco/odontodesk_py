"""Testes do prontuário: anamnese, evolução (24 h, adendos, versões), odontograma/planos e histórico."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from odontodesk import tempo  # noqa: E402
from test_web import Navegador, preparar  # noqa: E402


class Prontuario(unittest.TestCase):
    def setUp(self):
        self.app, self.st, self.d = preparar()
        self.q1 = self.st.salvar("anamnesisModel", {"q": "Tem alergia a algum medicamento?", "type": "yesno"})
        self.q2 = self.st.salvar("anamnesisModel", {"q": "Outras observações", "type": "text"})
        self.proc = self.st.salvar("procedures", {"name": "Restauração em resina", "price": 220, "code": "85100099", "source": "TUSS"})
        self.p = self.st.salvar("patients", {"name": "Joana Lima", "phone": "(21) 99999-0000", "anamnesis": {}, "gallery": [{"id": "g", "file": "g.jpg"}], "docs": []})
        self.n = Navegador(self.app)
        self.n.entrar("admin")

    def test_anamnese(self):
        url = f"/pacientes/{self.p['id']}/anamnese"
        self.n.post(url, {"_v": "1", "_queixa": "Dor no dente", self.q1["id"]: "sim", self.q1["id"] + "_obs": "Dipirona", self.q2["id"]: "nada"})
        an = self.st.get("patients", self.p["id"])["anamnesis"]
        self.assertEqual((an["_queixa"], an[self.q1["id"]], an[self.q1["id"] + "_obs"], an[self.q2["id"]], an["_updated"]),
                         ("Dor no dente", "sim", "Dipirona", "nada", tempo.hoje()))
        self.assertEqual(self.st.get("patients", self.p["id"])["gallery"][0]["file"], "g.jpg")  # o resto do cadastro fica intacto
        r = self.n.get(url + "/imprimir").get_data(as_text=True)
        self.assertIn("Dipirona", r)
        # dentista sem permissão de prontuário completo? (perfil dentista tem 2; auxiliar tem 1 = só consulta)
        self.st.salvar("users", {"name": "Aux", "login": "aux", "profileId": "auxiliar", "active": True, **__import__("odontodesk.seguranca", fromlist=["x"]).hash_senha("Senha1234")})
        n2 = Navegador(self.app)
        n2.entrar("aux")
        self.assertIn("disabled", n2.get(url).get_data(as_text=True))
        n2.post(url, {"_v": "2", "_queixa": "mudou"})
        self.assertEqual(self.st.get("patients", self.p["id"])["anamnesis"]["_queixa"], "Dor no dente")

    def test_evolucao_regras(self):
        hoje = tempo.hoje()
        a = self.st.salvar("appointments", {"date": hoje, "time": "09:00", "duration": 30, "patientId": self.p["id"], "dentistId": self.d["id"], "type": "consulta", "status": "confirmado"})
        url = f"/pacientes/{self.p['id']}/evolucao"
        self.assertIn("ainda sem evolução", self.n.get(url).get_data(as_text=True))
        self.n.post(url + "/nova", {"appointmentId": a["id"], "date": hoje, "dentistId": self.d["id"], "text": "Restauração 36 MO.\nAnestesia."}, de=url + "/nova")
        e = self.st.listar("evolutions")[0]
        self.assertEqual((e["authorName"], e["text"], e["appointmentId"]), ("Admin", "Restauração 36 MO.\nAnestesia.", a["id"]))
        self.assertTrue(e["createdAt"].endswith("Z"))                                   # mesmo formato do app em JavaScript
        self.assertEqual(self.st.get("appointments", a["id"])["status"], "atendido")    # consulta passa a atendida
        # data no futuro
        self.n.post(url + "/nova", {"date": tempo.soma_dias(hoje, 1), "text": "x"}, de=url + "/nova")
        self.assertIn("não pode ser no futuro", self.n.ultimo)
        # correção pelo autor guarda a versão anterior
        self.n.post(f"/evolucao/{e['id']}/editar", {"_v": "1", "date": hoje, "dentistId": self.d["id"], "appointmentId": a["id"], "text": "Restauração 36 MOD."})
        e2 = self.st.get("evolutions", e["id"])
        self.assertEqual((e2["text"], e2["history"][0]["text"]), ("Restauração 36 MOD.", "Restauração 36 MO.\nAnestesia."))
        self.assertIn("corrigido 1×", self.n.get(url).get_data(as_text=True))
        # outro usuário não corrige; só acrescenta adendo
        n2 = Navegador(self.app)
        n2.entrar("dentista")
        self.assertNotIn(f"/evolucao/{e['id']}/editar", n2.get(url).get_data(as_text=True))
        n2.post(f"/evolucao/{e['id']}/editar", {"_v": "2", "date": hoje, "text": "apagou tudo"}, de=url)
        self.assertEqual(self.st.get("evolutions", e["id"])["text"], "Restauração 36 MOD.")
        n2.post(f"/evolucao/{e['id']}/adendo", {"_v": "2", "text": "Paciente retornou sem dor."})
        ad = self.st.get("evolutions", e["id"])["addenda"]
        self.assertEqual((ad[0]["text"], ad[0]["authorName"]), ("Paciente retornou sem dor.", "Dentista"))
        # depois de 24 h nem o autor corrige ou exclui
        velha = self.st.get("evolutions", e["id"])
        velha["createdAt"] = "2026-01-01T10:00:00.000Z"
        self.st.salvar("evolutions", velha)
        self.n.post(f"/evolucao/{e['id']}/excluir", {}, de=url)
        self.assertIsNotNone(self.st.get("evolutions", e["id"]))
        self.assertIn("Paciente retornou sem dor.", self.n.get(url + "/imprimir").get_data(as_text=True))
        self.assertIn("Versão 1", self.n.get(f"/evolucao/{e['id']}/versoes").get_data(as_text=True))

    def test_plano_odontograma_orcamento_e_cobranca(self):
        url = f"/pacientes/{self.p['id']}/tratamentos"
        self.n.post(url + "/novo", {"title": "Plano A", "dentistId": self.d["id"], "dentition": "permanente"}, de=url)
        t = self.st.listar("treatments")[0]
        self.n.post(f"/tratamentos/{t['id']}/item", {"_v": "1", "tooth": "36", "faces": "M,O,X", "procId": self.proc["id"]}, de=url)
        self.n.post(f"/tratamentos/{t['id']}/item", {"_v": "2", "tooth": "", "faces": "", "procId": self.proc["id"]}, de=url)
        t = self.st.get("treatments", t["id"])
        self.assertEqual([(i["tooth"], i["faces"], i["price"], i["code"]) for i in t["items"]], [(36, ["M", "O"], 220, "85100099"), ("", [], 220, "85100099")])
        html = self.n.get(url).get_data(as_text=True)
        self.assertIn('data-tooth="36"', html)
        self.assertIn('class="plan"', html)                # faces planejadas pintadas
        # valores, desconto e procedimento realizado
        i1, i2 = t["items"]
        self.n.post(f"/tratamentos/{t['id']}/itens", {"_v": "3", f"st_{i1['id']}": "realizado", f"pr_{i1['id']}": "250,00", f"st_{i2['id']}": "planejado",
                                                      f"pr_{i2['id']}": "220,00", "discount": "70,00"}, de=url)
        t = self.st.get("treatments", t["id"])
        self.assertEqual((t["items"][0]["status"], t["items"][0]["doneAt"], t["items"][0]["price"], t["discount"]), ("realizado", tempo.hoje(), 250.0, 70.0))
        orc = self.n.get(f"/tratamentos/{t['id']}/orcamento").get_data(as_text=True)
        self.assertIn("R$ 400,00", orc)                     # 250 + 220 - 70
        self.assertIn("wa.me/5521999990000", self.n.get(url).get_data(as_text=True))
        # aprovar: entrada + 3 parcelas, a última ajusta os centavos
        self.n.post(f"/tratamentos/{t['id']}/aprovar", {"entry": "100,00", "n": "3", "first": "2026-12-10", "method": "Pix"}, de=f"/tratamentos/{t['id']}/aprovar")
        fin = sorted(self.st.listar("finance"), key=lambda f: f["due"])
        self.assertEqual([(f["value"], f["paid"], f["due"]) for f in fin],
                         [(100.0, True, tempo.hoje()), (100.0, False, "2026-12-10"), (100.0, False, "2027-01-10"), (100.0, False, "2027-02-10")])
        self.assertTrue(all(f["treatmentId"] == t["id"] and f["patientId"] == self.p["id"] for f in fin))
        self.assertEqual(self.st.get("treatments", t["id"])["status"], "aprovado")
        self.n.post(f"/tratamentos/{t['id']}/concluir", {}, de=url)
        t = self.st.get("treatments", t["id"])
        self.assertEqual((t["status"], {i["status"] for i in t["items"]}), ("concluido", {"realizado"}))
        hist = self.n.get(f"/pacientes/{self.p['id']}/historico").get_data(as_text=True)
        self.assertIn("Procedimento realizado: Restauração em resina (dente 36)", hist)

    def test_parcelas_com_centavos(self):
        t = self.st.salvar("treatments", {"patientId": self.p["id"], "title": "P", "status": "orcamento", "discount": 0, "createdAt": tempo.hoje(), "dentistId": "",
                                          "items": [{"id": "i", "tooth": "", "faces": [], "procId": "", "name": "X", "price": 100, "status": "planejado"}]})
        self.n.post(f"/tratamentos/{t['id']}/aprovar", {"entry": "0", "n": "3", "first": "2026-12-01", "method": "Pix"}, de=f"/tratamentos/{t['id']}/aprovar")
        self.assertEqual(sorted(f["value"] for f in self.st.listar("finance")), [33.33, 33.33, 33.34])

    def test_paginas_do_prontuario_abrem(self):
        pid = self.p["id"]
        for url in [f"/pacientes/{pid}", f"/pacientes/{pid}/anamnese", f"/pacientes/{pid}/evolucao", f"/pacientes/{pid}/evolucao/nova",
                    f"/pacientes/{pid}/tratamentos", f"/pacientes/{pid}/historico", f"/pacientes/{pid}/evolucao/imprimir"]:
            self.assertEqual(self.n.get(url).status_code, 200, url)
        n2 = Navegador(self.app)
        n2.entrar("recepcao")      # recepção: prontuário só consulta
        self.assertEqual(n2.get(f"/pacientes/{pid}/evolucao").status_code, 200)
        self.assertNotIn("+ Nova evolução", n2.ultimo)
        r = n2.get(f"/pacientes/{pid}/evolucao/nova", follow_redirects=True)   # só consulta: volta com aviso
        self.assertIn("só de consulta", r.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
