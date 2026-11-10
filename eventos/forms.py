from django import forms

from .models import Atividade, Evento


class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = ["nome", "descricao", "data_inicio", "data_fim", "inscricoes_abertas"]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_fim": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "descricao": forms.Textarea(attrs={"rows": 4}),
        }


class AtividadeForm(forms.ModelForm):
    class Meta:
        model = Atividade
        fields = ["titulo", "tipo", "descricao", "responsavel", "sala", "inicio", "fim"]
        widgets = {
            "inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "fim": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "descricao": forms.Textarea(attrs={"rows": 4}),
        }
