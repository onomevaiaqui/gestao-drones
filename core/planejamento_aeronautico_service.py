import json
import math
from urllib.parse import urlencode
from urllib.request import Request, urlopen


WFS_URL = "https://geoaisweb.decea.mil.br/geoserver/ows"
CAMADAS = {
    "aerodromo": "ICA:airport",
    "heliponto": "ICA:heliport",
    "perigosa": "ICA:eac_d",
    "proibida": "ICA:eac_p",
    "restrita": "ICA:eac_r",
}


def _pontos_area(planejamento):
    return [(float(lat), float(lon)) for lon, lat in planejamento.area_geojson["coordinates"][0]]


def _distancia_area(lat, lon, pontos):
    centro_lat = sum(p[0] for p in pontos) / len(pontos)
    sx = 111320 * math.cos(math.radians(centro_lat)); sy = 110540
    px, py = lon * sx, lat * sy
    menor = float("inf")
    for (lat1, lon1), (lat2, lon2) in zip(pontos, pontos[1:]):
        x1, y1, x2, y2 = lon1 * sx, lat1 * sy, lon2 * sx, lat2 * sy
        dx, dy = x2 - x1, y2 - y1
        t = max(0, min(1, ((px-x1)*dx + (py-y1)*dy) / (dx*dx + dy*dy or 1)))
        menor = min(menor, math.hypot(px-(x1+t*dx), py-(y1+t*dy)))
    return 0 if _dentro(lon, lat, [(p[1], p[0]) for p in pontos]) else menor


def _dentro(x, y, poligono):
    dentro = False
    j = len(poligono) - 1
    for i, (xi, yi) in enumerate(poligono):
        xj, yj = poligono[j]
        if (yi > y) != (yj > y) and x < (xj-xi) * (y-yi) / (yj-yi or 1e-12) + xi:
            dentro = not dentro
        j = i
    return dentro


def _orientacao(a, b, c):
    valor = (b[1]-a[1])*(c[0]-b[0]) - (b[0]-a[0])*(c[1]-b[1])
    return 0 if abs(valor) < 1e-12 else 1 if valor > 0 else 2


def _cruza(a, b, c, d):
    return _orientacao(a,b,c) != _orientacao(a,b,d) and _orientacao(c,d,a) != _orientacao(c,d,b)


def _aneis(geometry):
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"][0]]
    if geometry["type"] == "MultiPolygon":
        return [poligono[0] for poligono in geometry["coordinates"]]
    return []


def _intersecta(area, geometry):
    area_lonlat = [(lon, lat) for lat, lon in area]
    for anel in _aneis(geometry):
        if any(_dentro(x, y, anel) for x, y in area_lonlat) or any(_dentro(x, y, area_lonlat) for x, y in anel):
            return True
        if any(_cruza(a, b, c, d) for a, b in zip(area_lonlat, area_lonlat[1:]) for c, d in zip(anel, anel[1:])):
            return True
    return False


def _consultar_camada(nome, bbox):
    params = {"service":"WFS", "version":"2.0.0", "request":"GetFeature",
              "typeNames":nome, "outputFormat":"application/json", "srsName":"EPSG:4326",
              "bbox":f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:4326"}
    req = Request(WFS_URL + "?" + urlencode(params), headers={"User-Agent":"GestaoDrones/1.0"})
    with urlopen(req, timeout=25) as resposta:
        return json.loads(resposta.read().decode("utf-8")).get("features", [])


def consultar_condicionantes_aeronauticas(planejamento):
    area = _pontos_area(planejamento)
    lats, lons = [p[0] for p in area], [p[1] for p in area]
    margem = 0.10  # consulta de apoio; somente interseções aplicáveis entram no resultado final
    bbox = (min(lons)-margem, min(lats)-margem, max(lons)+margem, max(lats)+margem)
    itens, geojson = [], []
    for tipo, camada in CAMADAS.items():
        for feature in _consultar_camada(camada, bbox):
            prop, geom = feature.get("properties", {}), feature.get("geometry") or {}
            if tipo in ("aerodromo", "heliponto"):
                coords = geom.get("coordinates", [])
                if geom.get("type") == "MultiPoint": coords = coords[0]
                if len(coords) < 2: continue
                lon, lat = float(coords[0]), float(coords[1])
                distancia_km = _distancia_area(lat, lon, area) / 1000
                raio_frz_m = 9260 if tipo == "aerodromo" else 2000
                if distancia_km * 1000 > raio_frz_m:
                    continue
                nivel = "desfavoravel"
                item = {"tipo":tipo, "id":prop.get("localidade_id") or prop.get("ciad") or prop.get("nome") or tipo,
                        "nome":prop.get("nome") or "Sem nome", "distancia_km":round(distancia_km,2),
                        "nivel":nivel, "cidade":prop.get("cidade"), "operacao":prop.get("opr"),
                        "raio_atencao_m":raio_frz_m, "zona":"FRZ", "necessita_termo":True}
            else:
                if not _intersecta(area, geom): continue
                nivel = "desfavoravel" if tipo == "proibida" else "atencao"
                item = {"tipo":tipo, "id":prop.get("id") or prop.get("nome") or tipo, "nome":prop.get("nome") or "Sem nome",
                        "nivel":nivel, "limite_inferior":prop.get("lowerlimit"), "unidade_inferior":prop.get("uom_llimit"),
                        "limite_superior":prop.get("upperlimit"), "unidade_superior":prop.get("uom_ulimit"),
                        "zona":"EAC", "necessita_termo":tipo != "proibida"}
            itens.append(item)
            geojson.append({"type":"Feature", "geometry":geom, "properties":item})
    ordem = {"desfavoravel":2, "atencao":1, "informativo":0}
    nivel = max((ordem[i["nivel"]] for i in itens), default=0)
    return {
        "status": ["favoravel", "atencao", "desfavoravel"][nivel], "itens": itens,
        "geojson": {"type":"FeatureCollection", "features":geojson},
        "fonte":"AISWEB/DECEA – geosserviço oficial", "consultado":True,
        "aviso":"São exibidas somente interseções do planejamento com EAC ou zonas de triagem FRZ. Confirme a verificação oficial de interseções no SARPAS, além das publicações e NOTAM.",
        "referencia":"ICA 100-40/2026 e dados aeronáuticos AISWEB/DECEA",
    }


def camadas_aeronauticas_bbox(bbox):
    features = []
    for tipo, camada in CAMADAS.items():
        for feature in _consultar_camada(camada, bbox):
            prop = feature.setdefault("properties", {})
            prop["tipo_zona"] = tipo
            if tipo == "aerodromo": prop["raio_atencao_m"] = 9260
            elif tipo == "heliponto": prop["raio_atencao_m"] = 2000
            features.append(feature)
    return {"type":"FeatureCollection", "features":features,
            "aviso":"Raios de atenção para triagem visual; não representam proibição automática."}
