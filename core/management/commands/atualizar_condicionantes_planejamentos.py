from django.core.management.base import BaseCommand

from core.models import PlanejamentoVoo
from core.planejamento_aeronautico_service import consultar_condicionantes_aeronauticas


class Command(BaseCommand):
    help = "Recalcula as condicionantes aeronáuticas dos planejamentos existentes sem alterar meteorologia ou geometria."

    def add_arguments(self, parser):
        parser.add_argument("--planejamento", type=int, help="Atualiza somente um planejamento.")

    def handle(self, *args, **options):
        registros = PlanejamentoVoo.objects.exclude(area_geojson={}).order_by("pk")
        if options.get("planejamento"):
            registros = registros.filter(pk=options["planejamento"])
        atualizados = erros = 0
        for planejamento in registros.iterator():
            try:
                aeronautica = consultar_condicionantes_aeronauticas(planejamento)
                resumo = dict(planejamento.resumo_meteorologico or {})
                resumo["aeronautica"] = aeronautica
                planejamento.resumo_meteorologico = resumo
                planejamento.save(update_fields=["resumo_meteorologico", "atualizado_em"])
                atualizados += 1
                self.stdout.write(
                    f"Planejamento {planejamento.pk}: {len(aeronautica.get('itens', []))} condicionante(s)."
                )
            except Exception as erro:
                erros += 1
                self.stderr.write(f"Planejamento {planejamento.pk}: falha - {erro}")
        self.stdout.write(self.style.SUCCESS(
            f"Atualização concluída: {atualizados} atualizado(s), {erros} falha(s)."
        ))
