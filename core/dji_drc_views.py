import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .dji_drc_service import aplicar_comando_simulado, drc_real_habilitado, finalizar_sessao, heartbeat, iniciar_sessao_simulada
from .dji_dock_permissions import docks_operaveis, pode_operar_dock
from .dji_cloud_service import endereco_reproducao
from .models import DJIDock, DJIDockMissao, DJIDRCSessao
from .permissoes import usuario_e_admin, usuario_tem_visao_global
from .views import _base_context


def _pode_operar(request, sessao):
    return sessao.operador_id == request.user.id or usuario_e_admin(request.user)


@login_required
def cockpit_lista(request):
    sessoes = DJIDRCSessao.objects.select_related("dock", "operador", "missao")
    if not usuario_tem_visao_global(request.user):
        sessoes = sessoes.filter(operador=request.user)
    ctx = {
        "docks": docks_operaveis(request.user).select_related("drone"),
        "sessoes": sessoes[:100],
        "simulador": settings.DJI_DRC_SIMULATOR_ENABLED,
        "real_habilitado": drc_real_habilitado(),
    }
    ctx.update(_base_context(request))
    return render(request, "dji_cloud/cockpit_lista.html", ctx)


@login_required
@require_POST
def cockpit_iniciar(request):
    dock = get_object_or_404(docks_operaveis(request.user), pk=request.POST.get("dock"))
    missao = DJIDockMissao.objects.filter(pk=request.POST.get("missao"), dock=dock).first() if request.POST.get("missao") else None
    try:
        sessao = iniciar_sessao_simulada(
            dock, request.user, missao,
            request.POST.get("altitude_maxima_m", 120), request.POST.get("distancia_maxima_m", 500),
        )
    except (ValueError, TypeError, IntegrityError) as erro:
        if isinstance(erro, IntegrityError):
            erro = "Já existe uma sessão ativa para esta estação. Atualize a página."
        messages.error(request, str(erro))
        return redirect("dji_cockpit")
    return redirect("dji_cockpit_sessao", identificador=sessao.identificador)


@login_required
def cockpit_sessao(request, identificador):
    sessao = get_object_or_404(DJIDRCSessao.objects.select_related("dock", "dock__drone", "operador"), identificador=identificador)
    if not _pode_operar(request, sessao) or not pode_operar_dock(request.user, sessao.dock):
        messages.error(request, "Esta sessão pertence a outro operador.")
        return redirect("dji_cockpit")
    canais = sessao.dock.canais_video.filter(disponivel=True).select_related("transmissao_atual")
    canal_aeronave = canais.filter(origem="aeronave").first()
    canal_dock = canais.filter(origem="dock").first()
    ctx = {
        "sessao": sessao,
        "telemetria": sessao.telemetria_simulada,
        "real_habilitado": drc_real_habilitado(),
        "canal_aeronave": canal_aeronave,
        "canal_dock": canal_dock,
        "video_aeronave_url": endereco_reproducao(canal_aeronave.transmissao_atual, request.user) if canal_aeronave and canal_aeronave.transmissao_atual else "",
        "video_dock_url": endereco_reproducao(canal_dock.transmissao_atual, request.user) if canal_dock and canal_dock.transmissao_atual else "",
    }
    ctx.update(_base_context(request))
    return render(request, "dji_cloud/cockpit.html", ctx)


@login_required
@require_POST
def cockpit_comando(request, identificador):
    sessao = get_object_or_404(DJIDRCSessao, identificador=identificador)
    if not _pode_operar(request, sessao) or not pode_operar_dock(request.user, sessao.dock):
        return JsonResponse({"ok": False, "erro": "Sessão de outro operador."}, status=403)
    try:
        dados = json.loads(request.body or "{}")
        comando, telemetria = aplicar_comando_simulado(sessao, dados)
    except (ValueError, json.JSONDecodeError) as erro:
        return JsonResponse({"ok": False, "erro": str(erro)}, status=409)
    return JsonResponse({"ok": True, "seq": comando.sequencia, "telemetria": telemetria, "simulacao": True})


@login_required
@require_POST
def cockpit_heartbeat(request, identificador):
    sessao = get_object_or_404(DJIDRCSessao, identificador=identificador)
    if not _pode_operar(request, sessao) or not pode_operar_dock(request.user, sessao.dock):
        return JsonResponse({"ok": False}, status=403)
    try:
        heartbeat(sessao)
    except ValueError as erro:
        return JsonResponse({"ok": False, "erro": str(erro)}, status=409)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def cockpit_finalizar(request, identificador):
    sessao = get_object_or_404(DJIDRCSessao, identificador=identificador)
    if not _pode_operar(request, sessao) or not pode_operar_dock(request.user, sessao.dock):
        return JsonResponse({"ok": False}, status=403)
    finalizar_sessao(sessao, "Encerrada pelo operador.")
    messages.success(request, "Cockpit encerrado e controles neutralizados.")
    return redirect("dji_cockpit")
