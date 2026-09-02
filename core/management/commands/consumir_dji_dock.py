import json
import ssl

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.dji_cloud_service import configuracao_mqtt_dock
from core.dji_dock_service import processar_mensagem_dock


class Command(BaseCommand):
    help = "Consome telemetria/eventos da DJI Dock pelo broker MQTT configurado."

    def handle(self, *args, **options):
        if not settings.DJI_DOCK_ENABLED:
            raise CommandError("A conexão física está bloqueada. Defina DJI_DOCK_ENABLED=true após concluir a homologação.")
        config = configuracao_mqtt_dock()
        if not config:
            raise CommandError("DJI_CLOUD_MQTT_HOST está ausente ou inválido.")
        if not settings.DJI_DOCK_MQTT_USERNAME or not settings.DJI_DOCK_MQTT_PASSWORD:
            raise CommandError("Informe DJI_DOCK_MQTT_USERNAME e DJI_DOCK_MQTT_PASSWORD.")
        if not config["topics"]:
            raise CommandError("Informe pelo menos um tópico em DJI_DOCK_MQTT_TOPIC.")

        try:
            import paho.mqtt.client as mqtt
        except ImportError as erro:
            raise CommandError("Instale as dependências com pip install -r requirements.txt.") from erro

        transport = "websockets" if config["websockets"] else "tcp"
        cliente = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.DJI_DOCK_MQTT_CLIENT_ID,
            protocol=mqtt.MQTTv5,
            transport=transport,
        )
        cliente.username_pw_set(settings.DJI_DOCK_MQTT_USERNAME, settings.DJI_DOCK_MQTT_PASSWORD)
        if config["tls"]:
            cliente.tls_set(
                ca_certs=settings.DJI_DOCK_MQTT_CA_CERT or None,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )

        def conectado(client, userdata, flags, reason_code, properties):
            if reason_code != 0:
                self.stderr.write(self.style.ERROR(f"Broker recusou a conexão: {reason_code}"))
                return
            self.stdout.write(self.style.SUCCESS("Consumidor DJI Dock conectado."))
            for topico in config["topics"]:
                client.subscribe(topico, qos=1)
                self.stdout.write(f"Assinado: {topico}")

        def mensagem(client, userdata, msg):
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
                dock, evento, criado = processar_mensagem_dock(msg.topic, payload, origem="cloud_api")
                estado = "novo" if criado else "duplicado"
                self.stdout.write(f"{dock.numero_serie}: {evento.tipo} ({estado})")
            except Exception as erro:  # mantém o consumidor ativo e registra a falha
                self.stderr.write(self.style.ERROR(f"Mensagem recusada em {msg.topic}: {erro}"))

        cliente.on_connect = conectado
        cliente.on_message = mensagem
        self.stdout.write(f"Conectando a {config['host']}:{config['port']}...")
        try:
            cliente.connect(config["host"], config["port"], keepalive=60)
            cliente.loop_forever(retry_first_connection=True)
        except KeyboardInterrupt:
            self.stdout.write("Consumidor encerrado pelo operador.")
        except OSError as erro:
            raise CommandError(f"Não foi possível conectar ao broker: {erro}") from erro
        finally:
            cliente.disconnect()
