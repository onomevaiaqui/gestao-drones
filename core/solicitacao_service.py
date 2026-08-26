import unicodedata
from datetime import datetime

from django.db import models, transaction

from .models import Alocacao, Voo


class LiberacaoVooErro(ValueError):
    pass


def _finalidade_voo(texto):
    normalizado = unicodedata.normalize("NFKD", texto or "")
    normalizado = "".join(c for c in normalizado if not unicodedata.combining(c)).lower()
    for valor, nome in Voo.FINALIDADE_CHOICES:
        if valor in normalizado or unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower() in normalizado:
            return valor
    return "outro"


@transaction.atomic
def liberar_solicitacao(solicitacao, usuario):
    """Libera a solicitação e sincroniza calendário e registro de voo."""
    if solicitacao.status not in ("solicitado", "aprovado"):
        raise LiberacaoVooErro("Esta solicitação não está pendente de liberação.")

    if solicitacao.requer_avaliacao_risco:
        avaliacao = getattr(solicitacao, "avaliacao_risco", None)
        if not avaliacao or avaliacao.status != "aprovada":
            raise LiberacaoVooErro("O piloto precisa preencher e aceitar a avaliação de risco antes da liberação do voo.")

    if solicitacao.drone.status != "ativo":
        raise LiberacaoVooErro("O drone selecionado não está disponível.")

    conflitos = Alocacao.objects.filter(
        data__lte=solicitacao.data_final,
        drone=solicitacao.drone,
        status="reservado",
    ).filter(
        models.Q(data_fim__gte=solicitacao.data) | models.Q(data_fim__isnull=True, data__gte=solicitacao.data)
    )
    if solicitacao.alocacao_id:
        conflitos = conflitos.exclude(pk=solicitacao.alocacao_id)
    inicio_novo = datetime.combine(solicitacao.data, solicitacao.hora_inicio)
    fim_novo = datetime.combine(solicitacao.data_final, solicitacao.hora_fim)
    if any(
        datetime.combine(item.data, item.hora_inicio) < fim_novo
        and datetime.combine(item.data_final, item.hora_fim) > inicio_novo
        for item in conflitos
    ):
        raise LiberacaoVooErro("Existe outra reserva para este drone no horário.")

    dados_alocacao = {
        "data": solicitacao.data,
        "data_fim": solicitacao.data_final,
        "hora_inicio": solicitacao.hora_inicio,
        "hora_fim": solicitacao.hora_fim,
        "piloto": solicitacao.piloto,
        "drone": solicitacao.drone,
        "finalidade": solicitacao.finalidade,
        "local": solicitacao.local,
        "observacoes": solicitacao.observacoes,
        "status": "reservado",
        "criado_por": usuario,
    }
    if solicitacao.alocacao_id:
        alocacao = solicitacao.alocacao
        for campo, valor in dados_alocacao.items():
            setattr(alocacao, campo, valor)
        alocacao.save()
    else:
        alocacao = Alocacao.objects.create(**dados_alocacao)

    voo, _ = Voo.objects.get_or_create(
        data=solicitacao.data,
        piloto=solicitacao.piloto,
        drone=solicitacao.drone,
        defaults={
            "hora_inicio": solicitacao.hora_inicio,
            "hora_fim": solicitacao.hora_fim,
            "finalidade": _finalidade_voo(solicitacao.finalidade),
            "local": solicitacao.local,
            "observacoes": solicitacao.observacoes,
            "criado_por": solicitacao.criado_por,
            "alocacao_calendario": alocacao,
        },
    )
    voo.hora_inicio = solicitacao.hora_inicio
    voo.hora_fim = solicitacao.hora_fim
    voo.finalidade = _finalidade_voo(solicitacao.finalidade)
    voo.local = solicitacao.local
    voo.observacoes = solicitacao.observacoes
    voo.alocacao_calendario = alocacao
    voo.save()

    solicitacao.status = "aprovado"
    solicitacao.analisado_por = usuario
    solicitacao.alocacao = alocacao
    solicitacao.save(update_fields=["status", "analisado_por", "alocacao", "atualizado_em"])
    return alocacao, voo
