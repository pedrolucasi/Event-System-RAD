from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, DjangoModelPermissionsOrAnonReadOnly, IsAuthenticated
from rest_framework.response import Response

from .. import services
from ..models import Atividade, Evento, InscricaoAtividade, InscricaoEvento, Sala
from .permissions import EhOrganizadorDoEvento
from .serializers import (
    AtividadeSerializer,
    EventoProgramacaoSerializer,
    EventoSerializer,
    InscricaoAtividadeSerializer,
    InscricaoEventoSerializer,
    SalaSerializer,
)

# Papel (permissão do grupo Organizadores) + propriedade (ser o organizador do evento).
PERMISSOES_ORGANIZADOR = [DjangoModelPermissionsOrAnonReadOnly, EhOrganizadorDoEvento]


class SalaViewSet(viewsets.ReadOnlyModelViewSet):
    """Salas são cadastradas pelo Admin; a API só as expõe para leitura."""

    queryset = Sala.objects.all()
    serializer_class = SalaSerializer
    permission_classes = [AllowAny]


class EventoViewSet(viewsets.ModelViewSet):
    """Lista pública de eventos. O detalhe traz a programação completa em uma requisição."""

    permission_classes = PERMISSOES_ORGANIZADOR
    search_fields = ["nome", "descricao"]
    ordering_fields = ["data_inicio", "nome"]

    def get_queryset(self):
        eventos = Evento.objects.select_related("organizador")
        if self.action == "retrieve":
            atividades = Atividade.objects.com_vagas().select_related("sala")
            eventos = eventos.prefetch_related(Prefetch("atividades", queryset=atividades))
        return eventos

    def get_serializer_class(self):
        if self.action == "retrieve":
            return EventoProgramacaoSerializer
        return EventoSerializer

    def perform_create(self, serializer):
        serializer.save(organizador=self.request.user)


class AtividadeViewSet(viewsets.ModelViewSet):
    """Atividades de todos os eventos, paginadas. Filtre por evento com ?evento=<id>."""

    serializer_class = AtividadeSerializer
    permission_classes = PERMISSOES_ORGANIZADOR
    search_fields = ["titulo", "descricao"]
    ordering_fields = ["inicio"]
    ordering = ["inicio"]

    def get_queryset(self):
        atividades = Atividade.objects.com_vagas().select_related("sala", "evento")
        evento = self.request.query_params.get("evento")
        if evento and evento.isdigit():
            atividades = atividades.filter(evento_id=evento)
        return atividades

    def perform_update(self, serializer):
        serializer.save()
        # Recarrega com a anotação de vagas, que pode ter mudado com a troca de sala.
        serializer.instance = self.get_queryset().get(pk=serializer.instance.pk)


class InscricaoEventoViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Inscrições do usuário do token. Excluir cancela o evento e todas as atividades dele."""

    serializer_class = InscricaoEventoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return InscricaoEvento.objects.none()
        # Só as próprias: a inscrição de outra pessoa nem é encontrada (404).
        return InscricaoEvento.objects.filter(participante=self.request.user).select_related("evento")

    def perform_destroy(self, instance):
        services.cancelar_inscricao_evento(instance)


class InscricaoAtividadeViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Inscrições em atividades do usuário do token. Excluir libera a vaga."""

    serializer_class = InscricaoAtividadeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return InscricaoAtividade.objects.none()
        return InscricaoAtividade.objects.filter(
            inscricao_evento__participante=self.request.user
        ).select_related("atividade__evento", "atividade__sala")

    def perform_destroy(self, instance):
        services.cancelar_inscricao_atividade(instance)


@extend_schema(responses=InscricaoAtividadeSerializer(many=True))
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def agenda(request):
    """Atividades em que o usuário do token está inscrito, de todos os eventos, por data e hora."""
    inscricoes = (
        InscricaoAtividade.objects.filter(inscricao_evento__participante=request.user)
        .select_related("atividade__evento", "atividade__sala")
        .order_by("atividade__inicio", "atividade__fim")
    )
    return Response(InscricaoAtividadeSerializer(inscricoes, many=True).data)
