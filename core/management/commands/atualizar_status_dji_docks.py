from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import DJIDock


class Command(BaseCommand):
    help = "Marca como offline as DJI Docks sem telemetria recente."

    def handle(self, *args, **options):
        limite = timezone.now() - timedelta(seconds=settings.DJI_DOCK_OFFLINE_AFTER_SECONDS)
        total = DJIDock.objects.filter(ativo=True, online=True, ultimo_contato_em__lt=limite).update(
            online=False, status="offline"
        )
        self.stdout.write(self.style.SUCCESS(f"{total} Dock(s) marcada(s) como offline."))
