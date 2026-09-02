from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import DJIDockComando


class Command(BaseCommand):
    help = "Cancela comandos DJI pendentes ou bloqueados cuja validade terminou."

    def handle(self, *args, **options):
        agora = timezone.now()
        itens = DJIDockComando.objects.filter(status__in=["pendente", "bloqueado"], expira_em__lt=agora)
        total = itens.update(status="cancelado", concluido_em=agora, mensagem="Comando expirado sem publicação ou confirmação.")
        self.stdout.write(self.style.SUCCESS(f"{total} comando(s) expirado(s)."))
