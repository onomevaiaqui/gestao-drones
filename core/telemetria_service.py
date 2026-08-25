import csv
import io
import logging
import math
import unicodedata
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.conf import settings
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


def _parece_log_dji(bruto, nome):
    amostra = bruto[:4096]
    proporcao_legivel = sum(
        byte in (9, 10, 13) or 32 <= byte <= 126 for byte in amostra
    ) / max(1, len(amostra))
    return bruto.startswith(b"\x29\x03\x00\x00") or (
        nome.startswith("DJIFlightRecord_") and proporcao_legivel < 0.65
    )


def _processar_dji(importacao, bruto):
    chave = getattr(settings, "DJI_FLIGHT_RECORD_APP_KEY", "").strip()
    if not chave:
        raise ValueError("A chave DJI não está configurada no arquivo .env.")
    try:
        from dji_flightlog_parser import DJILog
    except ImportError as exc:
        raise ValueError(
            "O leitor de logs DJI não está instalado. Execute a instalação das dependências do projeto."
        ) from exc

    logging.getLogger("dji_flightlog_parser").setLevel(logging.CRITICAL)
    try:
        log = DJILog.from_bytes(bruto)
        if log.version not in (13, 14):
            raise ValueError(f"Flight Record DJI versão {log.version} ainda não suportado.")
        chaves = log.fetch_keychains(chave, use_cache=False)
        frames = log.frames(chaves)
    except ValueError:
        raise
    except Exception as exc:
        detalhe = str(exc)
        if "401" in detalhe or "403" in detalhe:
            detalhe = "a App Key DJI foi recusada ou não tem acesso à Flight Record Parsing API"
        raise ValueError(f"Não foi possível decodificar o Flight Record DJI: {detalhe}") from exc

    if not frames:
        raise ValueError("O log DJI foi aberto, mas não contém pontos de voo reconhecíveis.")
    if len(frames) > 100000:
        raise ValueError("O arquivo excede o limite de 100.000 pontos.")

    pontos = []
    for indice, frame in enumerate(frames, start=1):
        osd, bateria, rc = frame.osd, frame.battery, frame.rc
        instante = frame.custom.date_time
        if not instante or instante.year < 2000:
            instante = None
        latitude = osd.latitude if -90 <= osd.latitude <= 90 and osd.latitude != 0 else None
        longitude = osd.longitude if -180 <= osd.longitude <= 180 and osd.longitude != 0 else None
        velocidade = math.hypot(osd.x_speed, osd.y_speed)
        alerta = (frame.app.warn or "").strip()
        pontos.append(PontoTelemetria(
            importacao=importacao, indice=indice, instante=instante,
            segundos=Decimal(str(round(osd.fly_time, 3))),
            latitude=Decimal(str(latitude)) if latitude is not None else None,
            longitude=Decimal(str(longitude)) if longitude is not None else None,
            altitude_m=Decimal(str(round(osd.height, 2))),
            velocidade_ms=Decimal(str(round(velocidade, 2))),
            bateria_percentual=max(0, min(100, bateria.charge_level)),
            satelites=max(0, osd.gps_num),
            sinal_percentual=rc.downlink_signal,
            alerta=alerta[:255],
        ))

    detalhes = log.details
    ultimo = frames[-1]
    importacao.origem = "dji_flight_record"
    importacao.formato = f"dji-v{log.version}"
    importacao.versao_log = log.version
    importacao.drone_modelo_detectado = (detalhes.aircraft_name or ultimo.recover.aircraft_name or "")[:120]
    importacao.drone_serial_detectado = (detalhes.aircraft_sn or ultimo.recover.aircraft_sn or "")[:100]
    importacao.bateria_serial_detectada = (ultimo.battery.battery_serial or ultimo.recover.battery_sn or "")[:100]
    importacao.colunas_reconhecidas = [
        "tempo", "gps", "altitude", "velocidade", "bateria", "satelites", "sinal", "alertas"
    ]
    importacao._inicio_dji = detalhes.start_time
    importacao._duracao_dji = max(0, float(detalhes.total_time or 0))
    return pontos


def _concluir_importacao(importacao, pontos, atualizar_voo):
    PontoTelemetria.objects.bulk_create(pontos, batch_size=2000)
    coordenadas = [(p.latitude, p.longitude) for p in pontos if p.latitude is not None and p.longitude is not None]
    distancia = sum(_distancia(*anterior, *atual) for anterior, atual in zip(coordenadas, coordenadas[1:]))
    instantes = [p.instante for p in pontos if p.instante]
    segundos = [p.segundos for p in pontos if p.segundos is not None]
    baterias = [p.bateria_percentual for p in pontos if p.bateria_percentual is not None]
    importacao.total_pontos = len(pontos)
    # O relógio interno de alguns DJI Pilot 2 pode saltar entre quadros. O tempo
    # decorrido do voo é a fonte estável sempre que estiver disponível.
    duracao_dji = getattr(importacao, "_duracao_dji", None)
    if duracao_dji is not None:
        importacao.duracao_segundos = int(round(duracao_dji))
    elif segundos:
        importacao.duracao_segundos = int(max(segundos) - min(segundos))
    else:
        importacao.duracao_segundos = int((max(instantes) - min(instantes)).total_seconds()) if len(instantes) >= 2 else None
    inicio_dji = getattr(importacao, "_inicio_dji", None)
    if inicio_dji:
        importacao.inicio_registro = inicio_dji
        importacao.fim_registro = inicio_dji + timedelta(seconds=importacao.duracao_segundos or 0)
    elif instantes:
        importacao.inicio_registro = min(instantes)
        importacao.fim_registro = max(instantes)
    importacao.altitude_maxima_m = max((p.altitude_m for p in pontos if p.altitude_m is not None), default=None)
    importacao.velocidade_maxima_ms = max((p.velocidade_ms for p in pontos if p.velocidade_ms is not None), default=None)
    importacao.distancia_calculada_m = Decimal(str(round(distancia, 2))) if coordenadas else None
    importacao.bateria_inicial = baterias[0] if baterias else None
    importacao.bateria_final = baterias[-1] if baterias else None
    alertas, alerta_anterior = 0, ""
    for ponto in pontos:
        alerta_atual = (ponto.alerta or "").strip()
        if alerta_atual and alerta_atual != alerta_anterior:
            alertas += 1
        alerta_anterior = alerta_atual
    importacao.total_alertas = alertas
    importacao.status = "concluida"
    importacao.mensagem_erro = ""
    importacao.save()
    if atualizar_voo:
        voo = importacao.voo
        inicio_importado = importacao.inicio_registro
        if inicio_importado:
            data_importada = timezone.localtime(inicio_importado).date()
            voo_existente = type(voo).objects.filter(
                data=data_importada, piloto_id=voo.piloto_id, drone_id=voo.drone_id,
            ).exclude(pk=voo.pk).order_by("pk").first()
            if voo_existente:
                voo_original = voo
                voo_original.importacoes_log.update(voo=voo_existente)
                importacao.voo = voo_existente
                voo = voo_existente
                if not hasattr(voo_original, "registro_pos_voo"):
                    alocacao = voo_original.alocacao_calendario
                    voo_original.delete()
                    if alocacao and not hasattr(alocacao, "solicitacao_voo") and not hasattr(alocacao, "registro_pos_voo"):
                        alocacao.delete()
        importacoes = list(
            voo.importacoes_log.filter(status="concluida").order_by("inicio_registro", "criado_em")
        )
        campos = ["distancia_m", "bateria_inicial", "bateria_final"]
        com_horario = [item for item in importacoes if item.inicio_registro and item.fim_registro]
        if com_horario:
            inicio_local = timezone.localtime(min(item.inicio_registro for item in com_horario))
            fim_local = timezone.localtime(max(item.fim_registro for item in com_horario))
            voo.data = inicio_local.date()
            voo.hora_inicio = inicio_local.time().replace(tzinfo=None)
            voo.hora_fim = fim_local.time().replace(tzinfo=None)
            campos.extend(["data", "hora_inicio", "hora_fim"])
        distancias = [item.distancia_calculada_m for item in importacoes if item.distancia_calculada_m is not None]
        voo.distancia_m = sum(distancias, Decimal("0")) if distancias else None
        com_bateria = [item for item in importacoes if item.bateria_inicial is not None or item.bateria_final is not None]
        voo.bateria_inicial = com_bateria[0].bateria_inicial if com_bateria else None
        voo.bateria_final = com_bateria[-1].bateria_final if com_bateria else None
        voo.save(update_fields=list(dict.fromkeys(campos)))
    return importacao


@transaction.atomic
def processar_importacao(importacao, atualizar_voo=False):
    arquivo = importacao.arquivo
    arquivo.open("rb")
    bruto = arquivo.read(20 * 1024 * 1024 + 1)
    arquivo.close()
    if len(bruto) > 20 * 1024 * 1024:
        raise ValueError("O arquivo excede o limite de 20 MB.")
    if _parece_log_dji(bruto, importacao.nome_original):
        return _concluir_importacao(importacao, _processar_dji(importacao, bruto), atualizar_voo)
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
    importacao.origem = "csv"
    importacao.colunas_reconhecidas = sorted(mapa.keys())
    return _concluir_importacao(importacao, pontos, atualizar_voo)
