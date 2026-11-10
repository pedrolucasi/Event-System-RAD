from django.contrib.messages import get_messages
from django.urls import reverse

from ..models import Atividade, Evento, InscricaoAtividade, InscricaoEvento
from .base import CenarioTestCase, quando


def mensagens(resposta):
    return [str(m) for m in get_messages(resposta.wsgi_request)]


class SiteTestCase(CenarioTestCase):
    def post(self, usuario, nome, pk, dados=None):
        self.client.force_login(usuario)
        return self.client.post(reverse(f"eventos:{nome}", args=[pk]), dados or {})


class ProgramacaoPublicaTests(SiteTestCase):
    """RF5: a programação de um evento, aberta ao anônimo."""

    def test_lista_de_eventos_abre_sem_login(self):
        resposta = self.client.get(reverse("eventos:lista"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "eventos/evento_list.html")
        self.assertQuerySetEqual(resposta.context["eventos"], [self.semana, self.jornada, self.fechado])

    def test_programacao_abre_sem_login_com_template_e_contexto(self):
        resposta = self.client.get(reverse("eventos:detalhe", args=[self.semana.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "eventos/evento_detail.html")
        self.assertTemplateUsed(resposta, "base.html")
        self.assertEqual(resposta.context["evento"], self.semana)
        self.assertEqual(
            [a.titulo for a in resposta.context["atividades"]],
            ["Abertura", "Treinamento de Git", "Treinamento de Django"],  # mesmo início: termina antes, vem antes
        )
        self.assertIsNone(resposta.context["inscricao_evento"])

    def test_programacao_ordena_por_horario_e_nao_por_cadastro(self):
        self.criar_atividade(self.semana, "Credenciamento", self.auditorio, quando(10, 8), quando(10, 9))
        resposta = self.client.get(reverse("eventos:detalhe", args=[self.semana.pk]))
        self.assertEqual(resposta.context["atividades"][0].titulo, "Credenciamento")

    def test_programacao_mostra_sala_responsavel_e_vagas_restantes(self):
        self.inscrever_na_atividade(self.carla, self.django)
        resposta = self.client.get(reverse("eventos:detalhe", args=[self.semana.pk]))
        self.assertContains(resposta, "Treinamento de Django")
        self.assertContains(resposta, "Laboratório (B)")
        self.assertContains(resposta, "Responsável")
        self.assertContains(resposta, "1 de 2")
        self.assertContains(resposta, "40 de 40")

    def test_anonimo_ve_convite_para_entrar_e_nenhum_botao_de_inscricao(self):
        resposta = self.client.get(reverse("eventos:detalhe", args=[self.semana.pk]))
        self.assertContains(resposta, "Entre para se inscrever")
        self.assertNotContains(resposta, reverse("eventos:inscrever_evento", args=[self.semana.pk]))

    def test_programacao_de_evento_inexistente_devolve_404(self):
        self.assertEqual(self.client.get(reverse("eventos:detalhe", args=[9999])).status_code, 404)


class AutenticacaoTests(SiteTestCase):
    """RF7: o anônimo vai para o login com next apontando de volta."""

    def test_anonimo_na_agenda_vai_para_login_com_next(self):
        url = reverse("eventos:agenda")
        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")

    def test_anonimo_tentando_se_inscrever_vai_para_login_com_next(self):
        url = reverse("eventos:inscrever_evento", args=[self.semana.pk])
        resposta = self.client.post(url)
        self.assertRedirects(resposta, f"{reverse('login')}?next={url}")
        self.assertFalse(InscricaoEvento.objects.exists())

    def test_anonimo_no_cadastro_de_evento_vai_para_login_com_next(self):
        url = reverse("eventos:criar")
        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")

    def test_conta_recem_cadastrada_e_participante_comum(self):
        self.client.post(reverse("signup"), {
            "username": "novata", "password1": "Uma-senha-boa-123", "password2": "Uma-senha-boa-123",
        })
        self.assertTrue(self.client.login(username="novata", password="Uma-senha-boa-123"))
        self.assertEqual(self.client.get(reverse("eventos:criar")).status_code, 403)


class InscricaoNoEventoTests(SiteTestCase):
    """RF6: efeito no banco, redirect depois do POST e mensagem."""

    def test_inscricao_grava_redireciona_para_o_evento_e_avisa(self):
        resposta = self.post(self.carla, "inscrever_evento", self.semana.pk)
        self.assertRedirects(resposta, reverse("eventos:detalhe", args=[self.semana.pk]))
        self.assertTrue(InscricaoEvento.objects.filter(participante=self.carla, evento=self.semana).exists())
        self.assertEqual(mensagens(resposta), ["Inscrição no evento Semana de Tecnologia realizada."])

    def test_segunda_inscricao_no_mesmo_evento_e_recusada(self):
        self.inscrever_no_evento(self.carla, self.semana)
        resposta = self.post(self.carla, "inscrever_evento", self.semana.pk)
        self.assertRedirects(resposta, reverse("eventos:detalhe", args=[self.semana.pk]))
        self.assertEqual(InscricaoEvento.objects.filter(participante=self.carla).count(), 1)
        self.assertEqual(mensagens(resposta), ["Você já está inscrito neste evento."])

    def test_evento_com_inscricoes_fechadas_recusa(self):
        resposta = self.post(self.carla, "inscrever_evento", self.fechado.pk)
        self.assertFalse(InscricaoEvento.objects.exists())
        self.assertEqual(mensagens(resposta), ["As inscrições deste evento estão fechadas."])

    def test_get_na_inscricao_nao_altera_nada(self):
        self.client.force_login(self.carla)
        resposta = self.client.get(reverse("eventos:inscrever_evento", args=[self.semana.pk]))
        self.assertEqual(resposta.status_code, 405)
        self.assertFalse(InscricaoEvento.objects.exists())


class RegrasNaInscricaoEmAtividadeSiteTests(SiteTestCase):
    """RN1, RN2 e RN4 pela porta HTML."""

    def test_rn4_inscrito_no_evento_consegue_se_inscrever_na_atividade(self):
        self.inscrever_no_evento(self.carla, self.semana)
        resposta = self.post(self.carla, "inscrever_atividade", self.abertura.pk)
        self.assertRedirects(resposta, reverse("eventos:detalhe", args=[self.semana.pk]))
        self.assertEqual(self.inscritos(self.abertura), 1)
        self.assertEqual(mensagens(resposta), ['Inscrição em "Abertura" realizada.'])

    def test_rn4_sem_inscricao_no_evento_e_recusado(self):
        resposta = self.post(self.carla, "inscrever_atividade", self.abertura.pk)
        self.assertEqual(self.inscritos(self.abertura), 0)
        self.assertEqual(mensagens(resposta), ["Inscreva-se no evento antes de escolher atividades."])

    def test_rn4_inscricao_em_outro_evento_nao_vale(self):
        self.inscrever_no_evento(self.carla, self.jornada)
        self.post(self.carla, "inscrever_atividade", self.abertura.pk)
        self.assertEqual(self.inscritos(self.abertura), 0)

    def test_rn1_ultima_vaga_e_ocupada(self):
        self.inscrever_na_atividade(self.carla, self.django)
        self.inscrever_no_evento(self.diego, self.semana)
        self.post(self.diego, "inscrever_atividade", self.django.pk)
        self.assertEqual(self.inscritos(self.django), 2)

    def test_rn1_inscricao_alem_da_capacidade_e_recusada(self):
        self.inscrever_na_atividade(self.carla, self.django)
        self.inscrever_na_atividade(self.diego, self.django)
        self.inscrever_no_evento(self.elisa, self.semana)
        resposta = self.post(self.elisa, "inscrever_atividade", self.django.pk)
        self.assertEqual(self.inscritos(self.django), 2)
        self.assertEqual(mensagens(resposta), ["Atividade lotada: não há mais vagas na sala."])

    def test_rn2_atividades_em_horarios_diferentes_sao_aceitas(self):
        self.inscrever_na_atividade(self.carla, self.abertura)
        self.inscrever_no_evento(self.carla, self.jornada)
        self.post(self.carla, "inscrever_atividade", self.posteres.pk)
        self.assertEqual(InscricaoAtividade.objects.filter(inscricao_evento__participante=self.carla).count(), 2)

    def test_rn2_atividade_simultanea_no_mesmo_evento_e_recusada(self):
        self.inscrever_na_atividade(self.carla, self.django)
        resposta = self.post(self.carla, "inscrever_atividade", self.git.pk)
        self.assertEqual(self.inscritos(self.git), 0)
        self.assertIn("Conflito de horário", mensagens(resposta)[0])

    def test_rn2_atividade_simultanea_em_outro_evento_e_recusada(self):
        self.inscrever_na_atividade(self.carla, self.abertura)
        self.inscrever_no_evento(self.carla, self.jornada)
        resposta = self.post(self.carla, "inscrever_atividade", self.ciencia.pk)
        self.assertEqual(self.inscritos(self.ciencia), 0)
        self.assertIn('Conflito de horário com "Abertura"', mensagens(resposta)[0])


class CancelamentoSiteTests(SiteTestCase):
    """RF6 e RN5 pela porta HTML."""

    def test_cancelar_atividade_libera_a_vaga_e_mantem_o_evento(self):
        inscricao = self.inscrever_na_atividade(self.carla, self.django)
        resposta = self.post(self.carla, "cancelar_atividade", inscricao.pk)
        self.assertRedirects(resposta, reverse("eventos:detalhe", args=[self.semana.pk]))
        self.assertEqual(self.inscritos(self.django), 0)
        self.assertTrue(InscricaoEvento.objects.filter(pk=inscricao.inscricao_evento_id).exists())
        self.assertEqual(mensagens(resposta), ['Inscrição em "Treinamento de Django" cancelada.'])
        self.assertEqual(Atividade.objects.com_vagas().get(pk=self.django.pk).vagas, 2)

    def test_cancelar_volta_para_o_next_informado(self):
        inscricao = self.inscrever_na_atividade(self.carla, self.django)
        resposta = self.post(self.carla, "cancelar_atividade", inscricao.pk, {"next": reverse("eventos:agenda")})
        self.assertRedirects(resposta, reverse("eventos:agenda"))

    def test_rn5_cancelar_evento_remove_as_atividades_dele_e_so_dele(self):
        inscricao = self.inscrever_na_atividade(self.carla, self.abertura).inscricao_evento
        self.inscrever_na_atividade(self.carla, self.django)
        self.inscrever_na_atividade(self.carla, self.posteres)
        resposta = self.post(self.carla, "cancelar_evento", inscricao.pk)
        self.assertRedirects(resposta, reverse("eventos:detalhe", args=[self.semana.pk]))
        self.assertFalse(InscricaoEvento.objects.filter(pk=inscricao.pk).exists())
        self.assertEqual(
            list(InscricaoAtividade.objects.filter(inscricao_evento__participante=self.carla)
                 .values_list("atividade__titulo", flat=True)),
            ["Pôsteres"],
        )
        self.assertIn("cancelada, junto com as atividades dele", mensagens(resposta)[0])

    def test_rn5_ninguem_cancela_evento_de_outra_pessoa(self):
        inscricao = self.inscrever_na_atividade(self.carla, self.abertura).inscricao_evento
        resposta = self.post(self.diego, "cancelar_evento", inscricao.pk)
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(InscricaoEvento.objects.filter(pk=inscricao.pk).exists())
        self.assertEqual(self.inscritos(self.abertura), 1)

    def test_ninguem_cancela_atividade_de_outra_pessoa(self):
        inscricao = self.inscrever_na_atividade(self.carla, self.abertura)
        resposta = self.post(self.diego, "cancelar_atividade", inscricao.pk)
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(InscricaoAtividade.objects.filter(pk=inscricao.pk).exists())


class CadastroDeAtividadeSiteTests(SiteTestCase):
    """RN3 e as validações de período pela porta HTML."""

    def dados(self, **campos):
        return {
            "titulo": "Oficina", "tipo": "TREINAMENTO", "responsavel": "R", "sala": self.sala101.pk,
            "inicio": "2026-11-11T11:00", "fim": "2026-11-11T12:00", **campos,
        }

    def test_rn3_mesma_sala_em_outro_horario_e_aceita(self):
        resposta = self.post(self.ana, "atividade_criar", self.semana.pk, self.dados())
        self.assertRedirects(resposta, reverse("eventos:detalhe", args=[self.semana.pk]))
        self.assertTrue(Atividade.objects.filter(titulo="Oficina", sala=self.sala101).exists())

    def test_rn3_sala_ocupada_no_horario_e_recusada(self):
        resposta = self.post(self.ana, "atividade_criar", self.semana.pk,
                             self.dados(inicio="2026-11-11T10:00", fim="2026-11-11T12:00"))
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Atividade.objects.filter(titulo="Oficina").exists())
        self.assertIn("já está ocupada", resposta.context["form"].errors["sala"][0])

    def test_rn3_sala_ocupada_por_outro_evento_e_recusada(self):
        resposta = self.post(self.ana, "atividade_criar", self.semana.pk,
                             self.dados(sala=self.auditorio.pk, inicio="2026-11-11T10:00", fim="2026-11-11T11:00"))
        self.assertFalse(Atividade.objects.filter(titulo="Oficina").exists())
        self.assertIn("Ciência aberta", resposta.context["form"].errors["sala"][0])

    def test_atividade_fora_do_periodo_e_recusada_com_mensagem(self):
        resposta = self.post(self.ana, "atividade_criar", self.semana.pk,
                             self.dados(inicio="2026-11-20T10:00", fim="2026-11-20T11:00"))
        self.assertFalse(Atividade.objects.filter(titulo="Oficina").exists())
        self.assertContains(resposta, "dentro do período do evento")

    def test_atividade_com_fim_antes_do_inicio_e_recusada_com_mensagem(self):
        resposta = self.post(self.ana, "atividade_criar", self.semana.pk, self.dados(fim="2026-11-11T10:30"))
        self.assertFalse(Atividade.objects.filter(titulo="Oficina").exists())
        self.assertContains(resposta, "O fim da atividade precisa ser depois do início.")


class AutorizacaoSiteTests(SiteTestCase):
    """RF8: cada caso confere a resposta e o banco intacto."""

    def dados_evento(self, **campos):
        return {"nome": "Alterado", "data_inicio": "2026-11-09", "data_fim": "2026-11-13", **campos}

    def test_organizador_cria_evento_e_vira_o_organizador(self):
        self.client.force_login(self.ana)
        resposta = self.client.post(reverse("eventos:criar"), self.dados_evento(nome="Novo", organizador=self.bruno.pk))
        novo = Evento.objects.get(nome="Novo")
        self.assertRedirects(resposta, reverse("eventos:detalhe", args=[novo.pk]))
        self.assertEqual(novo.organizador, self.ana)

    def test_participante_nao_cria_evento(self):
        self.client.force_login(self.carla)
        resposta = self.client.post(reverse("eventos:criar"), self.dados_evento(nome="Novo"))
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(Evento.objects.filter(nome="Novo").exists())

    def test_participante_nao_edita_evento(self):
        resposta = self.post(self.carla, "editar", self.semana.pk, self.dados_evento())
        self.assertEqual(resposta.status_code, 403)
        self.semana.refresh_from_db()
        self.assertEqual(self.semana.nome, "Semana de Tecnologia")

    def test_dono_edita_o_proprio_evento(self):
        resposta = self.post(self.ana, "editar", self.semana.pk, self.dados_evento())
        self.assertRedirects(resposta, reverse("eventos:detalhe", args=[self.semana.pk]))
        self.semana.refresh_from_db()
        self.assertEqual(self.semana.nome, "Alterado")

    def test_organizador_nao_edita_evento_de_outro(self):
        resposta = self.post(self.bruno, "editar", self.semana.pk, self.dados_evento())
        self.assertEqual(resposta.status_code, 403)
        self.semana.refresh_from_db()
        self.assertEqual(self.semana.nome, "Semana de Tecnologia")

    def test_organizador_nao_exclui_evento_de_outro(self):
        resposta = self.post(self.bruno, "excluir", self.semana.pk)
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(Evento.objects.filter(pk=self.semana.pk).exists())

    def test_organizador_nao_cria_atividade_em_evento_de_outro(self):
        resposta = self.post(self.bruno, "atividade_criar", self.semana.pk, {
            "titulo": "Intrusa", "tipo": "PALESTRA", "responsavel": "R", "sala": self.auditorio.pk,
            "inicio": "2026-11-10T09:00", "fim": "2026-11-10T10:00",
        })
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(Atividade.objects.filter(titulo="Intrusa").exists())

    def test_organizador_nao_edita_atividade_de_evento_alheio(self):
        resposta = self.post(self.bruno, "atividade_editar", self.abertura.pk, {"titulo": "Intrusa"})
        self.assertEqual(resposta.status_code, 403)
        self.abertura.refresh_from_db()
        self.assertEqual(self.abertura.titulo, "Abertura")

    def test_organizador_nao_ve_painel_de_evento_alheio(self):
        self.client.force_login(self.bruno)
        resposta = self.client.get(reverse("eventos:painel", args=[self.semana.pk]))
        self.assertEqual(resposta.status_code, 403)

    def test_dono_ve_os_inscritos_no_painel(self):
        self.inscrever_na_atividade(self.carla, self.django)
        self.client.force_login(self.ana)
        resposta = self.client.get(reverse("eventos:painel", args=[self.semana.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "part_carla")


class InterfaceRefleteOPapelTests(SiteTestCase):
    """RF10: a tela não oferece o que o usuário não pode fazer."""

    def botao_inscrever(self, atividade):
        return f'action="{reverse("eventos:inscrever_atividade", args=[atividade.pk])}"'

    def abrir(self, usuario, evento):
        self.client.force_login(usuario)
        return self.client.get(reverse("eventos:detalhe", args=[evento.pk]))

    def test_quem_nao_esta_no_evento_nao_ve_botao_de_atividade(self):
        resposta = self.abrir(self.carla, self.semana)
        self.assertNotContains(resposta, self.botao_inscrever(self.abertura))
        self.assertContains(resposta, "Inscrever-se no evento")

    def test_inscrito_ve_botao_de_atividade_com_vaga(self):
        self.inscrever_no_evento(self.carla, self.semana)
        self.assertContains(self.abrir(self.carla, self.semana), self.botao_inscrever(self.abertura))

    def test_atividade_lotada_nao_oferece_botao(self):
        self.inscrever_na_atividade(self.carla, self.django)
        self.inscrever_na_atividade(self.diego, self.django)
        self.inscrever_no_evento(self.elisa, self.semana)
        resposta = self.abrir(self.elisa, self.semana)
        self.assertNotContains(resposta, self.botao_inscrever(self.django))
        self.assertContains(resposta, "Lotada")

    def test_atividade_conflitante_nao_oferece_botao(self):
        self.inscrever_na_atividade(self.carla, self.abertura)
        self.inscrever_no_evento(self.carla, self.jornada)
        resposta = self.abrir(self.carla, self.jornada)
        self.assertNotContains(resposta, self.botao_inscrever(self.ciencia))
        self.assertContains(resposta, "Conflita com sua agenda")

    def test_editar_e_excluir_aparecem_so_para_o_dono(self):
        url_editar = reverse("eventos:editar", args=[self.semana.pk])
        self.assertContains(self.abrir(self.ana, self.semana), url_editar)
        self.assertNotContains(self.abrir(self.bruno, self.semana), url_editar)


class AgendaSiteTests(SiteTestCase):
    def test_agenda_mostra_so_as_proprias_atividades_em_ordem(self):
        self.inscrever_na_atividade(self.carla, self.posteres)
        self.inscrever_na_atividade(self.carla, self.django)
        self.inscrever_na_atividade(self.carla, self.abertura)
        self.inscrever_na_atividade(self.diego, self.git)
        self.client.force_login(self.carla)
        resposta = self.client.get(reverse("eventos:agenda"))
        self.assertTemplateUsed(resposta, "eventos/agenda.html")
        self.assertEqual(
            [i.atividade.titulo for i in resposta.context["inscricoes"]],
            ["Abertura", "Treinamento de Django", "Pôsteres"],
        )
        self.assertNotContains(resposta, "Treinamento de Git")


class ConsultasDaProgramacaoSiteTests(SiteTestCase):
    """RF12: o número de consultas da programação não cresce com as atividades."""

    CONSULTAS = 3  # evento, organizador e atividades com sala e vagas

    def test_programacao_com_duas_atividades_custa_um_numero_fixo_de_consultas(self):
        with self.assertNumQueries(self.CONSULTAS):
            self.client.get(reverse("eventos:detalhe", args=[self.jornada.pk]))

    def test_programacao_com_mais_atividades_custa_as_mesmas_consultas(self):
        for dia in (12, 13, 14):
            extra = self.criar_atividade(self.jornada, f"Extra {dia}", self.sala101, quando(dia, 8), quando(dia, 9))
            self.inscrever_na_atividade(self.carla, extra)
        with self.assertNumQueries(self.CONSULTAS):
            self.client.get(reverse("eventos:detalhe", args=[self.jornada.pk]))
