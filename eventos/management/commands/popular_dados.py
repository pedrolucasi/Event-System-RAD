from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from eventos.models import Atividade, Evento, Sala

SENHA_PADRAO = "Eventos@2026"
GRUPO_ORGANIZADORES = "Organizadores"


def quando(dia, hora, minuto=0):
    return timezone.make_aware(datetime(2026, 11, dia, hora, minuto))


class Command(BaseCommand):
    help = "Cria o grupo Organizadores, as cinco contas de teste e os dados de exemplo."

    @transaction.atomic
    def handle(self, *args, **options):
        grupo = self.criar_grupo()
        usuarios = self.criar_usuarios(grupo)
        salas = self.criar_salas()
        self.criar_eventos(usuarios, salas)
        self.stdout.write(self.style.SUCCESS(f"Dados criados. Senha de todas as contas: {SENHA_PADRAO}"))

    def criar_grupo(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPO_ORGANIZADORES)
        codenames = [
            f"{acao}_{modelo}"
            for modelo in ("evento", "atividade")
            for acao in ("add", "change", "delete", "view")
        ]
        grupo.permissions.set(Permission.objects.filter(content_type__app_label="eventos", codename__in=codenames))
        return grupo

    def criar_usuarios(self, grupo):
        User = get_user_model()
        contas = [
            ("admin", "Administração", "", True),
            ("org_ana", "Ana", "Organizadora", False),
            ("org_bruno", "Bruno", "Organizador", False),
            ("part_carla", "Carla", "Participante", False),
            ("part_diego", "Diego", "Participante", False),
        ]
        usuarios = {}
        for username, first, last, superuser in contas:
            user, _ = User.objects.get_or_create(username=username)
            user.first_name, user.last_name = first, last
            user.email = f"{username}@exemplo.com"
            user.is_staff = user.is_superuser = superuser
            user.set_password(SENHA_PADRAO)
            user.save()
            usuarios[username] = user

        for username in ("org_ana", "org_bruno"):
            usuarios[username].groups.add(grupo)
        return usuarios

    def criar_salas(self):
        dados = [
            ("Auditório", "Bloco Central", 100),
            ("Sala 101", "Bloco A", 40),
            ("Laboratório 1", "Bloco B", 2),
        ]
        salas = {}
        for nome, bloco, capacidade in dados:
            sala, _ = Sala.objects.update_or_create(nome=nome, defaults={"bloco": bloco, "capacidade": capacidade})
            salas[nome] = sala
        return salas

    def criar_eventos(self, usuarios, salas):
        semana, _ = Evento.objects.update_or_create(
            nome="Semana de Tecnologia",
            defaults={
                "descricao": "Palestras e minicursos sobre desenvolvimento web.",
                "data_inicio": date(2026, 11, 9),
                "data_fim": date(2026, 11, 13),
                "inscricoes_abertas": True,
                "organizador": usuarios["org_ana"],
            },
        )
        jornada, _ = Evento.objects.update_or_create(
            nome="Jornada Científica",
            defaults={
                "descricao": "Apresentação de trabalhos de pesquisa e extensão.",
                "data_inicio": date(2026, 11, 11),
                "data_fim": date(2026, 11, 14),
                "inscricoes_abertas": True,
                "organizador": usuarios["org_bruno"],
            },
        )
        egressos, _ = Evento.objects.update_or_create(
            nome="Encontro de Egressos",
            defaults={
                "descricao": "Evento com inscrições fechadas, para testar a recusa.",
                "data_inicio": date(2026, 11, 20),
                "data_fim": date(2026, 11, 20),
                "inscricoes_abertas": False,
                "organizador": usuarios["org_ana"],
            },
        )

        atividades = [
            (semana, "Abertura: o futuro da web", Atividade.Tipo.PALESTRA, "Profa. Maria Souza",
             salas["Sala 101"], quando(11, 9), quando(11, 11)),
            (semana, "Treinamento de Django", Atividade.Tipo.TREINAMENTO, "Prof. João Lima",
             salas["Laboratório 1"], quando(11, 14), quando(11, 17)),
            (semana, "Treinamento de Git", Atividade.Tipo.TREINAMENTO, "Prof. Pedro Alves",
             salas["Sala 101"], quando(11, 14), quando(11, 16)),
            (semana, "Projetos dos alunos", Atividade.Tipo.APRESENTACAO, "Coordenação TSI",
             salas["Laboratório 1"], quando(12, 9), quando(12, 11)),
            (jornada, "Ciência aberta", Atividade.Tipo.PALESTRA, "Dr. Carlos Mendes",
             salas["Auditório"], quando(11, 9, 30), quando(11, 10, 30)),
            (jornada, "Pôsteres de iniciação científica", Atividade.Tipo.APRESENTACAO, "PRPIPG",
             salas["Auditório"], quando(12, 14), quando(12, 16)),
            (egressos, "Roda de conversa com egressos", Atividade.Tipo.APRESENTACAO, "Coordenação TSI",
             salas["Auditório"], quando(20, 19), quando(20, 21)),
        ]
        for evento, titulo, tipo, responsavel, sala, inicio, fim in atividades:
            atividade = Atividade.objects.filter(evento=evento, titulo=titulo).first() or Atividade(
                evento=evento, titulo=titulo
            )
            atividade.tipo, atividade.responsavel, atividade.sala = tipo, responsavel, sala
            atividade.inicio, atividade.fim = inicio, fim
            atividade.full_clean()
            atividade.save()
