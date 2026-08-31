import json
import math
import statistics
import struct
from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal

from .models import PontoTelemetria


MAGIC = b"AUTEL_FR"
MAX_TEMPO_MS = 14_400_000


def parece_autel_fr(bruto):
    return bruto.startswith(MAGIC)


def _texto_nulo(bruto, inicio, fim):
    return bruto[inicio:fim].split(b"\0", 1)[0].decode("ascii", "ignore").strip()


def _componentes(bruto):
    inicio = bruto.find(b'[{"Bootloader"')
    if inicio < 0:
        return []
    try:
        texto = bruto[inicio:].decode("utf-8", "ignore")
        componentes, _ = json.JSONDecoder().raw_decode(texto)
        return componentes if isinstance(componentes, list) else []
    except (ValueError, TypeError):
        return []


def _candidatos_gps(bruto):
    candidatos = []
    posicao = 128
    while True:
        marcador = bruto.find(b"\x01", posicao)
        if marcador < 0:
            break
        posicao = marcador + 1
        offset = marcador + 5
        if offset + 24 > len(bruto):
            break
        try:
            tempo_ms = struct.unpack_from("<I", bruto, marcador + 1)[0]
            latitude, longitude, altitude, vx, vy, vz = struct.unpack_from("<ffffff", bruto, offset)
        except struct.error:
            continue
        if not (0 <= tempo_ms <= MAX_TEMPO_MS):
            continue
        if not (-89 < latitude < 89 and -179 < longitude < 179 and abs(latitude) > 1 and abs(longitude) > 1):
            continue
        if not (-1000 < altitude < 10000):
            continue
        if not all(math.isfinite(valor) and abs(valor) < 300 for valor in (vx, vy, vz)):
            continue
        candidatos.append((tempo_ms, latitude, longitude, altitude, math.hypot(vx, vy)))
    return candidatos


def _filtrar_trajetoria(candidatos):
    if not candidatos:
        return []
    latitude_mediana = statistics.median(item[1] for item in candidatos)
    longitude_mediana = statistics.median(item[2] for item in candidatos)
    filtrados = [
        item for item in candidatos
        if abs(item[1] - latitude_mediana) <= 1 and abs(item[2] - longitude_mediana) <= 1
    ]
    unicos = {}
    for item in filtrados:
        unicos.setdefault(item[0], item)
    return [unicos[chave] for chave in sorted(unicos)]


def processar_autel_fr(importacao, bruto):
    if not parece_autel_fr(bruto):
        raise ValueError("O arquivo não possui a assinatura AUTEL_FR.")
    if len(bruto) < 160:
        raise ValueError("O registro AUTEL_FR está incompleto.")
    versao = struct.unpack_from("<I", bruto, 8)[0]
    if versao != 3:
        raise ValueError(f"Registro AUTEL_FR versão {versao} ainda não suportado.")
    trajetoria = _filtrar_trajetoria(_candidatos_gps(bruto))
    if len(trajetoria) < 2:
        raise ValueError(
            "O registro AUTEL_FR foi reconhecido, mas não contém uma trajetória GPS de voo. "
            "Ele pode ser um registro de inicialização, teste ou operação sem decolagem."
        )
    inicio_epoch_ms = struct.unpack_from("<Q", bruto, 0x91)[0]
    if not (946684800000 <= inicio_epoch_ms <= 4102444800000):
        raise ValueError("O registro AUTEL_FR não contém uma data inicial válida.")
    inicio = datetime.fromtimestamp(inicio_epoch_ms / 1000, tz=datetime_timezone.utc)
    pontos = []
    for indice, (tempo_ms, latitude, longitude, altitude, velocidade) in enumerate(trajetoria, 1):
        pontos.append(PontoTelemetria(
            importacao=importacao, indice=indice,
            instante=inicio + timedelta(milliseconds=tempo_ms),
            segundos=Decimal(str(round(tempo_ms / 1000, 3))),
            latitude=Decimal(str(round(latitude, 7))),
            longitude=Decimal(str(round(longitude, 7))),
            altitude_m=Decimal(str(round(altitude, 2))),
            velocidade_ms=Decimal(str(round(velocidade, 2))),
        ))
    componentes = _componentes(bruto)
    serial_uav = _texto_nulo(bruto, 14, 32) or next(
        (str(item.get("SerialNumber") or "") for item in componentes if item.get("ComponetName") == "DEV_UAV"), ""
    )
    serial_bateria = _texto_nulo(bruto, 32, 64) or next(
        (str(item.get("SerialNumber") or "") for item in componentes if item.get("ComponetName") == "DEV_BATTERY"), ""
    )
    importacao.origem = "autel_flight_record"
    importacao.formato = f"autel-fr-v{versao}"
    importacao.versao_log = versao
    importacao.drone_modelo_detectado = "Autel EVO II"
    importacao.drone_serial_detectado = serial_uav[:100]
    importacao.bateria_serial_detectada = serial_bateria[:100]
    importacao.componentes_detectados = []
    importacao.colunas_reconhecidas = ["tempo", "gps", "altitude", "velocidade"]
    return pontos
