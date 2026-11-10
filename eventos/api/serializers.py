from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from .. import services
from ..models import Atividade, Evento, InscricaoAtividade, InscricaoEvento, Sala
from .excecoes import converter_erro


class ValidaPeloModelMixin:
    """O DRF não chama o full_clean() do model sozinho; este mixin chama.

    As regras ficam no clean() do model, o mesmo que o ModelForm do site executa.
    """

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instancia = self.instance if self.instance is not None else self.Meta.model()
        for campo, valor in attrs.items():
            setattr(instancia, campo, valor)
        self.preparar_instancia(instancia)
        try:
            instancia.full_clean()
        except DjangoValidationError as erro:
            raise converter_erro(erro)
        return attrs

    def preparar_instancia(self, instancia):
        """Preenche na instância o que vem do servidor, não do JSON."""


class SalaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sala
        fields = ["id", "nome", "bloco", "capacidade"]


class AtividadeSerializer(ValidaPeloModelMixin, serializers.ModelSerializer):
    evento_nome = serializers.CharField(source="evento.nome", read_only=True)
    sala_nome = serializers.CharField(source="sala.nome", read_only=True)
    tipo_nome = serializers.CharField(source="get_tipo_display", read_only=True)
    vagas_restantes = serializers.SerializerMethodField()

    class Meta:
        model = Atividade
        fields = [
            "id", "evento", "evento_nome", "titulo", "tipo", "tipo_nome", "descricao",
            "responsavel", "sala", "sala_nome", "inicio", "fim", "vagas_restantes",
        ]

    def get_vagas_restantes(self, obj) -> int:
        return obj.vagas_restantes()

    def validate_evento(self, evento):
        if evento.organizador_id != self.context["request"].user.pk:
            raise PermissionDenied("Você só cadastra atividades nos eventos que organiza.")
        return evento


class AtividadeNaProgramacaoSerializer(AtividadeSerializer):
    class Meta(AtividadeSerializer.Meta):
        fields = [f for f in AtividadeSerializer.Meta.fields if f not in ("evento", "evento_nome")]


class EventoSerializer(ValidaPeloModelMixin, serializers.ModelSerializer):
    organizador = serializers.CharField(source="organizador.username", read_only=True)

    class Meta:
        model = Evento
        fields = ["id", "nome", "descricao", "data_inicio", "data_fim", "inscricoes_abertas", "organizador"]

    def preparar_instancia(self, instancia):
        if instancia.organizador_id is None:
            instancia.organizador = self.context["request"].user


class EventoProgramacaoSerializer(EventoSerializer):
    atividades = AtividadeNaProgramacaoSerializer(many=True, read_only=True)

    class Meta(EventoSerializer.Meta):
        fields = EventoSerializer.Meta.fields + ["atividades"]


class InscricaoEventoSerializer(serializers.ModelSerializer):
    evento_nome = serializers.CharField(source="evento.nome", read_only=True)

    class Meta:
        model = InscricaoEvento
        fields = ["id", "evento", "evento_nome", "data"]

    def create(self, validated_data):
        return services.inscrever_em_evento(self.context["request"].user, validated_data["evento"])


class InscricaoAtividadeSerializer(serializers.ModelSerializer):
    atividade_titulo = serializers.CharField(source="atividade.titulo", read_only=True)
    evento = serializers.CharField(source="atividade.evento.nome", read_only=True)
    sala = serializers.CharField(source="atividade.sala.nome", read_only=True)
    inicio = serializers.DateTimeField(source="atividade.inicio", read_only=True)
    fim = serializers.DateTimeField(source="atividade.fim", read_only=True)

    class Meta:
        model = InscricaoAtividade
        fields = ["id", "atividade", "atividade_titulo", "evento", "sala", "inicio", "fim", "data"]

    def create(self, validated_data):
        return services.inscrever_em_atividade(self.context["request"].user, validated_data["atividade"])
