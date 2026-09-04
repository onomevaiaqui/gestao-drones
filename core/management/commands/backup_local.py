from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from core.backup_service import criar_backup


class Command(BaseCommand):
    help = "Backup SQLite e mídia local; exige confirmação de pausa nas escritas. Não inclui segredos."

    def add_arguments(self, parser):
        parser.add_argument("destino")
        parser.add_argument("--confirmar-manutencao", action="store_true")

    def handle(self, *args, **options):
        if not options["confirmar_manutencao"]:
            raise CommandError("Pare Django e os workers de escrita antes de usar --confirmar-manutencao.")
        if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3" or settings.SISMOD_MEDIA_STORAGE != "local":
            raise CommandError("Este comando é exclusivo para SQLite + mídia local. Consulte o procedimento PostgreSQL/S3.")
        try:
            total = criar_backup(settings.DATABASES["default"]["NAME"], settings.MEDIA_ROOT, options["destino"])
        except (OSError, ValueError) as erro:
            raise CommandError(str(erro)) from erro
        self.stdout.write(f"Backup concluído: {total} arquivo(s). Proteja este pacote; contém dados pessoais.")
