"""Estado temporal das reservas e disponibilidade da frota."""

from datetime import datetime

from django.db.models import Q
from django.utils import timezone

from .models import Alocacao, Drone, DroneHistorico
from .operacao_service import intervalo_operacional


def reserva_em_andamento(reserva, agora=None):
    agora = agora or timezone.localtime()
    inicio, fim = intervalo_operacional(
        reserva.data, reserva.hora_inicio, reserva.data_final, reserva.hora_fim
    )
    fuso = timezone.get_current_timezone()
    return timezone.make_aware(inicio, fuso) <= agora < timezone.make_aware(fim, fuso)


def atualizar_reservas_vencidas(agora=None):
    agora = agora or timezone.localtime()
    ids = []
    for reserva in Alocacao.objects.filter(status="reservado", data__lte=agora.date()):
        _, fim = intervalo_operacional(
            reserva.data, reserva.hora_inicio, reserva.data_final, reserva.hora_fim
        )
        if timezone.make_aware(fim, timezone.get_current_timezone()) <= agora:
            ids.append(reserva.pk)
    if ids:
        Alocacao.objects.filter(pk__in=ids).update(status="concluido")
    return len(ids)


def drone_tem_reserva_em_andamento(drone, agora=None):
    agora = agora or timezone.localtime()
    candidatas = Alocacao.objects.filter(
        drone=drone, status="reservado", data__lte=agora.date()
    ).filter(Q(data_fim__gte=agora.date()) | Q(data_fim__isnull=True, data=agora.date()))
    return any(reserva_em_andamento(item, agora) for item in candidatas)


def atualizar_status_drones_por_reserva(agora=None):
    agora = agora or timezone.localtime()
    candidatas = (
        Alocacao.objects.filter(status="reservado", data__lte=agora.date())
        .filter(Q(data_fim__gte=agora.date()) | Q(data_fim__isnull=True, data=agora.date()))
        .select_related("drone")
    )
    reservas_ativas = [item for item in candidatas if reserva_em_andamento(item, agora)]
    drones_em_reserva = {item.drone_id for item in reservas_ativas}

    for reserva in reservas_ativas:
        drone = reserva.drone
        if drone.status in ("manutencao", "indisponivel", "em_campo"):
            continue
        anterior = drone.status
        drone.status = "em_campo"
        drone.save(update_fields=["status"])
        _registrar_historico(drone, anterior, "em_campo", "Status alterado automaticamente por reserva em andamento")

    for drone in Drone.objects.filter(status="em_campo").exclude(pk__in=drones_em_reserva):
        drone.status = "ativo"
        drone.save(update_fields=["status"])
        _registrar_historico(drone, "em_campo", "ativo", "Reserva finalizada. Status retornado automaticamente para Ativo")


def _registrar_historico(drone, anterior, novo, observacao):
    DroneHistorico.objects.create(
        drone=drone,
        status_anterior=anterior,
        status_novo=novo,
        localizacao_anterior=drone.localizacao,
        localizacao_nova=drone.localizacao,
        alterado_por=None,
        observacao=observacao,
    )
