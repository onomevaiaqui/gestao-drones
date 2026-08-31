import struct
from datetime import datetime, timezone

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from core.autel_binary_service import processar_autel_fr
from core.models import ImportacaoLog
from core.telemetria_forms import ImportacaoLogForm


def registro_autel_com_rota():
    bruto = bytearray(512)
    bruto[:8] = b"AUTEL_FR"
    struct.pack_into("<I", bruto, 8, 3)
    bruto[14:26] = b"UAV123456789"
    bruto[32:43] = b"BAT12345678"
    inicio = int(datetime(2026, 5, 4, 17, 21, tzinfo=timezone.utc).timestamp() * 1000)
    struct.pack_into("<Q", bruto, 0x91, inicio)
    for offset, tempo, lat, lon, alt, vx, vy in (
        (240, 1000, -23.3908, -46.9949, 10.0, 3.0, 4.0),
        (320, 1200, -23.3907, -46.9948, 11.0, 0.0, 2.0),
    ):
        bruto[offset] = 1
        struct.pack_into("<I", bruto, offset + 1, tempo)
        struct.pack_into("<ffffff", bruto, offset + 5, lat, lon, alt, vx, vy, 0.0)
    return bytes(bruto)


class AutelFlightRecordTests(SimpleTestCase):
    def test_processa_autel_fr_v3(self):
        importacao = ImportacaoLog()
        pontos = processar_autel_fr(importacao, registro_autel_com_rota())
        self.assertEqual(len(pontos), 2)
        self.assertEqual(importacao.origem, "autel_flight_record")
        self.assertEqual(importacao.drone_serial_detectado, "UAV123456789")
        self.assertEqual(importacao.bateria_serial_detectada, "BAT12345678")
        self.assertEqual(float(pontos[0].velocidade_ms), 5.0)

    def test_formulario_aceita_autel_sem_extensao_pela_assinatura(self):
        arquivo = SimpleUploadedFile("autel_2026-05-04_[17-21-06]_1", registro_autel_com_rota())
        self.assertTrue(ImportacaoLogForm._validar_arquivo(arquivo))

    def test_rejeita_autel_sem_trajetoria(self):
        importacao = ImportacaoLog()
        bruto = bytearray(200)
        bruto[:8] = b"AUTEL_FR"
        struct.pack_into("<I", bruto, 8, 3)
        with self.assertRaisesRegex(ValueError, "não contém uma trajetória GPS"):
            processar_autel_fr(importacao, bytes(bruto))
