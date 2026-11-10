from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404

from .models import Evento


class DonoDoEventoMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Exige a permissão do papel E ser o organizador do evento.

    A checagem de propriedade compara o organizador com o usuário logado, então
    nem um superusuário altera o evento de outra pessoa por aqui.
    """

    def get_evento(self):
        if not hasattr(self, "_evento"):
            self._evento = self.buscar_evento()
        return self._evento

    def buscar_evento(self):
        return get_object_or_404(Evento, pk=self.kwargs["pk"])

    def has_permission(self):
        return super().has_permission() and self.get_evento().organizador_id == self.request.user.pk
