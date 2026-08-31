import csv
import io
import logging
import math
import os
import re
import unicodedata
from datetime import datetime
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import PontoTelemetria


ALIASES = {
    "instante": ["timestamp", "datetime", "date_time", "data_hora", "time_stamp", "record_time", "flight_datetime", "utc_time"],
    "segundos": ["seconds", "second", "tempo_s", "time_s", "elapsed_time", "elapsed_seconds", "flight_time", "flighttime", "fly_time"],
    "latitude": ["latitude", "lat", "gps_latitude", "aircraft_latitude", "aircraftlatitude", "drone_latitude", "uav_latitude"],
    "longitude": ["longitude", "lon", "lng", "gps_longitude", "aircraft_longitude", "aircraftlongitude", "drone_longitude", "uav_longitude"],
    "altitude_m": ["altitude", "altitude_m", "height", "height_m", "altura", "altura_m", "relative_altitude", "altitude_above_takeoff", "aircraft_altitude"],
    "velocidade_ms": ["speed", "speed_ms", "velocity", "velocidade", "velocidade_ms", "horizontal_speed", "ground_speed", "flight_speed"],
    "bateria_percentual": ["battery", "battery_percent", "battery_percentage", "bateria", "bateria_percentual", "battery_level", "battery_remaining", "remaining_capacity"],
    "satelites": ["satellites", "satellite_count", "satelites", "gps_satellites", "gps_satellite_count", "gpssatellite_count", "gpssatellitecount", "satellite_number", "gps_count"],
    "sinal_percentual": ["signal", "signal_percent", "signal_strength", "sinal", "sinal_percentual", "rc_signal", "remote_controller_signal", "transmission_signal"],
    "alerta": ["warning", "warnings", "alert", "message", "alerta", "aviso", "warning_message", "flight_warning", "alarm"],
}

AUTEL_METADATA_ALIASES = {
    "modelo": ["aircraft_model", "drone_model", "product_model", "device_model"],
    "drone_serial": ["aircraft_sn", "aircraft_serial", "drone_sn", "drone_serial", "uav_sn"],
    "bateria_serial": ["battery_sn", "battery_serial", "battery_serial_number"],
    "bateria_ciclos": ["battery_cycle", "battery_cycles", "battery_cycle_count", "cycle_count"],
}


def _normalizar(valor):
    texto = unicodedata.normalize("NFKD", str(valor or "")).encode("ascii", "ignore").decode().lower().strip()
    texto = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(valor or "")).lower() if valor else texto
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", texto.replace("%", "percent")).strip("_")


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
    texto = str(valor).strip()
    numero = _decimal(texto)
    resultado = None
    if numero is not None and texto.replace(".", "", 1).isdigit() and float(numero) > 1000000000:
        timestamp = float(numero)
        if timestamp > 100000000000:
            timestamp /= 1000
        try:
            resultado = datetime.fromtimestamp(timestamp, tz=timezone.get_current_timezone())
        except (OverflowError, OSError, ValueError):
            resultado = None
    if resultado is None:
        resultado = parse_datetime(texto.replace("Z", "+00:00"))
    if resultado and timezone.is_naive(resultado):
        resultado = timezone.make_aware(resultado)
    return resultado


def _cabecalho_corresponde(normalizado, aliases):
    return normalizado in aliases or any(
        normalizado.endswith(f"_{alias}")
        or normalizado.startswith(f"{alias}_")
        or f"_{alias}_" in normalizado
        for alias in aliases
    )


def _mapear_cabecalhos(fieldnames, grupos):
    cabecalhos = {_normalizar(nome): nome for nome in fieldnames or []}
    mapa = {}
    for destino, aliases in grupos.items():
        for normalizado, original in cabecalhos.items():
            if _cabecalho_corresponde(normalizado, aliases):
                mapa[destino] = original
                break
    return mapa


def _parece_csv_autel(nome, texto, fieldnames):
    amostra = f"{nome}\n{texto[:4096]}".lower()
    normalizados = {_normalizar(item) for item in fieldnames or []}
    marcadores = ("autel", "evo_max", "evo max", "autel enterprise", "autel sky", "dragonfish")
    metadados = {alias for aliases in AUTEL_METADATA_ALIASES.values() for alias in aliases}
    return any(item in amostra for item in marcadores) or len(normalizados & metadados) >= 2


def _converter_unidade(valor, cabecalho, grandeza):
    numero = _decimal(valor)
    if numero is None:
        return None
    nome = _normalizar(cabecalho)
    if grandeza == "altitude" and ("feet" in nome or nome.endswith("_ft")):
        return numero * Decimal("0.3048")
    if grandeza == "velocidade":
        if "km_h" in nome or "kmh" in nome or "kph" in nome:
            return numero / Decimal("3.6")
        if "mph" in nome:
            return numero * Decimal("0.44704")
    return numero


def _primeiro_valor(linhas, coluna):
    if not coluna:
        return ""
    return next((str(linha.get(coluna) or "").strip() for linha in linhas if str(linha.get(coluna) or "").strip()), "")


def _localizar_cabecalho_csv(texto):
    """Ignora o pequeno bloco de metadados que alguns exports colocam antes da tabela."""
    linhas = texto.splitlines()
    aliases_lat = ALIASES["latitude"]
    aliases_lon = ALIASES["longitude"]
    for indice, linha in enumerate(linhas[:40]):
        partes = re.split(r"[,;\t|]", linha)
        normalizadas = [_normalizar(parte.strip(' "\'')) for parte in partes]
        tem_lat = any(_cabecalho_corresponde(item, aliases_lat) for item in normalizadas)
        tem_lon = any(_cabecalho_corresponde(item, aliases_lon) for item in normalizadas)
        if tem_lat and tem_lon:
            return "\n".join(linhas[indice:])
    return texto


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
    ciclos_detectados = [frame.battery.cycle_count for frame in frames if frame.battery.cycle_count is not None]
    importacao.bateria_ciclos_detectados = max(ciclos_detectados) if ciclos_detectados else None
    from dji_flightlog_parser.record.component_serial import ComponentSerial
    mapa_componentes = {
        "Gimbal": ("gimbal", "Gimbal DJI detectado"),
        "RightCamera": ("camera", "Câmera direita / payload DJI"),
        "LeftCamera": ("camera", "Câmera esquerda / payload DJI"),
        "RTK": ("sensor", "Módulo RTK DJI"),
        "UNKNOWN": ("acessorio", "Acessório DJI detectado"),
    }
    componentes, seriais_componentes = [], set()
    for registro in getattr(log, "_last_records", []) or []:
        if not isinstance(registro.data, ComponentSerial) or not registro.data.serial:
            continue
        origem = registro.data.component_type.name
        if origem not in mapa_componentes:
            continue
        serial = registro.data.serial.strip()[:100]
        if not serial or serial in seriais_componentes:
            continue
        tipo, nome = mapa_componentes[origem]
        componentes.append({"origem": origem, "serial": serial, "tipo": tipo, "nome": nome})
        seriais_componentes.add(serial)
    camera_serial = (detalhes.camera_sn or ultimo.recover.camera_sn or "").strip()[:100]
    if camera_serial and not any(item["tipo"] == "camera" for item in componentes):
        componentes.append({"origem": "Camera", "serial": camera_serial, "tipo": "camera", "nome": "Câmera / payload DJI"})
    importacao.componentes_detectados = componentes
    importacao.colunas_reconhecidas = [
        "tempo", "gps", "altitude", "velocidade", "bateria", "satelites", "sinal", "alertas"
    ]
    importacao._inicio_dji = detalhes.start_time
    importacao._duracao_dji = max(0, float(detalhes.total_time or 0))
    return pontos


def _destinar_importacao_ao_voo_da_data(importacao):
    """Separa operações de datas distintas sem dividir os trechos do mesmo dia."""
    voo_origem = importacao.voo
    if not importacao.inicio_registro:
        return voo_origem
    data_importada = timezone.localtime(importacao.inicio_registro).date()
    voo_destino = type(voo_origem).objects.filter(
        data=data_importada,
        piloto_id=voo_origem.piloto_id,
        drone_id=voo_origem.drone_id,
    ).order_by("pk").first()
    if voo_destino is None:
        possui_outros_logs = voo_origem.importacoes_log.filter(
            status="concluida"
        ).exclude(pk=importacao.pk).exists()
        pode_reutilizar = (
            not possui_outros_logs
            and voo_origem.alocacao_calendario_id is None
        )
        if pode_reutilizar:
            voo_destino = voo_origem
        else:
            voo_destino = type(voo_origem).objects.create(
                data=data_importada,
                piloto=voo_origem.piloto,
                drone=voo_origem.drone,
                finalidade=voo_origem.finalidade,
                local=voo_origem.local,
                observacoes=voo_origem.observacoes,
                criado_por=voo_origem.criado_por or importacao.importado_por,
            )
    if importacao.voo_id != voo_destino.pk:
        importacao.voo = voo_destino
        importacao.save(update_fields=["voo"])
    if voo_origem.pk != voo_destino.pk and not voo_origem.importacoes_log.exists():
        if not hasattr(voo_origem, "registro_pos_voo"):
            alocacao = voo_origem.alocacao_calendario
            voo_origem.delete()
            if alocacao and not hasattr(alocacao, "solicitacao_voo") and not hasattr(alocacao, "registro_pos_voo"):
                alocacao.delete()
    return voo_destino


def _recalcular_voo_pelos_logs(voo):
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
    return voo


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
    from .telemetria_bateria_service import sincronizar_ciclos_bateria
    sincronizar_ciclos_bateria(importacao)
    if atualizar_voo:
        voo = _destinar_importacao_ao_voo_da_data(importacao)
        _recalcular_voo_pelos_logs(voo)
        from .telemetria_bateria_service import sincronizar_registro_pos_voo
        sincronizar_registro_pos_voo(voo)
    return importacao


@transaction.atomic
def processar_importacao(importacao, atualizar_voo=False):
    extensao = os.path.splitext(importacao.nome_original or "")[1].lower()
    limite_bytes = (200 if extensao in (".bin", ".ulg") or not extensao else 20) * 1024 * 1024
    arquivo = importacao.arquivo
    arquivo.open("rb")
    bruto = arquivo.read(limite_bytes + 1)
    arquivo.close()
    if len(bruto) > limite_bytes:
        raise ValueError(f"O arquivo excede o limite de {limite_bytes // 1024 // 1024} MB.")
    if extensao == ".bin":
        from .pixhawk_service import processar_ardupilot
        return _concluir_importacao(importacao, processar_ardupilot(importacao, bruto), atualizar_voo)
    if extensao == ".ulg":
        from .pixhawk_service import processar_px4
        return _concluir_importacao(importacao, processar_px4(importacao, bruto), atualizar_voo)
    if extensao == ".json":
        from .sensefly_service import processar_sensefly_json
        return _concluir_importacao(importacao, processar_sensefly_json(importacao, bruto), atualizar_voo)
    from .autel_binary_service import parece_autel_fr, processar_autel_fr
    if parece_autel_fr(bruto):
        return _concluir_importacao(importacao, processar_autel_fr(importacao, bruto), atualizar_voo)
    if _parece_log_dji(bruto, importacao.nome_original):
        return _concluir_importacao(importacao, _processar_dji(importacao, bruto), atualizar_voo)
    try:
        texto = bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = bruto.decode("latin-1")
    tabela = _localizar_cabecalho_csv(texto)
    amostra = tabela[:8192]
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=",;\t|")
    except csv.Error:
        dialeto = csv.excel
    leitor = csv.DictReader(io.StringIO(tabela), dialect=dialeto)
    if not leitor.fieldnames:
        raise ValueError("O arquivo não possui cabeçalho.")
    mapa = _mapear_cabecalhos(leitor.fieldnames, ALIASES)
    if not mapa:
        raise ValueError("Nenhuma coluna de telemetria reconhecida.")
    linhas = list(leitor)
    if len(linhas) > 100000:
        raise ValueError("O arquivo excede o limite de 100.000 pontos.")
    pontos = []
    for indice, linha in enumerate(linhas, start=1):
        if indice > 100000:
            raise ValueError("O arquivo excede o limite de 100.000 pontos.")
        pontos.append(PontoTelemetria(
            importacao=importacao, indice=indice,
            instante=_instante(linha.get(mapa.get("instante", ""))),
            segundos=_decimal(linha.get(mapa.get("segundos", ""))),
            latitude=_decimal(linha.get(mapa.get("latitude", ""))),
            longitude=_decimal(linha.get(mapa.get("longitude", ""))),
            altitude_m=_converter_unidade(linha.get(mapa.get("altitude_m", "")), mapa.get("altitude_m", ""), "altitude"),
            velocidade_ms=_converter_unidade(linha.get(mapa.get("velocidade_ms", "")), mapa.get("velocidade_ms", ""), "velocidade"),
            bateria_percentual=_inteiro_percentual(linha.get(mapa.get("bateria_percentual", ""))),
            satelites=max(0, int(_decimal(linha.get(mapa.get("satelites", ""))) or 0)) if mapa.get("satelites") else None,
            sinal_percentual=_inteiro_percentual(linha.get(mapa.get("sinal_percentual", ""))),
            alerta=str(linha.get(mapa.get("alerta", "")) or "").strip()[:255],
        ))
    if not pontos:
        raise ValueError("O arquivo não possui linhas de dados.")
    autel = _parece_csv_autel(importacao.nome_original, texto, leitor.fieldnames)
    importacao.origem = "autel_csv" if autel else "csv"
    importacao.formato = "autel-csv" if autel else "csv"
    if autel:
        metadados = _mapear_cabecalhos(leitor.fieldnames, AUTEL_METADATA_ALIASES)
        importacao.drone_modelo_detectado = _primeiro_valor(linhas, metadados.get("modelo"))[:120]
        importacao.drone_serial_detectado = _primeiro_valor(linhas, metadados.get("drone_serial"))[:100]
        importacao.bateria_serial_detectada = _primeiro_valor(linhas, metadados.get("bateria_serial"))[:100]
        ciclos = _decimal(_primeiro_valor(linhas, metadados.get("bateria_ciclos")))
        importacao.bateria_ciclos_detectados = max(0, int(ciclos)) if ciclos is not None else None
    importacao.colunas_reconhecidas = sorted(mapa.keys())
    return _concluir_importacao(importacao, pontos, atualizar_voo)
