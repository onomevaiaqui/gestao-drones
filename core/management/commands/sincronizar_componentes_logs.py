from django.core.management.base import BaseCommand

from core.models import ImportacaoLog
from core.telemetria_service import _processar_dji


class Command(BaseCommand):
    help = "Relê Flight Records existentes para identificar payloads e acessórios sem alterar a telemetria."

    def add_arguments(self, parser):
        parser.add_argument("--todos", action="store_true", help="Relê também logs que já possuem componentes detectados.")

    def handle(self, *args, **options):
        importacoes = ImportacaoLog.objects.filter(status="concluida", origem="dji_flight_record")
        if not options["todos"]:
            importacoes = importacoes.filter(componentes_detectados=[])
        processadas, falhas = 0, []
        for importacao in importacoes.order_by("pk"):
            try:
                importacao.arquivo.open("rb")
                bruto = importacao.arquivo.read()
                importacao.arquivo.close()
                _processar_dji(importacao, bruto)
                importacao.save(update_fields=["componentes_detectados", "bateria_ciclos_detectados"])
                processadas += 1
                self.stdout.write(f"Log {importacao.pk}: {len(importacao.componentes_detectados)} equipamento(s)")
            except Exception as exc:
                falhas.append(f"Log {importacao.pk}: {exc}")
                self.stderr.write(self.style.WARNING(falhas[-1]))
        self.stdout.write(self.style.SUCCESS(f"Concluído: {processadas} processado(s) e {len(falhas)} falha(s)."))
