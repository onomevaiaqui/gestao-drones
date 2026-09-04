"""Construtores de mensagens DJI Cloud API, sem realizar publicação MQTT."""

import time
import uuid
import re


METODOS_VIDEO = {
    "iniciar_stream": "live_start_push",
    "parar_stream": "live_stop_push",
    "qualidade_stream": "live_set_quality",
    "trocar_lente": "live_lens_change",
}

QUALIDADE_DJI = {
    "adaptive": 0,
    "smooth": 1,
    "standard": 2,
    "high": 3,
}


def construir_previa_video(comando, *, qualidade="", lente=""):
    """Monta uma prévia auditável; dados secretos de ingestão ficam para o publicador."""
    metodo = METODOS_VIDEO.get(comando.tipo)
    if not metodo:
        raise ValueError("O comando não corresponde a uma ação de vídeo DJI.")

    video_id = str(comando.parametros.get("video_id") or "").strip()
    if not video_id or video_id.count("/") != 2:
        raise ValueError("Identificador de vídeo DJI inválido.")
    gateway_sn = str(comando.dock.numero_serie or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", gateway_sn):
        raise ValueError("Número de série da estação inválido para tópico MQTT.")

    dados = {"video_id": video_id}
    campos_runtime = []
    if comando.tipo == "iniciar_stream":
        dados["video_quality"] = QUALIDADE_DJI[_validar_qualidade(qualidade or "adaptive")]
        # A URL pode conter credenciais ou tokens e nunca deve ser persistida na fila.
        campos_runtime = ["data.url_type", "data.url"]
    elif comando.tipo == "qualidade_stream":
        dados["video_quality"] = QUALIDADE_DJI[_validar_qualidade(qualidade)]
    elif comando.tipo == "trocar_lente":
        lente = str(lente or "").strip()
        if lente not in {"normal", "wide", "zoom", "ir"}:
            raise ValueError("Tipo de lente DJI inválido.")
        dados["video_type"] = lente

    return {
        "topic": f"thing/product/{gateway_sn}/services",
        "payload": {
            "bid": str(uuid.uuid4()),
            "tid": str(comando.identificador),
            "timestamp": int(time.time() * 1000),
            "method": metodo,
            "data": dados,
        },
        "pronto_para_publicar": not campos_runtime,
        "campos_runtime": campos_runtime,
    }


def _validar_qualidade(valor):
    valor = str(valor or "").strip()
    if valor not in QUALIDADE_DJI:
        raise ValueError("Qualidade de vídeo DJI inválida.")
    return valor
