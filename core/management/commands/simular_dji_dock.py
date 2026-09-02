import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.dji_dock_service import processar_mensagem_dock


class Command(BaseCommand):
    help = "Gera telemetria local de uma DJI Dock sem enviar comandos ao equipamento."

    def add_arguments(self, parser):
        parser.add_argument("--serial", default="DOCK-SIM-001")
        parser.add_argument("--latitude", type=float, default=-25.5427)
        parser.add_argument("--longitude", type=float, default=-54.5854)
        parser.add_argument("--chuva", type=int, default=0, choices=[0, 1])
        parser.add_argument("--cenario", choices=["normal", "chuva", "falha", "offline", "missao", "midia"], default="normal")
        parser.add_argument("--missao", type=int)

    def handle(self, *args, **opcoes):
        if not settings.DJI_DOCK_SIMULATOR_ENABLED:
            raise CommandError("Defina DJI_DOCK_SIMULATOR_ENABLED=true somente no ambiente local.")
        cenario = opcoes["cenario"]
        if cenario in ("missao", "midia") and not opcoes["missao"]:
            raise CommandError("Informe --missao para este cenário.")
        chuva = 1 if cenario == "chuva" else opcoes["chuva"]
        dados = {
            "latitude": opcoes["latitude"], "longitude": opcoes["longitude"],
            "rainfall": chuva, "environment_temperature": 24.5,
            "wind_speed": 15.0 if cenario == "falha" else 3.2,
        }
        if cenario == "falha":
            dados["emergency_stop_state"] = 1
        payload = {
            "tid": f"sim-{time.time_ns()}",
            "data": {
                **dados,
            }
        }
        topico = f"thing/product/{opcoes['serial']}/osd"
        if cenario == "missao":
            from core.models import DJIDockMissao
            missao = DJIDockMissao.objects.get(pk=opcoes["missao"])
            payload.update({"method": "flighttask_progress", "data": {"output": {
                "status": "in_progress", "progress": {"percent": 50, "current_step": 21},
                "ext": {"flight_id": str(missao.identificador), "current_waypoint_index": 2, "media_count": 1},
            }}})
            topico = f"thing/product/{opcoes['serial']}/events"
        elif cenario == "midia":
            from core.models import DJIDockMissao
            missao = DJIDockMissao.objects.get(pk=opcoes["missao"])
            payload.update({"method": "file_upload_callback", "data": {"file": {
                "object_key": f"simulacao/{time.time_ns()}.jpg", "name": "foto-simulada.jpg",
                "path": "simulacao", "ext": {"flight_id": str(missao.identificador), "is_original": True},
                "metadata": {"relative_altitude": 50, "shoot_position": {"lat": opcoes["latitude"], "lng": opcoes["longitude"]}},
            }}})
            topico = f"thing/product/{opcoes['serial']}/events"
        dock, evento, _ = processar_mensagem_dock(
            topico, payload, origem="simulacao"
        )
        if cenario == "offline":
            dock.online = False
            dock.status = "offline"
            dock.save(update_fields=["online", "status"])
        self.stdout.write(self.style.SUCCESS(f"Telemetria criada para {dock.nome}; evento {evento.pk}."))
