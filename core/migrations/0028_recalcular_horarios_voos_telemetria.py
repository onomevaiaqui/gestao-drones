from django.db import migrations
from django.db.models import Max, Min
from django.utils import timezone


def recalcular_horarios(apps, schema_editor):
    Voo = apps.get_model("core", "Voo")
    for voo in Voo.objects.all().iterator():
        limites = voo.importacoes_log.filter(
            status="concluida",
            inicio_registro__isnull=False,
            fim_registro__isnull=False,
        ).aggregate(inicio=Min("inicio_registro"), fim=Max("fim_registro"))
        if not limites["inicio"] or not limites["fim"]:
            continue
        inicio = timezone.localtime(limites["inicio"])
        fim = timezone.localtime(limites["fim"])
        voo.data = inicio.date()
        voo.hora_inicio = inicio.time().replace(tzinfo=None)
        voo.hora_fim = fim.time().replace(tzinfo=None)
        voo.save(update_fields=["data", "hora_inicio", "hora_fim"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0027_solicitacaovoo_requer_avaliacao_risco"),
    ]

    operations = [
        migrations.RunPython(recalcular_horarios, migrations.RunPython.noop),
    ]
