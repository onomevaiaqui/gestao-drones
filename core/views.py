from functools import wraps
from collections import defaultdict
from datetime import date, timedelta, datetime
import calendar as pycalendar
import csv
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from .models import (
    Piloto,
    Drone,
    DroneHistorico,
    Voo,
    Alocacao,
    Manutencao,
    Documento,
    ConfiguracaoPapelTimbrado,
    SolicitacaoVoo,
)
from .drone_documento_forms import DocumentoDroneForm
from .papel_timbrado import PapelTimbradoRelatorioForm, aplicar_papel_timbrado

from .forms import (
    PilotoForm,
    PilotoEditForm,
    PrimeiroAcessoSenhaForm,
    DroneForm,
    VooForm,
    AlocacaoForm,
    ManutencaoForm,
)


# =========================================================
# PERMISSÕES E CONTEXTO
# =========================================================

def usuario_tem_perfil_admin(user):
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    try:
        return (
            user.piloto.perfil == "administrador"
            and user.piloto.ativo
        )
    except Piloto.DoesNotExist:
        return False


def usuario_e_admin(user):
    if not usuario_tem_perfil_admin(user):
        return False
    return getattr(user, "_modo_acesso", None) not in ("usuario", "coordenador", "pendente")


def usuario_e_coordenador(user):
    if not user.is_authenticated:
        return False
    modo = getattr(user, "_modo_acesso", None)
    if usuario_tem_perfil_admin(user):
        return modo == "coordenador"
    try:
        return user.piloto.perfil == "coordenador" and user.piloto.ativo
    except Piloto.DoesNotExist:
        return False


def usuario_tem_visao_global(user):
    return usuario_e_admin(user) or usuario_e_coordenador(user)


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not usuario_e_admin(request.user):
            messages.error(
                request,
                "Você não tem permissão para acessar esta área."
            )
            return redirect("dashboard")

        return view_func(request, *args, **kwargs)

    return wrapper


def visao_global_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not usuario_tem_visao_global(request.user):
            messages.error(request, "Você não tem permissão para acessar esta área.")
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)
    return wrapper


def _base_context(request):
    eh_admin = usuario_e_admin(request.user)
    eh_coordenador = usuario_e_coordenador(request.user)
    contexto = {
        "eh_admin": eh_admin,
        "eh_coordenador": eh_coordenador,
        "visao_global": eh_admin or eh_coordenador,
        "pode_escolher_modo": usuario_tem_perfil_admin(request.user),
        "modo_acesso": "admin" if eh_admin else ("coordenador" if eh_coordenador else "usuario"),
    }
    if eh_admin or eh_coordenador:
        from .alerta_service import resumo_alertas
        contexto["alertas_resumo_global"] = resumo_alertas()
    return contexto


# =========================================================
# E-MAIL DE ACESSO
# =========================================================

def _enviar_email_acesso(request, piloto):
    if not piloto.user or not piloto.user.email:
        raise ValueError(
            "O piloto não possui e-mail cadastrado."
        )

    site_url = getattr(
        settings,
        "SITE_URL",
        "http://127.0.0.1:8000"
    ).rstrip("/")

    login_url = (
        f"{site_url}/login/?next=/primeiro-acesso/"
    )

    contexto = {
        "piloto": piloto,
        "usuario": piloto.user,
        "login_url": login_url,
        "site_url": site_url,
    }

    assunto = (
        "Seu acesso ao Sistema de Gestão de Drones"
    )

    texto = render_to_string(
        "emails/acesso_usuario.txt",
        contexto
    )

    html = render_to_string(
        "emails/acesso_usuario.html",
        contexto
    )

    msg = EmailMultiAlternatives(
        assunto,
        texto,
        settings.DEFAULT_FROM_EMAIL,
        [piloto.user.email],
    )

    msg.attach_alternative(
        html,
        "text/html"
    )

    msg.send(
        fail_silently=False
    )


# =========================================================
# PRIMEIRO ACESSO
# =========================================================

def _redirecionar_primeiro_acesso(request):
    if request.user.is_superuser:
        return None

    try:
        piloto = request.user.piloto
    except Piloto.DoesNotExist:
        return None

    if piloto.primeiro_acesso:
        return redirect(
            "primeiro_acesso"
        )

    return None


@login_required
def primeiro_acesso(request):
    if request.user.is_superuser:
        return redirect("dashboard")

    try:
        piloto = request.user.piloto
    except Piloto.DoesNotExist:
        return redirect("dashboard")

    if not piloto.primeiro_acesso:
        return redirect("dashboard")

    form = PrimeiroAcessoSenhaForm(
        request.user,
        request.POST or None
    )

    if (
        request.method == "POST"
        and "alterar_senha" in request.POST
        and form.is_valid()
    ):
        user = form.save()

        update_session_auth_hash(
            request,
            user
        )

        piloto.primeiro_acesso = False
        piloto.save(
            update_fields=["primeiro_acesso"]
        )

        messages.success(
            request,
            "Senha alterada com sucesso."
        )

        return redirect("dashboard")

    ctx = {
        "form": form,
        "piloto": piloto,
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "primeiro_acesso/index.html",
        ctx
    )


@login_required
@require_POST
def primeiro_acesso_continuar(request):
    if request.user.is_superuser:
        return redirect("dashboard")

    try:
        piloto = request.user.piloto
    except Piloto.DoesNotExist:
        return redirect("dashboard")

    piloto.primeiro_acesso = False
    piloto.save(
        update_fields=["primeiro_acesso"]
    )

    messages.success(
        request,
        "Acesso confirmado. Você continuará usando a senha atual."
    )

    return redirect("dashboard")


# =========================================================
# RESERVAS - FUNÇÕES AUXILIARES
# =========================================================

def _reserva_pertence_ao_usuario(request, alocacao):
    if usuario_e_admin(request.user):
        return True

    try:
        return (
            alocacao.piloto_id
            == request.user.piloto.id
        )
    except Piloto.DoesNotExist:
        return False


def _atualizar_reservas_vencidas():
    agora = timezone.localtime()

    abertas = Alocacao.objects.filter(
        status="reservado",
        data__lte=agora.date(),
    )

    ids_concluir = []

    for reserva in abertas:
        fim = timezone.make_aware(
            datetime.combine(
                reserva.data,
                reserva.hora_fim
            ),
            timezone.get_current_timezone(),
        )

        if fim <= agora:
            ids_concluir.append(
                reserva.pk
            )

    if ids_concluir:
        Alocacao.objects.filter(
            pk__in=ids_concluir
        ).update(
            status="concluido"
        )



def _atualizar_status_drones_por_reserva():
    agora = timezone.localtime()
    reservas_ativas = (
        Alocacao.objects
        .filter(
            status="reservado",
            data=agora.date(),
            hora_inicio__lte=agora.time(),
            hora_fim__gt=agora.time(),
        )
        .select_related("drone")
    )

    drones_em_reserva = set()

    for reserva in reservas_ativas:
        drone = reserva.drone
        drones_em_reserva.add(drone.pk)

        if drone.status in ("manutencao", "indisponivel"):
            continue

        if drone.status != "em_campo":
            anterior = drone.status
            drone.status = "em_campo"
            drone.save(update_fields=["status"])

            DroneHistorico.objects.create(
                drone=drone,
                status_anterior=anterior,
                status_novo="em_campo",
                localizacao_anterior=getattr(drone, "localizacao", ""),
                localizacao_nova=getattr(drone, "localizacao", ""),
                alterado_por=None,
                observacao="Status alterado automaticamente por reserva em andamento",
            )

    for drone in Drone.objects.filter(status="em_campo").exclude(pk__in=drones_em_reserva):
        drone.status = "ativo"
        drone.save(update_fields=["status"])

        DroneHistorico.objects.create(
            drone=drone,
            status_anterior="em_campo",
            status_novo="ativo",
            localizacao_anterior=getattr(drone, "localizacao", ""),
            localizacao_nova=getattr(drone, "localizacao", ""),
            alterado_por=None,
            observacao="Reserva finalizada. Status retornado automaticamente para Ativo",
        )


# =========================================================
# DASHBOARD
# =========================================================

@login_required
def dashboard(request):
    _atualizar_reservas_vencidas()

    if "_atualizar_status_drones_por_reserva" in globals():
        _atualizar_status_drones_por_reserva()

    primeiro = _redirecionar_primeiro_acesso(request)
    if primeiro:
        return primeiro

    from .voo_service import filtrar_voos_realizados
    voos_qs = filtrar_voos_realizados(Voo.objects.select_related("piloto", "drone")).filter(
        data__isnull=False, hora_inicio__isnull=False, hora_fim__isnull=False,
    )
    piloto_sessao = None
    visao_global = usuario_tem_visao_global(request.user)
    if not visao_global:
        try:
            piloto_sessao = request.user.piloto
            voos_qs = voos_qs.filter(piloto=piloto_sessao)
        except Piloto.DoesNotExist:
            voos_qs = voos_qs.none()

    inicio = request.GET.get("inicio")
    fim = request.GET.get("fim")

    if inicio:
        voos_qs = voos_qs.filter(data__gte=inicio)

    if fim:
        voos_qs = voos_qs.filter(data__lte=fim)

    total_voos = voos_qs.count()
    total_segundos = sum(voo.duracao_segundos_operacionais for voo in voos_qs)
    total_minutos = total_segundos // 60
    horas = total_minutos // 60
    minutos = total_minutos % 60

    distancia_total_m = sum(
        float(voo.distancia_m or 0)
        for voo in voos_qs
    )

    media_minutos = round(total_segundos / 60 / total_voos) if total_voos else 0

    pilotos_data = []
    for piloto in Piloto.objects.filter(ativo=True):
        segundos_piloto = sum(
            voo.duracao_segundos_operacionais
            for voo in voos_qs
            if voo.piloto_id == piloto.id
        )
        if segundos_piloto > 0:
            pilotos_data.append({
                "nome": piloto.nome,
                "horas": round(segundos_piloto / 3600, 2),
            })

    drones_data = []
    for drone in Drone.objects.all():
        segundos_drone = sum(
            voo.duracao_segundos_operacionais
            for voo in voos_qs
            if voo.drone_id == drone.id
        )
        if segundos_drone > 0:
            drones_data.append({
                "nome": drone.nome,
                "horas": round(segundos_drone / 3600, 2),
            })

    finalidade_map = defaultdict(int)
    for voo in voos_qs:
        finalidade_map[voo.get_finalidade_display()] += voo.duracao_segundos_operacionais

    finalidades_data = [
        {
            "nome": nome,
            "horas": round(minutos_finalidade / 3600, 2),
        }
        for nome, minutos_finalidade in finalidade_map.items()
    ]

    dias = defaultdict(int)
    for voo in voos_qs:
        dias[voo.data.isoformat()] += voo.duracao_segundos_operacionais

    tempo_data = [
        {
            "data": data_voo,
            "horas": round(minutos_dia / 3600, 2),
        }
        for data_voo, minutos_dia in sorted(dias.items())
    ]

    status_drones = {
        "ativos": Drone.objects.filter(status="ativo").count(),
        "em_campo": Drone.objects.filter(status="em_campo").count(),
        "manutencao": Drone.objects.filter(status="manutencao").count(),
        "indisponiveis": Drone.objects.filter(status="indisponivel").count(),
    }

    agora_dashboard = timezone.localtime()

    operacoes_agora_qs = (
        Alocacao.objects
        .select_related("piloto", "drone")
        .filter(
            status="reservado",
            data=agora_dashboard.date(),
            hora_inicio__lte=agora_dashboard.time(),
            hora_fim__gt=agora_dashboard.time(),
        )
        .order_by("hora_inicio", "piloto__nome")
    )
    if piloto_sessao:
        operacoes_agora_qs = operacoes_agora_qs.filter(piloto=piloto_sessao)
    operacoes_agora = list(operacoes_agora_qs)

    operacoes_mapa = []
    if visao_global:
        reservas_mapa = (
            Alocacao.objects
            .select_related("piloto", "drone", "solicitacao_voo__planejamento")
            .filter(data=agora_dashboard.date())
            .exclude(status="cancelado")
            .order_by("hora_inicio")
        )
        for reserva in reservas_mapa:
            try:
                solicitacao = reserva.solicitacao_voo
            except SolicitacaoVoo.DoesNotExist:
                continue
            planejamento = solicitacao.planejamento
            if not planejamento or not planejamento.area_geojson:
                continue
            em_andamento = (
                reserva.status == "reservado"
                and reserva.hora_inicio <= agora_dashboard.time() < reserva.hora_fim
            )
            operacoes_mapa.append({
                "id": reserva.pk,
                "piloto": reserva.piloto.nome,
                "drone": reserva.drone.nome,
                "prefixo": reserva.drone.prefixo,
                "local": reserva.local or planejamento.local or "Local não informado",
                "horario": f"{reserva.hora_inicio.strftime('%H:%M')}–{reserva.hora_fim.strftime('%H:%M')}",
                "finalidade": reserva.finalidade,
                "situacao": "em_andamento" if em_andamento else reserva.status,
                "area": planejamento.area_geojson,
                "centro": [float(planejamento.centro_latitude), float(planejamento.centro_longitude)],
            })

    reservas_hoje_qs = Alocacao.objects.filter(
        data=agora_dashboard.date(),
        status="reservado",
    )
    if piloto_sessao:
        reservas_hoje_qs = reservas_hoje_qs.filter(piloto=piloto_sessao)
    reservas_hoje = reservas_hoje_qs.count()

    proximas_reservas_qs = (
        Alocacao.objects
        .select_related("piloto", "drone")
        .filter(
            status="reservado",
            data__gte=agora_dashboard.date(),
        )
    )
    if piloto_sessao:
        proximas_reservas_qs = proximas_reservas_qs.filter(piloto=piloto_sessao)
    proximas_reservas = proximas_reservas_qs.order_by("data", "hora_inicio")[:8]

    concluidas_sem_log_qs = Alocacao.objects.filter(status="concluido").exclude(
        voo_sincronizado__importacoes_log__status="concluida"
    )
    if piloto_sessao:
        concluidas_sem_log_qs = concluidas_sem_log_qs.filter(piloto=piloto_sessao)

    equipe_resumo = []
    inspecoes_atencao = []
    documentos_aeronaves_atencao = []
    seguranca_resumo = {}
    if visao_global:
        from .qualificacao_views import resumo_equipe_operacional
        from .models import AvaliacaoRisco, Documento, Incidente, PlanoInspecao
        equipe_resumo = resumo_equipe_operacional(limite=6)
        planos = list(
            PlanoInspecao.objects.filter(ativo=True, drone__isnull=False)
            .select_related("drone")
        )
        planos.sort(key=lambda plano: ({"vencido": 0, "proximo": 1, "em_dia": 2}.get(plano.situacao, 3), -plano.progresso))
        inspecoes_atencao = [plano for plano in planos if plano.situacao in {"vencido", "proximo"}][:6]
        limite_documentos = agora_dashboard.date() + timedelta(days=30)
        documentos_aeronaves_atencao = list(
            Documento.objects.filter(
                ativo=True,
                drone__isnull=False,
                data_validade__isnull=False,
                data_validade__lte=limite_documentos,
            ).select_related("drone").order_by("data_validade")[:6]
        )
        avaliacoes_aceitas = AvaliacaoRisco.objects.filter(status="aprovada")
        seguranca_resumo = {
            "riscos_pendentes": SolicitacaoVoo.objects.filter(requer_avaliacao_risco=True)
                .exclude(avaliacao_risco__status="aprovada").exclude(status__in=["cancelado", "rejeitado", "concluido"]).count(),
            "riscos_altos": sum(avaliacao.nivel_residual in {"alto", "critico"} for avaliacao in avaliacoes_aceitas),
            "incidentes_abertos": Incidente.objects.exclude(status="encerrado").count(),
            "incidentes_graves": Incidente.objects.filter(gravidade__in=["grave", "critico"]).exclude(status="encerrado").count(),
        }

    ctx = {
        "total_voos": total_voos,
        "total_horas": f"{horas}h {minutos:02d}min",
        "distancia_total": round(distancia_total_m / 1000, 2),
        "media_minutos": media_minutos,
        "reservas_hoje": reservas_hoje,
        "drones_em_campo": status_drones["em_campo"],
        "drones_em_manutencao": status_drones["manutencao"],
        "operacoes_agora": operacoes_agora,
        "operacoes_agora_total": len(operacoes_agora),
        "operacoes_mapa": operacoes_mapa,
        "pilotos_ativos_total": Piloto.objects.filter(ativo=True).count() if visao_global else (1 if piloto_sessao else 0),
        "operacoes_sem_log": concluidas_sem_log_qs.distinct().count(),
        "equipe_resumo": equipe_resumo,
        "inspecoes_atencao": inspecoes_atencao,
        "documentos_aeronaves_atencao": documentos_aeronaves_atencao,
        "seguranca_resumo": seguranca_resumo,
        "pilotos_data": pilotos_data,
        "drones_data": drones_data,
        "finalidades_data": finalidades_data,
        "tempo_data": tempo_data,
        "status_drones": status_drones,
        "proximas_reservas": proximas_reservas,
        "ultimos_voos": voos_qs[:6],
        "inicio": inicio or "",
        "fim": fim or "",
    }

    ctx.update(_base_context(request))

    return render(
        request,
        "dashboard.html",
        ctx
    )


@login_required
def minha_agenda(request):
    _atualizar_reservas_vencidas()

    if "_atualizar_status_drones_por_reserva" in globals():
        _atualizar_status_drones_por_reserva()

    hoje = timezone.localdate()

    if usuario_tem_visao_global(request.user):
        reservas = (
            Alocacao.objects
            .select_related("piloto", "drone")
            .filter(status="reservado", data__gte=hoje)
            .order_by("data", "hora_inicio")[:20]
        )
        voos_recentes = (
            Voo.objects
            .select_related("piloto", "drone")
            .order_by("-data", "-hora_inicio")[:10]
        )
        titulo = "Agenda Operacional"
        subtitulo = "Próximas reservas e voos recentes do sistema"
    else:
        try:
            piloto = request.user.piloto
        except Piloto.DoesNotExist:
            messages.error(request, "Seu usuário não está vinculado a um piloto.")
            return redirect("dashboard")

        reservas = (
            Alocacao.objects
            .select_related("piloto", "drone")
            .filter(
                piloto=piloto,
                status="reservado",
                data__gte=hoje,
            )
            .order_by("data", "hora_inicio")[:20]
        )
        voos_recentes = (
            Voo.objects
            .select_related("piloto", "drone")
            .filter(piloto=piloto)
            .order_by("-data", "-hora_inicio")[:10]
        )
        titulo = "Minha Agenda"
        subtitulo = "Suas próximas reservas e seus voos recentes"

    ctx = {
        "reservas": reservas,
        "voos_recentes": voos_recentes,
        "total_reservas": reservas.count(),
        "titulo": titulo,
        "subtitulo": subtitulo,
    }
    ctx.update(_base_context(request))
    return render(request, "agenda/minha_agenda.html", ctx)


def _sincronizar_voo_com_calendario(voo, usuario):
    if not voo.data or not voo.hora_inicio or not voo.hora_fim:
        return None
    agora = timezone.localtime()

    inicio_voo = timezone.make_aware(
        datetime.combine(voo.data, voo.hora_inicio),
        timezone.get_current_timezone(),
    )

    fim_voo = timezone.make_aware(
        datetime.combine(voo.data, voo.hora_fim),
        timezone.get_current_timezone(),
    )

    if fim_voo <= inicio_voo:
        fim_voo += timedelta(days=1)

    status_calendario = "concluido" if fim_voo <= agora else "reservado"

    finalidade_texto = (
        voo.get_finalidade_display()
        if hasattr(voo, "get_finalidade_display")
        else str(voo.finalidade)
    )

    alocacao = voo.alocacao_calendario
    if alocacao is None:
        alocacao = Alocacao.objects.filter(
            piloto=voo.piloto,
            drone=voo.drone,
            data=voo.data,
            hora_inicio=voo.hora_inicio,
            hora_fim=voo.hora_fim,
        ).first()

    if alocacao:
        alocacao.data = voo.data
        alocacao.hora_inicio = voo.hora_inicio
        alocacao.hora_fim = voo.hora_fim
        alocacao.piloto = voo.piloto
        alocacao.drone = voo.drone
        alocacao.finalidade = finalidade_texto
        alocacao.local = voo.local or ""
        alocacao.observacoes = voo.observacoes or ""

        if alocacao.status != "cancelado":
            alocacao.status = status_calendario

        alocacao.save(
            update_fields=[
                "data", "hora_inicio", "hora_fim", "piloto", "drone",
                "finalidade",
                "local",
                "observacoes",
                "status",
            ]
        )
        if voo.alocacao_calendario_id != alocacao.pk:
            voo.alocacao_calendario = alocacao
            voo.save(update_fields=["alocacao_calendario"])
        return alocacao

    alocacao = Alocacao.objects.create(
        data=voo.data,
        hora_inicio=voo.hora_inicio,
        hora_fim=voo.hora_fim,
        piloto=voo.piloto,
        drone=voo.drone,
        finalidade=finalidade_texto,
        local=voo.local or "",
        observacoes=voo.observacoes or "",
        status=status_calendario,
        criado_por=usuario,
    )
    voo.alocacao_calendario = alocacao
    voo.save(update_fields=["alocacao_calendario"])
    return alocacao


# =========================================================
# VOOS
# =========================================================

@login_required
def voos(request):
    _atualizar_status_drones_por_reserva()
    qs = Voo.objects.select_related(
        "piloto",
        "drone"
    )
    piloto_sessao = None
    if not usuario_tem_visao_global(request.user):
        try:
            piloto_sessao = request.user.piloto
            qs = qs.filter(piloto=piloto_sessao)
        except Piloto.DoesNotExist:
            qs = qs.none()

    busca = request.GET.get(
        "q",
        ""
    ).strip()

    piloto_id = request.GET.get("piloto")
    drone_id = request.GET.get("drone")
    finalidade = request.GET.get("finalidade")
    inicio = request.GET.get("inicio")
    fim = request.GET.get("fim")

    if busca:
        qs = qs.filter(
            Q(local__icontains=busca)
            | Q(observacoes__icontains=busca)
            | Q(piloto__nome__icontains=busca)
            | Q(drone__nome__icontains=busca)
        )

    if piloto_id:
        qs = qs.filter(
            piloto_id=piloto_id
        )

    if drone_id:
        qs = qs.filter(
            drone_id=drone_id
        )

    if finalidade:
        qs = qs.filter(
            finalidade=finalidade
        )

    if inicio:
        qs = qs.filter(
            data__gte=inicio
        )

    if fim:
        qs = qs.filter(
            data__lte=fim
        )

    ctx = {
        "voos": qs[:200],
        "pilotos": Piloto.objects.filter(pk=piloto_sessao.pk) if piloto_sessao else Piloto.objects.filter(ativo=True),
        "drones": Drone.objects.all(),
        "finalidades": (
            Voo.FINALIDADE_CHOICES
        ),
        "filtros": request.GET,
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "voos/lista.html",
        ctx
    )


@admin_required
def voo_novo(request):
    _atualizar_status_drones_por_reserva()
    form = VooForm(
        request.POST or None
    )

    if not usuario_e_admin(
        request.user
    ):
        try:
            form.fields[
                "piloto"
            ].queryset = (
                Piloto.objects.filter(
                    pk=request.user.piloto.pk
                )
            )

            form.fields[
                "piloto"
            ].initial = (
                request.user.piloto
            )

            form.fields[
                "piloto"
            ].disabled = True

        except Piloto.DoesNotExist:
            pass

    if form.is_valid():
        voo = form.save(
            commit=False
        )

        voo.criado_por = request.user

        if not usuario_e_admin(
            request.user
        ):
            try:
                voo.piloto = (
                    request.user.piloto
                )
            except Piloto.DoesNotExist:
                messages.error(
                    request,
                    "Seu usuário não está vinculado a um piloto."
                )
                return redirect(
                    "dashboard"
                )

        if voo.drone.status != "ativo":
            form.add_error(
                "drone",
                "Este drone não está disponível para novos voos."
            )

            ctx = {
                "form": form,
                "titulo": "Registrar novo voo",
            }

            ctx.update(
                _base_context(request)
            )

            return render(
                request,
                "voos/form.html",
                ctx
            )

        voo.save()

        _sincronizar_voo_com_calendario(
            voo,
            request.user
        )

        messages.success(
            request,
            "Voo registrado e calendário atualizado com sucesso."
        )

        return redirect(
            "voos"
        )

    ctx = {
        "form": form,
        "titulo": "Registrar novo voo",
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "voos/form.html",
        ctx
    )


@admin_required
def voo_editar(request, pk):
    voo = get_object_or_404(
        Voo,
        pk=pk
    )

    form = VooForm(
        request.POST or None,
        instance=voo
    )

    if form.is_valid():
        voo = form.save()

        _sincronizar_voo_com_calendario(
            voo,
            request.user
        )

        messages.success(
            request,
            "Voo atualizado com sucesso."
        )

        return redirect(
            "voos"
        )

    ctx = {
        "form": form,
        "titulo": (
            f"Editar voo - "
            f"{voo.data.strftime('%d/%m/%Y') if voo.data else 'aguardando telemetria'}"
        ),
        "voo": voo,
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "voos/form.html",
        ctx
    )


@admin_required
@require_POST
def voo_excluir(request, pk):
    voo = get_object_or_404(
        Voo,
        pk=pk
    )

    alocacao = voo.alocacao_calendario
    voo.delete()
    if alocacao and not hasattr(alocacao, "solicitacao_voo") and not hasattr(alocacao, "registro_pos_voo"):
        alocacao.delete()

    messages.success(
        request,
        "Voo excluído com sucesso."
    )

    return redirect(
        "voos"
    )


# =========================================================
# PILOTOS / USUÁRIOS
# =========================================================

@admin_required
def pilotos(request):
    ctx = {
        "pilotos": (
            Piloto.objects
            .select_related("user")
            .all()
        )
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "pilotos/lista.html",
        ctx
    )


@admin_required
def piloto_novo(request):
    form = PilotoForm(
        request.POST or None
    )

    if form.is_valid():
        piloto = form.save()

        if form.cleaned_data.get(
            "enviar_email_acesso"
        ):
            try:
                _enviar_email_acesso(
                    request,
                    piloto
                )

                messages.success(
                    request,
                    (
                        "Piloto criado e e-mail "
                        f"enviado para "
                        f"{piloto.user.email}."
                    )
                )

            except Exception as exc:
                messages.warning(
                    request,
                    (
                        "Piloto criado, mas o "
                        "e-mail não pôde ser enviado: "
                        f"{exc}"
                    )
                )

        else:
            messages.success(
                request,
                "Piloto e usuário criados com sucesso."
            )

        return redirect(
            "pilotos"
        )

    ctx = {
        "form": form,
        "titulo": "Novo piloto / usuário",
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "form.html",
        ctx
    )


@admin_required
def piloto_editar(request, pk):
    piloto = get_object_or_404(
        Piloto,
        pk=pk
    )

    form = PilotoEditForm(
        request.POST or None,
        instance=piloto
    )

    if form.is_valid():
        try:
            piloto = form.save()

            if form.cleaned_data.get(
                "enviar_email_acesso"
            ):
                piloto.primeiro_acesso = True
                piloto.save(
                    update_fields=[
                        "primeiro_acesso"
                    ]
                )

                _enviar_email_acesso(
                    request,
                    piloto
                )

                messages.success(
                    request,
                    (
                        "Piloto atualizado e "
                        "e-mail enviado para "
                        f"{piloto.user.email}."
                    )
                )

            else:
                messages.success(
                    request,
                    "Piloto atualizado com sucesso."
                )

            return redirect(
                "pilotos"
            )

        except Exception as exc:
            form.add_error(
                None,
                str(exc)
            )

    ctx = {
        "form": form,
        "titulo": (
            f"Editar piloto - "
            f"{piloto.nome}"
        ),
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "form.html",
        ctx
    )


@admin_required
@require_POST
def piloto_excluir(request, pk):
    piloto = get_object_or_404(
        Piloto,
        pk=pk
    )

    if piloto.user_id == request.user.id:
        messages.error(
            request,
            "Você não pode excluir a conta que está usando."
        )

        return redirect(
            "pilotos"
        )

    possui_historico = (
        Voo.objects.filter(
            piloto=piloto
        ).exists()
        or
        Alocacao.objects.filter(
            piloto=piloto
        ).exists()
    )

    if possui_historico:
        if piloto.user:
            piloto.user.delete()
            piloto.user = None

        piloto.ativo = False

        piloto.save(
            update_fields=[
                "user",
                "ativo"
            ]
        )

        messages.warning(
            request,
            (
                "O piloto possui histórico. "
                "O acesso foi removido e o "
                "cadastro foi inativado."
            )
        )

        return redirect(
            "pilotos"
        )

    user = piloto.user

    piloto.delete()

    if user:
        user.delete()

    messages.success(
        request,
        "Piloto/usuário excluído."
    )

    return redirect(
        "pilotos"
    )


# =========================================================
# DRONES
# =========================================================

@login_required
def drones(request):
    _atualizar_status_drones_por_reserva()
    from .voo_service import filtrar_voos_realizados
    voos_all = filtrar_voos_realizados(Voo.objects.select_related("drone"))

    drones_lista = []

    for d in Drone.objects.all():
        segundos = sum(
            v.duracao_segundos_operacionais
            for v in voos_all
            if v.drone_id == d.id
        )

        ultimo_historico = (
            DroneHistorico.objects
            .filter(drone=d)
            .select_related("alterado_por")
            .first()
        )

        drones_lista.append({
            "obj": d,
            "horas": (
                f"{segundos // 3600}h "
                f"{(segundos % 3600) // 60:02d}min"
            ),
            "ultimo_historico": ultimo_historico,
        })

    ctx = {
        "drones_lista": drones_lista
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "drones/lista.html",
        ctx
    )


@admin_required
def drone_novo(request):
    form = DroneForm(
        request.POST or None
    )

    if form.is_valid():
        drone = form.save()

        DroneHistorico.objects.create(
            drone=drone,
            status_anterior="",
            status_novo=drone.status,
            localizacao_anterior="",
            localizacao_nova=getattr(
                drone,
                "localizacao",
                ""
            ),
            alterado_por=request.user,
            observacao="Cadastro inicial do drone",
        )

        messages.success(
            request,
            "Drone cadastrado com sucesso."
        )

        return redirect(
            "drones"
        )

    ctx = {
        "form": form,
        "titulo": "Novo drone",
    }

    ctx.update(
        _base_context(request)
    )

    return render(request, "drones/form.html", ctx)


@admin_required
def drone_editar(request, pk):
    drone = get_object_or_404(
        Drone,
        pk=pk
    )

    status_anterior = drone.status
    localizacao_anterior = getattr(
        drone,
        "localizacao",
        ""
    )

    adicionando_documento = request.method == "POST" and request.POST.get("acao") == "adicionar_documento"
    form = DroneForm(
        None if adicionando_documento else (request.POST or None),
        instance=drone
    )
    documento_form = DocumentoDroneForm(request.POST if adicionando_documento else None, request.FILES if adicionando_documento else None)
    documento_form.instance.drone = drone
    documento_form.instance.criado_por = request.user

    if adicionando_documento and documento_form.is_valid():
        documento = documento_form.save(commit=False)
        documento.drone = drone
        documento.criado_por = request.user
        documento.ativo = True
        documento.save()
        messages.success(request, "Documento da aeronave adicionado com sucesso.")
        return redirect("drone_editar", pk=drone.pk)

    if form.is_valid():
        drone = form.save()

        localizacao_nova = getattr(
            drone,
            "localizacao",
            ""
        )

        if (
            drone.status != status_anterior
            or localizacao_nova != localizacao_anterior
        ):
            DroneHistorico.objects.create(
                drone=drone,
                status_anterior=status_anterior,
                status_novo=drone.status,
                localizacao_anterior=localizacao_anterior,
                localizacao_nova=localizacao_nova,
                alterado_por=request.user,
                observacao="Alteração pelo formulário de edição",
            )

        messages.success(
            request,
            "Drone atualizado com sucesso."
        )

        return redirect("drone_editar", pk=drone.pk)

    ctx = {
        "form": form,
        "titulo": (
            f"Editar drone - "
            f"{drone.nome}"
        ),
        "drone": drone,
        "documento_form": documento_form,
        "documentos": drone.documentos.filter(ativo=True),
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "drones/form.html",
        ctx
    )


@admin_required
@require_POST
def drone_documento_excluir(request, pk, documento_id):
    drone = get_object_or_404(Drone, pk=pk)
    documento = get_object_or_404(Documento, pk=documento_id, drone=drone)
    documento.ativo = False
    documento.save(update_fields=["ativo", "atualizado_em"])
    messages.success(request, "Documento removido do cadastro da aeronave.")
    return redirect("drone_editar", pk=drone.pk)


@admin_required
@require_POST
def drone_status_atualizar(request, pk):
    drone = get_object_or_404(Drone, pk=pk)
    novo_status = request.POST.get("status")

    validos = {v for v, _n in Drone.STATUS_CHOICES}
    if novo_status not in validos:
        messages.error(request, "Status inválido.")
        return redirect("drones")

    if novo_status == "em_campo":
        messages.warning(request, "O status Em campo é automático.")
        return redirect("drones")

    agora = timezone.localtime()
    reserva_ativa = Alocacao.objects.filter(
        drone=drone,
        status="reservado",
        data=agora.date(),
        hora_inicio__lte=agora.time(),
        hora_fim__gt=agora.time(),
    ).exists()

    if novo_status == "ativo" and reserva_ativa:
        _atualizar_status_drones_por_reserva()
        messages.warning(request, "Este drone possui uma reserva em andamento e permanecerá Em campo.")
        return redirect("drones")

    anterior = drone.status
    if anterior == novo_status:
        return redirect("drones")

    drone.status = novo_status
    drone.save(update_fields=["status"])

    DroneHistorico.objects.create(
        drone=drone,
        status_anterior=anterior,
        status_novo=novo_status,
        localizacao_anterior=getattr(drone, "localizacao", ""),
        localizacao_nova=getattr(drone, "localizacao", ""),
        alterado_por=request.user,
        observacao="Alteração rápida de status",
    )

    messages.success(request, f"Status do drone {drone.nome} atualizado.")
    return redirect("drones")

@login_required
def drone_historico(request, pk):
    drone = get_object_or_404(
        Drone,
        pk=pk
    )

    historico = (
        DroneHistorico.objects
        .filter(drone=drone)
        .select_related("alterado_por")
    )

    ctx = {
        "drone": drone,
        "historico": historico,
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "drones/historico.html",
        ctx
    )


@admin_required
@require_POST
def drone_excluir(request, pk):
    drone = get_object_or_404(
        Drone,
        pk=pk
    )

    possui_historico = (
        Voo.objects.filter(
            drone=drone
        ).exists()
        or
        Alocacao.objects.filter(
            drone=drone
        ).exists()
    )

    if possui_historico:
        status_anterior = drone.status
        drone.status = "indisponivel"

        drone.save(
            update_fields=["status"]
        )

        DroneHistorico.objects.create(
            drone=drone,
            status_anterior=status_anterior,
            status_novo="indisponivel",
            localizacao_anterior=getattr(
                drone,
                "localizacao",
                ""
            ),
            localizacao_nova=getattr(
                drone,
                "localizacao",
                ""
            ),
            alterado_por=request.user,
            observacao=(
                "Drone marcado como indisponível "
                "porque possui histórico operacional"
            ),
        )

        messages.warning(
            request,
            (
                "O drone possui histórico "
                "e foi marcado como "
                "Indisponível."
            )
        )

    else:
        drone.delete()

        messages.success(
            request,
            "Drone excluído com sucesso."
        )

    return redirect(
        "drones"
    )


# =========================================================
# CALENDÁRIO / RESERVAS
# =========================================================

@login_required
def calendario(request):
    _atualizar_reservas_vencidas()

    if "_atualizar_status_drones_por_reserva" in globals():
        _atualizar_status_drones_por_reserva()

    hoje = timezone.localdate()

    try:
        ano = int(request.GET.get("ano", hoje.year))
        mes = int(request.GET.get("mes", hoje.month))
    except (TypeError, ValueError):
        ano = hoje.year
        mes = hoje.month

    mes = max(1, min(12, mes))

    cal = pycalendar.Calendar(firstweekday=6)
    semanas_datas = cal.monthdatescalendar(ano, mes)

    inicio_periodo = semanas_datas[0][0]
    fim_periodo = semanas_datas[-1][-1]

    alocacoes = (
        Alocacao.objects
        .select_related("piloto", "drone")
        .filter(
            data__gte=inicio_periodo,
            data__lte=fim_periodo,
        )
        .order_by(
            "data",
            "hora_inicio",
            "hora_fim",
            "id",
        )
    )
    if not usuario_tem_visao_global(request.user):
        try:
            alocacoes = alocacoes.filter(piloto=request.user.piloto)
        except Piloto.DoesNotExist:
            alocacoes = alocacoes.none()

    por_dia = defaultdict(list)

    for reserva in alocacoes:
        por_dia[reserva.data].append(reserva)

    semanas = []

    for semana_datas in semanas_datas:
        semana = []

        for dia in semana_datas:
            reservas_do_dia = list(
                por_dia.get(dia, [])
            )

            semana.append({
                "data": dia,
                "mes_atual": dia.month == mes,
                "alocacoes": reservas_do_dia,
                "quantidade": len(reservas_do_dia),
            })

        semanas.append(semana)

    primeiro_dia = date(ano, mes, 1)
    anterior = primeiro_dia - timedelta(days=1)

    if mes == 12:
        proximo = date(ano + 1, 1, 1)
    else:
        proximo = date(ano, mes + 1, 1)

    lista_alocacoes = (
        Alocacao.objects
        .select_related("piloto", "drone")
        .filter(
            data__gte=inicio_periodo,
            data__lte=fim_periodo,
        )
        .order_by(
            "data",
            "hora_inicio",
            "hora_fim",
            "id",
        )
    )
    if not usuario_tem_visao_global(request.user):
        try:
            lista_alocacoes = lista_alocacoes.filter(piloto=request.user.piloto)
        except Piloto.DoesNotExist:
            lista_alocacoes = lista_alocacoes.none()

    ctx = {
        "semanas": semanas,
        "mes": mes,
        "ano": ano,
        "anterior": anterior,
        "proximo": proximo,
        "lista_alocacoes": lista_alocacoes,
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "calendario/calendario.html",
        ctx
    )

@login_required
def alocacao_nova(request):
    _atualizar_status_drones_por_reserva()
    if usuario_e_coordenador(request.user):
        messages.error(request, "O perfil de coordenador possui acesso somente para consulta.")
        return redirect("calendario")
    form = AlocacaoForm(
        request.POST or None
    )

    eh_admin = usuario_e_admin(
        request.user
    )

    if not eh_admin:
        try:
            form.fields[
                "piloto"
            ].queryset = (
                Piloto.objects.filter(
                    pk=request.user.piloto.pk
                )
            )

            form.fields[
                "piloto"
            ].initial = (
                request.user.piloto
            )

            form.fields[
                "piloto"
            ].disabled = True

        except Piloto.DoesNotExist:
            pass

    if form.is_valid():
        obj = form.save(
            commit=False
        )

        obj.criado_por = request.user

        if not eh_admin:
            try:
                obj.piloto = (
                    request.user.piloto
                )
            except Piloto.DoesNotExist:
                messages.error(
                    request,
                    (
                        "Seu usuário não está "
                        "vinculado a um piloto."
                    )
                )

                return redirect(
                    "calendario"
                )

        if obj.drone.status != "ativo":
            form.add_error(
                "drone",
                "Este drone não está disponível para novas reservas."
            )

            ctx = {
                "form": form,
                "titulo": "Nova reserva / alocação",
            }

            ctx.update(
                _base_context(request)
            )

            return render(
                request,
                "form.html",
                ctx
            )

        obj.save()

        messages.success(
            request,
            "Reserva criada com sucesso."
        )

        return redirect(
            "calendario"
        )

    ctx = {
        "form": form,
        "titulo": (
            "Nova reserva / alocação"
        ),
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "form.html",
        ctx
    )


@login_required
def alocacao_editar(request, pk):
    _atualizar_reservas_vencidas()

    if usuario_e_coordenador(request.user):
        messages.error(request, "O perfil de coordenador possui acesso somente para consulta.")
        return redirect("calendario")

    alocacao = get_object_or_404(
        Alocacao,
        pk=pk
    )

    eh_admin = usuario_e_admin(
        request.user
    )

    if not eh_admin:
        if (
            alocacao.status
            != "reservado"
        ):
            messages.error(
                request,
                (
                    "Reservas concluídas "
                    "só podem ser alteradas "
                    "por administradores."
                )
            )

            return redirect(
                "calendario"
            )

        if not _reserva_pertence_ao_usuario(
            request,
            alocacao
        ):
            messages.error(
                request,
                (
                    "Você só pode editar "
                    "reservas vinculadas "
                    "ao seu próprio piloto."
                )
            )

            return redirect(
                "calendario"
            )

    form = AlocacaoForm(
        request.POST or None,
        instance=alocacao
    )

    if not eh_admin:
        try:
            form.fields[
                "piloto"
            ].queryset = (
                Piloto.objects.filter(
                    pk=request.user.piloto.pk
                )
            )

            form.fields[
                "piloto"
            ].initial = (
                request.user.piloto
            )

            form.fields[
                "piloto"
            ].disabled = True

        except Piloto.DoesNotExist:
            pass

    if form.is_valid():
        reserva = form.save(
            commit=False
        )

        if not eh_admin:
            reserva.piloto = (
                request.user.piloto
            )

        reserva.save()

        messages.success(
            request,
            "Reserva atualizada com sucesso."
        )

        return redirect(
            "calendario"
        )

    ctx = {
        "form": form,
        "titulo": "Editar reserva",
        "alocacao": alocacao,
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "form.html",
        ctx
    )


@login_required
@require_POST
def alocacao_excluir(request, pk):
    _atualizar_reservas_vencidas()

    if usuario_e_coordenador(request.user):
        messages.error(request, "O perfil de coordenador possui acesso somente para consulta.")
        return redirect("calendario")

    alocacao = get_object_or_404(
        Alocacao,
        pk=pk
    )

    if usuario_e_admin(
        request.user
    ):
        alocacao.delete()

        messages.success(
            request,
            "Reserva excluída."
        )

        return redirect(
            "calendario"
        )

    if (
        alocacao.status
        != "reservado"
    ):
        messages.error(
            request,
            (
                "Reservas concluídas "
                "não podem ser excluídas "
                "por usuários."
            )
        )

        return redirect(
            "calendario"
        )

    if not _reserva_pertence_ao_usuario(
        request,
        alocacao
    ):
        messages.error(
            request,
            (
                "Você só pode excluir "
                "reservas vinculadas "
                "ao seu próprio piloto."
            )
        )

        return redirect(
            "calendario"
        )

    alocacao.delete()

    messages.success(
        request,
        "Reserva excluída."
    )

    return redirect(
        "calendario"
    )


@admin_required
def alocacao_concluir(request, pk):
    _atualizar_reservas_vencidas()

    alocacao = get_object_or_404(
        Alocacao,
        pk=pk
    )

    if request.method == "POST":
        form = VooForm(
            request.POST
        )

        form.fields[
            "drone"
        ].queryset = (
            Drone.objects.filter(
                Q(status="ativo")
                | Q(
                    pk=alocacao.drone_id
                )
            ).distinct()
        )

        form.fields[
            "piloto"
        ].queryset = (
            Piloto.objects.filter(
                Q(ativo=True)
                | Q(
                    pk=alocacao.piloto_id
                )
            ).distinct()
        )

        if form.is_valid():
            voo = form.save(
                commit=False
            )

            voo.criado_por = (
                request.user
            )

            voo.save()

            alocacao.status = (
                "concluido"
            )

            alocacao.save(
                update_fields=["status"]
            )

            messages.success(
                request,
                (
                    "Voo registrado e "
                    "reserva concluída "
                    "com sucesso."
                )
            )

            return redirect(
                "voos"
            )

    else:
        dados_iniciais = {
            "data": alocacao.data,
            "piloto": (
                alocacao.piloto
            ),
            "drone": alocacao.drone,
            "local": alocacao.local,
            "hora_inicio": (
                alocacao.hora_inicio
            ),
            "hora_fim": (
                alocacao.hora_fim
            ),
            "observacoes": (
                alocacao.observacoes
            ),
        }

        finalidade_map = {
            "levantamento": (
                "levantamento"
            ),
            "monitoramento": (
                "monitoramento"
            ),
            "inspeção": (
                "inspecao"
            ),
            "inspecao": (
                "inspecao"
            ),
            "mapeamento": (
                "mapeamento"
            ),
            "treinamento": (
                "treinamento"
            ),
        }

        finalidade_texto = (
            alocacao.finalidade
            or ""
        ).strip().lower()

        dados_iniciais[
            "finalidade"
        ] = finalidade_map.get(
            finalidade_texto,
            "outro"
        )

        form = VooForm(
            initial=dados_iniciais
        )

        form.fields[
            "drone"
        ].queryset = (
            Drone.objects.filter(
                Q(status="ativo")
                | Q(
                    pk=alocacao.drone_id
                )
            ).distinct()
        )

        form.fields[
            "piloto"
        ].queryset = (
            Piloto.objects.filter(
                Q(ativo=True)
                | Q(
                    pk=alocacao.piloto_id
                )
            ).distinct()
        )

        form.fields[
            "drone"
        ].initial = (
            alocacao.drone
        )

        form.fields[
            "piloto"
        ].initial = (
            alocacao.piloto
        )

    ctx = {
        "form": form,
        "titulo": (
            "Concluir reserva "
            "e registrar voo"
        ),
        "alocacao": alocacao,
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "calendario/concluir.html",
        ctx
    )


# =========================================================
# RELATÓRIOS
# =========================================================

def _filtrar_voos_relatorio(request):
    from .voo_service import filtrar_voos_realizados
    qs = filtrar_voos_realizados(Voo.objects.select_related(
        "piloto",
        "drone"
    )).filter(data__isnull=False, hora_inicio__isnull=False, hora_fim__isnull=False)

    inicio = request.GET.get("inicio")
    fim = request.GET.get("fim")
    piloto_id = request.GET.get("piloto")
    drone_id = request.GET.get("drone")

    if inicio:
        qs = qs.filter(data__gte=inicio)

    if fim:
        qs = qs.filter(data__lte=fim)

    if piloto_id:
        qs = qs.filter(piloto_id=piloto_id)

    if drone_id:
        qs = qs.filter(drone_id=drone_id)

    return qs


@admin_required
def relatorios(request):
    configuracao_timbre = ConfiguracaoPapelTimbrado.atual()
    timbre_form = PapelTimbradoRelatorioForm(request.POST or None, request.FILES or None, instance=configuracao_timbre)
    if request.method == "POST" and timbre_form.is_valid():
        configuracao = timbre_form.save(commit=False)
        configuracao.atualizado_por = request.user
        configuracao.save()
        messages.success(request, "Modelo de papel timbrado dos relatórios atualizado.")
        return redirect("relatorios")
    voos_qs = _filtrar_voos_relatorio(request)

    total_segundos = sum(
        voo.duracao_segundos_operacionais
        for voo in voos_qs
    )

    distancia_total_m = sum(
        float(voo.distancia_m or 0)
        for voo in voos_qs
    )

    por_piloto = []
    pilotos_ids = (
        voos_qs.values_list(
            "piloto_id",
            flat=True
        ).distinct()
    )

    for piloto in Piloto.objects.filter(
        pk__in=pilotos_ids
    ):
        voos_piloto = [
            voo
            for voo in voos_qs
            if voo.piloto_id == piloto.id
        ]

        segundos_piloto = sum(
            voo.duracao_segundos_operacionais
            for voo in voos_piloto
        )

        por_piloto.append({
            "nome": piloto.nome,
            "voos": len(voos_piloto),
            "horas": round(
                segundos_piloto / 3600,
                2
            ),
        })

    por_drone = []
    drones_ids = (
        voos_qs.values_list(
            "drone_id",
            flat=True
        ).distinct()
    )

    for drone in Drone.objects.filter(
        pk__in=drones_ids
    ):
        voos_drone = [
            voo
            for voo in voos_qs
            if voo.drone_id == drone.id
        ]

        segundos_drone = sum(
            voo.duracao_segundos_operacionais
            for voo in voos_drone
        )

        por_drone.append({
            "nome": drone.nome,
            "voos": len(voos_drone),
            "horas": round(
                segundos_drone / 3600,
                2
            ),
        })

    ctx = {
        "total_voos": voos_qs.count(),
        "total_horas": round(
            total_segundos / 3600,
            2
        ),
        "distancia_km": round(
            distancia_total_m / 1000,
            2
        ),
        "por_piloto": por_piloto,
        "por_drone": por_drone,
        "pilotos": Piloto.objects.filter(
            ativo=True
        ),
        "drones": Drone.objects.all(),
        "filtros": request.GET,
        "voos_relatorio": voos_qs[:200],
        "timbre_form": timbre_form,
        "configuracao_timbre": configuracao_timbre,
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "relatorios/relatorios.html",
        ctx
    )


@admin_required
def relatorios_exportar_pdf(request):
    voos_qs = _filtrar_voos_relatorio(request)

    total_voos = voos_qs.count()
    total_segundos = sum(voo.duracao_segundos_operacionais for voo in voos_qs)
    total_horas = round(total_segundos / 3600, 2)
    distancia_total_m = sum(float(voo.distancia_m or 0) for voo in voos_qs)
    distancia_total_km = round(distancia_total_m / 1000, 2)

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=30 * mm,
        bottomMargin=25 * mm,
    )

    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle(
        "TituloRelatorio",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        spaceAfter=10,
    )

    subtitulo_style = ParagraphStyle(
        "SubtituloRelatorio",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#536273"),
        spaceAfter=8,
    )

    normal_small = ParagraphStyle(
        "NormalSmall",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
    )

    elementos = [
        Paragraph("Relatório de Operações com Drones", titulo_style)
    ]

    inicio = request.GET.get("inicio") or "-"
    fim = request.GET.get("fim") or "-"
    piloto_id = request.GET.get("piloto")
    drone_id = request.GET.get("drone")

    piloto_nome = "Todos"
    drone_nome = "Todos"

    if piloto_id:
        piloto_obj = Piloto.objects.filter(pk=piloto_id).first()
        if piloto_obj:
            piloto_nome = piloto_obj.nome

    if drone_id:
        drone_obj = Drone.objects.filter(pk=drone_id).first()
        if drone_obj:
            drone_nome = drone_obj.nome

    elementos.append(
        Paragraph(
            f"Período: {inicio} até {fim} | Piloto: {piloto_nome} | Drone: {drone_nome}",
            subtitulo_style,
        )
    )

    resumo = Table(
        [
            ["Total de Voos", "Horas Totais", "Distância Total"],
            [str(total_voos), f"{total_horas} h", f"{distancia_total_km} km"],
        ],
        colWidths=[55 * mm, 55 * mm, 55 * mm],
    )

    resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0C2238")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F4F7FB")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9E1EA")),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    elementos.extend([resumo, Spacer(1, 8 * mm)])

    dados = [[
        "Data", "Piloto", "Drone", "Finalidade", "Local",
        "Início", "Fim", "Duração", "Distância"
    ]]

    for voo in voos_qs:
        dados.append([
            Paragraph(voo.data.strftime("%d/%m/%Y"), normal_small),
            Paragraph(voo.piloto.nome, normal_small),
            Paragraph(voo.drone.nome, normal_small),
            Paragraph(voo.get_finalidade_display(), normal_small),
            Paragraph(voo.local or "-", normal_small),
            Paragraph(voo.hora_inicio.strftime("%H:%M"), normal_small),
            Paragraph(voo.hora_fim.strftime("%H:%M"), normal_small),
            Paragraph(f"{voo.duracao_minutos} min", normal_small),
            Paragraph(
                f"{voo.distancia_m} m" if voo.distancia_m is not None else "-",
                normal_small
            ),
        ])

    if len(dados) == 1:
        dados.append(["", "", "", "", "Nenhum voo encontrado.", "", "", "", ""])

    tabela = Table(
        dados,
        repeatRows=1,
        colWidths=[
            20 * mm, 34 * mm, 29 * mm, 30 * mm, 50 * mm,
            16 * mm, 16 * mm, 19 * mm, 23 * mm
        ],
    )

    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0C2238")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E1EA")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white,
            colors.HexColor("#F8FAFC"),
        ]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    elementos.append(tabela)
    elementos.append(Spacer(1, 5 * mm))

    gerado_em = timezone.localtime().strftime("%d/%m/%Y %H:%M")
    elementos.append(
        Paragraph(
            f"Gerado pelo Sistema de Gestão de Drones em {gerado_em}.",
            subtitulo_style,
        )
    )

    doc.build(elementos)
    configuracao = ConfiguracaoPapelTimbrado.atual()
    conteudo = aplicar_papel_timbrado(buffer.getvalue(), configuracao.modelo_relatorios)
    response = HttpResponse(conteudo, content_type="application/pdf")
    disposicao = "inline" if request.GET.get("modo") in {"visualizar", "imprimir"} else "attachment"
    response["Content-Disposition"] = f'{disposicao}; filename="relatorio_voos.pdf"'
    return response


# =========================================================
# MANUTENÇÕES
# =========================================================

@admin_required
def manutencoes(request):
    ctx = {
        "manutencoes": (
            Manutencao.objects
            .select_related(
                "drone",
                "criado_por"
            )
        )
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "manutencoes/lista.html",
        ctx
    )


@admin_required
@require_POST
def manutencao_concluir(request, pk):
    manutencao = get_object_or_404(Manutencao, pk=pk)

    if manutencao.concluida:
        messages.warning(request, "Esta manutenção já está concluída.")
        return redirect("manutencoes")

    manutencao.concluida = True

    if not manutencao.data_fim:
        manutencao.data_fim = timezone.localdate()

    manutencao.save(update_fields=["concluida", "data_fim"])

    drone = manutencao.drone
    status_anterior = drone.status
    agora = timezone.localtime()

    reserva_ativa = Alocacao.objects.filter(
        drone=drone,
        status="reservado",
        data=agora.date(),
        hora_inicio__lte=agora.time(),
        hora_fim__gt=agora.time(),
    ).exists()

    novo_status = "em_campo" if reserva_ativa else "ativo"

    if drone.status != novo_status:
        drone.status = novo_status
        drone.save(update_fields=["status"])

        DroneHistorico.objects.create(
            drone=drone,
            status_anterior=status_anterior,
            status_novo=novo_status,
            localizacao_anterior=getattr(drone, "localizacao", ""),
            localizacao_nova=getattr(drone, "localizacao", ""),
            alterado_por=request.user,
            observacao="Status atualizado ao concluir manutenção",
        )

    messages.success(request, "Manutenção concluída com sucesso.")
    return redirect("manutencoes")



@admin_required
def manutencao_editar(request, pk):
    manutencao = get_object_or_404(Manutencao, pk=pk)
    form = ManutencaoForm(request.POST or None, instance=manutencao)

    if form.is_valid():
        obj = form.save(commit=False)
        obj.criado_por = manutencao.criado_por
        obj.save()

        if not obj.concluida:
            if obj.drone.status != "manutencao":
                anterior = obj.drone.status
                obj.drone.status = "manutencao"
                obj.drone.save(update_fields=["status"])
                DroneHistorico.objects.create(
                    drone=obj.drone,
                    status_anterior=anterior,
                    status_novo="manutencao",
                    localizacao_anterior=getattr(obj.drone, "localizacao", ""),
                    localizacao_nova=getattr(obj.drone, "localizacao", ""),
                    alterado_por=request.user,
                    observacao="Status atualizado ao editar manutenção",
                )

        messages.success(request, "Manutenção atualizada com sucesso.")
        return redirect("manutencoes")

    ctx = {"form": form, "titulo": "Editar manutenção"}
    ctx.update(_base_context(request))
    return render(request, "form.html", ctx)


@admin_required
@require_POST
def manutencao_excluir(request, pk):
    manutencao = get_object_or_404(Manutencao, pk=pk)
    drone = manutencao.drone
    estava_aberta = not manutencao.concluida

    manutencao.delete()

    if estava_aberta:
        outra_aberta = Manutencao.objects.filter(
            drone=drone,
            concluida=False
        ).exists()

        if not outra_aberta and drone.status == "manutencao":
            agora = timezone.localtime()
            reserva_ativa = Alocacao.objects.filter(
                drone=drone,
                status="reservado",
                data=agora.date(),
                hora_inicio__lte=agora.time(),
                hora_fim__gt=agora.time(),
            ).exists()

            novo_status = "em_campo" if reserva_ativa else "ativo"
            drone.status = novo_status
            drone.save(update_fields=["status"])

            DroneHistorico.objects.create(
                drone=drone,
                status_anterior="manutencao",
                status_novo=novo_status,
                localizacao_anterior=getattr(drone, "localizacao", ""),
                localizacao_nova=getattr(drone, "localizacao", ""),
                alterado_por=request.user,
                observacao="Drone liberado após exclusão de manutenção",
            )

    messages.success(request, "Manutenção excluída com sucesso.")
    return redirect("manutencoes")

@admin_required
def manutencao_nova(request):
    form = ManutencaoForm(
        request.POST or None
    )

    if form.is_valid():
        obj = form.save(
            commit=False
        )

        obj.criado_por = (
            request.user
        )

        obj.save()

        if not obj.concluida:
            status_anterior = obj.drone.status

            obj.drone.status = (
                "manutencao"
            )

            obj.drone.save(
                update_fields=["status"]
            )

            DroneHistorico.objects.create(
                drone=obj.drone,
                status_anterior=status_anterior,
                status_novo="manutencao",
                localizacao_anterior=getattr(
                    obj.drone,
                    "localizacao",
                    ""
                ),
                localizacao_nova=getattr(
                    obj.drone,
                    "localizacao",
                    ""
                ),
                alterado_por=request.user,
                observacao="Status alterado ao registrar manutenção",
            )

        messages.success(
            request,
            "Manutenção registrada."
        )

        return redirect(
            "manutencoes"
        )

    ctx = {
        "form": form,
        "titulo": "Nova manutenção",
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "form.html",
        ctx
    )
# PATCH REGISTRO POS-VOO: VIEWS
from django.contrib import messages as pos_voo_messages
from django.contrib.auth.decorators import login_required as pos_voo_login_required
from django.core.exceptions import PermissionDenied as PosVooPermissionDenied
from django.db import transaction as pos_voo_transaction
from django.shortcuts import get_object_or_404 as pos_voo_get_object_or_404
from django.shortcuts import redirect as pos_voo_redirect
from django.shortcuts import render as pos_voo_render
from .forms import RegistroPosVooForm
from .models import Alocacao, DroneHistorico, Manutencao, RegistroPosVoo, Voo

def _pos_voo_admin(user):
    return usuario_e_admin(user)

def _pos_voo_pode_acessar(user, alocacao):
    return _pos_voo_admin(user) or alocacao.piloto.user_id == user.id

def _pos_voo_finalidade(valor):
    validas = {codigo for codigo, _ in Voo.FINALIDADE_CHOICES}
    return valor if valor in validas else "outro"

@pos_voo_login_required
@pos_voo_transaction.atomic
def registro_pos_voo(request, alocacao_id):
    alocacao = pos_voo_get_object_or_404(
        Alocacao.objects.select_related("piloto__user", "drone"), pk=alocacao_id
    )
    if not _pos_voo_pode_acessar(request.user, alocacao):
        raise PosVooPermissionDenied

    registro = RegistroPosVoo.objects.filter(alocacao=alocacao).first()
    if registro and registro.concluido and not _pos_voo_admin(request.user):
        contexto = {
            "form": RegistroPosVooForm(instance=registro), "alocacao": alocacao,
            "registro": registro, "somente_leitura": True,
        }
        contexto.update(_base_context(request))
        return pos_voo_render(request, "core/registro_pos_voo.html", contexto)

    if request.method == "POST":
        form = RegistroPosVooForm(request.POST, instance=registro)
        if form.is_valid():
            registro = form.save(commit=False)
            registro.alocacao = alocacao
            if not registro.pk:
                registro.preenchido_por = request.user
            registro.save()
            form.save_m2m()
            total_baterias = registro.baterias.count()
            if total_baterias and registro.baterias_utilizadas != total_baterias:
                registro.baterias_utilizadas = total_baterias
                registro.save(update_fields=["baterias_utilizadas", "atualizado_em"])

            if registro.concluido:
                voo_defaults = {
                    "data": alocacao.data, "piloto": alocacao.piloto,
                    "drone": alocacao.drone,
                    "finalidade": _pos_voo_finalidade(alocacao.finalidade),
                    "local": alocacao.local or "Não informado",
                    "hora_inicio": registro.hora_inicio_real,
                    "hora_fim": registro.hora_fim_real,
                    "bateria_inicial": registro.bateria_inicial,
                    "bateria_final": registro.bateria_final,
                    "distancia_m": registro.distancia_m,
                    "observacoes": "\n\n".join(filter(None, [
                        registro.observacoes,
                        "Ocorrências: " + registro.ocorrencias if registro.ocorrencias else "",
                        "Danos: " + registro.danos if registro.danos else "",
                    ])),
                    "criado_por": registro.preenchido_por,
                }
                if registro.voo_id:
                    for campo, valor in voo_defaults.items():
                        setattr(registro.voo, campo, valor)
                    registro.voo.save()
                    voo = registro.voo
                else:
                    voo = Voo.objects.filter(alocacao_calendario=alocacao).first()
                    if voo is None:
                        voo = Voo.objects.filter(
                            data=alocacao.data,
                            piloto=alocacao.piloto,
                            drone=alocacao.drone,
                        ).first()
                    if voo is None:
                        voo = Voo.objects.create(alocacao_calendario=alocacao, **voo_defaults)
                    else:
                        for campo, valor in voo_defaults.items():
                            setattr(voo, campo, valor)
                        voo.alocacao_calendario = alocacao
                        voo.save()
                    registro.voo = voo
                    registro.save(update_fields=["voo", "atualizado_em"])

                if voo.alocacao_calendario_id != alocacao.pk:
                    voo.alocacao_calendario = alocacao
                    voo.save(update_fields=["alocacao_calendario"])

                if alocacao.status != "concluido":
                    alocacao.status = "concluido"
                    alocacao.save(update_fields=["status"])
                try:
                    solicitacao = alocacao.solicitacao_voo
                except Exception:
                    solicitacao = None
                if solicitacao and solicitacao.status != "concluido":
                    solicitacao.status = "concluido"
                    solicitacao.save(update_fields=["status", "atualizado_em"])

                if registro.necessita_manutencao:
                    drone = alocacao.drone
                    status_anterior = drone.status
                    drone.status = "manutencao"
                    drone.save(update_fields=["status"])
                    DroneHistorico.objects.create(
                        drone=drone, status_anterior=status_anterior,
                        status_novo="manutencao",
                        localizacao_anterior=drone.localizacao,
                        localizacao_nova=drone.localizacao,
                        alterado_por=request.user,
                        observacao=f"Manutenção solicitada no pós-voo da alocação #{alocacao.pk}.",
                    )
                    if not Manutencao.objects.filter(drone=drone, concluida=False).exists():
                        Manutencao.objects.create(
                            drone=drone, concluida=False,
                            tipo="inspecao", data_inicio=alocacao.data,
                            descricao="Inspeção gerada automaticamente pelo registro pós-voo."
                            + (f" Danos: {registro.danos}" if registro.danos else ""),
                            criado_por=request.user,
                        )
            pos_voo_messages.success(request, "Registro pós-voo salvo com sucesso.")
            return pos_voo_redirect("registro_pos_voo", alocacao_id=alocacao.pk)
    else:
        form = RegistroPosVooForm(instance=registro, initial={
            "hora_inicio_real": alocacao.hora_inicio,
            "hora_fim_real": alocacao.hora_fim,
        })
    contexto = {
        "form": form, "alocacao": alocacao, "registro": registro,
        "somente_leitura": False,
    }
    contexto.update(_base_context(request))
    return pos_voo_render(request, "core/registro_pos_voo.html", contexto)
