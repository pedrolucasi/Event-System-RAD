from datetime import date

from ..forms import AtividadeForm, EventoForm
from ..models import Atividade
from .base import CenarioTestCase, quando


class EventoFormTests(CenarioTestCase):
    def test_formulario_nao_oferece_o_campo_organizador(self):
        self.assertNotIn("organizador", EventoForm().fields)

    def test_dados_validos_chegam_ao_cleaned_data(self):
        form = EventoForm(data={
            "nome": "Hackathon", "descricao": "48 horas", "data_inicio": "2026-12-01",
            "data_fim": "2026-12-02", "inscricoes_abertas": "on",
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["nome"], "Hackathon")
        self.assertEqual(form.cleaned_data["data_inicio"], date(2026, 12, 1))
        self.assertIs(form.cleaned_data["inscricoes_abertas"], True)

    def test_organizador_enviado_no_post_e_ignorado(self):
        form = EventoForm(data={
            "nome": "Hackathon", "data_inicio": "2026-12-01", "data_fim": "2026-12-02",
            "organizador": self.bruno.pk,
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("organizador", form.cleaned_data)

    def test_fim_antes_do_inicio_gera_erro_no_campo_data_fim(self):
        form = EventoForm(data={"nome": "Hackathon", "data_inicio": "2026-12-02", "data_fim": "2026-12-01"})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["data_fim"], ["A data de fim não pode ser anterior à data de início."])


class AtividadeFormTests(CenarioTestCase):
    def formulario(self, **campos):
        dados = {
            "titulo": "Oficina", "tipo": "TREINAMENTO", "descricao": "", "responsavel": "R",
            "sala": self.auditorio.pk, "inicio": "2026-11-10T09:00", "fim": "2026-11-10T10:00",
        }
        return AtividadeForm(data={**dados, **campos}, instance=Atividade(evento=self.semana))

    def test_dados_validos_chegam_ao_cleaned_data(self):
        form = self.formulario()
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["sala"], self.auditorio)
        self.assertEqual(form.cleaned_data["inicio"], quando(10, 9))
        self.assertEqual(form.cleaned_data["tipo"], "TREINAMENTO")

    def test_fim_antes_do_inicio_gera_erro_no_campo_fim(self):
        form = self.formulario(fim="2026-11-10T08:00")
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["fim"], ["O fim da atividade precisa ser depois do início."])

    def test_sala_ocupada_gera_erro_no_campo_sala(self):
        form = self.formulario(sala=self.sala101.pk, inicio="2026-11-11T10:00", fim="2026-11-11T12:00")
        self.assertFalse(form.is_valid())
        self.assertIn("já está ocupada", form.errors["sala"][0])

    def test_fora_do_periodo_gera_erro_geral(self):
        form = self.formulario(inicio="2026-11-20T09:00", fim="2026-11-20T10:00")
        self.assertFalse(form.is_valid())
        self.assertIn("dentro do período do evento", form.non_field_errors()[0])

    def test_titulo_vazio_e_obrigatorio(self):
        form = self.formulario(titulo="")
        self.assertFalse(form.is_valid())
        self.assertIn("titulo", form.errors)
