"""Operações de inscrição e cancelamento usadas pelo site e pela API.

As regras de negócio moram nos models (``clean()`` e relacionamentos). Estas funções
são o único caminho de escrita das inscrições: montam o objeto, chamam ``full_clean()``
e gravam. Nenhuma das duas camadas grava inscrições por conta própria.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Atividade, InscricaoAtividade, InscricaoEvento


def inscrever_em_evento(participante, evento):
    inscricao = InscricaoEvento(evento=evento, participante=participante)
    inscricao.full_clean()
    inscricao.save()
    return inscricao


def inscrever_em_atividade(participante, atividade):
    with transaction.atomic():
        # O bloqueio da linha serializa inscrições concorrentes na mesma atividade (RN1).
        atividade = (
            Atividade.objects.select_for_update().select_related("evento", "sala").get(pk=atividade.pk)
        )
        # RN4: a inscrição em atividade pendura na inscrição do participante no evento.
        inscricao_evento = InscricaoEvento.objects.filter(
            evento_id=atividade.evento_id, participante=participante
        ).first()
        if inscricao_evento is None:
            raise ValidationError(
                "Inscreva-se no evento antes de escolher atividades.", code="sem_inscricao_no_evento"
            )
        inscricao = InscricaoAtividade(inscricao_evento=inscricao_evento, atividade=atividade)
        inscricao.full_clean()
        inscricao.save()
        return inscricao


def cancelar_inscricao_evento(inscricao):
    # RN5: o CASCADE de InscricaoAtividade.inscricao_evento remove as atividades junto.
    inscricao.delete()


def cancelar_inscricao_atividade(inscricao):
    inscricao.delete()
