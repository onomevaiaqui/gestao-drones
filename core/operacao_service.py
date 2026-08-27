"""Regras compartilhadas do ciclo operacional do SISMOD.

Este módulo concentra validações que antes eram repetidas em modelos,
formulários e serviços. Ele não depende da camada de apresentação.
"""

import unicodedata
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Alocacao, DroneHistorico, Manutencao, Voo


def normalizar_finalidade(valor):
    """Converte texto livre ou rótulo para um valor aceito por ``Voo``."""
    texto = unicodedata.normalize("NFKD", valor or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    for codigo, rotulo in Voo.FINALIDADE_CHOICES:
        rotulo_normalizado = (
            unicodedata.normalize("NFKD", rotulo)
            .encode("ascii", "ignore")
            .decode()
            .lower()
        )
        if codigo in texto or rotulo_normalizado in texto:
            return codigo
    return "outro"


def intervalo_operacional(data, hora_inicio, data_fim, hora_fim):
    """Retorna início e fim normalizados; ``data_fim`` pode ser omitida."""
    data_final = data_fim or data
    return datetime.combine(data, hora_inicio), datetime.combine(data_final, hora_fim)


def erro_intervalo(data, hora_inicio, data_fim, hora_fim):
    """Retorna uma mensagem de validação ou ``None`` para um período válido."""
    if not all((data, hora_inicio, hora_fim)):
        return None
    data_final = data_fim or data
    if data_final < data:
        return "A data final não pode ser anterior à data inicial."
    inicio, fim = intervalo_operacional(data, hora_inicio, data_final, hora_fim)
    if fim <= inicio:
        return "O término deve ser posterior ao início."
    return None


def alocacoes_conflitantes(drone, data, hora_inicio, data_fim, hora_fim, excluir_pk=None):
    """Retorna as reservas ativas que se sobrepõem ao período informado."""
    if not all((drone, data, hora_inicio, hora_fim)):
        return Alocacao.objects.none()
    data_final = data_fim or data
    inicio_novo, fim_novo = intervalo_operacional(data, hora_inicio, data_final, hora_fim)
    candidatas = (
        Alocacao.objects.filter(drone=drone, status="reservado", data__lte=data_final)
        .filter(Q(data_fim__gte=data) | Q(data_fim__isnull=True, data__gte=data))
    )
    if excluir_pk:
        candidatas = candidatas.exclude(pk=excluir_pk)
    ids = [
        item.pk
        for item in candidatas
        if intervalo_operacional(item.data, item.hora_inicio, item.data_final, item.hora_fim)[0] < fim_novo
        and intervalo_operacional(item.data, item.hora_inicio, item.data_final, item.hora_fim)[1] > inicio_novo
    ]
    return Alocacao.objects.filter(pk__in=ids)


def existe_conflito_alocacao(drone, data, hora_inicio, data_fim, hora_fim, excluir_pk=None):
    return alocacoes_conflitantes(
        drone, data, hora_inicio, data_fim, hora_fim, excluir_pk=excluir_pk
    ).exists()


def sincronizar_voo_da_alocacao(alocacao, usuario, dados=None):
    """Cria ou atualiza o único voo associado a uma reserva."""
    dados = dados or {}
    voo = Voo.objects.filter(alocacao_calendario=alocacao).first()
    if voo is None:
        voo = Voo.objects.filter(
            data=alocacao.data, piloto=alocacao.piloto, drone=alocacao.drone
        ).first()
    valores = {
        "data": alocacao.data,
        "piloto": alocacao.piloto,
        "drone": alocacao.drone,
        "finalidade": normalizar_finalidade(alocacao.finalidade),
        "local": alocacao.local or "Não informado",
        "hora_inicio": alocacao.hora_inicio,
        "hora_fim": alocacao.hora_fim,
        "observacoes": alocacao.observacoes or "",
        "criado_por": usuario,
    }
    valores.update(dados)
    if voo is None:
        voo = Voo.objects.create(alocacao_calendario=alocacao, **valores)
    else:
        for campo, valor in valores.items():
            setattr(voo, campo, valor)
        voo.alocacao_calendario = alocacao
        voo.save()
    return voo


def sincronizar_calendario_do_voo(voo, usuario, agora=None):
    """Mantém o vínculo legado de um voo manual com seu item de calendário."""
    if not voo.data or not voo.hora_inicio or not voo.hora_fim:
        return None
    agora = agora or timezone.localtime()
    inicio = timezone.make_aware(datetime.combine(voo.data, voo.hora_inicio))
    fim = timezone.make_aware(datetime.combine(voo.data, voo.hora_fim))
    if fim <= inicio:
        fim += timedelta(days=1)
    status = "concluido" if fim <= agora else "reservado"
    alocacao = voo.alocacao_calendario or Alocacao.objects.filter(
        piloto=voo.piloto, drone=voo.drone, data=voo.data,
        hora_inicio=voo.hora_inicio, hora_fim=voo.hora_fim,
    ).first()
    valores = {
        "data": voo.data, "data_fim": fim.date(), "hora_inicio": voo.hora_inicio,
        "hora_fim": voo.hora_fim, "piloto": voo.piloto, "drone": voo.drone,
        "finalidade": voo.get_finalidade_display(), "local": voo.local or "",
        "observacoes": voo.observacoes or "",
    }
    if alocacao is None:
        alocacao = Alocacao.objects.create(
            **valores, status=status, criado_por=usuario
        )
    else:
        for campo, valor in valores.items():
            setattr(alocacao, campo, valor)
        if alocacao.status != "cancelado":
            alocacao.status = status
        alocacao.save()
    if voo.alocacao_calendario_id != alocacao.pk:
        voo.alocacao_calendario = alocacao
        voo.save(update_fields=["alocacao_calendario"])
    return alocacao


@transaction.atomic
def concluir_registro_pos_voo(registro, usuario):
    """Conclui pós-voo, reserva, solicitação e manutenção de forma atômica."""
    alocacao = registro.alocacao
    observacoes = "\n\n".join(filter(None, [
        registro.observacoes,
        "Ocorrências: " + registro.ocorrencias if registro.ocorrencias else "",
        "Danos: " + registro.danos if registro.danos else "",
    ]))
    voo = sincronizar_voo_da_alocacao(alocacao, registro.preenchido_por, {
        "hora_inicio": registro.hora_inicio_real,
        "hora_fim": registro.hora_fim_real,
        "bateria_inicial": registro.bateria_inicial,
        "bateria_final": registro.bateria_final,
        "distancia_m": registro.distancia_m,
        "observacoes": observacoes,
    })
    if registro.voo_id != voo.pk:
        registro.voo = voo
        registro.save(update_fields=["voo", "atualizado_em"])
    if alocacao.status != "concluido":
        alocacao.status = "concluido"
        alocacao.save(update_fields=["status"])
    solicitacao = getattr(alocacao, "solicitacao_voo", None)
    if solicitacao and solicitacao.status != "concluido":
        solicitacao.status = "concluido"
        solicitacao.save(update_fields=["status", "atualizado_em"])

    if registro.necessita_manutencao:
        drone = alocacao.drone
        if drone.status != "manutencao":
            anterior = drone.status
            drone.status = "manutencao"
            drone.save(update_fields=["status"])
            DroneHistorico.objects.create(
                drone=drone, status_anterior=anterior, status_novo="manutencao",
                localizacao_anterior=drone.localizacao, localizacao_nova=drone.localizacao,
                alterado_por=usuario,
                observacao=f"Manutenção solicitada no pós-voo da alocação #{alocacao.pk}.",
            )
        Manutencao.objects.get_or_create(
            drone=drone, concluida=False,
            defaults={
                "tipo": "inspecao", "data_inicio": alocacao.data,
                "descricao": "Inspeção gerada automaticamente pelo registro pós-voo."
                + (f" Danos: {registro.danos}" if registro.danos else ""),
                "criado_por": usuario,
            },
        )
    return voo
