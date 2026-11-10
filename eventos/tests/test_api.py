from django.urls import reverse
from rest_framework import status

from ..models import Atividade, Evento, InscricaoAtividade, InscricaoEvento
from .base import CenarioTestCase, quando

CAMPOS_EVENTO = {"id", "nome", "descricao", "data_inicio", "data_fim", "inscricoes_abertas", "organizador"}
CAMPOS_ATIVIDADE_NA_PROGRAMACAO = {
    "id", "titulo", "tipo", "tipo_nome", "descricao", "responsavel", "sala", "sala_nome", "inicio", "fim",
    "vagas_restantes",
}


def url_detalhe(nome, pk):
    return reverse(f"api:{nome}-detail", args=[pk])


class PortaAbertaTests(CenarioTestCase):
    """RF10: leitura sem token, com os dados esperados e nada além deles."""

    def test_lista_de_eventos_responde_sem_token(self):
        resposta = self.api().get(reverse("api:evento-list"))
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data["count"], 3)
        self.assertEqual([e["nome"] for e in resposta.data["results"]],
                         ["Semana de Tecnologia", "Jornada Científica", "Encontro de Egressos"])

    def test_evento_publico_traz_exatamente_os_campos_previstos(self):
        evento = self.api().get(reverse("api:evento-list")).data["results"][0]
        self.assertEqual(set(evento), CAMPOS_EVENTO)
        self.assertEqual(evento["organizador"], "org_ana")

    def test_programacao_traz_atividades_com_nome_da_sala_e_vagas(self):
        self.inscrever_na_atividade(self.carla, self.django)
        resposta = self.api().get(url_detalhe("evento", self.semana.pk))
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        atividades = {a["titulo"]: a for a in resposta.data["atividades"]}
        self.assertEqual(list(atividades), ["Abertura", "Treinamento de Git", "Treinamento de Django"])
        self.assertEqual(atividades["Treinamento de Django"]["sala_nome"], "Laboratório")
        self.assertEqual(atividades["Treinamento de Django"]["vagas_restantes"], 1)
        self.assertEqual(atividades["Abertura"]["vagas_restantes"], 40)

    def test_programacao_ordena_por_horario_e_nao_por_cadastro(self):
        self.criar_atividade(self.semana, "Credenciamento", self.auditorio, quando(10, 8), quando(10, 9))
        resposta = self.api().get(url_detalhe("evento", self.semana.pk))
        self.assertEqual(resposta.data["atividades"][0]["titulo"], "Credenciamento")

    def test_programacao_nao_expoe_nada_alem_do_previsto(self):
        self.inscrever_na_atividade(self.carla, self.django)
        resposta = self.api().get(url_detalhe("evento", self.semana.pk))
        self.assertEqual(set(resposta.data), CAMPOS_EVENTO | {"atividades"})
        for atividade in resposta.data["atividades"]:
            self.assertEqual(set(atividade), CAMPOS_ATIVIDADE_NA_PROGRAMACAO)
        self.assertNotIn("part_carla", resposta.content.decode())

    def test_salas_sao_publicas_para_leitura(self):
        resposta = self.api().get(reverse("api:sala-list"))
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual({s["nome"] for s in resposta.data["results"]}, {"Auditório", "Sala 101", "Laboratório"})

    def test_documentacao_e_schema_estao_publicados(self):
        self.assertEqual(self.api().get(reverse("api:docs")).status_code, status.HTTP_200_OK)
        schema = self.api().get(reverse("api:schema")).content.decode()
        for caminho in ("/api/eventos/", "/api/atividades/", "/api/inscricoes-atividade/", "/api/agenda/"):
            self.assertIn(caminho, schema)


class ListaDeAtividadesTests(CenarioTestCase):
    """RF10 da atividade 06: paginada, buscável e ordenável."""

    def test_lista_vem_paginada(self):
        resposta = self.api().get(reverse("api:atividade-list"))
        self.assertEqual(set(resposta.data), {"count", "next", "previous", "results"})
        self.assertEqual(resposta.data["count"], 5)

    def test_busca_por_termo_no_titulo(self):
        resposta = self.api().get(reverse("api:atividade-list"), {"search": "treinamento"})
        self.assertEqual([a["titulo"] for a in resposta.data["results"]], ["Treinamento de Django", "Treinamento de Git"])

    def test_busca_por_termo_na_descricao(self):
        Atividade.objects.filter(pk=self.posteres.pk).update(descricao="Trabalhos de iniciação científica")
        resposta = self.api().get(reverse("api:atividade-list"), {"search": "iniciação"})
        self.assertEqual([a["titulo"] for a in resposta.data["results"]], ["Pôsteres"])

    def test_ordenacao_decrescente_por_inicio(self):
        resposta = self.api().get(reverse("api:atividade-list"), {"ordering": "-inicio"})
        self.assertEqual(resposta.data["results"][0]["titulo"], "Pôsteres")


class PortaFechadaTests(CenarioTestCase):
    """RF11: sem token 401; com token de quem não pode 403; com o token certo, acontece."""

    def nova_atividade(self, **campos):
        return {
            "evento": self.semana.pk, "titulo": "Oficina", "tipo": "TREINAMENTO", "responsavel": "R",
            "sala": self.sala101.pk, "inicio": quando(11, 11).isoformat(), "fim": quando(11, 12).isoformat(),
            **campos,
        }

    def test_criar_atividade_sem_token_devolve_401(self):
        resposta = self.api().post(reverse("api:atividade-list"), self.nova_atividade(), format="json")
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Atividade.objects.filter(titulo="Oficina").exists())

    def test_criar_atividade_com_token_de_participante_devolve_403(self):
        resposta = self.api(self.carla).post(reverse("api:atividade-list"), self.nova_atividade(), format="json")
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Atividade.objects.filter(titulo="Oficina").exists())

    def test_criar_atividade_com_token_do_organizador_devolve_201(self):
        resposta = self.api(self.ana).post(reverse("api:atividade-list"), self.nova_atividade(), format="json")
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resposta.data["sala_nome"], "Sala 101")
        self.assertEqual(resposta.data["vagas_restantes"], 40)
        self.assertTrue(Atividade.objects.filter(titulo="Oficina", evento=self.semana).exists())

    def test_organizador_nao_cria_atividade_no_evento_de_outro(self):
        resposta = self.api(self.bruno).post(reverse("api:atividade-list"), self.nova_atividade(), format="json")
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Atividade.objects.filter(titulo="Oficina").exists())

    def test_organizador_vem_do_token_e_nao_do_json(self):
        resposta = self.api(self.ana).post(reverse("api:evento-list"), {
            "nome": "Hackathon", "data_inicio": "2026-12-01", "data_fim": "2026-12-02", "organizador": self.bruno.pk,
        }, format="json")
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Evento.objects.get(nome="Hackathon").organizador, self.ana)

    def test_participante_nao_cria_evento(self):
        resposta = self.api(self.carla).post(reverse("api:evento-list"), {
            "nome": "Hackathon", "data_inicio": "2026-12-01", "data_fim": "2026-12-02",
        }, format="json")
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Evento.objects.filter(nome="Hackathon").exists())

    def test_dono_altera_o_proprio_evento(self):
        resposta = self.api(self.ana).patch(url_detalhe("evento", self.semana.pk), {"nome": "Semana 2026"}, format="json")
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.semana.refresh_from_db()
        self.assertEqual(self.semana.nome, "Semana 2026")

    def test_organizador_nao_altera_evento_de_outro(self):
        resposta = self.api(self.bruno).patch(url_detalhe("evento", self.semana.pk), {"nome": "Invadido"}, format="json")
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
        self.semana.refresh_from_db()
        self.assertEqual(self.semana.nome, "Semana de Tecnologia")

    def test_organizador_nao_exclui_evento_de_outro(self):
        resposta = self.api(self.bruno).delete(url_detalhe("evento", self.semana.pk))
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Evento.objects.filter(pk=self.semana.pk).exists())

    def test_organizador_nao_altera_atividade_de_evento_alheio(self):
        resposta = self.api(self.bruno).patch(url_detalhe("atividade", self.abertura.pk), {"titulo": "X"}, format="json")
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
        self.abertura.refresh_from_db()
        self.assertEqual(self.abertura.titulo, "Abertura")

    def test_atividade_com_fim_antes_do_inicio_devolve_400_em_json(self):
        resposta = self.api(self.ana).post(reverse("api:atividade-list"),
                                           self.nova_atividade(fim=quando(11, 10).isoformat()), format="json")
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.json(), {"fim": ["O fim da atividade precisa ser depois do início."]})

    def test_rn3_mesma_sala_em_outro_horario_e_aceita(self):
        resposta = self.api(self.ana).post(reverse("api:atividade-list"), self.nova_atividade(), format="json")
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)

    def test_rn3_sala_ocupada_no_horario_devolve_400_em_json(self):
        resposta = self.api(self.ana).post(reverse("api:atividade-list"), self.nova_atividade(
            inicio=quando(11, 10).isoformat(), fim=quando(11, 12).isoformat()), format="json")
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("já está ocupada", resposta.json()["sala"][0])
        self.assertFalse(Atividade.objects.filter(titulo="Oficina").exists())

    def test_rn3_editar_atividade_para_sala_ocupada_devolve_400(self):
        resposta = self.api(self.ana).patch(url_detalhe("atividade", self.git.pk), {
            "inicio": quando(11, 9).isoformat(), "fim": quando(11, 10).isoformat(),
        }, format="json")
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.git.refresh_from_db()
        self.assertEqual(self.git.inicio, quando(11, 14))


class InscricaoPelaApiTests(CenarioTestCase):
    """As cinco regras pela porta da API, com o código e a mensagem em JSON."""

    def inscrever_evento(self, usuario, evento):
        return self.api(usuario).post(reverse("api:inscricao-evento-list"), {"evento": evento.pk}, format="json")

    def inscrever_atividade(self, usuario, atividade):
        return self.api(usuario).post(reverse("api:inscricao-atividade-list"), {"atividade": atividade.pk}, format="json")

    def test_inscricao_sem_token_devolve_401(self):
        resposta = self.api().post(reverse("api:inscricao-evento-list"), {"evento": self.semana.pk}, format="json")
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(InscricaoEvento.objects.exists())

    def test_inscricao_no_evento_devolve_201_e_grava_para_o_dono_do_token(self):
        resposta = self.inscrever_evento(self.carla, self.semana)
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(InscricaoEvento.objects.get(pk=resposta.data["id"]).participante, self.carla)

    def test_segunda_inscricao_no_mesmo_evento_devolve_400(self):
        self.inscrever_no_evento(self.carla, self.semana)
        resposta = self.inscrever_evento(self.carla, self.semana)
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.json(), {"non_field_errors": ["Você já está inscrito neste evento."]})

    def test_evento_fechado_devolve_400(self):
        resposta = self.inscrever_evento(self.carla, self.fechado)
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(InscricaoEvento.objects.exists())

    def test_rn4_inscrito_no_evento_se_inscreve_na_atividade(self):
        self.inscrever_no_evento(self.carla, self.semana)
        resposta = self.inscrever_atividade(self.carla, self.abertura)
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.inscritos(self.abertura), 1)

    def test_rn4_sem_inscricao_no_evento_devolve_400(self):
        resposta = self.inscrever_atividade(self.carla, self.abertura)
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.json(), {"non_field_errors": ["Inscreva-se no evento antes de escolher atividades."]})
        self.assertEqual(self.inscritos(self.abertura), 0)

    def test_rn1_inscricao_com_vaga_devolve_201_e_as_vagas_diminuem(self):
        self.inscrever_no_evento(self.carla, self.semana)
        self.assertEqual(self.inscrever_atividade(self.carla, self.django).status_code, status.HTTP_201_CREATED)
        detalhe = self.api().get(url_detalhe("atividade", self.django.pk))
        self.assertEqual(detalhe.data["vagas_restantes"], 1)

    def test_rn1_inscricao_alem_da_capacidade_devolve_400_com_mensagem(self):
        self.inscrever_na_atividade(self.carla, self.django)
        self.inscrever_na_atividade(self.diego, self.django)
        self.inscrever_no_evento(self.elisa, self.semana)
        resposta = self.inscrever_atividade(self.elisa, self.django)
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.json(), {"non_field_errors": ["Atividade lotada: não há mais vagas na sala."]})
        self.assertEqual(self.inscritos(self.django), 2)

    def test_rn2_atividade_em_outro_horario_e_aceita(self):
        self.inscrever_na_atividade(self.carla, self.abertura)
        self.inscrever_no_evento(self.carla, self.jornada)
        self.assertEqual(self.inscrever_atividade(self.carla, self.posteres).status_code, status.HTTP_201_CREATED)

    def test_rn2_atividade_simultanea_no_mesmo_evento_devolve_400(self):
        self.inscrever_na_atividade(self.carla, self.django)
        resposta = self.inscrever_atividade(self.carla, self.git)
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Conflito de horário", resposta.json()["non_field_errors"][0])

    def test_rn2_atividade_simultanea_em_outro_evento_devolve_400(self):
        self.inscrever_na_atividade(self.carla, self.abertura)
        self.inscrever_no_evento(self.carla, self.jornada)
        resposta = self.inscrever_atividade(self.carla, self.ciencia)
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Conflito de horário com "Abertura"', resposta.json()["non_field_errors"][0])
        self.assertEqual(self.inscritos(self.ciencia), 0)


class CancelamentoPelaApiTests(CenarioTestCase):
    def test_cancelar_atividade_devolve_204_e_a_vaga_volta(self):
        inscricao = self.inscrever_na_atividade(self.carla, self.django)
        self.inscrever_na_atividade(self.diego, self.django)
        resposta = self.api(self.carla).delete(url_detalhe("inscricao-atividade", inscricao.pk))
        self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.api().get(url_detalhe("atividade", self.django.pk)).data["vagas_restantes"], 1)
        self.assertTrue(InscricaoEvento.objects.filter(pk=inscricao.inscricao_evento_id).exists())

    def test_rn5_cancelar_evento_remove_as_atividades_dele(self):
        inscricao = self.inscrever_na_atividade(self.carla, self.abertura).inscricao_evento
        self.inscrever_na_atividade(self.carla, self.django)
        self.inscrever_na_atividade(self.carla, self.posteres)
        resposta = self.api(self.carla).delete(url_detalhe("inscricao-evento", inscricao.pk))
        self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            list(InscricaoAtividade.objects.filter(inscricao_evento__participante=self.carla)
                 .values_list("atividade__titulo", flat=True)),
            ["Pôsteres"],
        )

    def test_rn5_ninguem_cancela_inscricao_no_evento_de_outra_pessoa(self):
        inscricao = self.inscrever_na_atividade(self.carla, self.abertura).inscricao_evento
        resposta = self.api(self.diego).delete(url_detalhe("inscricao-evento", inscricao.pk))
        self.assertEqual(resposta.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(InscricaoEvento.objects.filter(pk=inscricao.pk).exists())
        self.assertEqual(self.inscritos(self.abertura), 1)

    def test_ninguem_cancela_inscricao_em_atividade_de_outra_pessoa(self):
        inscricao = self.inscrever_na_atividade(self.carla, self.abertura)
        resposta = self.api(self.diego).delete(url_detalhe("inscricao-atividade", inscricao.pk))
        self.assertEqual(resposta.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(InscricaoAtividade.objects.filter(pk=inscricao.pk).exists())


class AgendaPelaApiTests(CenarioTestCase):
    def test_agenda_sem_token_devolve_401(self):
        self.assertEqual(self.api().get(reverse("api:agenda")).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_agenda_traz_so_as_atividades_do_dono_do_token_em_ordem(self):
        self.inscrever_na_atividade(self.carla, self.posteres)
        self.inscrever_na_atividade(self.carla, self.django)
        self.inscrever_na_atividade(self.carla, self.abertura)
        self.inscrever_na_atividade(self.diego, self.git)
        resposta = self.api(self.carla).get(reverse("api:agenda"))
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual([i["atividade_titulo"] for i in resposta.data],
                         ["Abertura", "Treinamento de Django", "Pôsteres"])
        self.assertEqual(resposta.data[0]["sala"], "Sala 101")
        self.assertEqual(resposta.data[2]["evento"], "Jornada Científica")

    def test_token_e_obtido_com_usuario_e_senha(self):
        self.carla.set_password("senha-carla")
        self.carla.save()
        resposta = self.api().post(reverse("api:token"), {"username": "part_carla", "password": "senha-carla"})
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data["token"], self.tokens[self.carla.pk])


class ConsultasDaProgramacaoApiTests(CenarioTestCase):
    """RF12: a programação pela API custa o mesmo número de consultas com 2 ou com 5 atividades."""

    CONSULTAS = 2  # evento com organizador e atividades com sala e vagas

    def test_programacao_com_duas_atividades_custa_um_numero_fixo_de_consultas(self):
        with self.assertNumQueries(self.CONSULTAS):
            self.api().get(url_detalhe("evento", self.jornada.pk))

    def test_programacao_com_mais_atividades_custa_as_mesmas_consultas(self):
        for dia in (12, 13, 14):
            extra = self.criar_atividade(self.jornada, f"Extra {dia}", self.sala101, quando(dia, 8), quando(dia, 9))
            self.inscrever_na_atividade(self.carla, extra)
        with self.assertNumQueries(self.CONSULTAS):
            resposta = self.api().get(url_detalhe("evento", self.jornada.pk))
        self.assertEqual(len(resposta.data["atividades"]), 5)
