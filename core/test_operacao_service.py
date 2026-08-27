from datetime import date, time

from django.contrib.auth.models import User
from django.test import TestCase

from .geo_utils import distancia_km, distancia_m
from .models import Alocacao, Bateria, Drone, ImportacaoLog, Piloto, RegistroPosVoo, Voo
from .operacao_service import (
    erro_intervalo,
    existe_conflito_alocacao,
    normalizar_finalidade,
)
from .reserva_service import atualizar_reservas_vencidas, reserva_em_andamento
from .telemetria_bateria_service import (
    resumo_pos_voo_telemetria,
    sincronizar_registro_pos_voo,
)


class OperacaoServiceTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("operador")
        self.piloto = Piloto.objects.create(nome="Operador", user=self.usuario)
        self.drone = Drone.objects.create(nome="Drone 1", modelo="Teste")

    def test_normaliza_codigo_ou_rotulo_de_finalidade(self):
        self.assertEqual(normalizar_finalidade("fotografia"), "fotografia")
        self.assertEqual(normalizar_finalidade("Inspeção técnica"), "inspecao")
        self.assertEqual(normalizar_finalidade("atividade não cadastrada"), "outro")

    def test_valida_periodo_em_mais_de_um_dia(self):
        self.assertIsNone(
            erro_intervalo(date(2026, 8, 27), time(22), date(2026, 8, 28), time(2))
        )
        self.assertIsNotNone(
            erro_intervalo(date(2026, 8, 28), time(8), date(2026, 8, 27), time(9))
        )

    def test_detecta_sobreposicao_e_aceita_periodos_adjacentes(self):
        Alocacao.objects.create(
            data=date(2026, 8, 27),
            data_fim=date(2026, 8, 27),
            hora_inicio=time(8),
            hora_fim=time(10),
            piloto=self.piloto,
            drone=self.drone,
            finalidade="inspecao",
            criado_por=self.usuario,
        )
        self.assertTrue(
            existe_conflito_alocacao(
                self.drone, date(2026, 8, 27), time(9), date(2026, 8, 27), time(11)
            )
        )
        self.assertFalse(
            existe_conflito_alocacao(
                self.drone, date(2026, 8, 27), time(10), date(2026, 8, 27), time(11)
            )
        )

    def test_estado_temporal_e_conclusao_usam_o_periodo_completo(self):
        reserva = Alocacao.objects.create(
            data=date(2026, 8, 27), data_fim=date(2026, 8, 28),
            hora_inicio=time(22), hora_fim=time(2), piloto=self.piloto,
            drone=self.drone, finalidade="inspecao", criado_por=self.usuario,
        )
        from datetime import datetime
        from django.utils import timezone

        durante = timezone.make_aware(datetime(2026, 8, 28, 1, 0))
        depois = timezone.make_aware(datetime(2026, 8, 28, 3, 0))
        self.assertTrue(reserva_em_andamento(reserva, durante))
        self.assertEqual(atualizar_reservas_vencidas(depois), 1)
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, "concluido")


class GeoUtilsTests(TestCase):
    def test_unidades_usam_o_mesmo_calculo(self):
        metros = distancia_m(-25.5, -54.5, -25.6, -54.6)
        self.assertAlmostEqual(distancia_km(-25.5, -54.5, -25.6, -54.6), metros / 1000)


class TelemetriaBateriaTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("telemetria_bateria")
        self.piloto = Piloto.objects.create(nome="Piloto", user=self.usuario)
        self.drone = Drone.objects.create(nome="Matrice", modelo="4T")
        self.alocacao = Alocacao.objects.create(
            data=date(2026, 8, 27), hora_inicio=time(8), hora_fim=time(9),
            piloto=self.piloto, drone=self.drone, finalidade="inspecao",
            criado_por=self.usuario,
        )
        self.voo = Voo.objects.create(
            data=self.alocacao.data, hora_inicio=time(8), hora_fim=time(9),
            piloto=self.piloto, drone=self.drone, finalidade="inspecao", local="Área",
            distancia_m="1500.50", criado_por=self.usuario,
            alocacao_calendario=self.alocacao,
        )

    def test_conta_seriais_distintos_e_reconhece_bateria_cadastrada(self):
        Bateria.objects.create(codigo="BAT-1", numero_serie="SERIAL-1", drone=self.drone)
        for serial in ("SERIAL-1", "SERIAL-2", "SERIAL-2"):
            ImportacaoLog.objects.create(
                voo=self.voo, nome_original=f"{serial}.txt", formato="txt",
                status="concluida", bateria_serial_detectada=serial,
                importado_por=self.usuario,
            )
        resumo = resumo_pos_voo_telemetria(self.alocacao)
        self.assertEqual(resumo["quantidade_baterias"], 2)
        self.assertEqual([item.numero_serie for item in resumo["baterias"]], ["SERIAL-1"])
        self.assertEqual(resumo["seriais_novos"], ["SERIAL-2"])
        self.assertEqual(resumo["distancia_m"], self.voo.distancia_m)

    def test_novo_log_atualiza_pos_voo_existente(self):
        bateria = Bateria.objects.create(codigo="BAT-1", numero_serie="SERIAL-1", drone=self.drone)
        ImportacaoLog.objects.create(
            voo=self.voo, nome_original="voo.txt", formato="txt", status="concluida",
            bateria_serial_detectada="SERIAL-1", importado_por=self.usuario,
        )
        registro = RegistroPosVoo.objects.create(
            alocacao=self.alocacao, voo=self.voo, hora_inicio_real=time(8),
            hora_fim_real=time(9), resultado="concluido", preenchido_por=self.usuario,
        )
        sincronizar_registro_pos_voo(self.voo)
        registro.refresh_from_db()
        self.voo.refresh_from_db()
        self.assertEqual(registro.distancia_m, self.voo.distancia_m)
        self.assertEqual(registro.baterias_utilizadas, 1)
        self.assertEqual(list(registro.baterias.all()), [bateria])
