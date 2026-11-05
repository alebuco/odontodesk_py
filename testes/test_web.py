"""Testes das páginas (navegador simulado do Flask)."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from odontodesk import seguranca, tempo  # noqa: E402
from odontodesk.app import create_app  # noqa: E402
from odontodesk.dados.drivers import SqliteDriver  # noqa: E402
from odontodesk.dados.store import Store  # noqa: E402


def preparar():
    st = Store(SqliteDriver(":memory:"), "WEB-PYTHON")
    st.criar_tabelas()
    st.salvar("clinic", {"name": "Instituto Teste", "start": "08:00", "end": "12:00", "slot": 30, "profiles": seguranca.perfis_padrao()})
    d = st.salvar("dentists", {"name": "Dr. Alexandre", "cro": "CRO-RJ 1", "commission": 40})
    for nome, login, perfil in (("Admin", "admin", "admin"), ("Recepção", "recepcao", "recepcao"), ("Dentista", "dentista", "dentista")):
        st.salvar("users", {"name": nome, "login": login, "profileId": perfil, "active": True, "mustChange": False,
                            "dentistId": d["id"] if perfil == "dentista" else "", **seguranca.hash_senha("Senha1234")})
    app = create_app({"chave_secreta": "teste", "testes": True}, store=st)
    return app, st, d


class Navegador:
    def __init__(self, app):
        self.c = app.test_client()

    def token(self, html):
        m = re.search(r'name="_csrf" value="([^"]+)"', html)
        return m.group(1) if m else ""

    def get(self, url, **k):
        r = self.c.get(url, **k)
        self.ultimo = r.get_data(as_text=True)
        return r

    def post(self, url, dados=None, de=None, **k):
        html = self.get(de or url).get_data(as_text=True) if (de or url) else ""
        dados = {**(dados or {}), "_csrf": self.token(html)}
        r = self.c.post(url, data=dados, **k)
        self.ultimo = r.get_data(as_text=True)
        return r

    def entrar(self, login, senha="Senha1234"):
        return self.post("/entrar", {"login": login, "senha": senha}, follow_redirects=True)


class Paginas(unittest.TestCase):
    def setUp(self):
        self.app, self.st, self.d = preparar()
        self.n = Navegador(self.app)

    def test_login_e_bloqueio(self):
        r = self.n.get("/")
        self.assertEqual(r.status_code, 302)
        r = self.n.entrar("admin", "errada")
        self.assertIn("Usuário ou senha incorretos", self.n.ultimo)
        r = self.n.entrar("ADMIN")
        self.assertIn("Olá, Admin", self.n.ultimo)
        self.assertEqual(self.st.get("users", self.st.listar("users")[0]["id"])["login"], "admin")

    def test_formulario_sem_token_e_recusado(self):
        self.n.entrar("admin")
        r = self.n.c.post("/pacientes/novo", data={"name": "X"})
        self.assertEqual(r.status_code, 400)

    def test_paciente_validacao_e_cadastro(self):
        self.n.entrar("recepcao")
        self.n.post("/pacientes/novo", {"name": "Maria", "cpf": "529.982.247-24", "phone": "2199999000", "usesSocial": "n"})
        self.assertIn("CPF inválido", self.n.ultimo)
        self.assertIn("Celular precisa de 9 dígitos", self.n.ultimo)
        r = self.n.post("/pacientes/novo", {"name": "Maria", "cpf": "52998224725", "phone": "21999990000", "usesSocial": "s", "socialName": "Mari",
                                            "cep": "20040002", "street": "Rua A", "number": "10", "city": "Rio", "uf": "RJ"}, follow_redirects=True)
        p = self.st.listar("patients")[0]
        self.assertEqual((p["cpf"], p["phone"], p["socialName"], p["address"]), ("529.982.247-25", "(21) 99999-0000", "Mari", "Rua A, 10 - Rio/RJ - CEP 20040-002"))
        self.assertEqual((p["anamnesis"], p["gallery"], p["docs"]), ({}, [], []))
        self.assertIn("Mari", self.n.ultimo)
        # CPF repetido
        self.n.post("/pacientes/novo", {"name": "Outra", "cpf": "529.982.247-25", "usesSocial": "n"})
        self.assertIn("CPF já cadastrado para Maria", self.n.ultimo)
        # busca por telefone sem pontuação
        self.n.get("/pacientes/?q=999990000")
        self.assertIn("Mari", self.n.ultimo)

    def test_edicao_conflito(self):
        self.n.entrar("admin")
        p = self.st.salvar("patients", {"name": "Ana"})
        html = self.n.get(f"/pacientes/{p['id']}/editar").get_data(as_text=True)
        tok = self.n.token(html)
        outro = dict(self.st.get("patients", p["id"]))
        outro["phone"] = "(21) 3333-4444"
        self.st.salvar("patients", outro)  # outro computador alterou enquanto isso
        r = self.n.c.post(f"/pacientes/{p['id']}/editar", data={"_csrf": tok, "_v": "1", "name": "Ana Paula", "usesSocial": "n"}, follow_redirects=True)
        self.assertIn("alterado em outro computador", r.get_data(as_text=True))
        self.assertEqual(self.st.get("patients", p["id"])["name"], "Ana")

    def test_agenda_dia_semana_e_choque(self):
        self.n.entrar("recepcao")
        p = self.st.salvar("patients", {"name": "Joana"})
        h = tempo.hoje()
        self.n.post("/agenda/nova", {"date": h, "time": "09:00", "duration": "60", "type": "consulta", "patientId": p["id"], "dentistId": self.d["id"], "status": "agendado"},
                    de=f"/agenda/nova?data={h}")
        self.assertEqual(len(self.st.listar("appointments")), 1)
        # choque de horário com o mesmo dentista
        self.n.post("/agenda/nova", {"date": h, "time": "09:30", "duration": "30", "type": "consulta", "patientId": p["id"], "dentistId": self.d["id"], "status": "agendado"},
                    de=f"/agenda/nova?data={h}")
        self.assertIn("já tem horário marcado", self.n.ultimo)
        self.assertEqual(len(self.st.listar("appointments")), 1)
        self.n.post("/agenda/nova", {"date": h, "time": "09:30", "duration": "30", "type": "encaixe", "patientId": p["id"], "dentistId": self.d["id"], "status": "agendado", "mesmo_assim": "1"},
                    de=f"/agenda/nova?data={h}")
        self.assertEqual(len(self.st.listar("appointments")), 2)
        self.n.get(f"/agenda/?data={h}")
        self.assertIn("Joana", self.n.ultimo)
        self.assertIn("+ marcar 11:30", self.n.ultimo)
        self.n.get(f"/agenda/?data={h}&modo=semana")
        self.assertIn("Joana", self.n.ultimo)
        a = self.st.listar("appointments", ordem="hora")[0]
        self.n.post(f"/agenda/{a['id']}/situacao", {"status": "confirmado"}, de=f"/agenda/{a['id']}")
        self.assertEqual(self.st.get("appointments", a["id"])["status"], "confirmado")

    def test_permissoes_por_perfil(self):
        self.n.entrar("dentista")
        self.assertEqual(self.n.get("/financeiro/").status_code, 403)
        self.assertNotIn(">Financeiro<", self.n.get("/").get_data(as_text=True))
        self.assertEqual(self.n.get("/financeiro/periodos").status_code, 403)
        n2 = Navegador(self.app)
        n2.entrar("recepcao")
        self.assertEqual(n2.get("/financeiro/").status_code, 200)
        self.assertNotIn("Períodos contábeis", n2.ultimo)
        self.assertEqual(n2.get("/financeiro/periodos").status_code, 403)

    def test_financeiro_lancamentos_e_periodo_fechado(self):
        self.n.entrar("admin")
        h = tempo.hoje()
        mes_passado = tempo.soma_dias(h[:8] + "01", -10)
        self.n.post("/financeiro/novo", {"type": "receita", "desc": "Consulta antiga", "value": "1.200,50", "due": mes_passado, "method": "Pix",
                                         "paid": "1", "paidDate": mes_passado, "repeat": "1"}, de="/financeiro/novo")
        self.n.post("/financeiro/novo", {"type": "receita", "desc": "Parcela", "value": "100", "due": mes_passado, "method": "Pix", "repeat": "3"}, de="/financeiro/novo")
        lanc = self.st.listar("finance", ordem="vencimento")
        self.assertEqual(len(lanc), 4)
        antiga = next(f for f in lanc if f["desc"] == "Consulta antiga")
        self.assertEqual(antiga["value"], 1200.5)
        self.assertEqual(sorted(f["desc"] for f in lanc if f["desc"].startswith("Parcela")), ["Parcela (1/3)", "Parcela (2/3)", "Parcela (3/3)"])
        # fecha o período até o fim do mês passado
        fim = tempo.soma_dias(h[:8] + "01", -1)
        self.n.post("/financeiro/periodos", {"ate": fim}, de=f"/financeiro/periodos?ate={fim}", follow_redirects=True)
        self.assertIn("Período fechado até", self.n.ultimo)
        cl = self.st.clinica()
        self.assertEqual(cl["finClosings"][0]["until"], fim)       # mesmo campo que o app em JavaScript usa
        self.assertEqual(cl["finClosings"][0]["rec"], 1200.5)
        # lançamento fechado: só consulta, não altera nem exclui
        self.n.get(f"/financeiro/{antiga['id']}")
        self.assertIn("só consulta", self.n.ultimo)
        self.n.post(f"/financeiro/{antiga['id']}", {"type": "receita", "desc": "mudou", "value": "1", "due": mes_passado, "paid": "1", "paidDate": mes_passado})
        self.n.post(f"/financeiro/{antiga['id']}/excluir", {}, de=f"/financeiro/{antiga['id']}")
        self.assertEqual(self.st.get("finance", antiga["id"])["desc"], "Consulta antiga")
        # pagamento com data dentro do período fechado é recusado
        p1 = next(f for f in lanc if f["desc"] == "Parcela (1/3)")
        self.n.post(f"/financeiro/{p1['id']}", {"type": "receita", "desc": "Parcela (1/3)", "value": "100", "due": p1["due"], "method": "Pix", "paid": "1", "paidDate": mes_passado})
        self.assertIn("Período contábil fechado", self.n.ultimo)
        self.assertFalse(self.st.get("finance", p1["id"])["paid"])
        # a conta em aberto do mês passado pode ser baixada hoje
        self.n.post(f"/financeiro/{p1['id']}/baixar", {}, de="/financeiro/")
        self.assertEqual(self.st.get("finance", p1["id"])["paidDate"], h)
        # reabrir
        cid = cl["finClosings"][0]["id"]
        self.n.post(f"/financeiro/periodos/{cid}/reabrir", {}, de="/financeiro/periodos")
        self.assertEqual(self.st.clinica()["finClosings"], [])
        self.assertTrue(any("REABERTO" in a["action"] for a in self.st.auditoria()))

    def test_paginas_abrem_sem_erro(self):
        self.n.entrar("admin")
        p = self.st.salvar("patients", {"name": "Zé", "birth": "1980-02-03"})
        f = self.st.salvar("finance", {"type": "receita", "desc": "R", "value": 10, "due": tempo.hoje(), "paid": True, "paidDate": tempo.hoje(), "patientId": p["id"]})
        for url in ["/", "/sobre", "/pacientes/", f"/pacientes/{p['id']}", f"/pacientes/{p['id']}?aba=consultas", f"/pacientes/{p['id']}?aba=pagamentos",
                    f"/pacientes/{p['id']}/editar", "/agenda/", "/agenda/?modo=semana", "/agenda/nova", "/financeiro/", "/financeiro/?filtro=vencidos",
                    "/financeiro/novo", f"/financeiro/{f['id']}", f"/financeiro/{f['id']}/recibo", "/financeiro/periodos", "/financeiro/csv", "/trocar-senha"]:
            r = self.n.get(url)
            self.assertEqual(r.status_code, 200, url)
        self.assertIn("Recebemos de <b>Zé</b>", self.n.get(f"/financeiro/{f['id']}/recibo").get_data(as_text=True))

    def test_primeiro_acesso_banco_vazio(self):
        st = Store(SqliteDriver(":memory:"))
        st.criar_tabelas()
        app = create_app({"chave_secreta": "x", "testes": True}, store=st)
        n = Navegador(app)
        r = n.get("/entrar")
        self.assertEqual(r.headers["Location"], "/primeiro-acesso")
        n.post("/primeiro-acesso", {"clinica": "Clínica Nova", "nome": "Dra. Bia", "login": "bia", "senha": "Sorriso2026", "senha2": "Sorriso2026"}, follow_redirects=True)
        self.assertIn("Olá, Dra.", n.ultimo)
        self.assertEqual(st.clinica()["profiles"][0]["id"], "admin")

    def test_troca_de_senha_encerra_outras_sessoes(self):
        self.n.entrar("admin")
        outro = Navegador(self.app)
        outro.entrar("admin")
        self.n.post("/trocar-senha", {"atual": "Senha1234", "nova": "NovaSenha99", "nova2": "NovaSenha99"}, follow_redirects=True)
        self.assertIn("Senha alterada", self.n.ultimo)
        self.assertEqual(outro.get("/").status_code, 302)  # a outra sessão saiu


if __name__ == "__main__":
    unittest.main()
