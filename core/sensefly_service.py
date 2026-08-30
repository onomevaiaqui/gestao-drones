"""Normalização do JSON de registro de voo exportado pelo senseFly eMotion."""

import json

from .models import PontoTelemetria
from .telemetria_service import (
    ALIASES, _cabecalho_corresponde, _converter_unidade, _decimal, _instante,
    _inteiro_percentual, _mapear_cabecalhos, _normalizar,
)


def _achatar(objeto, prefixo=""):
    resultado = {}
    for chave, valor in (objeto or {}).items():
        nome = f"{prefixo}_{chave}" if prefixo else str(chave)
        if isinstance(valor, dict):
            resultado.update(_achatar(valor, nome))
        elif not isinstance(valor, (list, tuple, dict)):
            resultado[nome] = valor
    return resultado


def _listas_de_registros(objeto):
    if isinstance(objeto, list) and objeto and all(isinstance(item, dict) for item in objeto):
        yield objeto
    if isinstance(objeto, dict):
        for valor in objeto.values():
            yield from _listas_de_registros(valor)
    elif isinstance(objeto, list):
        for valor in objeto:
            yield from _listas_de_registros(valor)


def _selecionar_telemetria(documento):
    melhor, melhor_pontuacao = None, -1
    for lista in _listas_de_registros(documento):
        amostra = [_achatar(item) for item in lista[:5]]
        campos = {chave for item in amostra for chave in item}
        mapa = _mapear_cabecalhos(campos, ALIASES)
        pontuacao = len(mapa) + (4 if "latitude" in mapa and "longitude" in mapa else 0)
        if pontuacao > melhor_pontuacao:
            melhor, melhor_pontuacao = ([_achatar(item) for item in lista], mapa), pontuacao
    return melhor if melhor_pontuacao >= 6 else (None, None)


def _buscar_metadado(objeto, aliases):
    if isinstance(objeto, dict):
        for chave, valor in objeto.items():
            if not isinstance(valor, (dict, list)) and _cabecalho_corresponde(_normalizar(chave), aliases):
                return str(valor or "").strip()
        for valor in objeto.values():
            encontrado = _buscar_metadado(valor, aliases)
            if encontrado:
                return encontrado
    elif isinstance(objeto, list):
        for valor in objeto[:20]:
            encontrado = _buscar_metadado(valor, aliases)
            if encontrado:
                return encontrado
    return ""


def processar_sensefly_json(importacao, bruto):
    try:
        documento = json.loads(bruto.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"O JSON senseFly/eMotion não pôde ser lido: {exc}") from exc
    linhas, mapa = _selecionar_telemetria(documento)
    if not linhas or "latitude" not in mapa or "longitude" not in mapa:
        raise ValueError("O JSON não contém a telemetria esperada. No eMotion, exporte marcando ‘Create JSON flight log’.")
    if len(linhas) > 100000:
        raise ValueError("O registro senseFly excede o limite de 100.000 pontos.")
    pontos = []
    for linha in linhas:
        latitude, longitude = _decimal(linha.get(mapa["latitude"])), _decimal(linha.get(mapa["longitude"]))
        if latitude is None or longitude is None or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue
        pontos.append(PontoTelemetria(
            importacao=importacao, indice=len(pontos) + 1,
            instante=_instante(linha.get(mapa.get("instante", ""))),
            segundos=_decimal(linha.get(mapa.get("segundos", ""))), latitude=latitude, longitude=longitude,
            altitude_m=_converter_unidade(linha.get(mapa.get("altitude_m", "")), mapa.get("altitude_m", ""), "altitude"),
            velocidade_ms=_converter_unidade(linha.get(mapa.get("velocidade_ms", "")), mapa.get("velocidade_ms", ""), "velocidade"),
            bateria_percentual=_inteiro_percentual(linha.get(mapa.get("bateria_percentual", ""))),
            satelites=max(0, int(_decimal(linha.get(mapa.get("satelites", ""))) or 0)) if mapa.get("satelites") else None,
            sinal_percentual=_inteiro_percentual(linha.get(mapa.get("sinal_percentual", ""))),
            alerta=str(linha.get(mapa.get("alerta", "")) or "")[:255],
        ))
    if not pontos:
        raise ValueError("O JSON senseFly/eMotion não contém posições GPS válidas.")
    importacao.origem, importacao.formato = "sensefly_emotion", "sensefly-json"
    importacao.drone_modelo_detectado = _buscar_metadado(documento, ["aircraft_model", "drone_model", "product_model", "model"])[:120] or "senseFly eBee"
    importacao.drone_serial_detectado = _buscar_metadado(documento, ["aircraft_serial", "drone_serial", "serial_number", "serial"])[:100]
    importacao.bateria_serial_detectada = _buscar_metadado(documento, ["battery_serial", "battery_serial_number"])[:100]
    importacao.colunas_reconhecidas = sorted(mapa.keys())
    return pontos
