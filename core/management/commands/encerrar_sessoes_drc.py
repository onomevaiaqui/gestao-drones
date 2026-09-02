from django.core.management.base import BaseCommand

from core.dji_drc_service import finalizar_sessao, sessao_expirada
from core.models import DJIDRCSessao


class Command(BaseCommand):
    help = "Neutraliza e encerra sessões DRC sem heartbeat ou vencidas."

    def handle(self, *args, **options):
        total = 0
        for sessao in DJIDRCSessao.objects.filter(status="ativa"):
            if sessao_expirada(sessao):
                finalizar_sessao(sessao, "Watchdog: heartbeat ausente ou sessão expirada.")
                total += 1
        self.stdout.write(self.style.SUCCESS(f"{total} sessão(ões) DRC encerrada(s)."))
