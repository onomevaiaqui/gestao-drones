import json
import time

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Publica uma mensagem OSD fictícia no broker MQTT local."

    def add_arguments(self, parser):
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=1883)
        parser.add_argument("--serial", default="DOCK-MQTT-SIM-001")

    def handle(self, *args, **opcoes):
        try:
            import paho.mqtt.client as mqtt
        except ImportError as erro:
            raise CommandError("Instale as dependências do projeto.") from erro
        payload = {
            "tid": f"teste-local-{time.time_ns()}",
            "timestamp": int(time.time() * 1000),
            "data": {
                "latitude": -25.5427,
                "longitude": -54.5854,
                "environment_temperature": 24.5,
                "wind_speed": 3.2,
                "rainfall": 0,
            },
        }
        cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
        try:
            cliente.connect(opcoes["host"], opcoes["port"], 30)
            cliente.loop_start()
            info = cliente.publish(
                f"thing/product/{opcoes['serial']}/osd", json.dumps(payload), qos=1
            )
            info.wait_for_publish(timeout=10)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise CommandError(f"O broker recusou a publicação: código {info.rc}.")
        except OSError as erro:
            raise CommandError(f"Broker local indisponível: {erro}") from erro
        finally:
            cliente.loop_stop()
            cliente.disconnect()
        self.stdout.write(self.style.SUCCESS("Mensagem de teste publicada no MQTT local."))
