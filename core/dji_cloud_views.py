import json
from datetime import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .dji_cloud_service import (
    diagnostico_open_platforms, endereco_ingestao, token_pilot,
    usuario_mqtt, validar_token_pilot,
)
from .models import Alocacao, Drone, Piloto, PlanejamentoVoo, TransmissaoAoVivo
from .permissoes import admin_required
from .views import _base_context


def _integracao_desativada():
    return JsonResponse(
        {"ok": False, "erro": "A integração automática DJI está desativada."},
        status=503,
    )


class DJIPilotLoginView(LoginView):
    template_name = "dji_cloud/login.html"

    def form_valid(self, form):
        resposta = super().form_valid(form)
        self.request.session["modo_acesso"] = "usuario"
        return resposta

    def get_success_url(self):
        return "/integracoes/dji/pilot/"


@admin_required
def dji_cloud_configuracao(request):
    diagnostico = diagnostico_open_platforms()
    ctx = {
        "diagnostico": diagnostico,
        "portal_url": (
            f"{settings.DJI_CLOUD_PUBLIC_URL}/integracoes/dji/pilot/login/"
            if settings.DJI_CLOUD_PUBLIC_URL else ""
        ),
        "drones_sem_serial": Drone.objects.filter(numero_serie="").order_by("nome"),
    }
    ctx.update(_base_context(request))
    return render(request, "dji_cloud/configuracao.html", ctx)


@login_required(login_url="dji_pilot_login")
def dji_pilot_portal(request):
    if not settings.DJI_CLOUD_ENABLED:
        return _integracao_desativada()
    diagnostico = diagnostico_open_platforms()
    token = token_pilot(request.user)
    piloto = Piloto.objects.filter(user=request.user, ativo=True).first()
    agendamentos = PlanejamentoVoo.objects.none()
    if piloto:
        hoje = timezone.localdate()
        agendamentos = PlanejamentoVoo.objects.filter(
            piloto=piloto, livestream_planejada=True,
        ).filter(Q(data_fim__gte=hoje) | Q(data_fim__isnull=True, data__gte=hoje)).order_by("data", "hora_inicio")[:20]
    ctx = {
        "diagnostico": diagnostico,
        "cloud": {
            "app_id": settings.DJI_CLOUD_APP_ID,
            "app_key": settings.DJI_CLOUD_APP_KEY,
            "license": settings.DJI_CLOUD_APP_LICENSE,
            "workspace_id": settings.DJI_CLOUD_WORKSPACE_ID,
            "api_host": settings.DJI_CLOUD_API_HOST,
            "mqtt_host": settings.DJI_CLOUD_MQTT_HOST,
            "mqtt_username": usuario_mqtt(request.user),
            "mqtt_password": token,
            "platform_name": settings.DJI_CLOUD_PLATFORM_NAME,
            "workspace_name": settings.DJI_CLOUD_WORKSPACE_NAME,
            "workspace_description": settings.DJI_CLOUD_WORKSPACE_DESCRIPTION,
            "token": token,
            "livestream_enabled": settings.DJI_LIVESTREAM_ENABLED,
        },
        "agendamentos_livestream": agendamentos,
    }
    return render(request, "dji_cloud/pilot_portal.html", ctx)


@login_required(login_url="dji_pilot_login")
@require_POST
def dji_pilot_identificar(request):
    if not settings.DJI_CLOUD_ENABLED:
        return _integracao_desativada()
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "erro": "Dados inválidos."}, status=400)
    aeronave_sn = str(payload.get("aeronave_sn") or "").strip()[:100]
    controle_sn = str(payload.get("controle_sn") or "").strip()[:100]
    if not aeronave_sn:
        return JsonResponse({"ok": False, "erro": "O DJI Pilot 2 não informou o serial da aeronave."}, status=400)
    drone = Drone.objects.filter(numero_serie__iexact=aeronave_sn).first()
    piloto = Piloto.objects.filter(user=request.user, ativo=True).first()
    request.session["dji_aeronave_sn"] = aeronave_sn
    request.session["dji_controle_sn"] = controle_sn
    return JsonResponse({
        "ok": True,
        "aeronave_sn": aeronave_sn,
        "controle_sn": controle_sn,
        "drone_encontrado": bool(drone),
        "drone": drone.nome if drone else None,
        "piloto": piloto.nome if piloto else request.user.username,
    })


@csrf_exempt
@require_POST
def dji_mqtt_autorizar(request):
    """Endpoint de autenticação HTTP para o broker MQTT (formato EMQX 5)."""
    if not settings.DJI_CLOUD_ENABLED:
        return JsonResponse({"result": "deny", "is_superuser": False})
    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = request.POST
    username = str(payload.get("username") or "")
    password = str(payload.get("password") or "")
    dados = validar_token_pilot(password)
    esperado = (
        f"{settings.DJI_CLOUD_MQTT_USERNAME_PREFIX}-{dados.get('usuario_id')}"
        if dados and dados.get("usuario_id") else ""
    )
    autorizado = bool(dados and username == esperado)
    return JsonResponse({"result": "allow" if autorizado else "deny", "is_superuser": False})


def _reserva_atual(piloto, drone):
    agora = timezone.localtime()
    candidatas = Alocacao.objects.filter(
        piloto=piloto, status="reservado", data__lte=agora.date(),
    ).filter(Q(data_fim__gte=agora.date()) | Q(data_fim__isnull=True, data=agora.date()))
    if drone:
        candidatas = candidatas.filter(drone=drone)
    for reserva in candidatas.order_by("data", "hora_inicio"):
        inicio = timezone.make_aware(datetime.combine(reserva.data, reserva.hora_inicio))
        fim = timezone.make_aware(datetime.combine(reserva.data_final, reserva.hora_fim))
        if inicio <= agora < fim:
            return reserva
    return None


@login_required(login_url="dji_pilot_login")
@require_POST
def dji_livestream_preparar(request):
    diagnostico = diagnostico_open_platforms()["livestream"]
    if not diagnostico["pronto"]:
        return JsonResponse({"ok": False, "erro": "A transmissão ao vivo ainda não está habilitada no servidor."}, status=503)
    piloto = Piloto.objects.filter(user=request.user, ativo=True).first()
    if not piloto:
        return JsonResponse({"ok": False, "erro": "Usuário sem piloto operacional ativo."}, status=403)
    aeronave_sn = str(request.session.get("dji_aeronave_sn") or "").strip()
    controle_sn = str(request.session.get("dji_controle_sn") or "").strip()
    drone = Drone.objects.filter(numero_serie__iexact=aeronave_sn).first() if aeronave_sn else None
    if not drone:
        return JsonResponse({"ok": False, "erro": "Cadastre o número de série da aeronave antes de transmitir."}, status=400)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}
    planejamento_id = payload.get("planejamento_id")
    planejamento = None
    if planejamento_id:
        planejamento = PlanejamentoVoo.objects.filter(
            pk=planejamento_id, piloto=piloto, livestream_planejada=True,
        ).first()
        if not planejamento:
            return JsonResponse({"ok": False, "erro": "Agendamento de transmissão inválido."}, status=400)

    TransmissaoAoVivo.objects.filter(piloto=piloto, status__in=["preparada", "ao_vivo"]).update(
        status="finalizada", finalizada_em=timezone.now()
    )
    transmissao = TransmissaoAoVivo.objects.create(
        piloto=piloto,
        drone=drone,
        alocacao=_reserva_atual(piloto, drone),
        planejamento=planejamento,
        origem="agendada" if planejamento else "avulsa",
        aeronave_serial=aeronave_sn,
        controle_serial=controle_sn,
    )
    request.session["dji_livestream_id"] = transmissao.pk
    return JsonResponse({
        "ok": True,
        "transmissao": str(transmissao.identificador),
        "rtmp_url": endereco_ingestao(transmissao),
    })


@login_required(login_url="dji_pilot_login")
@require_POST
def dji_livestream_status(request):
    piloto = Piloto.objects.filter(user=request.user, ativo=True).first()
    transmissao = TransmissaoAoVivo.objects.filter(
        pk=request.session.get("dji_livestream_id"), piloto=piloto,
    ).first()
    if not transmissao:
        return JsonResponse({"ok": False, "erro": "Sessão de transmissão não encontrada."}, status=404)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "erro": "Dados inválidos."}, status=400)
    evento = str(payload.get("evento") or "status")
    metricas = payload.get("metricas") if isinstance(payload.get("metricas"), dict) else {}
    transmissao.metricas = metricas
    campos = ["metricas", "atualizada_em"]
    if evento == "iniciada":
        transmissao.status = "ao_vivo"
        transmissao.iniciada_em = transmissao.iniciada_em or timezone.now()
        campos += ["status", "iniciada_em"]
    elif evento == "finalizada":
        transmissao.status = "finalizada"
        transmissao.finalizada_em = timezone.now()
        campos += ["status", "finalizada_em"]
    elif evento == "erro":
        transmissao.status = "erro"
        transmissao.mensagem_erro = str(payload.get("mensagem") or "Falha informada pelo DJI Pilot 2")[:255]
        campos += ["status", "mensagem_erro"]
    transmissao.save(update_fields=campos)
    return JsonResponse({"ok": True, "status": transmissao.status})
