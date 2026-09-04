import json
import ssl

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.dji_cloud_service import configuracao_mqtt_dock
from core.dji_command_publisher import concluir_publicacao, falhar_publicacao, reservar_para_publicacao
from core.models import DJIDockComando


class Command(BaseCommand):
    help = "Publica um lote limitado de comandos DJI previamente autorizados e aptos."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=1)
        parser.add_argument("--confirm-real-publication", action="store_true")

    def handle(self, *args, **opcoes):
        if not opcoes["confirm_real_publication"]:
            raise CommandError("Use --confirm-real-publication somente durante uma operação homologada.")
        if settings.DJI_DOCK_EMERGENCY_STOP:
            raise CommandError("Parada de emergência ativa; nenhum comando será publicado.")
        if not (settings.DJI_DOCK_ENABLED and settings.DJI_DOCK_COMMANDS_ENABLED and settings.DJI_DOCK_PUBLISHER_ENABLED):
            raise CommandError("As três travas DJI precisam estar habilitadas.")
        limite = opcoes["limit"]
        if limite < 1 or limite > 20:
            raise CommandError("O limite deve estar entre 1 e 20.")
        config = configuracao_mqtt_dock()
        if not config or not settings.DJI_DOCK_MQTT_PUBLISHER_USERNAME or not settings.DJI_DOCK_MQTT_PUBLISHER_PASSWORD:
            raise CommandError("Broker MQTT e credenciais da Dock estão incompletos.")

        try:
            import paho.mqtt.client as mqtt
        except ImportError as erro:
            raise CommandError("Instale as dependências com pip install -r requirements.txt.") from erro

        cliente = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.DJI_DOCK_MQTT_PUBLISHER_CLIENT_ID,
            protocol=mqtt.MQTTv5,
            transport="websockets" if config["websockets"] else "tcp",
        )
        cliente.username_pw_set(settings.DJI_DOCK_MQTT_PUBLISHER_USERNAME, settings.DJI_DOCK_MQTT_PUBLISHER_PASSWORD)
        if config["tls"]:
            cliente.tls_set(ca_certs=settings.DJI_DOCK_MQTT_CA_CERT or None, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
        try:
            cliente.connect(config["host"], config["port"], keepalive=30)
            cliente.loop_start()
            ids = list(DJIDockComando.objects.filter(status="pendente").order_by("solicitado_em").values_list("pk", flat=True)[:limite])
            publicados = 0
            for comando_id in ids:
                try:
                    comando, topico, payload = reservar_para_publicacao(comando_id)
                    info = cliente.publish(topico, json.dumps(payload, separators=(",", ":")), qos=1)
                    info.wait_for_publish(timeout=10)
                    if info.rc != mqtt.MQTT_ERR_SUCCESS:
                        raise RuntimeError(f"Broker recusou a mensagem: código {info.rc}.")
                    concluir_publicacao(comando.pk)
                    publicados += 1
                except (ValueError, OSError, RuntimeError) as erro:
                    falhar_publicacao(comando_id, erro)
                    self.stderr.write(self.style.ERROR(f"Comando {comando_id}: {erro}"))
            self.stdout.write(self.style.SUCCESS(f"{publicados} comando(s) publicado(s)."))
        except OSError as erro:
            raise CommandError(f"Não foi possível conectar ao broker: {erro}") from erro
        finally:
            cliente.loop_stop()
            cliente.disconnect()
