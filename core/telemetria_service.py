import csv
import io
import math
import unicodedata
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import PontoTelemetria


ALIASES = {
    "instante": ["timestamp", "datetime", "date_time", "data_hora", "time_stamp"],
    "segundos": ["seconds", "second", "tempo_s", "time_s", "elapsed_time", "elapsed_seconds"],
    "latitude": ["latitude", "lat", "gps_latitude"],
    "longitude": ["longitude", "lon", "lng", "gps_longitude"],
    "altitude_m": ["altitude", "altitude_m", "height", "height_m", "altura", "altura_m"],
    "velocidade_ms": ["speed", "speed_ms", "velocity", "velocidade", "velocidade_ms"],
    "bateria_percentual": ["battery", "battery_percent", "battery_percentage", "bateria", "bateria_percentual"],
    "satelites": ["satellites", "satellite_count", "satelites", "gps_satellites"],
    "sinal_percentual": ["signal", "signal_percent", "signal_strength", "sinal", "sinal_percentual"],
    "alerta": ["warning", "warnings", "alert", "message", "alerta", "aviso"],
}


def _normalizar(valor):
    texto = unicodedata.normalize("NFKD", str(valor or "")).encode("ascii", "ignore").decode().lower().strip()
    return "_".join(texto.replace("%", "percent").replace("(", " ").replace(")", " ").split())


def _decimal(valor):
    texto = str(valor or "").strip().replace(" ", "")
    if not texto:
        return None
    try:
        return Decimal(texto.replace(",", "."))
    except InvalidOperation:
        return None


def _inteiro_percentual(valor):
    numero = _decimal(valor)
    if numero is None:
        return None
    return max(0, min(100, int(round(numero))))


def _instante(valor):
    if not valor:
        return None
    resultado = parse_datetime(str(valor).strip().replace("Z", "+00:00"))
    if resultado and timezone.is_naive(resultado):
        resultado = timezone.make_aware(resultado)
    return resultado


def _distancia(lat1, lon1, lat2, lon2):
    raio = 6371000
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dp = math.radians(float(lat2 - lat1)); dl = math.radians(float(lon2 - lon1))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * raio * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@transaction.atomic
def processar_importacao(importacao, atualizar_voo=False):
    arquivo = importacao.arquivo
    arquivo.open("rb")
    bruto = arquivo.read(20 * 1024 * 1024 + 1)
    arquivo.close()
    if len(bruto) > 20 * 1024 * 1024:
        raise ValueError("O arquivo excede o limite de 20 MB.")
    amostra_binaria = bruto[:4096]
    proporcao_legivel = (
        sum(byte in (9, 10, 13) or 32 <= byte <= 126 for byte in amostra_binaria)
        / max(1, len(amostra_binaria))
    )
    if bruto.startswith(b"\x29\x03\x00\x00") or (
        importacao.nome_original.startswith("DJIFlightRecord_") and proporcao_legivel < 0.65
    ):
        raise ValueError(
            "Arquivo nativo DJI FlightRecord detectado. Ele é binário e protegido, apesar da extensão .txt. "
            "Para processá-lo é necessário configurar o parser oficial DJI com uma App Key, "
            "ou importar uma versão convertida para CSV."
        )
    try:
        texto = bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = bruto.decode("latin-1")
    amostra = texto[:8192]
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=",;\t|")
    except csv.Error:
        dialeto = csv.excel
    leitor = csv.DictReader(io.StringIO(texto), dialect=dialeto)
    if not leitor.fieldnames:
        raise ValueError("O arquivo não possui cabeçalho.")
    cabecalhos = {_normalizar(nome): nome for nome in leitor.fieldnames}
    mapa = {}
    for destino, aliases in ALIASES.items():
        for alias in aliases:
            if alias in cabecalhos:
                mapa[destino] = cabecalhos[alias]
                break
    if not mapa:
        raise ValueError("Nenhuma coluna de telemetria reconhecida.")
    pontos = []
    for indice, linha in enumerate(leitor, start=1):
        if indice > 100000:
            raise ValueError("O arquivo excede o limite de 100.000 pontos.")
        pontos.append(PontoTelemetria(
            importacao=importacao, indice=indice,
            instante=_instante(linha.get(mapa.get("instante", ""))),
            segundos=_decimal(linha.get(mapa.get("segundos", ""))),
            latitude=_decimal(linha.get(mapa.get("latitude", ""))),
            longitude=_decimal(linha.get(mapa.get("longitude", ""))),
            altitude_m=_decimal(linha.get(mapa.get("altitude_m", ""))),
            velocidade_ms=_decimal(linha.get(mapa.get("velocidade_ms", ""))),
            bateria_percentual=_inteiro_percentual(linha.get(mapa.get("bateria_percentual", ""))),
            satelites=max(0, int(_decimal(linha.get(mapa.get("satelites", ""))) or 0)) if mapa.get("satelites") else None,
            sinal_percentual=_inteiro_percentual(linha.get(mapa.get("sinal_percentual", ""))),
            alerta=str(linha.get(mapa.get("alerta", "")) or "").strip()[:255],
        ))
    if not pontos:
        raise ValueError("O arquivo não possui linhas de dados.")
    PontoTelemetria.objects.bulk_create(pontos, batch_size=2000)
    coordenadas = [(p.latitude, p.longitude) for p in pontos if p.latitude is not None and p.longitude is not None]
    distancia = sum(_distancia(*anterior, *atual) for anterior, atual in zip(coordenadas, coordenadas[1:]))
    instantes = [p.instante for p in pontos if p.instante]
    segundos = [p.segundos for p in pontos if p.segundos is not None]
    baterias = [p.bateria_percentual for p in pontos if p.bateria_percentual is not None]
    importacao.total_pontos = len(pontos)
    importacao.duracao_segundos = int((max(instantes) - min(instantes)).total_seconds()) if len(instantes) >= 2 else int(max(segundos) - min(segundos)) if len(segundos) >= 2 else None
    importacao.altitude_maxima_m = max((p.altitude_m for p in pontos if p.altitude_m is not None), default=None)
    importacao.velocidade_maxima_ms = max((p.velocidade_ms for p in pontos if p.velocidade_ms is not None), default=None)
    importacao.distancia_calculada_m = Decimal(str(round(distancia, 2))) if coordenadas else None
    importacao.bateria_inicial = baterias[0] if baterias else None
    importacao.bateria_final = baterias[-1] if baterias else None
    importacao.total_alertas = sum(bool(p.alerta) for p in pontos)
    importacao.colunas_reconhecidas = sorted(mapa.keys())
    importacao.status = "concluida"
    importacao.mensagem_erro = ""
    importacao.save()
    if atualizar_voo:
        voo = importacao.voo
        campos = []
        for campo, valor in [("distancia_m", importacao.distancia_calculada_m), ("bateria_inicial", importacao.bateria_inicial), ("bateria_final", importacao.bateria_final)]:
            if valor is not None:
                setattr(voo, campo, valor); campos.append(campo)
        if campos:
            voo.save(update_fields=campos)
    return importacao
