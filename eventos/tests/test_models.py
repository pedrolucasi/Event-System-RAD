from datetime import date

from django.core.exceptions import ValidationError

from ..models import Atividade, Evento, InscricaoAtividade, Sala, intervalos_sobrepostos
from .base import CenarioTestCase, quando


class SobreposicaoDeIntervalosTests(CenarioTestCase):
    """A pergunta comum a RN2 e RN3: dois intervalos se sobrepõem?"""

    def test_todos_os_casos_de_sobreposicao_sao_detectados(self):
        # Referência: 9h às 11h.
        casos = {
            "começa antes e termina dentro": (quando(11, 8), quando(11, 10)),
            "começa dentro e termina depois": (quando(11, 10), quando(11, 12)),
            "contido na referência": (quando(11, 9, 30), quando(11, 10)),
            "contém a referência": (quando(11, 8), quando(11, 12)),
            "idêntico": (quando(11, 9), quando(11, 11)),
        }
        for nome, (inicio, fim) in casos.items():
            with self.subTest(nome):
                self.assertTrue(intervalos_sobrepostos(quando(11, 9), quando(11, 11), inicio, fim))
                self.assertTrue(intervalos_sobrepostos(inicio, fim, quando(11, 9), quando(11, 11)))

    def test_intervalos_que_se_encostam_ou_sao_separados_nao_conflitam(self):
        casos = {
            "termina quando a referência começa": (quando(11, 8), quando(11, 9)),
            "começa quando a referência termina": (quando(11, 11), quando(11, 12)),
            "em outro dia": (quando(12, 9), quando(12, 11)),
        }
        for nome, (inicio, fim) in casos.items():
            with self.subTest(nome):
                self.assertFalse(intervalos_sobrepostos(quando(11, 9), quando(11, 11), inicio, fim))


class ValidacaoDaSalaTests(CenarioTestCase):
    def test_sala_com_capacidade_negativa_e_recusada(self):
        with self.assertRaises(ValidationError) as ctx:
            Sala(nome="Sala X", capacidade=-1).full_clean()
        self.assertIn("capacidade", ctx.exception.message_dict)

    def test_sala_sem_nome_e_recusada(self):
        with self.assertRaises(ValidationError) as ctx:
            Sala(nome="", capacidade=10).full_clean()
        self.assertIn("nome", ctx.exception.message_dict)

    def test_sala_valida_passa_na_validacao(self):
        Sala(nome="Sala X", bloco="C", capacidade=10).full_clean()


class ValidacaoDoEventoTests(CenarioTestCase):
    def novo_evento(self, **campos):
        dados = {"nome": "Novo", "data_inicio": date(2026, 12, 1), "data_fim": date(2026, 12, 2), "organizador": self.ana}
        return Evento(**{**dados, **campos})

    def test_evento_com_fim_antes_do_inicio_e_recusado(self):
        with self.assertRaises(ValidationError) as ctx:
            self.novo_evento(data_fim=date(2026, 11, 30)).full_clean()
        self.assertIn("data_fim", ctx.exception.message_dict)

    def test_evento_sem_nome_e_recusado(self):
        with self.assertRaises(ValidationError) as ctx:
            self.novo_evento(nome="").full_clean()
        self.assertIn("nome", ctx.exception.message_dict)

    def test_encurtar_evento_que_deixaria_atividade_de_fora_e_recusado(self):
        self.semana.data_fim = date(2026, 11, 10)
        with self.assertRaisesMessage(ValidationError, "Abertura"):
            self.semana.full_clean()


class ValidacaoDaAtividadeTests(CenarioTestCase):
    def nova_atividade(self, **campos):
        dados = {
            "evento": self.semana, "titulo": "Nova", "tipo": Atividade.Tipo.PALESTRA, "responsavel": "R",
            "sala": self.auditorio, "inicio": quando(10, 9), "fim": quando(10, 10),
        }
        return Atividade(**{**dados, **campos})

    def test_atividade_valida_passa_na_validacao(self):
        self.nova_atividade().full_clean()

    def test_atividade_com_fim_antes_do_inicio_e_recusada(self):
        with self.assertRaises(ValidationError) as ctx:
            self.nova_atividade(inicio=quando(10, 10), fim=quando(10, 9)).full_clean()
        self.assertEqual(ctx.exception.message_dict["fim"], ["O fim da atividade precisa ser depois do início."])

    def test_atividade_com_fim_igual_ao_inicio_e_recusada(self):
        with self.assertRaises(ValidationError) as ctx:
            self.nova_atividade(inicio=quando(10, 10), fim=quando(10, 10)).full_clean()
        self.assertIn("fim", ctx.exception.message_dict)

    def test_atividade_sem_titulo_e_recusada(self):
        with self.assertRaises(ValidationError) as ctx:
            self.nova_atividade(titulo="").full_clean()
        self.assertIn("titulo", ctx.exception.message_dict)

    def test_atividade_com_tipo_inexistente_e_recusada(self):
        with self.assertRaises(ValidationError) as ctx:
            self.nova_atividade(tipo="OFICINA").full_clean()
        self.assertIn("tipo", ctx.exception.message_dict)

    def test_atividade_fora_do_periodo_do_evento_e_recusada(self):
        with self.assertRaisesMessage(ValidationError, "dentro do período do evento"):
            self.nova_atividade(inicio=quando(14, 9), fim=quando(14, 10)).full_clean()

    def test_rn3_sala_ocupada_em_qualquer_caso_de_sobreposicao_e_recusada(self):
        # Abertura ocupa a Sala 101 de 9h às 11h do dia 11.
        casos = {
            "parcial antes": (quando(11, 8), quando(11, 10)),
            "parcial depois": (quando(11, 10), quando(11, 12)),
            "contida": (quando(11, 9, 30), quando(11, 10)),
            "contém": (quando(11, 8), quando(11, 12)),
            "idêntica": (quando(11, 9), quando(11, 11)),
        }
        for nome, (inicio, fim) in casos.items():
            with self.subTest(nome), self.assertRaises(ValidationError) as ctx:
                self.nova_atividade(sala=self.sala101, inicio=inicio, fim=fim).full_clean()
            self.assertIn("já está ocupada", ctx.exception.message_dict["sala"][0])

    def test_rn3_sala_ocupada_por_atividade_de_outro_evento_e_recusada(self):
        # Ciência (Jornada) ocupa o Auditório; a nova atividade é da Semana.
        with self.assertRaises(ValidationError) as ctx:
            self.nova_atividade(sala=self.auditorio, inicio=quando(11, 10), fim=quando(11, 11)).full_clean()
        self.assertIn("Ciência aberta", ctx.exception.message_dict["sala"][0])

    def test_rn3_mesma_sala_em_horario_encostado_e_aceita(self):
        self.nova_atividade(sala=self.sala101, inicio=quando(11, 11), fim=quando(11, 12)).full_clean()

    def test_editar_atividade_sem_mudar_horario_nao_conflita_com_ela_mesma(self):
        self.abertura.titulo = "Abertura oficial"
        self.abertura.full_clean()

    def test_trocar_para_sala_menor_que_os_inscritos_e_recusado(self):
        for usuario in (self.carla, self.diego, self.elisa):
            self.inscrever_na_atividade(usuario, self.abertura)
        self.abertura.sala = self.lab
        self.abertura.inicio, self.abertura.fim = quando(12, 14), quando(12, 15)
        with self.assertRaisesMessage(ValidationError, "comporta 2 pessoas"):
            self.abertura.full_clean()


class VagasRestantesTests(CenarioTestCase):
    def test_vagas_restantes_descontam_os_inscritos_da_capacidade_da_sala(self):
        self.inscrever_na_atividade(self.carla, self.django)
        self.assertEqual(self.django.vagas_restantes(), 1)

    def test_anotacao_com_vagas_bate_com_o_calculo_do_model(self):
        self.inscrever_na_atividade(self.carla, self.django)
        self.inscrever_na_atividade(self.diego, self.django)
        anotada = Atividade.objects.com_vagas().get(pk=self.django.pk)
        self.assertEqual(anotada.vagas, 0)
        self.assertEqual(Atividade.objects.get(pk=self.django.pk).vagas_restantes(), 0)


class CascataNoModelTests(CenarioTestCase):
    def test_rn5_excluir_inscricao_no_evento_remove_as_inscricoes_nas_atividades(self):
        inscricao = self.inscrever_na_atividade(self.carla, self.abertura).inscricao_evento
        self.inscrever_na_atividade(self.carla, self.django)
        inscricao.delete()
        self.assertFalse(InscricaoAtividade.objects.filter(inscricao_evento__participante=self.carla).exists())
