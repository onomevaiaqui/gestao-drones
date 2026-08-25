from django.db import migrations
from django.db.models import Max, Min


def corrigir_duracoes(apps, schema_editor):
    ImportacaoLog = apps.get_model("core", "ImportacaoLog")
    for importacao in ImportacaoLog.objects.filter(status="concluida").iterator():
        limites = importacao.pontos.exclude(segundos__isnull=True).aggregate(
            inicio=Min("segundos"), fim=Max("segundos")
        )
        if limites["inicio"] is not None and limites["fim"] is not None:
            duracao = max(0, int(limites["fim"] - limites["inicio"]))
            if importacao.duracao_segundos != duracao:
                importacao.duracao_segundos = duracao
                importacao.save(update_fields=["duracao_segundos"])


class Migration(migrations.Migration):
    dependencies = [("core", "0020_importacaolog_bateria_serial_detectada_and_more")]
    operations = [migrations.RunPython(corrigir_duracoes, migrations.RunPython.noop)]
