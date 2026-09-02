"""Triagem de liberação e montagem da fila segura da DJI Dock."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .dji_wpml_service import dados_flighttask_prepare
from .models import AvaliacaoRisco, DJIDockComando, Documento, Manutencao, QualificacaoPiloto


def avaliar_liberacao_missao(missao):
    p = missao.planejamento
    itens = []
    def add(nivel, codigo, mensagem):
        itens.append({"nivel": nivel, "codigo": codigo, "mensagem": mensagem})
    if not missao.parametros_confirmados:
        add("bloqueio", "parametros", "Parâmetros operacionais ainda não confirmados.")
    if missao.dock.drone_id is None:
        add("bloqueio", "drone", "Dock sem aeronave vinculada.")
    elif missao.dock.drone.status != "ativo":
        add("bloqueio", "drone_status", f"Aeronave está {missao.dock.drone.get_status_display().lower()}.")
    if missao.dock.drone_id and Manutencao.objects.filter(drone=missao.dock.drone, concluida=False).exists():
        add("bloqueio", "manutencao", "Existe manutenção aberta para a aeronave.")
    termos = p.termos_coordenacao.all()
    if termos.filter(data_assinatura__isnull=True).exists():
        add("bloqueio", "coordenacao", "Existe Termo de Coordenação sem assinatura.")
    solicitacoes = p.solicitacoes_voo.all()
    if not solicitacoes.filter(status__in=["aprovado", "concluido"]).exists():
        add("alerta", "reserva", "Não existe reserva confirmada vinculada ao planejamento.")
    if solicitacoes.filter(requer_avaliacao_risco=True).exists():
        ids = solicitacoes.filter(requer_avaliacao_risco=True).values_list("pk", flat=True)
        if not AvaliacaoRisco.objects.filter(solicitacao_id__in=ids, status="aprovada", declaracao_conformidade=True).exists():
            add("bloqueio", "risco", "Avaliação de risco exigida ainda não foi aceita pelo piloto.")
    if p.status_meteorologico in ("desfavoravel", "indisponivel", "nao_consultado"):
        add("alerta", "meteorologia", f"Meteorologia: {p.get_status_meteorologico_display()}.")
    if Documento.objects.filter(drone=missao.dock.drone, ativo=True, data_validade__lt=timezone.localdate()).exists():
        add("bloqueio", "documentos", "A aeronave possui documento vencido.")
    qualificacoes = QualificacaoPiloto.objects.filter(piloto=p.piloto, ativo=True)
    if qualificacoes.filter(data_validade__lt=timezone.localdate()).exists():
        add("bloqueio", "qualificacao", "O piloto possui qualificação operacional vencida.")
    elif not qualificacoes.exists():
        add("alerta", "qualificacao", "O piloto não possui qualificação operacional cadastrada.")
    return itens


def enfileirar_preparacao(missao, usuario):
    validacoes = avaliar_liberacao_missao(missao)
    bloqueios = [item for item in validacoes if item["nivel"] == "bloqueio"]
    if bloqueios:
        raise ValueError("; ".join(item["mensagem"] for item in bloqueios))
    dados = dados_flighttask_prepare(missao)
    comando = DJIDockComando.objects.create(
        dock=missao.dock, tipo="iniciar_missao", status="bloqueado",
        parametros={"missao_id": missao.pk}, mensagem_mqtt={
            "method": "flighttask_prepare", "data": dados,
        }, critico=True, solicitado_por=usuario,
        expira_em=timezone.now() + timedelta(seconds=settings.DJI_DOCK_COMMAND_TTL_SECONDS),
        mensagem="Prévia criada; publicação física permanece bloqueada.",
    )
    return comando, validacoes
