import json
import math
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.utils import timezone

from .geo_utils import distancia_m


VARIAVEIS = [
    "temperature_2m", "relative_humidity_2m", "dew_point_2m",
    "precipitation_probability", "precipitation", "weather_code",
    "cloud_cover_low", "visibility", "wind_speed_10m", "wind_speed_80m",
    "wind_speed_120m", "wind_direction_10m", "wind_gusts_10m", "cape",
    "boundary_layer_height",
]


def calcular_geometria(geojson):
    geometria = geojson.get("geometry", geojson) if isinstance(geojson, dict) else None
    if not geometria or geometria.get("type") not in ("Polygon", "Rectangle"):
        raise ValueError("Desenhe uma área fechada no mapa.")
    coordenadas = geometria.get("coordinates", [[]])[0]
    if len(coordenadas) < 4:
        raise ValueError("A área desenhada não possui pontos suficientes.")
    pontos = [(float(item[1]), float(item[0])) for item in coordenadas]
    lat_centro = sum(p[0] for p in pontos[:-1]) / max(1, len(pontos) - 1)
    lon_centro = sum(p[1] for p in pontos[:-1]) / max(1, len(pontos) - 1)
    escala_x = 111320 * math.cos(math.radians(lat_centro))
    escala_y = 110540
    xy = [((lon - lon_centro) * escala_x, (lat - lat_centro) * escala_y) for lat, lon in pontos]
    area = abs(sum(xy[i][0] * xy[i + 1][1] - xy[i + 1][0] * xy[i][1] for i in range(len(xy) - 1))) / 2
    return {
        "geojson": {"type": "Polygon", "coordinates": [[[lon, lat] for lat, lon in pontos]]},
        "centro_latitude": Decimal(str(round(lat_centro, 7))),
        "centro_longitude": Decimal(str(round(lon_centro, 7))),
        "area_hectares": Decimal(str(round(area / 10000, 2))),
        "pontos": pontos,
    }


def _pontos_amostragem(planejamento):
    calculada = calcular_geometria(planejamento.area_geojson)
    centro = (float(planejamento.centro_latitude), float(planejamento.centro_longitude))
    vertices = calculada["pontos"][:-1]
    if len(vertices) > 4:
        passo = max(1, len(vertices) // 4)
        vertices = vertices[::passo][:4]
    return [centro] + vertices


def _valor(hora, nome, indice):
    valores = hora.get(nome) or []
    return valores[indice] if indice < len(valores) else None


def _maximo(valores):
    validos = [v for v in valores if v is not None]
    return max(validos) if validos else None


def _minimo(valores):
    validos = [v for v in valores if v is not None]
    return min(validos) if validos else None


def consultar_previsao(planejamento):
    hoje = timezone.localdate()
    if planejamento.data < hoje or planejamento.data_final < planejamento.data or (planejamento.data_final - hoje).days > 15:
        raise ValueError("A previsão está disponível entre hoje e os próximos 15 dias.")
    pontos = _pontos_amostragem(planejamento)
    parametros = {
        "latitude": ",".join(str(p[0]) for p in pontos),
        "longitude": ",".join(str(p[1]) for p in pontos),
        "hourly": ",".join(VARIAVEIS),
        "timezone": "America/Sao_Paulo",
        "start_date": planejamento.data.isoformat(),
        "end_date": planejamento.data_final.isoformat(),
        "wind_speed_unit": "kmh",
    }
    requisicao = Request(
        "https://api.open-meteo.com/v1/forecast?" + urlencode(parametros),
        headers={"User-Agent": "GestaoDrones/1.0"},
    )
    with urlopen(requisicao, timeout=20) as resposta:
        bruto = json.loads(resposta.read().decode("utf-8"))
    locais = bruto if isinstance(bruto, list) else [bruto]
    if not locais or "hourly" not in locais[0]:
        raise ValueError("A previsão meteorológica não retornou dados para a área.")

    inicio = datetime.combine(planejamento.data, planejamento.hora_inicio)
    fim = datetime.combine(planejamento.data_final, planejamento.hora_fim)
    horas = []
    niveis_neblina_globais = [0] * len(pontos)
    for indice, texto in enumerate(locais[0]["hourly"]["time"]):
        instante = datetime.fromisoformat(texto)
        if inicio <= instante <= fim:
            por_local = []
            for local in locais:
                dados = local["hourly"]
                temperatura = _valor(dados, "temperature_2m", indice)
                orvalho = _valor(dados, "dew_point_2m", indice)
                por_local.append({nome: _valor(dados, nome, indice) for nome in VARIAVEIS} | {
                    "amplitude_orvalho": round(temperatura - orvalho, 1) if temperatura is not None and orvalho is not None else None
                })
            visibilidade = _minimo([p["visibility"] for p in por_local])
            umidade = _maximo([p["relative_humidity_2m"] for p in por_local])
            amplitude = _minimo([p["amplitude_orvalho"] for p in por_local])
            codigo = int(_maximo([p["weather_code"] for p in por_local]) or 0)
            rajada = _maximo([p["wind_gusts_10m"] for p in por_local])
            chuva = _maximo([p["precipitation"] for p in por_local])
            cape = _maximo([p["cape"] for p in por_local])
            niveis_neblina = []
            for ponto in por_local:
                forte = ponto["weather_code"] in (45, 48) or (ponto["visibility"] is not None and ponto["visibility"] < 1000)
                possivel = forte or (ponto["visibility"] is not None and ponto["visibility"] < 3000) or (
                    ponto["relative_humidity_2m"] is not None and ponto["relative_humidity_2m"] >= 95
                    and ponto["amplitude_orvalho"] is not None and ponto["amplitude_orvalho"] <= 2
                )
                niveis_neblina.append(2 if forte else 1 if possivel else 0)
            niveis_neblina_globais = [
                max(anterior, atual)
                for anterior, atual in zip(niveis_neblina_globais, niveis_neblina)
            ]
            afetados = sum(nivel > 0 for nivel in niveis_neblina)
            motivos = []
            nivel = 0
            if max(niveis_neblina) == 2:
                nivel = 2; motivos.append(f"Neblina ou visibilidade crítica: {int(visibilidade or 0)} m.")
            elif max(niveis_neblina) == 1:
                nivel = max(nivel, 1); motivos.append(f"Risco de neblina: visibilidade mínima {int(visibilidade or 0)} m, umidade {int(umidade or 0)}%.")
            if codigo >= 95:
                nivel = 2; motivos.append("Previsão de tempestade na área.")
            elif cape is not None and cape >= 500:
                nivel = max(nivel, 1); motivos.append(f"Atmosfera instável (CAPE {int(cape)} J/kg).")
            if rajada is not None and rajada >= 40:
                nivel = 2; motivos.append(f"Rajadas críticas de até {round(rajada, 1)} km/h.")
            elif rajada is not None and rajada >= 25:
                nivel = max(nivel, 1); motivos.append(f"Rajadas exigem atenção: {round(rajada, 1)} km/h.")
            if chuva is not None and chuva >= 5:
                nivel = 2; motivos.append(f"Chuva intensa: {round(chuva, 1)} mm/h.")
            elif chuva is not None and chuva >= 1:
                nivel = max(nivel, 1); motivos.append(f"Previsão de chuva: {round(chuva, 1)} mm/h.")
            horas.append({
                "hora": instante.strftime("%d/%m %H:%M") if planejamento.data_final != planejamento.data else instante.strftime("%H:%M"), "nivel": nivel,
                "status": ["favoravel", "atencao", "desfavoravel"][nivel],
                "motivos": motivos or ["Condições previstas dentro dos limites de referência."],
                "visibilidade_m": visibilidade, "umidade": umidade, "amplitude_orvalho": amplitude,
                "vento_10m": _maximo([p["wind_speed_10m"] for p in por_local]),
                "vento_80m": _maximo([p["wind_speed_80m"] for p in por_local]),
                "vento_120m": _maximo([p["wind_speed_120m"] for p in por_local]),
                "rajada": rajada, "chuva": chuva, "prob_chuva": _maximo([p["precipitation_probability"] for p in por_local]),
                "cape": cape, "nuvens_baixas": _maximo([p["cloud_cover_low"] for p in por_local]),
                "camada_limite_m": _maximo([p["boundary_layer_height"] for p in por_local]),
                "neblina_area_percentual": round(afetados / len(por_local) * 100),
            })
    if not horas:
        raise ValueError("Não há horários de previsão correspondentes ao período planejado.")
    nivel_geral = max(item["nivel"] for item in horas)
    pontos_neblina = [p for p, nivel in zip(pontos, niveis_neblina_globais) if nivel > 0]
    centro = pontos[0]
    raio_neblina = max((distancia_m(*centro, *p) for p in pontos_neblina), default=0) / 1000
    percentual_afetado = _maximo([item["neblina_area_percentual"] for item in horas]) or 0
    raio_equivalente = math.sqrt(
        float(planejamento.area_hectares or 0) * 10000 * percentual_afetado / 100 / math.pi
    ) / 1000
    raio_neblina = max(raio_neblina, raio_equivalente)
    return {
        "status": ["favoravel", "atencao", "desfavoravel"][nivel_geral],
        "horas": horas,
        "pontos_consultados": len(pontos),
        "raio_neblina_estimado_km": round(raio_neblina, 2),
        "pontos_neblina": [
            {"latitude": p[0], "longitude": p[1], "nivel": nivel}
            for p, nivel in zip(pontos, niveis_neblina_globais) if nivel > 0
        ],
        "visibilidade_min_m": _minimo([item["visibilidade_m"] for item in horas]),
        "neblina_area_max_percentual": percentual_afetado,
        "camada_limite_max_m": _maximo([item["camada_limite_m"] for item in horas]),
        "rajada_max_kmh": _maximo([item["rajada"] for item in horas]),
        "chuva_max_mm": _maximo([item["chuva"] for item in horas]),
        "fonte": "Open-Meteo",
        "aviso": "Neblina, extensão e camada vertical são estimativas de modelo, não medições locais.",
    }
