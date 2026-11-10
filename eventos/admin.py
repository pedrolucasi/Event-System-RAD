from django.contrib import admin

from .models import Atividade, Evento, InscricaoAtividade, InscricaoEvento, Sala


@admin.register(Sala)
class SalaAdmin(admin.ModelAdmin):
    list_display = ["nome", "bloco", "capacidade"]
    list_filter = ["bloco"]
    search_fields = ["nome", "bloco"]


class AtividadeInline(admin.TabularInline):
    model = Atividade
    extra = 0
    fields = ["titulo", "tipo", "responsavel", "sala", "inicio", "fim"]


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ["nome", "data_inicio", "data_fim", "inscricoes_abertas", "organizador"]
    list_filter = ["inscricoes_abertas", "data_inicio", "organizador"]
    search_fields = ["nome", "descricao", "organizador__username"]
    date_hierarchy = "data_inicio"
    inlines = [AtividadeInline]


@admin.register(Atividade)
class AtividadeAdmin(admin.ModelAdmin):
    list_display = ["titulo", "evento", "tipo", "sala", "inicio", "fim", "responsavel", "inscritos"]
    list_filter = ["tipo", "evento", "sala"]
    search_fields = ["titulo", "responsavel", "evento__nome"]
    date_hierarchy = "inicio"
    list_select_related = ["evento", "sala"]

    @admin.display(description="inscritos")
    def inscritos(self, obj):
        return f"{obj.total_inscritos()}/{obj.sala.capacidade}"


class InscricaoAtividadeInline(admin.TabularInline):
    model = InscricaoAtividade
    extra = 0
    readonly_fields = ["data"]


@admin.register(InscricaoEvento)
class InscricaoEventoAdmin(admin.ModelAdmin):
    list_display = ["participante", "evento", "data"]
    list_filter = ["evento"]
    search_fields = ["participante__username", "evento__nome"]
    readonly_fields = ["data"]
    inlines = [InscricaoAtividadeInline]


@admin.register(InscricaoAtividade)
class InscricaoAtividadeAdmin(admin.ModelAdmin):
    list_display = ["participante", "atividade", "evento", "data"]
    list_filter = ["atividade__evento", "atividade"]
    search_fields = ["inscricao_evento__participante__username", "atividade__titulo"]
    readonly_fields = ["data"]
    list_select_related = ["inscricao_evento__participante", "atividade__evento"]

    @admin.display(description="evento")
    def evento(self, obj):
        return obj.atividade.evento
