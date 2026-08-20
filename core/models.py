from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.db import models


# =========================================================
# PILOTOS / USUÁRIOS
# =========================================================

class Piloto(models.Model):
    PERFIL_CHOICES = [
        ("administrador", "Administrador"),
        ("usuario", "Usuário"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="piloto",
    )

    nome = models.CharField(
        max_length=150
    )

    matricula = models.CharField(
        max_length=50,
        blank=True
    )

    perfil = models.CharField(
        max_length=20,
        choices=PERFIL_CHOICES,
        default="usuario",
    )

    ativo = models.BooleanField(
        default=True
    )

    primeiro_acesso = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["nome"]
        verbose_name = "Piloto"
        verbose_name_plural = "Pilotos"

    def __str__(self):
        return self.nome


# =========================================================
# DRONES
# =========================================================

class Drone(models.Model):
    STATUS_CHOICES = [
        ("ativo", "Ativo"),
        ("em_campo", "Em campo"),
        ("manutencao", "Em manutenção"),
        ("indisponivel", "Indisponível"),
    ]

    nome = models.CharField(
        max_length=100
    )

    modelo = models.CharField(
        max_length=150
    )

    numero_serie = models.CharField(
        max_length=100,
        blank=True
    )

    localizacao = models.CharField(
        max_length=150,
        blank=True,
        default=""
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="ativo",
    )

    class Meta:
        ordering = ["nome"]
        verbose_name = "Drone"
        verbose_name_plural = "Drones"

    def __str__(self):
        return f"{self.nome} - {self.modelo}"


# =========================================================
# HISTÓRICO DOS DRONES
# =========================================================

class DroneHistorico(models.Model):
    drone = models.ForeignKey(
        Drone,
        on_delete=models.CASCADE,
        related_name="historico",
    )

    status_anterior = models.CharField(
        max_length=20,
        blank=True
    )

    status_novo = models.CharField(
        max_length=20
    )

    localizacao_anterior = models.CharField(
        max_length=150,
        blank=True
    )

    localizacao_nova = models.CharField(
        max_length=150,
        blank=True
    )

    alterado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    alterado_em = models.DateTimeField(
        auto_now_add=True
    )

    observacao = models.CharField(
        max_length=255,
        blank=True
    )

    class Meta:
        ordering = ["-alterado_em"]
        verbose_name = "Histórico do Drone"
        verbose_name_plural = "Históricos dos Drones"

    def __str__(self):
        return (
            f"{self.drone} - "
            f"{self.status_novo} - "
            f"{self.alterado_em}"
        )


# =========================================================
# VOOS
# =========================================================

class Voo(models.Model):
    FINALIDADE_CHOICES = [
        ("levantamento", "Levantamento"),
        ("monitoramento", "Monitoramento"),
        ("inspecao", "Inspeção"),
        ("mapeamento", "Mapeamento"),
        ("treinamento", "Treinamento"),
        ("outro", "Outro"),
    ]

    data = models.DateField()

    piloto = models.ForeignKey(
        Piloto,
        on_delete=models.PROTECT
    )

    drone = models.ForeignKey(
        Drone,
        on_delete=models.PROTECT
    )

    finalidade = models.CharField(
        max_length=30,
        choices=FINALIDADE_CHOICES
    )

    local = models.CharField(
        max_length=200
    )

    hora_inicio = models.TimeField()

    hora_fim = models.TimeField()

    bateria_inicial = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    bateria_final = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    distancia_m = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    observacoes = models.TextField(
        blank=True
    )

    criado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = [
            "-data",
            "-hora_inicio",
        ]
        verbose_name = "Voo"
        verbose_name_plural = "Voos"

    def __str__(self):
        return (
            f"{self.data} - "
            f"{self.piloto} - "
            f"{self.drone}"
        )

    @property
    def duracao_minutos(self):
        inicio = datetime.combine(
            self.data,
            self.hora_inicio
        )

        fim = datetime.combine(
            self.data,
            self.hora_fim
        )

        if fim < inicio:
            fim += timedelta(
                days=1
            )

        return int(
            (
                fim - inicio
            ).total_seconds()
            // 60
        )

    @property
    def consumo_bateria(self):
        if (
            self.bateria_inicial is None
            or self.bateria_final is None
        ):
            return None

        return (
            self.bateria_inicial
            - self.bateria_final
        )


# =========================================================
# ALOCAÇÕES / RESERVAS
# =========================================================

class Alocacao(models.Model):
    STATUS_CHOICES = [
        ("reservado", "Reservado"),
        ("concluido", "Concluído"),
        ("cancelado", "Cancelado"),
    ]

    data = models.DateField()

    hora_inicio = models.TimeField()

    hora_fim = models.TimeField()

    piloto = models.ForeignKey(
        Piloto,
        on_delete=models.PROTECT
    )

    drone = models.ForeignKey(
        Drone,
        on_delete=models.PROTECT
    )

    finalidade = models.CharField(
        max_length=100
    )

    local = models.CharField(
        max_length=200,
        blank=True
    )

    observacoes = models.TextField(
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="reservado",
    )

    criado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT
    )

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = [
            "data",
            "hora_inicio",
        ]
        verbose_name = "Alocação"
        verbose_name_plural = "Alocações"

    def __str__(self):
        return (
            f"{self.data} - "
            f"{self.drone} - "
            f"{self.piloto}"
        )

    def conflita(self):
        return (
            Alocacao.objects
            .filter(
                data=self.data,
                drone=self.drone,
                status="reservado",
                hora_inicio__lt=self.hora_fim,
                hora_fim__gt=self.hora_inicio,
            )
            .exclude(
                pk=self.pk
            )
            .exists()
        )


# =========================================================
# MANUTENÇÕES
# =========================================================

class Manutencao(models.Model):
    TIPO_CHOICES = [
        ("preventiva", "Preventiva"),
        ("corretiva", "Corretiva"),
        ("inspecao", "Inspeção"),
        ("atualizacao", "Atualização"),
    ]

    drone = models.ForeignKey(
        Drone,
        on_delete=models.PROTECT
    )

    tipo = models.CharField(
        max_length=30,
        choices=TIPO_CHOICES
    )

    data_inicio = models.DateField()

    data_fim = models.DateField(
        null=True,
        blank=True
    )

    descricao = models.TextField()

    concluida = models.BooleanField(
        default=False
    )

    criado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT
    )

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = [
            "-data_inicio"
        ]
        verbose_name = "Manutenção"
        verbose_name_plural = "Manutenções"

    def __str__(self):
        return (
            f"{self.drone} - "
            f"{self.get_tipo_display()} - "
            f"{self.data_inicio}"
        )

# =========================================================
# SOLICITAÇÕES DE VOO
# =========================================================

class SolicitacaoVoo(models.Model):
    STATUS_CHOICES = [
        ("solicitado", "Solicitado"),
        ("aprovado", "Aprovado"),
        ("rejeitado", "Rejeitado"),
        ("cancelado", "Cancelado"),
        ("concluido", "Concluído"),
    ]

    piloto = models.ForeignKey(Piloto, on_delete=models.PROTECT, related_name="solicitacoes_voo")
    drone = models.ForeignKey(Drone, on_delete=models.PROTECT, related_name="solicitacoes_voo")
    data = models.DateField()
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()
    finalidade = models.CharField(max_length=100)
    local = models.CharField(max_length=200, blank=True)
    observacoes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="solicitado")
    motivo_rejeicao = models.TextField(blank=True)
    criado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="solicitacoes_voo_criadas")
    analisado_por = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name="solicitacoes_voo_analisadas")
    alocacao = models.OneToOneField(Alocacao, on_delete=models.SET_NULL, null=True, blank=True, related_name="solicitacao_voo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data", "-hora_inicio", "-criado_em"]

    def __str__(self):
        return f"{self.data} - {self.piloto} - {self.drone} - {self.get_status_display()}"

