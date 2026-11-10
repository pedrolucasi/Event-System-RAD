from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Atividade, Evento, InscricaoAtividade, InscricaoEvento, Sala


def quando(dia, hora, minuto=0):
    return timezone.make_aware(datetime(2026, 11, dia, hora, minuto))


class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        grupo = Group.objects.create(name="Organizadores")
        grupo.permissions.set(Permission.objects.filter(
            content_type__app_label="eventos", content_type__model__in=["evento", "atividade"]
        ))
        cls.org2 = User.objects.create_user("org2", password="x")
        cls.org3 = User.objects.create_user("org3", password="x")
        cls.org2.groups.add(grupo)
        cls.org3.groups.add(grupo)
        cls.p4 = User.objects.create_user("p4", password="x")
        cls.p5 = User.objects.create_user("p5", password="x")
        cls.p6 = User.objects.create_user("p6", password="x")

        cls.auditorio = Sala.objects.create(nome="Auditório", capacidade=100)
        cls.sala101 = Sala.objects.create(nome="Sala 101", capacidade=40)
        cls.lab = Sala.objects.create(nome="Lab", capacidade=2)

        cls.semana = Evento.objects.create(
            nome="Semana", data_inicio=date(2026, 11, 9), data_fim=date(2026, 11, 13), organizador=cls.org2
        )
        cls.jornada = Evento.objects.create(
            nome="Jornada", data_inicio=date(2026, 11, 11), data_fim=date(2026, 11, 14), organizador=cls.org3
        )
        cls.fechado = Evento.objects.create(
            nome="Fechado", data_inicio=date(2026, 11, 20), data_fim=date(2026, 11, 20),
            inscricoes_abertas=False, organizador=cls.org2,
        )
        cls.abertura = Atividade.objects.create(
            evento=cls.semana, titulo="Abertura", tipo="PALESTRA", responsavel="X",
            sala=cls.sala101, inicio=quando(11, 9), fim=quando(11, 11),
        )
        cls.django = Atividade.objects.create(
            evento=cls.semana, titulo="Django", tipo="TREINAMENTO", responsavel="Y",
            sala=cls.lab, inicio=quando(11, 14), fim=quando(11, 17),
        )
        cls.ciencia = Atividade.objects.create(
            evento=cls.jornada, titulo="Ciência", tipo="PALESTRA", responsavel="Z",
            sala=cls.auditorio, inicio=quando(11, 9, 30), fim=quando(11, 10, 30),
        )

    def inscrever_evento(self, user, evento):
        return InscricaoEvento.objects.create(participante=user, evento=evento)


class SobreposicaoTests(BaseTestCase):
    def nova(self, inicio, fim, sala=None):
        return Atividade(
            evento=self.semana, titulo="Nova", tipo="PALESTRA", responsavel="R",
            sala=sala or self.sala101, inicio=inicio, fim=fim,
        )

    def test_casos_de_sobreposicao_na_sala(self):
        # Abertura ocupa a Sala 101 de 9h às 11h.
        conflitantes = [
            (quando(11, 8), quando(11, 10)),    # começa antes, termina dentro
            (quando(11, 10), quando(11, 12)),   # começa dentro, termina depois
            (quando(11, 9, 30), quando(11, 10)),  # contida
            (quando(11, 8), quando(11, 12)),    # contém
            (quando(11, 9), quando(11, 11)),    # idêntica
        ]
        for inicio, fim in conflitantes:
            with self.subTest(inicio=inicio, fim=fim):
                self.assertIn("sala", self._erros(self.nova(inicio, fim)))

    def test_horarios_encostados_nao_conflitam(self):
        self.nova(quando(11, 11), quando(11, 12)).full_clean()
        self.nova(quando(11, 8), quando(11, 9)).full_clean()

    def test_outra_sala_mesmo_horario_aceita(self):
        self.nova(quando(11, 9), quando(11, 11), sala=self.lab).full_clean()

    def test_fim_antes_do_inicio(self):
        self.assertIn("fim", self._erros(self.nova(quando(11, 12), quando(11, 10))))

    def test_fora_do_periodo(self):
        self.assertTrue(self._erros(self.nova(quando(14, 9), quando(14, 10))))

    def _erros(self, atividade):
        try:
            atividade.full_clean()
        except Exception as erro:
            return erro.message_dict
        return {}


class InscricaoViewsTests(BaseTestCase):
    def post(self, user, nome, pk):
        self.client.force_login(user)
        return self.client.post(reverse(f"eventos:{nome}", args=[pk]))

    def test_publico_ve_lista_e_programacao(self):
        self.assertEqual(self.client.get(reverse("eventos:lista")).status_code, 200)
        resp = self.client.get(reverse("eventos:detalhe", args=[self.semana.pk]))
        self.assertContains(resp, "Abertura")

    def test_anonimo_vai_para_login(self):
        resp = self.client.post(reverse("eventos:inscrever_evento", args=[self.semana.pk]))
        self.assertRedirects(resp, f"{reverse('login')}?next={reverse('eventos:inscrever_evento', args=[self.semana.pk])}",
                             fetch_redirect_response=False)

    def test_inscricao_evento_duplicada_e_fechada(self):
        self.post(self.p4, "inscrever_evento", self.semana.pk)
        self.post(self.p4, "inscrever_evento", self.semana.pk)
        self.post(self.p4, "inscrever_evento", self.fechado.pk)
        self.assertEqual(InscricaoEvento.objects.filter(participante=self.p4).count(), 1)

    def test_get_nao_inscreve(self):
        self.client.force_login(self.p4)
        resp = self.client.get(reverse("eventos:inscrever_evento", args=[self.semana.pk]))
        self.assertEqual(resp.status_code, 405)

    def test_atividade_sem_inscricao_no_evento(self):
        self.post(self.p4, "inscrever_atividade", self.abertura.pk)
        self.assertFalse(InscricaoAtividade.objects.exists())

    def test_capacidade(self):
        for user in (self.p4, self.p5, self.p6):
            self.inscrever_evento(user, self.semana)
            self.post(user, "inscrever_atividade", self.django.pk)
        self.assertEqual(self.django.inscricoes.count(), 2)

    def test_conflito_entre_eventos(self):
        self.inscrever_evento(self.p4, self.semana)
        self.inscrever_evento(self.p4, self.jornada)
        self.post(self.p4, "inscrever_atividade", self.abertura.pk)
        self.post(self.p4, "inscrever_atividade", self.ciencia.pk)
        self.assertEqual(InscricaoAtividade.objects.filter(inscricao_evento__participante=self.p4).count(), 1)

    def test_cancelamentos(self):
        ie = self.inscrever_evento(self.p4, self.semana)
        self.post(self.p4, "inscrever_atividade", self.abertura.pk)
        self.post(self.p4, "inscrever_atividade", self.django.pk)
        ia = InscricaoAtividade.objects.get(atividade=self.abertura)

        self.assertEqual(self.post(self.p5, "cancelar_atividade", ia.pk).status_code, 403)
        self.post(self.p4, "cancelar_atividade", ia.pk)
        self.assertTrue(InscricaoEvento.objects.filter(pk=ie.pk).exists())
        self.assertEqual(ie.inscricoes_atividade.count(), 1)

        self.assertEqual(self.post(self.p5, "cancelar_evento", ie.pk).status_code, 403)
        self.post(self.p4, "cancelar_evento", ie.pk)
        self.assertFalse(InscricaoAtividade.objects.exists())


class OrganizadorTests(BaseTestCase):
    def test_organizador_preenchido_pelo_sistema(self):
        self.client.force_login(self.org2)
        self.client.post(reverse("eventos:criar"), {
            "nome": "Novo", "data_inicio": "2026-12-01", "data_fim": "2026-12-02",
            "inscricoes_abertas": "on", "organizador": self.org3.pk,
        })
        self.assertEqual(Evento.objects.get(nome="Novo").organizador, self.org2)

    def test_nao_altera_evento_alheio(self):
        self.client.force_login(self.org3)
        for nome in ("editar", "excluir", "painel", "atividade_criar"):
            with self.subTest(nome=nome):
                resp = self.client.get(reverse(f"eventos:{nome}", args=[self.semana.pk]))
                self.assertEqual(resp.status_code, 403)
        resp = self.client.get(reverse("eventos:atividade_editar", args=[self.abertura.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_participante_nao_cria_evento(self):
        self.client.force_login(self.p4)
        self.assertEqual(self.client.get(reverse("eventos:criar")).status_code, 403)

    def test_dono_ve_painel(self):
        self.client.force_login(self.org2)
        self.assertEqual(self.client.get(reverse("eventos:painel", args=[self.semana.pk])).status_code, 200)
