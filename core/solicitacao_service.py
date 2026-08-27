from django.db import transaction

from .models import Alocacao
from .operacao_service import existe_conflito_alocacao, sincronizar_voo_da_alocacao


class LiberacaoVooErro(ValueError):
    pass


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

    if existe_conflito_alocacao(
        solicitacao.drone,
        solicitacao.data,
        solicitacao.hora_inicio,
        solicitacao.data_final,
        solicitacao.hora_fim,
        excluir_pk=solicitacao.alocacao_id,
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

    voo = sincronizar_voo_da_alocacao(alocacao, solicitacao.criado_por)

    solicitacao.status = "aprovado"
    solicitacao.analisado_por = usuario
    solicitacao.alocacao = alocacao
    solicitacao.save(update_fields=["status", "analisado_por", "alocacao", "atualizado_em"])
    return alocacao, voo
