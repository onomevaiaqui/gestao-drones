from datetime import time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import PlanejamentoVoo, Piloto
from .planejamento_service import calcular_geometria, consultar_previsao
from .planejamento_aeronautico_service import consultar_condicionantes_aeronauticas
from .planejamento_kml import extrair_poligono_kml
from .avaliacao_risco_service import classificar_matriz, dados_automaticos_avaliacao
from .planejamento_sisclaten import classificar_sisclaten


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
    def test_matriz_is_e94_003_classifica_celulas(self):
        self.assertEqual(classificar_matriz(5, "A"), "Extremo")
        self.assertEqual(classificar_matriz(3, "A"), "Alto")
        self.assertEqual(classificar_matriz(2, "B"), "Moderado")
        self.assertEqual(classificar_matriz(1, "B"), "Baixo")
        self.assertEqual(classificar_matriz(1, "E"), "Muito baixo")
    def setUp(self):
        self.user = User.objects.create_user("planejador", password="teste")
        self.piloto = Piloto.objects.create(user=self.user, nome="Planejador", primeiro_acesso=False)
        calculada = calcular_geometria(AREA)
        self.obj = PlanejamentoVoo.objects.create(
            titulo="Inspeção", piloto=self.piloto, data=timezone.localdate() + timedelta(days=1),
            hora_inicio=time(9), hora_fim=time(10), local="Parque Ambiental, Guarapuava/PR",
            area_geojson=calculada["geojson"],
            centro_latitude=calculada["centro_latitude"], centro_longitude=calculada["centro_longitude"],
            area_hectares=calculada["area_hectares"], criado_por=self.user,
        )

    def test_area_e_centro_sao_calculados(self):
        calculada = calcular_geometria(AREA)
        self.assertGreater(calculada["area_hectares"], 400)
        self.assertAlmostEqual(float(calculada["centro_latitude"]), -25.39, places=2)

    def test_sisclaten_nao_se_aplica_sem_aerolevantamento(self):
        self.assertEqual(classificar_sisclaten(self.obj)["status"], "nao_aplicavel")

    def test_sisclaten_classifica_dispensa_de_aafa_quando_todos_requisitos_atendidos(self):
        self.obj.gera_dados_aerolevantamento = True
        self.obj.tipo_aerolevantamento = "fotogrametrico"
        self.obj.dentro_condicionantes_ica = "sim"
        self.obj.interseca_area_sensivel_defesa = "nao"
        self.obj.projeto_contiguo_12_meses = "nao"
        resultado = classificar_sisclaten(self.obj)
        self.assertEqual(resultado["status"], "dispensa_aafa")
        self.assertLessEqual(resultado["raio_maximo_km"], 2.2)

    def test_sisclaten_exige_aafa_para_aerolevantamento_geofisico(self):
        self.obj.gera_dados_aerolevantamento = True
        self.obj.tipo_aerolevantamento = "geofisico"
        resultado = classificar_sisclaten(self.obj)
        self.assertEqual(resultado["status"], "aafa_necessaria")
        self.assertTrue(any("geofísico" in motivo for motivo in resultado["motivos"]))

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

    def test_reserva_iniciada_pelo_planejamento_vem_pre_preenchida(self):
        self.client.force_login(self.user)
        resposta = self.client.get(reverse("solicitacao_voo_nova"), {"planejamento": self.obj.pk})
        form = resposta.context["form"]
        self.assertEqual(form.initial["data"], self.obj.data)
        self.assertEqual(form.initial["data_fim"], self.obj.data)
        self.assertEqual(form.initial["hora_inicio"], self.obj.hora_inicio)
        self.assertEqual(form.initial["hora_fim"], self.obj.hora_fim)
        self.assertEqual(form.initial["local"], "Parque Ambiental, Guarapuava/PR")
        self.assertEqual(form.initial["finalidade"], self.obj.finalidade)
        self.assertContains(resposta, "Reservar drone")
        self.assertNotContains(resposta, f"{self.obj.data.isoformat()} - Inspeção")
        self.assertContains(resposta, f'value="{self.obj.data.isoformat()}"')
        self.assertContains(resposta, "Fotografia")

    @patch("core.planejamento_views.urlopen")
    def test_busca_local_retorna_pontos_de_interesse_e_cidades(self, urlopen):
        import json
        urlopen.return_value = _Resposta(json.dumps([
            {
                "lat": "-23.9608", "lon": "-46.3336", "name": "Porto de Santos",
                "display_name": "Porto de Santos, Santos, São Paulo, Brasil",
                "type": "harbour", "address": {"city": "Santos", "state": "São Paulo"},
                "namedetails": {"name": "Porto de Santos"},
            },
            {
                "lat": "-23.5505", "lon": "-46.6333", "name": "Santos",
                "display_name": "Santos, São Paulo, Brasil", "type": "city",
                "address": {"city": "Santos", "state": "São Paulo"},
            },
        ]))
        self.client.force_login(self.user)
        resposta = self.client.get(reverse("planejamento_buscar_local"), {"q": "Porto de Santos"})
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(len(dados["resultados"]), 2)
        self.assertEqual(dados["resultados"][0]["titulo"], "Porto de Santos")
        self.assertEqual(dados["resultados"][0]["contexto"], "Santos, São Paulo")
        requisicao = urlopen.call_args.args[0]
        self.assertIn("addressdetails=1", requisicao.full_url)
        self.assertIn("limit=7", requisicao.full_url)

    def test_importa_poligono_kml(self):
        conteudo = b'''<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>-51.47,-25.40,0 -51.45,-25.40,0 -51.45,-25.38,0 -51.47,-25.38,0</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></kml>'''
        geometria = extrair_poligono_kml(SimpleUploadedFile("area.kml", conteudo))
        self.assertEqual(geometria["type"], "Polygon")
        self.assertEqual(geometria["coordinates"][0][0], geometria["coordinates"][0][-1])

    def test_baixa_kml_do_planejamento(self):
        self.client.force_login(self.user)
        resposta = self.client.get(reverse("planejamento_baixar_kml", args=[self.obj.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"].split(";")[0], "application/vnd.google-earth.kml+xml")
        self.assertIn(b"<Polygon>", resposta.content)
        self.assertIn(b"Parque Ambiental", resposta.content)

    def test_avaliacao_automatica_indica_coordenacao_aeronautica(self):
        from types import SimpleNamespace
        self.obj.resumo_meteorologico = {
            "status":"atencao", "visibilidade_min_m":2500, "rajada_max_kmh":28,
            "horas":[{"hora":"09:00", "status":"atencao", "motivos":["Risco de neblina."]}],
            "aeronautica":{"status":"atencao", "itens":[{
                "tipo":"aerodromo", "id":"SBGU", "nome":"Guarapuava", "distancia_km":5.4,
            }]},
        }
        dados = dados_automaticos_avaliacao(SimpleNamespace(planejamento=self.obj))
        self.assertIn("SBGU", dados["perigos_identificados"])
        self.assertIn("coordenação", dados["medidas_mitigadoras"])
        self.assertIn("SARPAS", dados["medidas_mitigadoras"])

    @patch("core.planejamento_aeronautico_service.urlopen")
    def test_aerodromo_proximo_e_area_proibida_sao_detectados(self, urlopen):
        import json
        aeroporto = {"type":"Feature", "geometry":{"type":"Point", "coordinates":[-51.46,-25.39]},
                     "properties":{"localidade_id":"SBXX", "nome":"Teste"}}
        proibida = {"type":"Feature", "geometry":AREA,
                    "properties":{"id":"SBP999", "nome":"Área teste", "lowerlimit":0,
                                  "uom_llimit":"FT", "upperlimit":1000, "uom_ulimit":"FT"}}
        def resposta(req, timeout=0):
            features = [aeroporto] if "airport" in req.full_url else [proibida] if "eac_p" in req.full_url else []
            return _Resposta(json.dumps({"features":features}))
        urlopen.side_effect = resposta
        resultado = consultar_condicionantes_aeronauticas(self.obj)
        self.assertEqual(resultado["status"], "desfavoravel")
        self.assertEqual({i["tipo"] for i in resultado["itens"]}, {"aerodromo", "proibida"})
