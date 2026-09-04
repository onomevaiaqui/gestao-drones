"""Resolve dados sigilosos do livestream somente em memória, imediatamente antes do envio."""

from copy import deepcopy
from urllib.parse import urlparse

from django.conf import settings

from .dji_cloud_service import endereco_ingestao
from .models import TransmissaoAoVivo


def resolver_previa_runtime(comando):
    previa = deepcopy(comando.mensagem_mqtt or {})
    campos = previa.get("campos_runtime") or []
    if not campos:
        return previa
    if comando.tipo != "iniciar_stream":
        raise ValueError("Existem campos de runtime não reconhecidos nesta mensagem.")
    if not settings.DJI_LIVESTREAM_ENABLED:
        raise ValueError("Livestream DJI desativado.")
    transmissao_id = comando.parametros.get("transmissao_id")
    transmissao = TransmissaoAoVivo.objects.filter(pk=transmissao_id, status="preparada").first()
    if not transmissao:
        raise ValueError("Sessão de livestream preparada não encontrada.")
    url = endereco_ingestao(transmissao)
    parsed = urlparse(url)
    local_inseguro = (
        settings.DEBUG
        and settings.DJI_LIVESTREAM_ALLOW_INSECURE_LOCAL
        and parsed.scheme == "rtmp"
        and parsed.hostname in {"127.0.0.1", "localhost", "mediamtx"}
    )
    if (parsed.scheme != "rtmps" or not parsed.hostname) and not local_inseguro:
        raise ValueError("A ingestão da transmissão deve usar RTMPS válido.")
    dados = previa.setdefault("payload", {}).setdefault("data", {})
    dados["url_type"] = 1
    dados["url"] = url
    previa["campos_runtime"] = []
    previa["pronto_para_publicar"] = True
    return previa
