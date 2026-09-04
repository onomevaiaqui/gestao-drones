"""Gerenciamento auditável de vídeo; não publica comandos físicos nesta fase."""

from django.db import transaction
from django.utils import timezone

from .dji_dock_service import registrar_intencao_comando
from .dji_mqtt_commands import construir_previa_video
from .models import DJIDockCanalVideo, TransmissaoAoVivo


ACOES = {"iniciar", "parar", "qualidade", "lente"}


@transaction.atomic
def controlar_canal_video(canal, acao, usuario, *, qualidade="", lente=""):
    canal = DJIDockCanalVideo.objects.select_for_update().get(pk=canal.pk)
    if acao not in ACOES:
        raise ValueError("Ação de vídeo inválida.")
    if not canal.disponivel and acao != "parar":
        raise ValueError("Este canal não está disponível na estação.")

    parametros = {"canal_id": canal.pk, "video_id": canal.video_id}
    if acao == "iniciar":
        tipo = "iniciar_stream"
        if qualidade:
            canal.qualidade = _validar_qualidade(qualidade)
        canal.status = "simulado"
        piloto = getattr(usuario, "piloto", None)
        if piloto:
            transmissao = canal.transmissao_atual
            if not transmissao or transmissao.status not in {"preparada", "ao_vivo"}:
                transmissao = TransmissaoAoVivo.objects.create(
                    piloto=piloto,
                    drone=canal.dock.drone,
                    origem="avulsa",
                    aeronave_serial=canal.dispositivo_serial if canal.origem == "aeronave" else "",
                )
            canal.transmissao_atual = transmissao
            parametros["transmissao_id"] = transmissao.pk
    elif acao == "parar":
        tipo = "parar_stream"
        canal.status = "parado"
        if canal.transmissao_atual_id:
            parametros["transmissao_id"] = canal.transmissao_atual_id
    elif acao == "qualidade":
        tipo = "qualidade_stream"
        canal.qualidade = _validar_qualidade(qualidade)
        parametros["qualidade"] = canal.qualidade
    else:
        tipo = "trocar_lente"
        lente = str(lente or "").strip()[:30]
        permitidas = set(canal.lentes_alternativas or []) | ({canal.lente} if canal.lente else set())
        if not lente or lente not in permitidas:
            raise ValueError("Lente não anunciada por este canal.")
        canal.lente = lente
        parametros["lente"] = lente

    comando = registrar_intencao_comando(canal.dock, tipo, usuario, parametros)
    comando.mensagem_mqtt = construir_previa_video(
        comando,
        qualidade=canal.qualidade,
        lente=canal.lente,
    )
    comando.save(update_fields=["mensagem_mqtt"])
    canal.solicitado_por = usuario
    canal.solicitado_em = timezone.now()
    canal.save()
    return canal, comando


def _validar_qualidade(valor):
    valor = str(valor or "").strip()
    permitidas = {codigo for codigo, _ in DJIDockCanalVideo.QUALIDADE_CHOICES}
    if valor not in permitidas:
        raise ValueError("Qualidade de vídeo inválida.")
    return valor
