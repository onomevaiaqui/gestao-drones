"""Cockpit DJI DRC seguro; nesta fase, somente simulação local."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import DJIDRCComando, DJIDRCSessao


NEUTRO = 1024
MINIMO = 364
MAXIMO = 1684


def drc_real_habilitado():
    return settings.DJI_DRC_ENABLED and settings.DJI_DRC_COMMANDS_ENABLED and settings.DJI_DOCK_ENABLED


@transaction.atomic
def iniciar_sessao_simulada(dock, operador, missao=None, altitude_maxima=120, distancia_maxima=500):
    if not settings.DJI_DRC_SIMULATOR_ENABLED:
        raise ValueError("O simulador do Cockpit Virtual está desativado.")
    if not dock.online:
        raise ValueError("A Dock precisa estar online para abrir o cockpit.")
    if DJIDRCSessao.objects.select_for_update().filter(dock=dock, status="ativa").exists():
        raise ValueError("Já existe uma sessão ativa para esta Dock.")
    agora = timezone.now()
    return DJIDRCSessao.objects.create(
        dock=dock, missao=missao, operador=operador, modo="simulacao", status="ativa",
        altitude_maxima_m=max(20, min(1500, int(altitude_maxima))),
        distancia_maxima_m=max(10, min(10000, int(distancia_maxima))),
        iniciada_em=agora, ultimo_heartbeat_em=agora,
        telemetria_simulada={
            "latitude": float(dock.latitude or 0), "longitude": float(dock.longitude or 0),
            "altitude_m": 0, "velocidade_ms": 0, "yaw": 0, "bateria": 100,
            "satelites": 20, "link": 100,
        },
    )


def sessao_expirada(sessao, agora=None):
    agora = agora or timezone.now()
    if not sessao.ultimo_heartbeat_em:
        return True
    limite_heartbeat = timedelta(seconds=settings.DJI_DRC_HEARTBEAT_TIMEOUT_SECONDS)
    limite_sessao = timedelta(seconds=settings.DJI_DRC_SESSION_TTL_SECONDS)
    return agora - sessao.ultimo_heartbeat_em > limite_heartbeat or agora - sessao.iniciada_em > limite_sessao


@transaction.atomic
def finalizar_sessao(sessao, motivo):
    sessao = DJIDRCSessao.objects.select_for_update().get(pk=sessao.pk)
    if sessao.status != "ativa":
        return sessao
    sessao.sequencia_atual += 1
    DJIDRCComando.objects.create(
        sessao=sessao, sequencia=sessao.sequencia_atual,
        roll=NEUTRO, pitch=NEUTRO, throttle=NEUTRO, yaw=NEUTRO, gimbal_pitch=NEUTRO,
        motivo="Neutralização automática ao encerrar.",
    )
    sessao.status = "finalizada"
    sessao.finalizada_em = timezone.now()
    sessao.motivo_finalizacao = str(motivo)[:255]
    sessao.save()
    return sessao


@transaction.atomic
def aplicar_comando_simulado(sessao, canais):
    sessao = DJIDRCSessao.objects.select_for_update().get(pk=sessao.pk)
    if sessao.status != "ativa":
        raise ValueError("A sessão de cockpit não está ativa.")
    if sessao_expirada(sessao):
        finalizar_sessao(sessao, "Sessão encerrada por perda de heartbeat.")
        raise ValueError("Sessão expirada; os controles foram neutralizados.")
    valores = {}
    for nome in ("roll", "pitch", "throttle", "yaw", "gimbal_pitch"):
        try:
            valor = int(canais.get(nome, NEUTRO))
        except (TypeError, ValueError):
            raise ValueError(f"Canal {nome} inválido.")
        if not MINIMO <= valor <= MAXIMO:
            raise ValueError(f"Canal {nome} fora do limite DJI.")
        valores[nome] = valor
    sessao.sequencia_atual += 1
    comando = DJIDRCComando.objects.create(sessao=sessao, sequencia=sessao.sequencia_atual, **valores)
    telemetria = dict(sessao.telemetria_simulada or {})
    altitude = max(0, min(sessao.altitude_maxima_m, float(telemetria.get("altitude_m", 0)) + (valores["throttle"] - NEUTRO) / 660))
    telemetria.update({
        "altitude_m": round(altitude, 1),
        "velocidade_ms": round(max(abs(valores["roll"] - NEUTRO), abs(valores["pitch"] - NEUTRO)) / 132, 1),
        "yaw": round((float(telemetria.get("yaw", 0)) + (valores["yaw"] - NEUTRO) / 66) % 360, 1),
        "bateria": max(0, round(float(telemetria.get("bateria", 100)) - 0.01, 2)),
    })
    sessao.telemetria_simulada = telemetria
    sessao.ultimo_heartbeat_em = timezone.now()
    sessao.save(update_fields=["sequencia_atual", "telemetria_simulada", "ultimo_heartbeat_em"])
    return comando, telemetria


@transaction.atomic
def heartbeat(sessao):
    sessao = DJIDRCSessao.objects.select_for_update().get(pk=sessao.pk)
    if sessao.status != "ativa":
        raise ValueError("Sessão encerrada.")
    sessao.ultimo_heartbeat_em = timezone.now()
    sessao.save(update_fields=["ultimo_heartbeat_em"])
    return sessao
