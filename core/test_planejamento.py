from datetime import time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import PlanejamentoVoo, Piloto
from .planejamento_service import calcular_geometria, consultar_previsao


AREA = {"type": "Polygon", "coordinates": [[
    [-51.47, -25.40], [-51.45, -25.40], [-51.45, -25.38],
    [-51.47, -25.38], [-51.47, -25.40],
]]}


class _Resposta:
    def __init__(self, conteudo): self.conteudo = conteudo
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return self.conteudo.encode()


class PlanejamentoVooTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("planejador", password="teste")
        self.piloto = Piloto.objects.create(user=self.user, nome="Planejador", primeiro_acesso=False)
        calculada = calcular_geometria(AREA)
        self.obj = PlanejamentoVoo.objects.create(
            titulo="Inspeção", piloto=self.piloto, data=timezone.localdate() + timedelta(days=1),
            hora_inicio=time(9), hora_fim=time(10), area_geojson=calculada["geojson"],
            centro_latitude=calculada["centro_latitude"], centro_longitude=calculada["centro_longitude"],
            area_hectares=calculada["area_hectares"], criado_por=self.user,
        )

    def test_area_e_centro_sao_calculados(self):
        calculada = calcular_geometria(AREA)
        self.assertGreater(calculada["area_hectares"], 400)
        self.assertAlmostEqual(float(calculada["centro_latitude"]), -25.39, places=2)

    def test_usuario_so_visualiza_o_proprio_planejamento(self):
        outro = User.objects.create_user("outro")
        piloto_outro = Piloto.objects.create(user=outro, nome="Outro")
        PlanejamentoVoo.objects.create(
            titulo="Oculto", piloto=piloto_outro, data=self.obj.data, hora_inicio=time(8), hora_fim=time(9),
            area_geojson=AREA, centro_latitude=-25.39, centro_longitude=-51.46, criado_por=outro,
        )
        self.client.force_login(self.user)
        resposta = self.client.get(reverse("planejamentos"))
        self.assertContains(resposta, "Inspeção")
        self.assertNotContains(resposta, "Oculto")

    @patch("core.planejamento_service.urlopen")
    def test_neblina_gera_condicao_desfavoravel_e_estimativa(self, urlopen):
        import json
        hora = {
            "time": [f"{self.obj.data.isoformat()}T09:00", f"{self.obj.data.isoformat()}T10:00"],
        }
        for nome in (
            "temperature_2m", "relative_humidity_2m", "dew_point_2m", "precipitation_probability",
            "precipitation", "weather_code", "cloud_cover_low", "visibility", "wind_speed_10m",
            "wind_speed_80m", "wind_speed_120m", "wind_direction_10m", "wind_gusts_10m", "cape",
            "boundary_layer_height",
        ):
            hora[nome] = [0, 0]
        hora.update(relative_humidity_2m=[99, 99], dew_point_2m=[9, 9], temperature_2m=[10, 10],
                    weather_code=[45, 45], visibility=[500, 600], boundary_layer_height=[120, 140])
        urlopen.return_value = _Resposta(json.dumps([{"hourly": hora}] * 5))
        resultado = consultar_previsao(self.obj)
        self.assertEqual(resultado["status"], "desfavoravel")
        self.assertEqual(resultado["neblina_area_max_percentual"], 100)
        self.assertGreater(resultado["raio_neblina_estimado_km"], 0)
        self.assertTrue(resultado["pontos_neblina"])
