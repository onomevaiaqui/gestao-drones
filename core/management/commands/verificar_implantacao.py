from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import connection

from core.dji_storage_service import diagnostico_armazenamento


class Command(BaseCommand):
    help = "Verifica banco, armazenamento e travas da implantação SISMOD."

    def handle(self, *args, **options):
        connection.ensure_connection()
        self.stdout.write(self.style.SUCCESS(f"Banco conectado: {connection.vendor}"))
        diag = diagnostico_armazenamento()
        if not diag["configurado"]:
            self.stderr.write(self.style.ERROR(diag["mensagem"]))
        else:
            nome = default_storage.save("healthcheck/sismod.txt", ContentFile(b"ok"))
            default_storage.delete(nome)
            self.stdout.write(self.style.SUCCESS(f"Armazenamento {diag['tipo']} gravável."))
        estado = "ATIVOS" if settings.DJI_DOCK_ENABLED and settings.DJI_DOCK_COMMANDS_ENABLED else "bloqueados"
        self.stdout.write(f"Comandos físicos DJI: {estado}.")
