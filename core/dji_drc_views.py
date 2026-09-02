import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .dji_drc_service import aplicar_comando_simulado, drc_real_habilitado, finalizar_sessao, heartbeat, iniciar_sessao_simulada
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
        "docks": DJIDock.objects.filter(ativo=True).select_related("drone"),
        "sessoes": sessoes[:100],
        "simulador": settings.DJI_DRC_SIMULATOR_ENABLED,
        "real_habilitado": drc_real_habilitado(),
    }
    ctx.update(_base_context(request))
    return render(request, "dji_cloud/cockpit_lista.html", ctx)


@login_required
@require_POST
def cockpit_iniciar(request):
    dock = get_object_or_404(DJIDock, pk=request.POST.get("dock"), ativo=True)
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
    if not _pode_operar(request, sessao):
        messages.error(request, "Esta sessão pertence a outro operador.")
        return redirect("dji_cockpit")
    ctx = {"sessao": sessao, "telemetria": sessao.telemetria_simulada, "real_habilitado": drc_real_habilitado()}
    ctx.update(_base_context(request))
    return render(request, "dji_cloud/cockpit.html", ctx)


@login_required
@require_POST
def cockpit_comando(request, identificador):
    sessao = get_object_or_404(DJIDRCSessao, identificador=identificador)
    if not _pode_operar(request, sessao):
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
    if not _pode_operar(request, sessao):
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
    if not _pode_operar(request, sessao):
        return JsonResponse({"ok": False}, status=403)
    finalizar_sessao(sessao, "Encerrada pelo operador.")
    messages.success(request, "Cockpit encerrado e controles neutralizados.")
    return redirect("dji_cockpit")
