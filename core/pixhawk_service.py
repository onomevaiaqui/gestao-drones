"""Leitores de logs gerados por controladoras Pixhawk (ArduPilot e PX4)."""

import bisect
import math
import os
import tempfile
from datetime import datetime
from decimal import Decimal

from django.utils import timezone

from .models import PontoTelemetria


LIMITE_PONTOS = 100000


def _decimal(valor, casas=7):
    if valor is None:
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numero):
        return None
    return Decimal(str(round(numero, casas)))


def _percentual(valor, escala_fracao=False):
    if valor is None:
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if escala_fracao and 0 <= numero <= 1:
        numero *= 100
    if numero < 0:
        return None
    return max(0, min(100, int(round(numero))))


def _coordenada(valor, limite):
    numero = float(valor or 0)
    if abs(numero) > limite:
        numero /= 1e7
    return _decimal(numero) if 0 < abs(numero) <= limite else None


def _instante_epoch(segundos):
    if not segundos or segundos < 946684800:  # 01/01/2000
        return None
    return datetime.fromtimestamp(float(segundos), tz=timezone.get_current_timezone())


def _arquivo_temporario(bruto, sufixo):
    arquivo = tempfile.NamedTemporaryFile(delete=False, suffix=sufixo)
    try:
        arquivo.write(bruto)
        return arquivo.name
    finally:
        arquivo.close()


def processar_ardupilot(importacao, bruto):
    try:
        from pymavlink import DFReader
    except ImportError as exc:
        raise ValueError("O leitor Pixhawk/ArduPilot não está instalado.") from exc

    caminho = _arquivo_temporario(bruto, ".bin")
    pontos, alertas_pendentes = [], []
    bateria, sinal = None, None
    modelo, serial = "ArduPilot / Pixhawk", ""
    inicio_monotonico = None
    try:
        leitor = DFReader.DFReader_binary(caminho)
        while True:
            mensagem = leitor.recv_msg()
            if mensagem is None:
                break
            tipo = mensagem.get_type()
            if tipo in ("BAT", "CURR"):
                bateria = _percentual(getattr(mensagem, "RemPct", None)) or bateria
                continue
            if tipo == "RSSI":
                bruto_sinal = getattr(mensagem, "RXRSSI", None)
                sinal = _percentual(float(bruto_sinal) * 100 / 255) if bruto_sinal is not None else sinal
                continue
            if tipo == "ERR":
                alertas_pendentes.append(
                    f"ArduPilot ERR: subsistema {getattr(mensagem, 'Subsys', '?')}, código {getattr(mensagem, 'ECode', '?')}"
                )
                continue
            if tipo == "MSG":
                texto = str(getattr(mensagem, "Message", "") or "").strip()
                if texto.startswith(("Ardu", "PX4")):
                    modelo = texto[:120]
                continue
            if tipo == "VER":
                uid = getattr(mensagem, "UID", None)
                if uid not in (None, 0, "0"):
                    serial = str(uid)[:100]
                continue
            if tipo != "GPS":
                continue
            latitude = _coordenada(getattr(mensagem, "Lat", None), 90)
            longitude = _coordenada(getattr(mensagem, "Lng", None), 180)
            if latitude is None or longitude is None:
                continue
            if len(pontos) >= LIMITE_PONTOS:
                raise ValueError("O log Pixhawk excede o limite de 100.000 pontos GPS.")
            tempo_us = getattr(mensagem, "TimeUS", None)
            tempo_s = float(tempo_us) / 1e6 if tempo_us is not None else float(getattr(mensagem, "_timestamp", 0) or 0)
            if inicio_monotonico is None:
                inicio_monotonico = tempo_s
            instante = _instante_epoch(float(getattr(mensagem, "_timestamp", 0) or 0))
            alerta = "; ".join(alertas_pendentes)[:255]
            alertas_pendentes.clear()
            pontos.append(PontoTelemetria(
                importacao=importacao, indice=len(pontos) + 1, instante=instante,
                segundos=_decimal(max(0, tempo_s - inicio_monotonico), 3),
                latitude=latitude, longitude=longitude,
                altitude_m=_decimal(getattr(mensagem, "RelAlt", getattr(mensagem, "Alt", None)), 2),
                velocidade_ms=_decimal(getattr(mensagem, "Spd", None), 2),
                bateria_percentual=bateria,
                satelites=max(0, int(getattr(mensagem, "NSats", 0))) if hasattr(mensagem, "NSats") else None,
                sinal_percentual=sinal, alerta=alerta,
            ))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Não foi possível ler o log ArduPilot BIN: {exc}") from exc
    finally:
        os.unlink(caminho)
    if not pontos:
        raise ValueError("O log ArduPilot não contém mensagens GPS válidas.")
    importacao.origem = "pixhawk_ardupilot"
    importacao.formato = "ardupilot-bin"
    importacao.drone_modelo_detectado = modelo
    importacao.drone_serial_detectado = serial
    importacao.colunas_reconhecidas = ["tempo", "gps", "altitude", "velocidade", "bateria", "satelites", "sinal", "alertas"]
    return pontos


def _dataset(ulog, nome):
    return next((item for item in ulog.data_list if item.name == nome and item.multi_id == 0), None)


def _mais_proximo(tempos, valores, instante):
    if not tempos:
        return None
    indice = bisect.bisect_left(tempos, instante)
    candidatos = [item for item in (indice - 1, indice) if 0 <= item < len(tempos)]
    escolhido = min(candidatos, key=lambda item: abs(tempos[item] - instante))
    return valores[escolhido]


def processar_px4(importacao, bruto):
    try:
        from pyulog import ULog
    except ImportError as exc:
        raise ValueError("O leitor Pixhawk/PX4 não está instalado.") from exc

    caminho = _arquivo_temporario(bruto, ".ulg")
    try:
        ulog = ULog(caminho)
    except Exception as exc:
        raise ValueError(f"Não foi possível ler o log PX4 ULog: {exc}") from exc
    finally:
        os.unlink(caminho)

    gps = _dataset(ulog, "vehicle_gps_position")
    if gps is None:
        raise ValueError("O log PX4 não contém o tópico vehicle_gps_position.")
    dados = gps.data
    quantidade = len(dados.get("timestamp", []))
    if quantidade > LIMITE_PONTOS:
        raise ValueError("O log Pixhawk excede o limite de 100.000 pontos GPS.")

    bateria_ds = _dataset(ulog, "battery_status")
    bateria_tempos = list(bateria_ds.data.get("timestamp", [])) if bateria_ds else []
    bateria_valores = list(bateria_ds.data.get("remaining", [])) if bateria_ds else []
    local_ds = _dataset(ulog, "vehicle_local_position")
    local_tempos = list(local_ds.data.get("timestamp", [])) if local_ds else []
    local_z = list(local_ds.data.get("z", [])) if local_ds else []
    alertas = sorted(getattr(ulog, "logged_messages", []) or [], key=lambda item: item.timestamp)
    alerta_indice = 0
    timestamps = list(dados.get("timestamp", []))
    primeiro_us = timestamps[0] if timestamps else 0
    pontos = []
    for indice in range(quantidade):
        timestamp = int(timestamps[indice])
        latitude = _coordenada(dados.get("lat", [0] * quantidade)[indice], 90)
        longitude = _coordenada(dados.get("lon", [0] * quantidade)[indice], 180)
        if latitude is None or longitude is None:
            continue
        avisos = []
        while alerta_indice < len(alertas) and alertas[alerta_indice].timestamp <= timestamp:
            item = alertas[alerta_indice]
            if int(getattr(item, "log_level", 7)) <= 4:
                avisos.append(str(getattr(item, "message", "")))
            alerta_indice += 1
        utc_lista = dados.get("time_utc_usec")
        utc_us = int(utc_lista[indice]) if utc_lista is not None else 0
        instante = _instante_epoch(utc_us / 1e6)
        altitude = None
        z = _mais_proximo(local_tempos, local_z, timestamp)
        if z is not None and math.isfinite(float(z)):
            altitude = -float(z)
        elif "alt" in dados:
            altitude = float(dados["alt"][indice]) / 1000
        velocidade = dados.get("vel_m_s")
        bateria_restante = _mais_proximo(bateria_tempos, bateria_valores, timestamp)
        pontos.append(PontoTelemetria(
            importacao=importacao, indice=len(pontos) + 1, instante=instante,
            segundos=_decimal((timestamp - primeiro_us) / 1e6, 3),
            latitude=latitude, longitude=longitude, altitude_m=_decimal(altitude, 2),
            velocidade_ms=_decimal(velocidade[indice], 2) if velocidade is not None else None,
            bateria_percentual=_percentual(bateria_restante, escala_fracao=True),
            satelites=max(0, int(dados["satellites_used"][indice])) if "satellites_used" in dados else None,
            alerta="; ".join(avisos)[:255],
        ))
    if not pontos:
        raise ValueError("O log PX4 não contém posições GPS válidas.")
    versao = str(ulog.msg_info_dict.get("ver_sw", "") or "").strip()
    hardware = str(ulog.msg_info_dict.get("ver_hw", "") or "").strip()
    identificadores = " ".join([importacao.nome_original or "", hardware, versao] + [str(valor) for valor in ulog.msg_info_dict.values()])
    wingtra = "wingtra" in identificadores.lower()
    importacao.origem = "wingtra" if wingtra else "pixhawk_px4"
    importacao.formato = "wingtra-ulog" if wingtra else "px4-ulog"
    importacao.drone_modelo_detectado = (("WingtraOne" if wingtra else "PX4") + (f" {hardware}" if hardware else ""))[:120]
    importacao.drone_serial_detectado = str(ulog.msg_info_dict.get("sys_uuid", "") or "")[:100]
    importacao.versao_log = 0
    importacao.colunas_reconhecidas = ["tempo", "gps", "altitude", "velocidade", "bateria", "satelites", "alertas"]
    if versao:
        importacao.drone_modelo_detectado = f"{importacao.drone_modelo_detectado} · {versao}"[:120]
    return pontos
