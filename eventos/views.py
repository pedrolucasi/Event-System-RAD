from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from . import services
from .forms import AtividadeForm, EventoForm
from .mixins import DonoDoEventoMixin
from .models import (
    Atividade,
    Evento,
    InscricaoAtividade,
    InscricaoEvento,
    intervalos_sobrepostos,
)


class SignupView(CreateView):
    form_class = UserCreationForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        messages.success(self.request, "Conta criada. Faça login para continuar.")
        return super().form_valid(form)


# ---------------------------------------------------------------- programação pública

class EventoListView(ListView):
    model = Evento
    template_name = "eventos/evento_list.html"
    context_object_name = "eventos"

    def get_queryset(self):
        return Evento.objects.select_related("organizador").annotate(
            num_atividades=Count("atividades")
        )


class EventoDetailView(DetailView):
    model = Evento
    template_name = "eventos/evento_detail.html"
    context_object_name = "evento"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        evento = self.object
        user = self.request.user

        atividades = list(evento.atividades.com_vagas().select_related("sala"))

        inscricao_evento = None
        minhas = []
        if user.is_authenticated:
            inscricao_evento = InscricaoEvento.objects.filter(evento=evento, participante=user).first()
            minhas = list(
                InscricaoAtividade.objects.filter(inscricao_evento__participante=user)
                .select_related("atividade")
            )
        minhas_por_atividade = {ia.atividade_id: ia for ia in minhas}

        for a in atividades:
            a.minha_inscricao = minhas_por_atividade.get(a.pk)
            a.lotada = a.vagas <= 0
            a.conflita = any(
                ia.atividade_id != a.pk
                and intervalos_sobrepostos(ia.atividade.inicio, ia.atividade.fim, a.inicio, a.fim)
                for ia in minhas
            )
            a.pode_inscrever = (
                inscricao_evento is not None
                and a.minha_inscricao is None
                and not a.lotada
                and not a.conflita
            )

        context.update(
            atividades=atividades,
            inscricao_evento=inscricao_evento,
            eh_dono=user.is_authenticated and evento.organizador_id == user.pk,
        )
        return context


# ---------------------------------------------------------------- cadastro (organizador)

class MeusEventosView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "eventos.add_evento"
    template_name = "eventos/meus_eventos.html"
    context_object_name = "eventos"

    def get_queryset(self):
        return Evento.objects.filter(organizador=self.request.user).annotate(
            num_atividades=Count("atividades", distinct=True),
            num_inscritos=Count("inscricoes", distinct=True),
        )


class EventoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "eventos.add_evento"
    model = Evento
    form_class = EventoForm
    template_name = "eventos/evento_form.html"

    def form_valid(self, form):
        form.instance.organizador = self.request.user
        messages.success(self.request, "Evento criado.")
        return super().form_valid(form)


class EventoUpdateView(DonoDoEventoMixin, UpdateView):
    permission_required = "eventos.change_evento"
    model = Evento
    form_class = EventoForm
    template_name = "eventos/evento_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Evento atualizado.")
        return super().form_valid(form)


class EventoDeleteView(DonoDoEventoMixin, DeleteView):
    permission_required = "eventos.delete_evento"
    model = Evento
    template_name = "eventos/confirmar_exclusao.html"
    success_url = reverse_lazy("eventos:meus_eventos")

    def form_valid(self, form):
        messages.success(self.request, "Evento excluído.")
        return super().form_valid(form)


class AtividadeCreateView(DonoDoEventoMixin, CreateView):
    permission_required = "eventos.add_atividade"
    model = Atividade
    form_class = AtividadeForm
    template_name = "eventos/atividade_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # O evento precisa estar na instância antes da validação (período e conflitos).
        kwargs["instance"] = Atividade(evento=self.get_evento())
        return kwargs

    def get_context_data(self, **kwargs):
        return super().get_context_data(evento=self.get_evento(), **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Atividade cadastrada.")
        return super().form_valid(form)

    def get_success_url(self):
        return self.get_evento().get_absolute_url()


class AtividadeDonoMixin(DonoDoEventoMixin):
    def buscar_evento(self):
        atividade = get_object_or_404(Atividade.objects.select_related("evento"), pk=self.kwargs["pk"])
        return atividade.evento

    def get_context_data(self, **kwargs):
        return super().get_context_data(evento=self.get_evento(), **kwargs)

    def get_success_url(self):
        return self.get_evento().get_absolute_url()


class AtividadeUpdateView(AtividadeDonoMixin, UpdateView):
    permission_required = "eventos.change_atividade"
    model = Atividade
    form_class = AtividadeForm
    template_name = "eventos/atividade_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Atividade atualizada.")
        return super().form_valid(form)


class AtividadeDeleteView(AtividadeDonoMixin, DeleteView):
    permission_required = "eventos.delete_atividade"
    model = Atividade
    template_name = "eventos/confirmar_exclusao.html"

    def form_valid(self, form):
        messages.success(self.request, "Atividade excluída.")
        return super().form_valid(form)


class PainelView(DonoDoEventoMixin, DetailView):
    permission_required = "eventos.change_evento"
    model = Evento
    template_name = "eventos/painel.html"
    context_object_name = "evento"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        inscricoes = InscricaoAtividade.objects.select_related("inscricao_evento__participante").order_by("data")
        context["atividades"] = (
            self.object.atividades.com_vagas()
            .select_related("sala")
            .prefetch_related(Prefetch("inscricoes", queryset=inscricoes))
        )
        context["inscricoes_evento"] = self.object.inscricoes.select_related("participante").order_by("data")
        return context


# ---------------------------------------------------------------- inscrições (participante)

def _mostrar_erros(request, erro):
    for msg in erro.messages:
        messages.error(request, msg)


def _voltar(request, padrao):
    destino = request.POST.get("next")
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return redirect(destino)
    return redirect(padrao)


@login_required
@require_POST
def inscrever_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    try:
        services.inscrever_em_evento(request.user, evento)
        messages.success(request, f"Inscrição no evento {evento} realizada.")
    except ValidationError as erro:
        _mostrar_erros(request, erro)
    return redirect(evento)


@login_required
@require_POST
def cancelar_inscricao_evento(request, pk):
    inscricao = get_object_or_404(InscricaoEvento.objects.select_related("evento"), pk=pk)
    if inscricao.participante_id != request.user.pk:
        raise PermissionDenied("Você só pode cancelar as suas próprias inscrições.")
    evento = inscricao.evento
    services.cancelar_inscricao_evento(inscricao)
    messages.success(request, f"Inscrição no evento {evento} cancelada, junto com as atividades dele.")
    return _voltar(request, evento)


@login_required
@require_POST
def inscrever_atividade(request, pk):
    atividade = get_object_or_404(Atividade.objects.select_related("evento"), pk=pk)
    try:
        services.inscrever_em_atividade(request.user, atividade)
        messages.success(request, f"Inscrição em \"{atividade.titulo}\" realizada.")
    except ValidationError as erro:
        _mostrar_erros(request, erro)
    return redirect(atividade.evento)


@login_required
@require_POST
def cancelar_inscricao_atividade(request, pk):
    inscricao = get_object_or_404(
        InscricaoAtividade.objects.select_related("inscricao_evento", "atividade__evento"), pk=pk
    )
    if inscricao.inscricao_evento.participante_id != request.user.pk:
        raise PermissionDenied("Você só pode cancelar as suas próprias inscrições.")
    atividade = inscricao.atividade
    services.cancelar_inscricao_atividade(inscricao)
    messages.success(request, f"Inscrição em \"{atividade.titulo}\" cancelada.")
    return _voltar(request, atividade.evento)


@login_required
def minha_agenda(request):
    inscricoes = (
        InscricaoAtividade.objects.filter(inscricao_evento__participante=request.user)
        .select_related("atividade__evento", "atividade__sala")
        .order_by("atividade__inicio", "atividade__fim")
    )
    inscricoes_evento = (
        InscricaoEvento.objects.filter(participante=request.user)
        .select_related("evento")
        .order_by("evento__data_inicio")
    )
    return render(
        request,
        "eventos/agenda.html",
        {"inscricoes": inscricoes, "inscricoes_evento": inscricoes_evento, "next": reverse("eventos:agenda")},
    )
