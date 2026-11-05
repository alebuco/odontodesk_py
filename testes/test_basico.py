"""Testes da camada de dados, das validações e das senhas.   Rodar:  python -m unittest discover -s testes -v"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from odontodesk import br, seguranca  # noqa: E402
from odontodesk.dados.drivers import SqliteDriver  # noqa: E402
from odontodesk.dados.store import Conflito, Store  # noqa: E402


def novo_store():
    st = Store(SqliteDriver(":memory:"), "TESTE")
    st.criar_tabelas()
    return st


class Dados(unittest.TestCase):
    def test_grava_le_e_preserva_campos_extras(self):
        st = novo_store()
        p = st.salvar("patients", {"name": "Ana", "birth": "1990-01-02", "anamnesis": {"q1": "sim"}, "gallery": [{"id": "g", "file": "g.jpg"}]})
        g = st.get("patients", p["id"])
        self.assertEqual((g["name"], g["birth"], g["anamnesis"], g["gallery"][0]["file"], g["_v"]), ("Ana", "1990-01-02", {"q1": "sim"}, "g.jpg", 1))
        g["phone"] = "(21) 99999-0000"
        g2 = st.salvar("patients", g)
        self.assertEqual(g2["_v"], 2)
        self.assertEqual(st.get("patients", p["id"])["gallery"][0]["file"], "g.jpg")

    def test_conflito_quando_outro_alterou(self):
        st = novo_store()
        p = st.salvar("patients", {"name": "Ana"})
        a, b = dict(st.get("patients", p["id"])), dict(st.get("patients", p["id"]))
        a["phone"] = "1"
        st.salvar("patients", a)
        b["phone"] = "2"
        with self.assertRaises(Conflito) as cm:
            st.salvar("patients", b, acao="não deve aparecer no histórico")
        self.assertEqual(cm.exception.atual["phone"], "1")
        self.assertFalse(any("não deve" in x["action"] for x in st.auditoria()))

    def test_exclusao_logica_e_feed(self):
        st = novo_store()
        p = st.salvar("patients", {"name": "Ana"})
        st.excluir("patients", p["id"], acao="Paciente excluído", usuario="Adm")
        self.assertIsNone(st.get("patients", p["id"]))
        self.assertEqual([x["op"] for x in st.alteracoes_desde(0)], ["put", "del"])
        self.assertEqual(st.auditoria()[0]["action"], "Paciente excluído")

    def test_clinica_e_ordenados(self):
        st = novo_store()
        st.salvar("clinic", {"name": "Clínica X", "profiles": seguranca.perfis_padrao()})
        self.assertEqual(st.clinica()["name"], "Clínica X")
        st.salvar("dentists", {"name": "B"})
        st.salvar("dentists", {"name": "A"})
        self.assertEqual([d["name"] for d in st.listar("dentists")], ["B", "A"])  # mantém a ordem de cadastro

    def test_valores_e_datas(self):
        st = novo_store()
        f = st.salvar("finance", {"type": "receita", "desc": "x", "value": 1234.5, "due": "2026-11-05", "paid": True, "paidDate": "2026-11-05"})
        g = st.get("finance", f["id"])
        self.assertEqual((g["value"], g["paid"], g["paidDate"]), (1234.5, True, "2026-11-05"))


class Validacoes(unittest.TestCase):
    def test_cpf(self):
        self.assertTrue(br.cpf_valido("529.982.247-25"))
        self.assertFalse(br.cpf_valido("529.982.247-24"))
        self.assertFalse(br.cpf_valido("111.111.111-11"))
        self.assertEqual(br.cpf_formata("52998224725"), "529.982.247-25")
        self.assertEqual(br.cpf_erro("5299"), "CPF incompleto (4 de 11 dígitos)")

    def test_cnpj_inclusive_alfanumerico(self):
        self.assertTrue(br.cnpj_valido("11.222.333/0001-81"))
        self.assertFalse(br.cnpj_valido("11.222.333/0001-80"))
        self.assertTrue(br.cnpj_valido("12.ABC.345/01DE-35"))
        self.assertEqual(br.doc_formata("12abc34501de35"), "12.ABC.345/01DE-35")
        self.assertEqual(br.doc_tipo("52998224725"), "cpf")

    def test_telefone(self):
        self.assertEqual(br.telefone_formata("21999990000"), "(21) 99999-0000")
        self.assertEqual(br.telefone_formata("+55 21 3333-4444"), "(21) 3333-4444")
        self.assertEqual(br.telefone_erro("2099999000"), "DDD 20 não existe")
        self.assertEqual(br.telefone_erro("2199999000"), "Celular precisa de 9 dígitos após o DDD")
        self.assertEqual(br.telefone_erro("21999990000"), "")

    def test_cep_e_endereco(self):
        self.assertEqual(br.cep_formata("20040002"), "20040-002")
        self.assertEqual(br.endereco_formata({"street": "Rua A", "number": "10", "district": "Centro", "city": "Rio", "uf": "RJ", "cep": "20040002"}),
                         "Rua A, 10 - Centro, Rio/RJ - CEP 20040-002")


class Senhas(unittest.TestCase):
    def test_senha_criada_no_app_javascript_confere(self):
        # gerado com o mesmo PBKDF2 do app em JavaScript (Node crypto), senha "Sorriso2026"
        u = {"hash": "Tl0bux3BOYwWSSlbtju37JdMo4rN+rjB3g6xTN2Av9I=", "salt": "MDEyMzQ1Njc4OWFiY2RlZg==", "iter": 210000}
        self.assertTrue(seguranca.confere_senha("Sorriso2026", u))
        self.assertFalse(seguranca.confere_senha("sorriso2026", u))

    def test_regras_da_senha(self):
        self.assertTrue(seguranca.problema_senha("curta1"))
        self.assertTrue(seguranca.problema_senha("semnumeros"))
        self.assertTrue(seguranca.problema_senha("maria2026x", "maria"))
        self.assertEqual(seguranca.problema_senha("Sorriso2026", "ana"), "")

    def test_permissoes(self):
        cl = {"profiles": seguranca.perfis_padrao()}
        rec, den, adm = {"profileId": "recepcao"}, {"profileId": "dentista"}, {"profileId": "admin"}
        self.assertEqual(seguranca.nivel(rec, cl, "financeiro"), 2)
        self.assertEqual(seguranca.nivel(den, cl, "financeiro"), 0)
        self.assertEqual(seguranca.nivel(rec, cl, "_admin"), 0)
        self.assertEqual(seguranca.nivel(adm, cl, "_admin"), 2)
        self.assertEqual(seguranca.normaliza_login("  João.Silva "), "joao.silva")


if __name__ == "__main__":
    unittest.main()
