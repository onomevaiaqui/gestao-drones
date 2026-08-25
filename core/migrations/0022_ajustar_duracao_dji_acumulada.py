from django.db import migrations
from django.db.models import Max, Min


def ajustar_duracoes(apps, schema_editor):
    ImportacaoLog = apps.get_model("core", "ImportacaoLog")
    for importacao in ImportacaoLog.objects.filter(status="concluida").iterator():
        limites = importacao.pontos.exclude(segundos__isnull=True).aggregate(
            inicio=Min("segundos"), fim=Max("segundos")
        )
        if limites["fim"] is None:
            continue
        if importacao.origem == "dji_flight_record":
            duracao = int(limites["fim"])
        else:
            duracao = max(0, int(limites["fim"] - limites["inicio"]))
        if importacao.duracao_segundos != duracao:
            importacao.duracao_segundos = duracao
            importacao.save(update_fields=["duracao_segundos"])


class Migration(migrations.Migration):
    dependencies = [("core", "0021_corrigir_duracao_telemetria")]
    operations = [migrations.RunPython(ajustar_duracoes, migrations.RunPython.noop)]
