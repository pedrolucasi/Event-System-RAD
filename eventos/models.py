from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count, F
from django.urls import reverse
from django.utils import timezone


def intervalos_sobrepostos(inicio_a, fim_a, inicio_b, fim_b):
    """Dois intervalos [inicio, fim) se sobrepõem se cada um começa antes do outro terminar.

    Cobre todos os casos: parcial à esquerda, parcial à direita, um contendo o outro
    e intervalos idênticos. Intervalos que apenas se encostam (fim == início) não conflitam.
    """
    return inicio_a < fim_b and fim_a > inicio_b


class Sala(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    bloco = models.CharField(max_length=100, blank=True)
    capacidade = models.PositiveIntegerField(help_text="Número de lugares; limita as inscrições.")

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.bloco})" if self.bloco else self.nome


class Evento(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    data_inicio = models.DateField("data de início")
    data_fim = models.DateField("data de fim")
    inscricoes_abertas = models.BooleanField("inscrições abertas", default=True)
    organizador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="eventos_organizados",
    )

    class Meta:
        ordering = ["data_inicio", "nome"]

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse("eventos:detalhe", args=[self.pk])

    def clean(self):
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            raise ValidationError({"data_fim": "A data de fim não pode ser anterior à data de início."})

        if self.pk and self.data_inicio and self.data_fim:
            fora = [
                a for a in self.atividades.all()
                if timezone.localtime(a.inicio).date() < self.data_inicio
                or timezone.localtime(a.fim).date() > self.data_fim
            ]
            if fora:
                titulos = ", ".join(a.titulo for a in fora)
                raise ValidationError(
                    f"O novo período deixaria atividades fora do evento: {titulos}."
                )


class AtividadeQuerySet(models.QuerySet):
    def com_vagas(self):
        return self.annotate(num_inscritos=Count("inscricoes", distinct=True)).annotate(
            vagas=F("sala__capacidade") - F("num_inscritos")
        )


class Atividade(models.Model):
    class Tipo(models.TextChoices):
        PALESTRA = "PALESTRA", "Palestra"
        TREINAMENTO = "TREINAMENTO", "Treinamento"
        APRESENTACAO = "APRESENTACAO", "Apresentação"

    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="atividades")
    titulo = models.CharField("título", max_length=200)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    descricao = models.TextField("descrição", blank=True)
    responsavel = models.CharField("responsável", max_length=200)
    sala = models.ForeignKey(Sala, on_delete=models.PROTECT, related_name="atividades")
    inicio = models.DateTimeField("início")
    fim = models.DateTimeField()

    objects = AtividadeQuerySet.as_manager()

    class Meta:
        ordering = ["inicio"]

    def __str__(self):
        return f"{self.titulo} ({self.evento})"

    def total_inscritos(self):
        return self.inscricoes.count()

    def clean(self):
        if not (self.inicio and self.fim):
            return

        if self.fim <= self.inicio:
            raise ValidationError({"fim": "O fim da atividade precisa ser depois do início."})

        if self.evento_id:
            evento = self.evento
            if (
                timezone.localtime(self.inicio).date() < evento.data_inicio
                or timezone.localtime(self.fim).date() > evento.data_fim
            ):
                raise ValidationError(
                    f"A atividade precisa acontecer dentro do período do evento "
                    f"({evento.data_inicio:%d/%m/%Y} a {evento.data_fim:%d/%m/%Y})."
                )

        if self.sala_id:
            # RN3: a mesma sala não pode ter duas atividades sobrepostas, de qualquer evento.
            ocupada = (
                Atividade.objects.filter(sala_id=self.sala_id, inicio__lt=self.fim, fim__gt=self.inicio)
                .exclude(pk=self.pk)
                .select_related("evento")
                .first()
            )
            if ocupada:
                raise ValidationError({
                    "sala": f"A sala já está ocupada nesse horário por \"{ocupada.titulo}\" "
                            f"({timezone.localtime(ocupada.inicio):%d/%m %H:%M}–"
                            f"{timezone.localtime(ocupada.fim):%H:%M}, evento {ocupada.evento})."
                })

            if self.pk:
                inscritos = self.inscricoes.count()
                if inscritos > self.sala.capacidade:
                    raise ValidationError({
                        "sala": f"A sala comporta {self.sala.capacidade} pessoas, mas a atividade "
                                f"já tem {inscritos} inscritos."
                    })


class InscricaoEvento(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="inscricoes")
    participante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inscricoes_evento",
    )
    data = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "inscrição no evento"
        verbose_name_plural = "inscrições em eventos"
        ordering = ["-data"]
        constraints = [
            models.UniqueConstraint(
                fields=["evento", "participante"],
                name="inscricao_unica_por_evento",
                violation_error_message="Você já está inscrito neste evento.",
            )
        ]

    def __str__(self):
        return f"{self.participante} em {self.evento}"

    def clean(self):
        if self._state.adding and self.evento_id and not self.evento.inscricoes_abertas:
            raise ValidationError("As inscrições deste evento estão fechadas.")


class InscricaoAtividade(models.Model):
    # Ligar à InscricaoEvento (e não direto ao usuário) garante pela estrutura que só
    # existe inscrição em atividade para quem está inscrito em algum evento, e o CASCADE
    # faz o cancelamento do evento remover as atividades (RN5).
    inscricao_evento = models.ForeignKey(
        InscricaoEvento,
        on_delete=models.CASCADE,
        related_name="inscricoes_atividade",
        verbose_name="inscrição no evento",
    )
    atividade = models.ForeignKey(Atividade, on_delete=models.CASCADE, related_name="inscricoes")
    data = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "inscrição em atividade"
        verbose_name_plural = "inscrições em atividades"
        ordering = ["atividade__inicio"]
        constraints = [
            models.UniqueConstraint(
                fields=["inscricao_evento", "atividade"],
                name="inscricao_unica_por_atividade",
                violation_error_message="Você já está inscrito nesta atividade.",
            )
        ]

    def __str__(self):
        return f"{self.inscricao_evento.participante} em {self.atividade.titulo}"

    @property
    def participante(self):
        return self.inscricao_evento.participante

    def clean(self):
        if not (self.inscricao_evento_id and self.atividade_id):
            return

        atividade = self.atividade
        inscricao_evento = self.inscricao_evento

        # RN4: a inscrição no evento precisa ser do mesmo evento da atividade.
        if inscricao_evento.evento_id != atividade.evento_id:
            raise ValidationError("É preciso estar inscrito no evento desta atividade.")

        # RN1: capacidade vem da sala; contagem feita no banco no momento do envio.
        inscritos = atividade.inscricoes.exclude(pk=self.pk).count()
        if inscritos >= atividade.sala.capacidade:
            raise ValidationError("Atividade lotada: não há mais vagas na sala.")

        # RN2: conflito considera todas as atividades do participante, de qualquer evento.
        conflito = (
            InscricaoAtividade.objects.filter(
                inscricao_evento__participante_id=inscricao_evento.participante_id,
                atividade__inicio__lt=atividade.fim,
                atividade__fim__gt=atividade.inicio,
            )
            .exclude(pk=self.pk)
            .select_related("atividade__evento")
            .first()
        )
        if conflito:
            outra = conflito.atividade
            raise ValidationError(
                f"Conflito de horário com \"{outra.titulo}\" do evento {outra.evento} "
                f"({timezone.localtime(outra.inicio):%d/%m %H:%M}–{timezone.localtime(outra.fim):%H:%M})."
            )
