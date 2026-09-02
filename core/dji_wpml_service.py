"""Geração determinística e entrega assinada de pacotes WPML."""

from hashlib import md5
from datetime import datetime
from io import BytesIO
from decimal import Decimal
from urllib.parse import urljoin
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo
from xml.etree import ElementTree as ET

from django.conf import settings
from django.core import signing
from django.urls import reverse
from django.utils import timezone


KML = "http://www.opengis.net/kml/2.2"
WPML = "http://www.dji.com/wpmz/1.0.2"
ET.register_namespace("", KML)
ET.register_namespace("wpml", WPML)


def _tag(ns, nome):
    return f"{{{ns}}}{nome}"


def _texto(pai, ns, nome, valor):
    elemento = ET.SubElement(pai, _tag(ns, nome))
    elemento.text = str(valor)
    return elemento


def _numero(valor):
    decimal = Decimal(str(valor))
    texto = format(decimal.normalize(), "f")
    return "0" if texto in ("-0", "") else texto


def _coordenadas(missao):
    geometria = missao.planejamento.area_geojson or {}
    if geometria.get("type") == "Polygon":
        anel = (geometria.get("coordinates") or [[]])[0]
    elif geometria.get("type") == "MultiPolygon":
        anel = (geometria.get("coordinates") or [[[]]])[0][0]
    else:
        raise ValueError("A missão não possui polígono compatível com WPML.")
    pontos = [(float(item[0]), float(item[1])) for item in anel if isinstance(item, (list, tuple)) and len(item) >= 2]
    if len(pontos) > 1 and pontos[0] == pontos[-1]:
        pontos.pop()
    if len(pontos) < 3:
        raise ValueError("A rota precisa de pelo menos três pontos distintos.")
    return pontos


def _mission_config(documento, missao):
    config = ET.SubElement(documento, _tag(WPML, "missionConfig"))
    _texto(config, WPML, "flyToWaylineMode", "safely")
    _texto(config, WPML, "finishAction", "goHome")
    _texto(config, WPML, "exitOnRCLost", "executeLostAction")
    _texto(config, WPML, "executeRCLostAction", "goBack")
    _texto(config, WPML, "globalTransitionalSpeed", _numero(missao.velocidade_ms))
    drone = ET.SubElement(config, _tag(WPML, "droneInfo"))
    _texto(drone, WPML, "droneEnumValue", missao.dock.aeronave_tipo_dji)
    if missao.dock.aeronave_subtipo_dji is not None:
        _texto(drone, WPML, "droneSubEnumValue", missao.dock.aeronave_subtipo_dji)
    payload = ET.SubElement(config, _tag(WPML, "payloadInfo"))
    _texto(payload, WPML, "payloadEnumValue", missao.dock.payload_tipo_dji)
    if missao.dock.payload_subtipo_dji is not None:
        _texto(payload, WPML, "payloadSubEnumValue", missao.dock.payload_subtipo_dji)
    _texto(payload, WPML, "payloadPositionIndex", missao.dock.payload_posicao_dji or 0)


def _placemark(pasta, indice, lon, lat, altura, executavel=False):
    marca = ET.SubElement(pasta, _tag(KML, "Placemark"))
    ponto = ET.SubElement(marca, _tag(KML, "Point"))
    _texto(ponto, KML, "coordinates", f"{lon:.7f},{lat:.7f}")
    _texto(marca, WPML, "index", indice)
    if executavel:
        _texto(marca, WPML, "executeHeight", altura)
        _texto(marca, WPML, "waypointSpeed", "5")
    else:
        _texto(marca, WPML, "ellipsoidHeight", altura)
        _texto(marca, WPML, "height", altura)
        _texto(marca, WPML, "useGlobalHeight", 1)
        _texto(marca, WPML, "useGlobalSpeed", 1)
        _texto(marca, WPML, "useGlobalHeadingParam", 1)
        _texto(marca, WPML, "useGlobalTurnParam", 1)
    return marca


def _arquivo_template(missao, pontos):
    raiz = ET.Element(_tag(KML, "kml"))
    documento = ET.SubElement(raiz, _tag(KML, "Document"))
    _texto(documento, WPML, "author", "SISMOD")
    _mission_config(documento, missao)
    pasta = ET.SubElement(documento, _tag(KML, "Folder"))
    _texto(pasta, WPML, "templateType", "waypoint")
    _texto(pasta, WPML, "templateId", 0)
    sistema = ET.SubElement(pasta, _tag(WPML, "waylineCoordinateSysParam"))
    _texto(sistema, WPML, "coordinateMode", "WGS84")
    _texto(sistema, WPML, "heightMode", "relativeToStartPoint")
    _texto(pasta, WPML, "autoFlightSpeed", _numero(missao.velocidade_ms))
    _texto(pasta, WPML, "globalHeight", missao.altura_m)
    _texto(pasta, WPML, "globalWaypointTurnMode", "toPointAndStopWithDiscontinuityCurvature")
    _texto(pasta, WPML, "globalUseStraightLine", 1)
    for indice, (lon, lat) in enumerate(pontos):
        _placemark(pasta, indice, lon, lat, missao.altura_m)
    return ET.tostring(raiz, encoding="utf-8", xml_declaration=True)


def _arquivo_waylines(missao, pontos):
    raiz = ET.Element(_tag(KML, "kml"))
    documento = ET.SubElement(raiz, _tag(KML, "Document"))
    _mission_config(documento, missao)
    pasta = ET.SubElement(documento, _tag(KML, "Folder"))
    _texto(pasta, WPML, "templateId", 0)
    _texto(pasta, WPML, "waylineId", 0)
    _texto(pasta, WPML, "executeHeightMode", "relativeToStartPoint")
    _texto(pasta, WPML, "autoFlightSpeed", _numero(missao.velocidade_ms))
    for indice, (lon, lat) in enumerate(pontos):
        _placemark(pasta, indice, lon, lat, missao.altura_m, executavel=True)
    return ET.tostring(raiz, encoding="utf-8", xml_declaration=True)


def gerar_kmz_wpml(missao):
    if missao.dock.aeronave_tipo_dji is None or missao.dock.payload_tipo_dji is None:
        raise ValueError("A Dock ainda não informou os códigos DJI da aeronave e do payload.")
    if any(item.get("nivel") == "erro" for item in missao.validacoes or []):
        raise ValueError("A missão possui erros estruturais e não pode gerar o pacote.")
    pontos = _coordenadas(missao)
    saida = BytesIO()
    with ZipFile(saida, "w", ZIP_DEFLATED) as pacote:
        # Data fixa torna o KMZ reproduzível; a impressão digital informada à DJI
        # precisa continuar igual quando o equipamento fizer o download.
        for nome, conteudo in (
            ("wpmz/template.kml", _arquivo_template(missao, pontos)),
            ("wpmz/waylines.wpml", _arquivo_waylines(missao, pontos)),
        ):
            item = ZipInfo(nome, date_time=(2020, 1, 1, 0, 0, 0))
            item.compress_type = ZIP_DEFLATED
            pacote.writestr(item, conteudo)
    return saida.getvalue()


def token_download_wpml(missao):
    return signing.TimestampSigner(salt="sismod.dji.wpml").sign(str(missao.identificador))


def validar_token_download_wpml(token, identificador):
    try:
        valor = signing.TimestampSigner(salt="sismod.dji.wpml").unsign(
            token, max_age=settings.DJI_DOCK_WPML_URL_TTL_SECONDS,
        )
    except signing.BadSignature:
        return False
    return valor == str(identificador)


def descritor_publico_wpml(missao):
    """Monta URL e fingerprint; não publica nem muda o estado da missão."""
    base = settings.DJI_CLOUD_PUBLIC_URL
    if not base.lower().startswith("https://"):
        raise ValueError("Defina DJI_CLOUD_PUBLIC_URL com um endereço HTTPS público antes do envio à Dock.")
    conteudo = gerar_kmz_wpml(missao)
    caminho = reverse(
        "dji_dock_missao_wpml_publico",
        kwargs={"identificador": missao.identificador, "token": token_download_wpml(missao)},
    )
    return {
        "flight_id": str(missao.identificador),
        # A especificação DJI define este campo como MD5 do conteúdo. Ele não é
        # usado para autenticação; a autorização é feita pela URL assinada.
        "file": {"url": urljoin(f"{base}/", caminho.lstrip("/")), "fingerprint": md5(conteudo, usedforsecurity=False).hexdigest()},
    }


def dados_flighttask_prepare(missao):
    """Monta dados oficiais de preparação, sem publicá-los no MQTT."""
    if not missao.parametros_confirmados:
        raise ValueError("Confirme os parâmetros operacionais antes de preparar o envio.")
    if not 20 <= missao.altura_retorno_m <= 1500:
        raise ValueError("A altura de retorno deve estar entre 20 e 1500 metros.")
    if not 10 <= missao.bateria_minima_percent <= 100:
        raise ValueError("A bateria mínima deve estar entre 10% e 100%.")
    planejamento = missao.planejamento
    inicio = timezone.make_aware(datetime.combine(planejamento.data, planejamento.hora_inicio))
    fim = timezone.make_aware(datetime.combine(planejamento.data_final, planejamento.hora_fim))
    descritor = descritor_publico_wpml(missao)
    return {
        **descritor,
        "task_type": 2,
        "execute_time": int(inicio.timestamp() * 1000),
        "ready_conditions": {
            "battery_capacity": missao.bateria_minima_percent,
            "begin_time": int(inicio.timestamp() * 1000),
            "end_time": int(fim.timestamp() * 1000),
        },
        "executable_conditions": {"storage_capacity": missao.armazenamento_minimo_mb},
        "rth_altitude": missao.altura_retorno_m,
        "rth_mode": 1,
        "out_of_control_action": 0,
        "exit_wayline_when_rc_lost": 1 if missao.interromper_na_perda_sinal else 0,
        "flight_safety_advance_check": 1,
        "wayline_precision_type": 0,
    }
