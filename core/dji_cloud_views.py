import json
from datetime import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .dji_cloud_service import (
    diagnostico_open_platforms, endereco_ingestao, token_pilot,
    usuario_mqtt, validar_token_pilot,
)
from .dji_dock_service import preparar_missao, processar_mensagem_dock
from .dji_dock_permissions import docks_visiveis, pode_operar_dock
from .dji_wpml_service import gerar_kmz_wpml, validar_token_download_wpml
from .dji_operacao_service import avaliar_liberacao_missao, enfileirar_preparacao
from .dji_storage_service import armazenar_upload_missao, diagnostico_armazenamento
from .models import Alocacao, DJIDock, DJIDockAcesso, DJIDockArquivo, DJIDockCanalVideo, DJIDockComando, DJIDockMissao, Drone, Piloto, PlanejamentoVoo, TransmissaoAoVivo
from .permissoes import admin_required, usuario_e_admin, usuario_tem_visao_global
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
        "docks": DJIDock.objects.filter(ativo=True),
    }
    ctx.update(_base_context(request))
    return render(request, "dji_cloud/configuracao.html", ctx)


@login_required
def dji_docks(request):
    ctx = {"docks": docks_visiveis(request.user).select_related("drone")}
    ctx.update(_base_context(request))
    return render(request, "dji_cloud/docks.html", ctx)


@login_required
def dji_missoes(request):
    missoes = DJIDockMissao.objects.filter(dock__in=docks_visiveis(request.user)).select_related("dock", "dock__drone", "planejamento", "planejamento__piloto")
    if not usuario_tem_visao_global(request.user):
        missoes = missoes.filter(planejamento__piloto__user=request.user)
    status = request.GET.get("status", "")
    dock_id = request.GET.get("dock", "")
    if status:
        missoes = missoes.filter(status=status)
    if dock_id.isdigit():
        missoes = missoes.filter(dock_id=dock_id)
    linhas = [{"missao": item, "liberacao": avaliar_liberacao_missao(item)} for item in missoes[:200]]
    ctx = {"linhas": linhas, "docks": DJIDock.objects.filter(ativo=True), "status_atual": status, "dock_atual": dock_id}
    ctx.update(_base_context(request))
    return render(request, "dji_cloud/missoes.html", ctx)


@login_required
def dji_midias(request):
    escopo_docks = docks_visiveis(request.user)
    itens = DJIDockArquivo.objects.filter(missao__dock__in=escopo_docks).select_related("missao__dock", "missao__planejamento")
    missoes_disponiveis = DJIDockMissao.objects.filter(dock__in=escopo_docks).select_related("planejamento")
    if not usuario_tem_visao_global(request.user):
        itens = itens.filter(missao__planejamento__piloto__user=request.user)
        missoes_disponiveis = missoes_disponiveis.filter(planejamento__piloto__user=request.user)
    missao_id = request.GET.get("missao", "")
    if missao_id.isdigit():
        itens = itens.filter(missao_id=missao_id)
    ctx = {
        "itens": itens[:300], "missoes": missoes_disponiveis[:200],
        "missao_atual": missao_id, "armazenamento": diagnostico_armazenamento(),
    }
    ctx.update(_base_context(request))
    return render(request, "dji_cloud/midias.html", ctx)


@admin_required
@require_POST
def dji_midia_upload(request):
    from django.contrib import messages
    from django.shortcuts import get_object_or_404
    missao = get_object_or_404(DJIDockMissao, pk=request.POST.get("missao"))
    upload = request.FILES.get("arquivo")
    if not upload:
        messages.error(request, "Selecione um arquivo.")
    else:
        try:
            armazenar_upload_missao(missao, upload)
            messages.success(request, "Mídia armazenada e vinculada à missão.")
        except (ValueError, OSError) as erro:
            messages.error(request, str(erro))
    return redirect("dji_midias")


@login_required
def dji_midia_download(request, pk):
    from django.http import FileResponse, Http404
    from django.shortcuts import get_object_or_404
    item = get_object_or_404(DJIDockArquivo, pk=pk, status="concluido", missao__dock__in=docks_visiveis(request.user))
    if not usuario_tem_visao_global(request.user) and item.missao.planejamento.piloto.user_id != request.user.id:
        raise Http404
    if not item.arquivo:
        raise Http404
    return FileResponse(item.arquivo.open("rb"), as_attachment=True, filename=item.nome)


@admin_required
@require_POST
def dji_missao_enfileirar(request, pk):
    from django.contrib import messages
    from django.shortcuts import get_object_or_404
    missao = get_object_or_404(DJIDockMissao, pk=pk)
    try:
        enfileirar_preparacao(missao, request.user)
        messages.success(request, "Prévia adicionada à fila bloqueada. Nada foi publicado.")
    except ValueError as erro:
        messages.error(request, str(erro))
    return redirect("dji_missoes")


@login_required
def dji_dock_detalhe(request, pk):
    from django.shortcuts import get_object_or_404
    dock = get_object_or_404(docks_visiveis(request.user).select_related("drone"), pk=pk)
    acesso_global = usuario_tem_visao_global(request.user)
    missoes = dock.missoes.select_related("planejamento", "criada_por").prefetch_related("arquivos")
    if not acesso_global:
        missoes = missoes.filter(planejamento__piloto__user=request.user)
    ctx = {
        "dock": dock,
        "eventos": dock.eventos.all()[:100] if acesso_global else (),
        "comandos": dock.comandos.all()[:50] if acesso_global else (),
        "missoes": missoes[:50],
        "planejamentos": (
            PlanejamentoVoo.objects.exclude(missoes_dji_dock__dock=dock).order_by("-data", "-hora_inicio")[:100]
            if usuario_e_admin(request.user) else ()
        ),
        "acessos": dock.acessos.select_related("usuario", "usuario__piloto").all() if usuario_e_admin(request.user) else (),
        "canais_video": dock.canais_video.select_related("transmissao_atual"),
        "usuarios_disponiveis": User.objects.filter(is_active=True, piloto__ativo=True).order_by("piloto__nome") if usuario_e_admin(request.user) else (),
        "pode_operar_estacao": pode_operar_dock(request.user, dock),
    }
    ctx.update(_base_context(request))
    return render(request, "dji_cloud/dock_detalhe.html", ctx)


@login_required
@require_POST
def dji_canal_video_acao(request, pk, canal_pk):
    from django.contrib import messages
    from django.shortcuts import get_object_or_404
    from .dji_video_service import controlar_canal_video

    dock = get_object_or_404(docks_visiveis(request.user), pk=pk)
    canal = get_object_or_404(DJIDockCanalVideo, pk=canal_pk, dock=dock)
    if not pode_operar_dock(request.user, dock):
        messages.error(request, "Você possui acesso somente para monitoramento desta estação.")
        return redirect("dji_dock_detalhe", pk=dock.pk)
    try:
        controlar_canal_video(
            canal, request.POST.get("acao", ""), request.user,
            qualidade=request.POST.get("qualidade", ""), lente=request.POST.get("lente", ""),
        )
        messages.success(request, "Ação de vídeo registrada em modo seguro de simulação.")
    except ValueError as erro:
        messages.error(request, str(erro))
    return redirect("dji_dock_detalhe", pk=dock.pk)


@admin_required
@require_POST
def dji_comando_autorizar(request, pk, comando_pk):
    from django.contrib import messages
    from django.shortcuts import get_object_or_404
    from .dji_command_safety import autorizar_intencao

    dock = get_object_or_404(DJIDock, pk=pk, ativo=True)
    comando = get_object_or_404(DJIDockComando, pk=comando_pk, dock=dock)
    confirmado_em = request.session.get("reauth_em", 0)
    if timezone.now().timestamp() - confirmado_em > settings.SISMOD_REAUTH_SECONDS:
        request.session["acao_critica_pendente"] = {"tipo": "autorizar_comando_dock", "dock": dock.pk, "comando": comando.pk}
        return redirect("confirmar_acao_critica")
    try:
        autorizar_intencao(comando, request.user)
        messages.success(request, "Confirmação registrada. Nenhum comando foi publicado.")
    except (PermissionError, ValueError) as erro:
        messages.error(request, str(erro))
    return redirect("dji_dock_detalhe", pk=dock.pk)


@admin_required
@require_POST
def dji_dock_acesso_salvar(request, pk):
    from django.contrib import messages
    from django.shortcuts import get_object_or_404

    dock = get_object_or_404(DJIDock, pk=pk, ativo=True)
    usuario = get_object_or_404(User, pk=request.POST.get("usuario"), is_active=True, piloto__ativo=True)
    acesso, criado = DJIDockAcesso.objects.update_or_create(
        dock=dock,
        usuario=usuario,
        defaults={
            "ativo": True,
            "pode_operar": request.POST.get("pode_operar") == "on",
            "concedido_por": request.user,
        },
    )
    nivel = "operação e monitoramento" if acesso.pode_operar else "somente monitoramento"
    messages.success(request, f"Acesso de {usuario.get_full_name() or usuario.username} salvo: {nivel}.")
    return redirect("dji_dock_detalhe", pk=dock.pk)


@admin_required
@require_POST
def dji_dock_acesso_revogar(request, pk, acesso_pk):
    from django.contrib import messages
    from django.shortcuts import get_object_or_404

    dock = get_object_or_404(DJIDock, pk=pk, ativo=True)
    acesso = get_object_or_404(DJIDockAcesso, pk=acesso_pk, dock=dock)
    nome = acesso.usuario.get_full_name() or acesso.usuario.username
    acesso.delete()
    messages.success(request, f"Acesso de {nome} removido desta estação.")
    return redirect("dji_dock_detalhe", pk=dock.pk)


@admin_required
@require_POST
def dji_dock_preparar_missao(request, pk):
    from django.contrib import messages
    from django.shortcuts import get_object_or_404, redirect
    dock = get_object_or_404(DJIDock, pk=pk, ativo=True)
    planejamento = get_object_or_404(PlanejamentoVoo, pk=request.POST.get("planejamento"))
    preparar_missao(dock, planejamento, request.user)
    messages.success(request, "Missão preparada para validação. Nenhum comando foi enviado à Dock.")
    return redirect("dji_dock_detalhe", pk=dock.pk)


@login_required
def dji_dock_missao_wpml(request, pk):
    from django.http import HttpResponse
    from django.shortcuts import get_object_or_404
    from django.utils.text import slugify
    missao = get_object_or_404(DJIDockMissao.objects.select_related("dock", "planejamento"), pk=pk, dock__in=docks_visiveis(request.user))
    if not usuario_tem_visao_global(request.user) and missao.planejamento.piloto.user_id != request.user.id:
        return JsonResponse({"ok": False, "erro": "Esta missão pertence a outro piloto."}, status=403)
    try:
        conteudo = gerar_kmz_wpml(missao)
    except ValueError as erro:
        return JsonResponse({"ok": False, "erro": str(erro)}, status=409)
    nome = slugify(missao.planejamento.titulo) or f"missao-{missao.pk}"
    resposta = HttpResponse(conteudo, content_type="application/vnd.google-earth.kmz")
    resposta["Content-Disposition"] = f'attachment; filename="{nome}-pre-validacao.kmz"'
    resposta["X-SISMOD-WPML-STATUS"] = "pre-validacao"
    return resposta


def dji_dock_missao_wpml_publico(request, identificador, token):
    """Download sem sessão, protegido por assinatura curta para consumo da Dock."""
    from django.http import Http404, HttpResponse
    from django.shortcuts import get_object_or_404
    missao = get_object_or_404(DJIDockMissao.objects.select_related("dock", "planejamento"), identificador=identificador)
    if not validar_token_download_wpml(token, missao.identificador):
        raise Http404
    try:
        conteudo = gerar_kmz_wpml(missao)
    except ValueError as erro:
        return JsonResponse({"ok": False, "erro": str(erro)}, status=409)
    resposta = HttpResponse(conteudo, content_type="application/vnd.google-earth.kmz")
    resposta["Content-Disposition"] = 'attachment; filename="sismod-mission.kmz"'
    resposta["Cache-Control"] = "private, no-store"
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


@admin_required
@require_POST
def dji_dock_missao_parametros(request, pk):
    from django.contrib import messages
    from django.shortcuts import get_object_or_404, redirect
    missao = get_object_or_404(DJIDockMissao, pk=pk)
    try:
        altura = int(request.POST.get("altura_retorno_m", ""))
        bateria = int(request.POST.get("bateria_minima_percent", ""))
        armazenamento = int(request.POST.get("armazenamento_minimo_mb", ""))
    except (TypeError, ValueError):
        messages.error(request, "Informe valores numéricos válidos para os parâmetros operacionais.")
        return redirect("dji_dock_detalhe", pk=missao.dock_id)
    if not 20 <= altura <= 1500 or not 10 <= bateria <= 100 or armazenamento < 0:
        messages.error(request, "Revise os limites de retorno, bateria e armazenamento.")
        return redirect("dji_dock_detalhe", pk=missao.dock_id)
    missao.altura_retorno_m = altura
    missao.bateria_minima_percent = bateria
    missao.armazenamento_minimo_mb = armazenamento
    missao.interromper_na_perda_sinal = request.POST.get("interromper_na_perda_sinal") == "on"
    missao.parametros_confirmados = True
    missao.parametros_confirmados_por = request.user
    missao.parametros_confirmados_em = timezone.now()
    missao.save()
    messages.success(request, "Parâmetros operacionais confirmados. Nenhum comando foi enviado à Dock.")
    return redirect("dji_dock_detalhe", pk=missao.dock_id)


@admin_required
@require_POST
def dji_dock_simular(request):
    if not settings.DJI_DOCK_SIMULATOR_ENABLED:
        return JsonResponse({"ok": False, "erro": "O simulador da Dock está desativado."}, status=403)
    try:
        payload = json.loads(request.body or "{}")
        topico = str(payload.pop("topico", "thing/product/DOCK-SIM-001/osd"))
        dock, evento, criado = processar_mensagem_dock(topico, payload, origem="simulacao")
    except (json.JSONDecodeError, ValueError) as erro:
        return JsonResponse({"ok": False, "erro": str(erro)}, status=400)
    return JsonResponse({"ok": True, "dock_id": dock.pk, "evento_id": evento.pk, "criado": criado})


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
