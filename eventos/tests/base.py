from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from ..models import Atividade, Evento, InscricaoAtividade, InscricaoEvento, Sala


def quando(dia, hora, minuto=0):
    return timezone.make_aware(datetime(2026, 11, dia, hora, minuto))


class CenarioTestCase(TestCase):
    """Cenário compartilhado, criado uma vez por classe e desfeito ao final de cada teste.

    - Semana (org_ana, 09 a 13/11) e Jornada (org_bruno, 11 a 14/11) se cruzam.
    - Abertura (Semana, Sala 101, 11/11 9h–11h) contém Ciência (Jornada, Auditório, 9h30–10h30).
    - Django (Semana, Laboratório de capacidade 2) e Git (Semana, Sala 101) são simultâneos.
    """

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        organizadores = Group.objects.create(name="Organizadores")
        organizadores.permissions.set(Permission.objects.filter(
            content_type__app_label="eventos", content_type__model__in=["evento", "atividade"]
        ))
        # Sem senha: os testes entram com force_login ou token, e o hash de senha deixaria a suíte lenta.
        cls.ana = User.objects.create_user("org_ana")
        cls.bruno = User.objects.create_user("org_bruno")
        cls.ana.groups.add(organizadores)
        cls.bruno.groups.add(organizadores)
        cls.carla = User.objects.create_user("part_carla")
        cls.diego = User.objects.create_user("part_diego")
        cls.elisa = User.objects.create_user("part_elisa")
        cls.tokens = {u.pk: Token.objects.create(user=u).key for u in (cls.ana, cls.bruno, cls.carla, cls.diego, cls.elisa)}

        cls.auditorio = Sala.objects.create(nome="Auditório", bloco="Central", capacidade=100)
        cls.sala101 = Sala.objects.create(nome="Sala 101", bloco="A", capacidade=40)
        cls.lab = Sala.objects.create(nome="Laboratório", bloco="B", capacidade=2)

        cls.semana = Evento.objects.create(
            nome="Semana de Tecnologia", data_inicio=date(2026, 11, 9), data_fim=date(2026, 11, 13),
            organizador=cls.ana,
        )
        cls.jornada = Evento.objects.create(
            nome="Jornada Científica", data_inicio=date(2026, 11, 11), data_fim=date(2026, 11, 14),
            organizador=cls.bruno,
        )
        cls.fechado = Evento.objects.create(
            nome="Encontro de Egressos", data_inicio=date(2026, 11, 20), data_fim=date(2026, 11, 20),
            inscricoes_abertas=False, organizador=cls.ana,
        )

        cls.abertura = cls.criar_atividade(cls.semana, "Abertura", cls.sala101, quando(11, 9), quando(11, 11))
        cls.django = cls.criar_atividade(cls.semana, "Treinamento de Django", cls.lab, quando(11, 14), quando(11, 17))
        cls.git = cls.criar_atividade(cls.semana, "Treinamento de Git", cls.sala101, quando(11, 14), quando(11, 16))
        cls.ciencia = cls.criar_atividade(cls.jornada, "Ciência aberta", cls.auditorio, quando(11, 9, 30), quando(11, 10, 30))
        cls.posteres = cls.criar_atividade(cls.jornada, "Pôsteres", cls.auditorio, quando(12, 14), quando(12, 16))

    @staticmethod
    def criar_atividade(evento, titulo, sala, inicio, fim, **extra):
        dados = {"tipo": Atividade.Tipo.PALESTRA, "responsavel": "Responsável", **extra}
        return Atividade.objects.create(evento=evento, titulo=titulo, sala=sala, inicio=inicio, fim=fim, **dados)

    # Atalhos que gravam direto no banco, para montar o cenário de um teste sem passar pelas regras.
    @staticmethod
    def inscrever_no_evento(usuario, evento):
        return InscricaoEvento.objects.create(participante=usuario, evento=evento)

    def inscrever_na_atividade(self, usuario, atividade):
        inscricao_evento, _ = InscricaoEvento.objects.get_or_create(participante=usuario, evento=atividade.evento)
        return InscricaoAtividade.objects.create(inscricao_evento=inscricao_evento, atividade=atividade)

    def api(self, usuario=None):
        cliente = APIClient()
        if usuario is not None:
            cliente.credentials(HTTP_AUTHORIZATION=f"Token {self.tokens[usuario.pk]}")
        return cliente

    @staticmethod
    def inscritos(atividade):
        return InscricaoAtividade.objects.filter(atividade=atividade).count()
