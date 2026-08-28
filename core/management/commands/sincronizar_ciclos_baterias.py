from django.core.management.base import BaseCommand

from core.models import Bateria, ImportacaoLog
from core.telemetria_bateria_service import sincronizar_ciclos_bateria
from core.telemetria_service import _processar_dji


class Command(BaseCommand):
    help = "Relê o log DJI mais recente de cada bateria sem alterar a telemetria."

    def add_arguments(self, parser):
        parser.add_argument("--todos", action="store_true", help="Relê também baterias que já possuem ciclos detectados.")

    def handle(self, *args, **options):
        baterias = Bateria.objects.all()
        if not options["todos"]:
            baterias = baterias.filter(ciclos_detectados_log__isnull=True)
        atualizadas = 0
        sem_log = 0
        falhas = []
        for bateria in baterias:
            importacoes = (
                ImportacaoLog.objects.filter(
                    status="concluida",
                    bateria_serial_detectada=bateria.numero_serie,
                )
                .order_by("-inicio_registro", "-pk")
            )
            if not importacoes.exists():
                sem_log += 1
                continue
            processada = False
            for importacao in importacoes:
                try:
                    importacao.arquivo.open("rb")
                    bruto = importacao.arquivo.read()
                    importacao.arquivo.close()
                    _processar_dji(importacao, bruto)
                    importacao.save(update_fields=["bateria_ciclos_detectados"])
                    sincronizar_ciclos_bateria(importacao)
                    processada = True
                    if importacao.bateria_ciclos_detectados is not None:
                        break
                except Exception as exc:
                    falhas.append(f"{bateria.codigo} / log {importacao.pk}: {exc}")
                    self.stderr.write(self.style.WARNING(falhas[-1]))
            bateria.refresh_from_db(fields=["ciclos_detectados_log"])
            if processada:
                atualizadas += 1
            self.stdout.write(f"{bateria.codigo}: {bateria.ciclos_detectados_log if bateria.ciclos_detectados_log is not None else 'não fornecido'}")
        self.stdout.write(self.style.SUCCESS(f"Concluído: {atualizadas} processada(s), {sem_log} sem log e {len(falhas)} falha(s)."))
