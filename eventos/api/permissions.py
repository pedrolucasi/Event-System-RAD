from rest_framework.permissions import SAFE_METHODS, BasePermission

from ..models import Evento


class EhOrganizadorDoEvento(BasePermission):
    """Leitura para todos; escrita só para o organizador do evento (ou do evento da atividade).

    Compara com o usuário do token, nunca com is_superuser.
    """

    message = "Apenas o organizador do evento pode alterá-lo."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        evento = obj if isinstance(obj, Evento) else obj.evento
        return evento.organizador_id == request.user.pk
