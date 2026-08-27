"""Utilitários geográficos independentes de provedores externos."""

import math


def distancia_m(lat1, lon1, lat2, lon2):
    raio = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * raio * math.asin(math.sqrt(a))


def distancia_km(lat1, lon1, lat2, lon2):
    return distancia_m(lat1, lon1, lat2, lon2) / 1000
