from django.core.exceptions import NON_FIELD_ERRORS
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.serializers import as_serializer_error
from rest_framework.settings import api_settings
from rest_framework.views import exception_handler


def converter_erro(exc):
    """ValidationError do Django -> ValidationError do DRF, com "__all__" em non_field_errors."""
    detalhe = as_serializer_error(exc)
    if NON_FIELD_ERRORS in detalhe:
        detalhe[api_settings.NON_FIELD_ERRORS_KEY] = detalhe.pop(NON_FIELD_ERRORS)
    return ValidationError(detalhe)


def tratar_excecao(exc, context):
    """Converte o ValidationError do Django (models e services) em 400 com JSON.

    Assim as regras escritas no clean() dos models e em services.py chegam ao cliente
    da API com a mesma mensagem que o site mostra, sem uma segunda cópia no serializer.
    """
    if isinstance(exc, DjangoValidationError):
        exc = converter_erro(exc)
    return exception_handler(exc, context)
