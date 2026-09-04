from django.core.management.base import BaseCommand, CommandError
from core.backup_service import restaurar_backup


class Command(BaseCommand):
    help = "Restaura e valida backup em pasta nova, sem alterar o banco em uso."

    def add_arguments(self, parser):
        parser.add_argument("pacote")
        parser.add_argument("destino")

    def handle(self, *args, **options):
        try:
            total = restaurar_backup(options["pacote"], options["destino"])
        except Exception as erro:
            raise CommandError("Restauração recusada/incompleta. Verifique pacote e destino; o banco em uso não foi alterado.") from erro
        self.stdout.write(f"{total} arquivo(s) restaurados e validados em destino separado. Banco em uso preservado.")
