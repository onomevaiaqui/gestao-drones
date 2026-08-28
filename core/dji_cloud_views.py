import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .dji_cloud_service import diagnostico_open_platforms, token_pilot, usuario_mqtt, validar_token_pilot
from .models import Drone, Piloto
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
        },
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
