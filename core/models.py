from datetime import date, datetime, timedelta
import uuid

from django.contrib.auth.models import User
from django.db import models


# =========================================================
# PILOTOS / USUÁRIOS
# =========================================================

class Piloto(models.Model):
    PERFIL_CHOICES = [
        ("administrador", "Administrador"),
        ("coordenador", "Coordenador"),
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

    cpf = models.CharField(max_length=14, blank=True, verbose_name="CPF")
    codigo_sarpas = models.CharField(max_length=50, blank=True, verbose_name="Código SARPAS")

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

    foto = models.ImageField(
        upload_to="perfis/%Y/%m/",
        null=True,
        blank=True,
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

    prefixo = models.CharField(
        max_length=50,
        blank=True,
        default="",
        db_index=True,
        verbose_name="Prefixo",
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
        ("fotografia", "Fotografia"),
        ("treinamento", "Treinamento"),
        ("outro", "Outro"),
    ]

    data = models.DateField(null=True, blank=True)

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

    hora_inicio = models.TimeField(null=True, blank=True)

    hora_fim = models.TimeField(null=True, blank=True)

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

    alocacao_calendario = models.OneToOneField(
        "Alocacao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voo_sincronizado",
    )

    class Meta:
        ordering = [
            "-data",
            "-hora_inicio",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["data", "piloto", "drone"],
                condition=models.Q(data__isnull=False),
                name="voo_unico_por_data_piloto_drone",
            ),
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
    def duracao_segundos_operacionais(self):
        logs_carregados = getattr(self, "logs_concluidos", None)
        if logs_carregados is None:
            duracoes = list(
                self.importacoes_log.filter(status="concluida", duracao_segundos__isnull=False)
                .values_list("duracao_segundos", flat=True)
            )
        else:
            duracoes = [
                log.duracao_segundos for log in logs_carregados
                if log.duracao_segundos is not None
            ]
        if duracoes:
            return sum(duracoes)
        return 0

    @property
    def duracao_minutos(self):
        return self.duracao_segundos_operacionais // 60

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

    data_fim = models.DateField(null=True, blank=True, verbose_name="Data de finalização")

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

    @property
    def data_final(self):
        return self.data_fim or self.data

    def conflita(self):
        from .operacao_service import existe_conflito_alocacao

        return existe_conflito_alocacao(
            self.drone,
            self.data,
            self.hora_inicio,
            self.data_final,
            self.hora_fim,
            excluir_pk=self.pk,
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

class PlanejamentoVoo(models.Model):
    STATUS_METEO_CHOICES = [
        ("nao_consultado", "Não consultado"),
        ("favoravel", "Favorável"),
        ("atencao", "Atenção"),
        ("desfavoravel", "Desfavorável"),
        ("indisponivel", "Previsão indisponível"),
    ]
    CONFIRMACAO_CHOICES = [("sim", "Sim"), ("nao", "Não"), ("nao_sei", "Não sei / confirmar")]
    TIPO_AEROLEVANTAMENTO_CHOICES = [
        ("fotogrametrico", "Aerofotogramétrico / ortomosaico / modelo 3D"),
        ("laser", "Varredura a laser / LiDAR"), ("espectral", "Pancromático ou espectral"),
        ("geofisico", "Aerogeofísico"), ("outro", "Outro aerolevantamento"),
    ]

    titulo = models.CharField(max_length=150)
    piloto = models.ForeignKey(Piloto, on_delete=models.PROTECT, related_name="planejamentos_voo")
    data = models.DateField()
    data_fim = models.DateField(null=True, blank=True, verbose_name="Data final")
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()
    altura_maxima_m = models.PositiveIntegerField(default=120)
    finalidade = models.CharField(max_length=100, choices=Voo.FINALIDADE_CHOICES, default="outro")
    local = models.CharField(max_length=200, blank=True, verbose_name="Local/região")
    area_geojson = models.JSONField()
    centro_latitude = models.DecimalField(max_digits=10, decimal_places=7)
    centro_longitude = models.DecimalField(max_digits=10, decimal_places=7)
    area_hectares = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    observacoes = models.TextField(blank=True)
    gera_dados_aerolevantamento = models.BooleanField(
        default=False, verbose_name="A operação produzirá dados de aerolevantamento",
        help_text="Marque se haverá captura destinada a ortomosaico, mapa, modelo 3D, nuvem de pontos, LiDAR, dado espectral ou geofísico.",
    )
    tipo_aerolevantamento = models.CharField(max_length=30, choices=TIPO_AEROLEVANTAMENTO_CHOICES, blank=True)
    atividade_agroflorestal = models.BooleanField(default=False, verbose_name="Atividade agroflorestal")
    exclusivo_proprietario_rural = models.CharField(max_length=12, choices=CONFIRMACAO_CHOICES, default="nao_sei", verbose_name="Destinado exclusivamente ao proprietário do imóvel rural")
    dentro_condicionantes_ica = models.CharField(max_length=12, choices=CONFIRMACAO_CHOICES, default="nao_sei", verbose_name="Operação dentro das condicionantes da ICA 100-40")
    interseca_area_sensivel_defesa = models.CharField(max_length=12, choices=CONFIRMACAO_CHOICES, default="nao_sei", verbose_name="Interseção com área/instalação sensível à Defesa")
    projeto_contiguo_12_meses = models.CharField(max_length=12, choices=CONFIRMACAO_CHOICES, default="nao_sei", verbose_name="Projeto contíguo executado nos últimos 12 meses")
    status_meteorologico = models.CharField(
        max_length=20, choices=STATUS_METEO_CHOICES, default="nao_consultado"
    )
    resumo_meteorologico = models.JSONField(default=dict, blank=True)
    previsao_consultada_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="planejamentos_voo_criados")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data", "-hora_inicio"]
        verbose_name = "Planejamento de voo"
        verbose_name_plural = "Planejamentos de voo"

    def __str__(self):
        return f"{self.titulo} - {self.piloto}"

    @property
    def data_final(self):
        return self.data_fim or self.data

class SolicitacaoVoo(models.Model):
    STATUS_CHOICES = [
        ("solicitado", "Pendente de avaliação"),
        ("aprovado", "Reservado"),
        ("rejeitado", "Rejeitado"),
        ("cancelado", "Cancelado"),
        ("concluido", "Concluído"),
    ]

    piloto = models.ForeignKey(Piloto, on_delete=models.PROTECT, related_name="solicitacoes_voo")
    drone = models.ForeignKey(Drone, on_delete=models.PROTECT, related_name="solicitacoes_voo")
    data = models.DateField()
    data_fim = models.DateField(null=True, blank=True, verbose_name="Data de finalização")
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()
    finalidade = models.CharField(max_length=100, choices=Voo.FINALIDADE_CHOICES)
    local = models.CharField(max_length=200, blank=True)
    observacoes = models.TextField(blank=True)
    planejamento = models.ForeignKey(
        PlanejamentoVoo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitacoes_voo",
    )
    requer_avaliacao_risco = models.BooleanField(
        default=False,
        verbose_name="Necessita avaliação de risco operacional",
    )
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

    @property
    def data_final(self):
        return self.data_fim or self.data

# =========================================================
# CHECKLIST PRÉ-VOO
# =========================================================

class ChecklistPreVoo(models.Model):
    alocacao = models.OneToOneField(
        Alocacao,
        on_delete=models.CASCADE,
        related_name="checklist_pre_voo",
    )
    bateria_ok = models.BooleanField(default=False)
    helices_ok = models.BooleanField(default=False)
    estrutura_ok = models.BooleanField(default=False)
    controle_ok = models.BooleanField(default=False)
    gps_ok = models.BooleanField(default=False)
    memoria_ok = models.BooleanField(default=False)
    area_segura = models.BooleanField(default=False)
    meteorologia_ok = models.BooleanField(default=False)
    observacoes = models.TextField(blank=True)
    concluido = models.BooleanField(default=False)
    preenchido_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="checklists_pre_voo",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    def atualizar_status(self):
        self.concluido = all([
            self.bateria_ok,
            self.helices_ok,
            self.estrutura_ok,
            self.controle_ok,
            self.gps_ok,
            self.memoria_ok,
            self.area_segura,
            self.meteorologia_ok,
        ])

    def __str__(self):
        return f"Checklist - {self.alocacao}"
class RegistroPosVoo(models.Model):
    RESULTADO_CHOICES = [
        ("concluido", "Concluído"),
        ("parcial", "Parcial"),
        ("abortado", "Abortado"),
    ]

    alocacao = models.OneToOneField(
        Alocacao, on_delete=models.CASCADE, related_name="registro_pos_voo"
    )
    voo = models.OneToOneField(
        Voo, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="registro_pos_voo",
    )
    hora_inicio_real = models.TimeField()
    hora_fim_real = models.TimeField()
    resultado = models.CharField(max_length=20, choices=RESULTADO_CHOICES)
    baterias_utilizadas = models.PositiveIntegerField(default=1)
    bateria_inicial = models.PositiveIntegerField(null=True, blank=True)
    bateria_final = models.PositiveIntegerField(null=True, blank=True)
    distancia_m = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    ocorrencias = models.TextField(blank=True)
    danos = models.TextField(blank=True)
    necessita_manutencao = models.BooleanField(default=False)
    observacoes = models.TextField(blank=True)
    concluido = models.BooleanField(default=False)
    preenchido_por = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="registros_pos_voo"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    baterias = models.ManyToManyField(
        "Bateria",
        blank=True,
        related_name="registros_pos_voo",
    )

    class Meta:
        ordering = ["-alocacao__data", "-hora_inicio_real"]
        verbose_name = "Registro pós-voo"
        verbose_name_plural = "Registros pós-voo"

    def __str__(self):
        return f"Pós-voo - {self.alocacao}"

    @property
    def duracao_minutos(self):
        inicio = datetime.combine(self.alocacao.data, self.hora_inicio_real)
        fim = datetime.combine(self.alocacao.data, self.hora_fim_real)
        if fim < inicio:
            fim += timedelta(days=1)
        return int((fim - inicio).total_seconds() // 60)


# =========================================================
# BATERIAS
# =========================================================

class Bateria(models.Model):
    STATUS_CHOICES = [
        ("disponivel", "Disponível"),
        ("em_uso", "Em uso"),
        ("manutencao", "Em manutenção"),
        ("descartada", "Descartada"),
    ]

    codigo = models.CharField(max_length=50, unique=True)
    numero_serie = models.CharField(max_length=100, unique=True)
    fabricante = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    capacidade_mah = models.PositiveIntegerField(null=True, blank=True)
    drone = models.ForeignKey(
        Drone, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="baterias",
    )
    data_aquisicao = models.DateField(null=True, blank=True)
    ciclos_informados = models.PositiveIntegerField(default=0)
    saude_percentual = models.PositiveIntegerField(default=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="disponivel")
    localizacao = models.CharField(max_length=150, blank=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "Bateria"
        verbose_name_plural = "Baterias"

    def __str__(self):
        return f"{self.codigo} - {self.numero_serie}"

    @property
    def voos_registrados(self):
        return self.registros_pos_voo.filter(concluido=True).count()

    @property
    def ciclos_totais(self):
        return self.ciclos_informados + self.voos_registrados


# =========================================================
# PLANOS DE INSPEÇÃO / MANUTENÇÃO PROGRAMADA
# =========================================================

class PlanoInspecao(models.Model):
    TIPO_CHOICES = [
        ("inspecao", "Inspeção"),
        ("preventiva", "Manutenção preventiva"),
        ("componente", "Substituição de componente"),
        ("bateria", "Verificação de bateria"),
    ]

    nome = models.CharField(max_length=150)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default="inspecao")
    drone = models.ForeignKey(Drone, on_delete=models.CASCADE, null=True, blank=True, related_name="planos_inspecao")
    bateria = models.ForeignKey(Bateria, on_delete=models.CASCADE, null=True, blank=True, related_name="planos_inspecao")
    descricao = models.TextField(blank=True)
    intervalo_dias = models.PositiveIntegerField(null=True, blank=True)
    intervalo_voos = models.PositiveIntegerField(null=True, blank=True)
    intervalo_horas = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    intervalo_ciclos = models.PositiveIntegerField(null=True, blank=True)
    ultima_execucao = models.DateField(default=date.today)
    voos_base = models.PositiveIntegerField(default=0)
    minutos_base = models.PositiveIntegerField(default=0)
    ciclos_base = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True)
    criado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="planos_inspecao_criados")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def clean(self):
        from django.core.exceptions import ValidationError
        if bool(self.drone_id) == bool(self.bateria_id):
            raise ValidationError("Selecione um drone ou uma bateria, mas não ambos.")
        if not any([self.intervalo_dias, self.intervalo_voos, self.intervalo_horas, self.intervalo_ciclos]):
            raise ValidationError("Informe pelo menos um intervalo de execução.")

    @property
    def alvo(self):
        return self.drone or self.bateria

    def _uso_atual(self):
        if self.drone_id:
            from .voo_service import filtrar_voos_realizados
            voos = list(filtrar_voos_realizados(Voo.objects.filter(drone_id=self.drone_id)))
            return len(voos), sum(v.duracao_minutos for v in voos), 0
        return 0, 0, self.bateria.ciclos_totais

    @property
    def progresso(self):
        hoje = date.today()
        voos, minutos, ciclos = self._uso_atual()
        valores = []
        if self.intervalo_dias:
            valores.append(max(0, (hoje - self.ultima_execucao).days) / self.intervalo_dias * 100)
        if self.intervalo_voos:
            valores.append(max(0, voos - self.voos_base) / self.intervalo_voos * 100)
        if self.intervalo_horas:
            valores.append(max(0, minutos - self.minutos_base) / (float(self.intervalo_horas) * 60) * 100)
        if self.intervalo_ciclos:
            valores.append(max(0, ciclos - self.ciclos_base) / self.intervalo_ciclos * 100)
        return round(max(valores or [0]), 1)

    @property
    def situacao(self):
        if not self.ativo:
            return "inativo"
        if self.progresso >= 100:
            return "vencido"
        if self.progresso >= 80:
            return "proximo"
        return "em_dia"

    def atualizar_bases(self, data_execucao=None):
        voos, minutos, ciclos = self._uso_atual()
        self.ultima_execucao = data_execucao or date.today()
        self.voos_base = voos
        self.minutos_base = minutos
        self.ciclos_base = ciclos


class ExecucaoInspecao(models.Model):
    plano = models.ForeignKey(PlanoInspecao, on_delete=models.CASCADE, related_name="execucoes")
    data = models.DateField(default=date.today)
    observacoes = models.TextField(blank=True)
    executado_por = models.ForeignKey(User, on_delete=models.PROTECT)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data", "-criado_em"]

    def __str__(self):
        return f"{self.plano} - {self.data}"


# =========================================================
# DOCUMENTOS E VENCIMENTOS
# =========================================================

class Documento(models.Model):
    TIPO_CHOICES = [
        ("habilitacao", "Habilitação / certificado de piloto"),
        ("registro_drone", "Registro do drone"),
        ("seguro", "Seguro"),
        ("autorizacao", "Autorização"),
        ("treinamento", "Treinamento"),
        ("manual", "Manual"),
        ("nota_fiscal", "Nota fiscal"),
        ("outro", "Outro"),
    ]

    titulo = models.CharField(max_length=180)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    numero = models.CharField(max_length=100, blank=True)
    piloto = models.ForeignKey(Piloto, on_delete=models.CASCADE, null=True, blank=True, related_name="documentos")
    drone = models.ForeignKey(Drone, on_delete=models.CASCADE, null=True, blank=True, related_name="documentos")
    bateria = models.ForeignKey(Bateria, on_delete=models.CASCADE, null=True, blank=True, related_name="documentos")
    organizacional = models.BooleanField(default=False)
    data_emissao = models.DateField(null=True, blank=True)
    data_validade = models.DateField(null=True, blank=True)
    arquivo = models.FileField(upload_to="documentos/%Y/%m/", null=True, blank=True)
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    criado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="documentos_criados")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["data_validade", "titulo"]

    def __str__(self):
        return self.titulo

    def clean(self):
        from django.core.exceptions import ValidationError
        alvos = sum(bool(valor) for valor in [self.piloto_id, self.drone_id, self.bateria_id, self.organizacional])
        if alvos != 1:
            raise ValidationError("Selecione exatamente um vínculo: piloto, drone, bateria ou organização.")
        if self.data_emissao and self.data_validade and self.data_validade < self.data_emissao:
            raise ValidationError("A validade não pode ser anterior à emissão.")

    @property
    def alvo(self):
        if self.organizacional:
            return "Organização"
        return self.piloto or self.drone or self.bateria

    @property
    def dias_para_vencer(self):
        if not self.data_validade:
            return None
        return (self.data_validade - date.today()).days

    @property
    def situacao(self):
        if not self.ativo:
            return "inativo"
        if self.dias_para_vencer is None:
            return "sem_validade"
        if self.dias_para_vencer < 0:
            return "vencido"
        if self.dias_para_vencer <= 30:
            return "vencendo"
        return "valido"


# =========================================================
# AVALIAÇÃO DE RISCO E INCIDENTES
# =========================================================

class AvaliacaoRisco(models.Model):
    STATUS_CHOICES = [
        ("rascunho", "Rascunho"),
        ("aprovada", "Aceita pelo piloto"),
    ]
    NIVEL_CHOICES = [(1, "1 - Muito baixo"), (2, "2 - Baixo"), (3, "3 - Moderado"), (4, "4 - Alto"), (5, "5 - Muito alto")]
    AREA_TERCEIROS_CHOICES = [
        ("sim", "Sim"), ("nao", "Não"), ("nao_aplicavel", "Não aplicável"),
    ]

    solicitacao = models.OneToOneField(SolicitacaoVoo, on_delete=models.CASCADE, related_name="avaliacao_risco")
    perigos_identificados = models.TextField()
    probabilidade_inicial = models.PositiveSmallIntegerField(choices=NIVEL_CHOICES)
    impacto_inicial = models.PositiveSmallIntegerField(choices=NIVEL_CHOICES)
    medidas_mitigadoras = models.TextField()
    probabilidade_residual = models.PositiveSmallIntegerField(choices=NIVEL_CHOICES)
    impacto_residual = models.PositiveSmallIntegerField(choices=NIVEL_CHOICES)
    condicoes_meteorologicas = models.TextField(blank=True)
    pessoas_expostas = models.BooleanField(default=False)
    area_controlada = models.BooleanField(default=False)
    observacoes = models.TextField(blank=True)
    operador_nome = models.CharField(max_length=200, blank=True)
    operador_documento = models.CharField(max_length=30, blank=True, verbose_name="CPF/CNPJ do operador")
    codigo_sarpas = models.CharField(max_length=50, blank=True, verbose_name="Código SARPAS")
    aeronave_identificacao = models.TextField(blank=True)
    cenario_operacional = models.TextField(blank=True)
    aspectos_gerais = models.TextField(blank=True)
    legislacao_aplicavel = models.TextField(blank=True)
    area_distante_terceiros = models.CharField(max_length=20, choices=AREA_TERCEIROS_CHOICES, blank=True)
    treinamento_requerido = models.BooleanField(default=False)
    descricao_treinamento = models.TextField(blank=True)
    procedimento_acidente = models.TextField(blank=True)
    situacoes_risco = models.JSONField(default=list, blank=True)
    matriz_risco = models.CharField(max_length=150, blank=True, default="Matriz 5 × 5 da IS E94-003A")
    declaracao_conformidade = models.BooleanField(default=False)
    responsavel_informacoes = models.CharField(max_length=200, blank=True)
    data_avaliacao = models.DateField(default=date.today)
    validade_ate = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="rascunho")
    preenchido_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="avaliacoes_risco_preenchidas")
    analisado_por = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name="avaliacoes_risco_analisadas")
    analisado_em = models.DateTimeField(null=True, blank=True)
    aceito_em = models.DateTimeField(null=True, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Risco - {self.solicitacao}"

    @property
    def risco_inicial(self):
        return self.probabilidade_inicial * self.impacto_inicial

    @property
    def risco_residual(self):
        return self.probabilidade_residual * self.impacto_residual

    @staticmethod
    def classificar(pontuacao):
        if pontuacao >= 17:
            return "critico"
        if pontuacao >= 10:
            return "alto"
        if pontuacao >= 5:
            return "medio"
        return "baixo"

    @property
    def nivel_residual(self):
        return self.classificar(self.risco_residual)


class ConfiguracaoPapelTimbrado(models.Model):
    modelo_relatorios = models.FileField(upload_to="papel_timbrado/", null=True, blank=True)
    modelo_avaliacao_risco = models.FileField(upload_to="papel_timbrado/", null=True, blank=True)
    atualizado_por = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração de papel timbrado"
        verbose_name_plural = "Configurações de papel timbrado"

    @classmethod
    def atual(cls):
        configuracao, _ = cls.objects.get_or_create(pk=1)
        return configuracao


class Incidente(models.Model):
    GRAVIDADE_CHOICES = [("leve", "Leve"), ("moderado", "Moderado"), ("grave", "Grave"), ("critico", "Crítico")]
    STATUS_CHOICES = [("aberto", "Aberto"), ("investigacao", "Em investigação"), ("encerrado", "Encerrado")]
    TIPO_CHOICES = [
        ("falha_equipamento", "Falha de equipamento"), ("perda_sinal", "Perda de sinal"),
        ("queda", "Queda / colisão"), ("violacao_espaco", "Violação de espaço aéreo"),
        ("lesao", "Lesão a pessoa"), ("dano_terceiro", "Dano a terceiro"),
        ("quase_acidente", "Quase acidente"), ("outro", "Outro"),
    ]

    alocacao = models.ForeignKey(Alocacao, on_delete=models.PROTECT, related_name="incidentes")
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    gravidade = models.CharField(max_length=20, choices=GRAVIDADE_CHOICES)
    data_hora = models.DateTimeField()
    descricao = models.TextField()
    acoes_imediatas = models.TextField(blank=True)
    danos = models.TextField(blank=True)
    houve_lesao = models.BooleanField(default=False)
    houve_dano_terceiro = models.BooleanField(default=False)
    notificacao_obrigatoria = models.BooleanField(default=False)
    anexo = models.FileField(upload_to="incidentes/%Y/%m/", null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="aberto")
    causa_raiz = models.TextField(blank=True)
    acoes_corretivas = models.TextField(blank=True)
    registrado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="incidentes_registrados")
    responsavel_investigacao = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name="incidentes_investigados")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_hora"]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.alocacao}"


# =========================================================
# QUALIFICAÇÕES DOS PILOTOS
# =========================================================

class QualificacaoPiloto(models.Model):
    CATEGORIA_CHOICES = [
        ("regulatoria", "Regulatória"), ("modelo_drone", "Modelo de drone"),
        ("tipo_operacao", "Tipo de operação"), ("seguranca", "Segurança"),
        ("software", "Software / processamento"), ("instrutor", "Instrutor"),
        ("outro", "Outro"),
    ]
    NIVEL_CHOICES = [
        ("basico", "Básico"), ("intermediario", "Intermediário"),
        ("avancado", "Avançado"), ("instrutor", "Instrutor"),
    ]

    piloto = models.ForeignKey(Piloto, on_delete=models.CASCADE, related_name="qualificacoes")
    nome = models.CharField(max_length=160)
    categoria = models.CharField(max_length=30, choices=CATEGORIA_CHOICES)
    nivel = models.CharField(max_length=20, choices=NIVEL_CHOICES, default="basico")
    instituicao = models.CharField(max_length=150, blank=True)
    numero_certificado = models.CharField(max_length=100, blank=True)
    modelo_drone = models.CharField(max_length=150, blank=True)
    tipo_operacao = models.CharField(max_length=150, blank=True)
    carga_horaria = models.PositiveIntegerField(null=True, blank=True)
    data_conclusao = models.DateField(null=True, blank=True)
    data_validade = models.DateField(null=True, blank=True)
    documento = models.ForeignKey(Documento, on_delete=models.SET_NULL, null=True, blank=True, related_name="qualificacoes")
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    criado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="qualificacoes_criadas")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["piloto__nome", "categoria", "nome"]

    def __str__(self):
        return f"{self.piloto} - {self.nome}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.data_conclusao and self.data_validade and self.data_validade < self.data_conclusao:
            raise ValidationError("A validade não pode ser anterior à conclusão.")
        if self.documento_id and self.documento.piloto_id != self.piloto_id:
            raise ValidationError("O documento selecionado deve pertencer ao mesmo piloto.")

    @property
    def dias_para_vencer(self):
        return None if not self.data_validade else (self.data_validade - date.today()).days

    @property
    def situacao(self):
        if not self.ativo:
            return "inativa"
        if self.dias_para_vencer is None:
            return "valida"
        if self.dias_para_vencer < 0:
            return "vencida"
        if self.dias_para_vencer <= 30:
            return "vencendo"
        return "valida"


# =========================================================
# IMPORTAÇÃO DE LOGS E TELEMETRIA
# =========================================================

class ImportacaoLog(models.Model):
    STATUS_CHOICES = [
        ("processando", "Processando"), ("concluida", "Concluída"),
        ("erro", "Erro"),
    ]

    voo = models.ForeignKey(Voo, on_delete=models.CASCADE, related_name="importacoes_log")
    arquivo = models.FileField(upload_to="telemetria/%Y/%m/")
    nome_original = models.CharField(max_length=255)
    formato = models.CharField(max_length=20, default="csv")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="processando")
    total_pontos = models.PositiveIntegerField(default=0)
    duracao_segundos = models.PositiveIntegerField(null=True, blank=True)
    inicio_registro = models.DateTimeField(null=True, blank=True)
    fim_registro = models.DateTimeField(null=True, blank=True)
    altitude_maxima_m = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    velocidade_maxima_ms = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    distancia_calculada_m = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    bateria_inicial = models.PositiveIntegerField(null=True, blank=True)
    bateria_final = models.PositiveIntegerField(null=True, blank=True)
    total_alertas = models.PositiveIntegerField(default=0)
    colunas_reconhecidas = models.JSONField(default=list, blank=True)
    origem = models.CharField(max_length=30, default="csv")
    versao_log = models.PositiveSmallIntegerField(null=True, blank=True)
    drone_modelo_detectado = models.CharField(max_length=120, blank=True)
    drone_serial_detectado = models.CharField(max_length=100, blank=True)
    bateria_serial_detectada = models.CharField(max_length=100, blank=True)
    mensagem_erro = models.TextField(blank=True)
    importado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="logs_importados")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Log {self.pk} - {self.voo}"


class PontoTelemetria(models.Model):
    importacao = models.ForeignKey(ImportacaoLog, on_delete=models.CASCADE, related_name="pontos")
    indice = models.PositiveIntegerField()
    instante = models.DateTimeField(null=True, blank=True)
    segundos = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    altitude_m = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    velocidade_ms = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    bateria_percentual = models.PositiveIntegerField(null=True, blank=True)
    satelites = models.PositiveIntegerField(null=True, blank=True)
    sinal_percentual = models.PositiveIntegerField(null=True, blank=True)
    alerta = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["indice"]
        constraints = [models.UniqueConstraint(fields=["importacao", "indice"], name="telemetria_indice_unico")]

    def __str__(self):
        return f"{self.importacao_id} - ponto {self.indice}"


# =========================================================
# EQUIPAMENTOS E COMPONENTES
# =========================================================

class Componente(models.Model):
    TIPO_CHOICES = [
        ("camera", "Câmera"), ("sensor", "Sensor"), ("helice", "Hélice"),
        ("motor", "Motor"), ("gimbal", "Gimbal"), ("controle", "Controle"),
        ("carregador", "Carregador"), ("acessorio", "Acessório"), ("outro", "Outro"),
    ]
    STATUS_CHOICES = [
        ("disponivel", "Disponível"), ("instalado", "Instalado"),
        ("manutencao", "Em manutenção"), ("indisponivel", "Indisponível"),
        ("baixado", "Baixado"),
    ]

    codigo = models.CharField(max_length=50, unique=True)
    nome = models.CharField(max_length=150)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    fabricante = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    numero_serie = models.CharField(max_length=100, blank=True)
    drone = models.ForeignKey(Drone, on_delete=models.PROTECT, null=True, blank=True, related_name="componentes")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="disponivel")
    data_aquisicao = models.DateField(null=True, blank=True)
    data_instalacao = models.DateField(null=True, blank=True)
    vida_util_horas = models.PositiveIntegerField(null=True, blank=True)
    observacoes = models.TextField(blank=True)
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    criado_por = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tipo", "codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class MovimentacaoComponente(models.Model):
    componente = models.ForeignKey(Componente, on_delete=models.CASCADE, related_name="movimentacoes")
    drone_anterior = models.ForeignKey(Drone, on_delete=models.PROTECT, null=True, blank=True, related_name="componentes_removidos")
    drone_novo = models.ForeignKey(Drone, on_delete=models.PROTECT, null=True, blank=True, related_name="componentes_instalados")
    status_anterior = models.CharField(max_length=20, blank=True)
    status_novo = models.CharField(max_length=20)
    motivo = models.CharField(max_length=255, blank=True)
    realizado_por = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.componente} - {self.criado_em}"
