"""Configuração e tokens da integração DJI Open Platforms."""

import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.core import signing


def diagnostico_open_platforms():
    valores = {
        "app_id": bool(settings.DJI_CLOUD_APP_ID),
        "app_key": bool(settings.DJI_CLOUD_APP_KEY),
        "app_license": bool(settings.DJI_CLOUD_APP_LICENSE),
        "workspace_id": _uuid_valido(settings.DJI_CLOUD_WORKSPACE_ID),
        "public_url": _https_valido(settings.DJI_CLOUD_PUBLIC_URL),
        "api_host": _https_valido(settings.DJI_CLOUD_API_HOST),
        "mqtt_host": _mqtt_valido(settings.DJI_CLOUD_MQTT_HOST),
        "mqtt_prefixo": bool(settings.DJI_CLOUD_MQTT_USERNAME_PREFIX),
    }
    configurado = all(valores.values())
    return {
        "itens": valores,
        "configurado": configurado,
        "habilitado": settings.DJI_CLOUD_ENABLED,
        "pronto": settings.DJI_CLOUD_ENABLED and configurado,
        "livestream": diagnostico_livestream(),
        "dock": diagnostico_dock(),
    }


def diagnostico_dock():
    mqtt = configuracao_mqtt_dock()
    itens = {
        "broker": bool(mqtt),
        "usuario": bool(settings.DJI_DOCK_MQTT_USERNAME),
        "senha": bool(settings.DJI_DOCK_MQTT_PASSWORD),
        "cliente": bool(settings.DJI_DOCK_MQTT_CLIENT_ID),
        "topicos": bool(settings.DJI_DOCK_MQTT_TOPIC),
    }
    return {
        "itens": itens,
        "configurado": all(itens.values()),
        "habilitado": settings.DJI_DOCK_ENABLED,
        "simulador": settings.DJI_DOCK_SIMULATOR_ENABLED,
        "comandos": settings.DJI_DOCK_COMMANDS_ENABLED,
        "pronto": settings.DJI_DOCK_ENABLED and all(itens.values()),
    }


def configuracao_mqtt_dock():
    """Normaliza o endereço do broker sem expor credenciais."""
    parsed = urlparse(settings.DJI_CLOUD_MQTT_HOST)
    if parsed.scheme not in ("tcp", "ssl", "ws", "wss") or not parsed.hostname:
        return None
    seguro = parsed.scheme in ("ssl", "wss")
    return {
        "host": parsed.hostname,
        "port": parsed.port or (8883 if seguro else 1883),
        "tls": seguro,
        "websockets": parsed.scheme in ("ws", "wss"),
        "topics": [item.strip() for item in settings.DJI_DOCK_MQTT_TOPIC.split(",") if item.strip()],
    }


def diagnostico_livestream():
    rtmp = _rtmp_valido(settings.DJI_LIVESTREAM_RTMP_BASE_URL)
    playback = _https_valido(settings.DJI_LIVESTREAM_PLAYBACK_BASE_URL)
    configurado = rtmp and playback
    return {
        "itens": {"rtmp": rtmp, "playback": playback},
        "configurado": configurado,
        "habilitado": settings.DJI_LIVESTREAM_ENABLED,
        "pronto": settings.DJI_CLOUD_ENABLED and settings.DJI_LIVESTREAM_ENABLED and configurado,
    }


def endereco_ingestao(transmissao):
    return f"{settings.DJI_LIVESTREAM_RTMP_BASE_URL}/{transmissao.chave_stream}"


def endereco_reproducao(transmissao):
    """Página WebRTC do MediaMTX/SRS; nunca expõe a URL privada de ingestão."""
    return f"{settings.DJI_LIVESTREAM_PLAYBACK_BASE_URL}/{transmissao.chave_stream}"


def token_pilot(user):
    return signing.dumps(
        {"usuario_id": user.pk, "finalidade": "dji-pilot-open-platforms"},
        salt="sismod.dji.cloud",
        compress=True,
    )


def validar_token_pilot(token, max_age=12 * 60 * 60):
    try:
        dados = signing.loads(token, salt="sismod.dji.cloud", max_age=max_age)
    except signing.BadSignature:
        return None
    if dados.get("finalidade") != "dji-pilot-open-platforms":
        return None
    return dados


def usuario_mqtt(user):
    return f"{settings.DJI_CLOUD_MQTT_USERNAME_PREFIX}-{user.pk}"


def _uuid_valido(valor):
    try:
        uuid.UUID(valor)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _https_valido(valor):
    parsed = urlparse(valor)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _mqtt_valido(valor):
    parsed = urlparse(valor)
    return parsed.scheme in ("tcp", "ssl", "ws", "wss") and bool(parsed.netloc)


def _rtmp_valido(valor):
    parsed = urlparse(valor)
    return parsed.scheme in ("rtmp", "rtmps") and bool(parsed.netloc)
