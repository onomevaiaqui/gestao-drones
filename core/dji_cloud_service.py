"""Configuração e tokens da integração DJI Open Platforms."""

import uuid
import json
from urllib.request import urlopen
from urllib.error import URLError
from urllib.parse import urlencode, urlparse

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
        "publicador": settings.DJI_DOCK_PUBLISHER_ENABLED,
        "parada_emergencia": settings.DJI_DOCK_EMERGENCY_STOP,
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
        "servidor": diagnostico_mediamtx(),
    }


def diagnostico_mediamtx():
    url = settings.SISMOD_MEDIAMTX_API_URL
    if not url:
        return {"configurado": False, "online": False, "caminhos_ativos": 0, "erro": "API não configurada."}
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return {"configurado": False, "online": False, "caminhos_ativos": 0, "erro": "URL da API inválida."}
    try:
        with urlopen(f"{url}/v3/paths/list", timeout=2) as resposta:
            dados = json.loads(resposta.read(1_000_000).decode("utf-8"))
        itens = dados.get("items", []) if isinstance(dados, dict) else []
        ativos = sum(1 for item in itens if isinstance(item, dict) and item.get("ready"))
        return {"configurado": True, "online": True, "caminhos_ativos": ativos, "erro": ""}
    except (OSError, URLError, ValueError, json.JSONDecodeError) as erro:
        return {"configurado": True, "online": False, "caminhos_ativos": 0, "erro": str(erro)[:160]}


def endereco_ingestao(transmissao):
    base = f"{settings.DJI_LIVESTREAM_RTMP_BASE_URL}/{transmissao.chave_stream}"
    token = token_mediamtx(transmissao, "publish")
    return f"{base}?{urlencode({'token': token})}" if token else base


def endereco_reproducao(transmissao, usuario=None):
    """Página WebRTC do MediaMTX/SRS; nunca expõe a URL privada de ingestão."""
    parsed = urlparse(settings.DJI_LIVESTREAM_PLAYBACK_BASE_URL)
    local_inseguro = (
        settings.DEBUG
        and settings.DJI_LIVESTREAM_ALLOW_INSECURE_LOCAL
        and parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost"}
    )
    if not settings.DJI_LIVESTREAM_ENABLED or (not _https_valido(settings.DJI_LIVESTREAM_PLAYBACK_BASE_URL) and not local_inseguro):
        return ""
    if transmissao.status != "ao_vivo":
        return ""
    base = f"{settings.DJI_LIVESTREAM_PLAYBACK_BASE_URL}/{transmissao.chave_stream}"
    token = token_mediamtx(transmissao, "read", usuario)
    if settings.SISMOD_MEDIAMTX_AUTH_SECRET and not token:
        return ""
    return f"{base}?{urlencode({'token': token})}" if token else base


def pode_acessar_video(usuario, transmissao, acao):
    from .permissoes import usuario_e_admin, usuario_tem_visao_global
    from .dji_dock_permissions import pode_visualizar_dock
    if not usuario or not usuario.is_active or not transmissao.piloto.ativo:
        return False
    piloto = getattr(usuario, "piloto", None)
    if piloto is not None and not piloto.ativo:
        return False
    if acao == "publish":
        return transmissao.status in {"preparada", "ao_vivo"} and transmissao.piloto.user_id == usuario.pk
    if acao != "read" or transmissao.status != "ao_vivo":
        return False
    canais = list(transmissao.canais_dock.select_related("dock"))
    if canais and not any(c.disponivel and pode_visualizar_dock(usuario, c.dock) for c in canais):
        return False
    if usuario_e_admin(usuario) or transmissao.piloto.user_id == usuario.pk:
        return True
    return usuario_tem_visao_global(usuario) and (
        not transmissao.planejamento_id or transmissao.planejamento.livestream_acesso == "coordenacao"
    )


def token_mediamtx(transmissao, acao, usuario=None):
    if not settings.SISMOD_MEDIAMTX_AUTH_SECRET:
        return ""
    usuario = usuario or transmissao.piloto.user
    if not pode_acessar_video(usuario, transmissao, acao):
        return ""
    return signing.dumps(
        {"stream": str(transmissao.chave_stream), "action": acao, "uid": usuario.pk,
         "auth": usuario.get_session_auth_hash(), "mode": getattr(usuario, "_modo_acesso", None)},
        key=settings.SISMOD_MEDIAMTX_AUTH_SECRET,
        salt="sismod.mediamtx",
        compress=True,
    )


def validar_token_mediamtx(token, caminho, acao, *, conexao_ativa=False):
    if not settings.SISMOD_MEDIAMTX_AUTH_SECRET or not token:
        return False
    try:
        dados = signing.loads(
            token,
            key=settings.SISMOD_MEDIAMTX_AUTH_SECRET,
            salt="sismod.mediamtx",
            max_age=None if conexao_ativa else settings.SISMOD_MEDIAMTX_TOKEN_TTL_SECONDS,
        )
    except (signing.BadSignature, TypeError, ValueError):
        return False
    if not isinstance(dados, dict) or not isinstance(caminho, str) or not isinstance(acao, str):
        return False
    acao_esperada = "read" if acao in {"read", "playback"} else acao
    if dados.get("stream") != caminho.strip("/") or dados.get("action") != acao_esperada:
        return False
    from django.contrib.auth import get_user_model
    from django.utils.crypto import constant_time_compare
    from .models import TransmissaoAoVivo
    try:
        usuario = get_user_model().objects.filter(pk=dados.get("uid"), is_active=True).first()
        transmissao = TransmissaoAoVivo.objects.select_related("piloto__user", "planejamento").filter(chave_stream=caminho.strip("/")).first()
    except (ValueError, TypeError):
        return False
    if not usuario or not transmissao or not constant_time_compare(dados.get("auth", ""), usuario.get_session_auth_hash()):
        return False
    usuario._modo_acesso = dados.get("mode")
    return pode_acessar_video(usuario, transmissao, acao_esperada)


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
