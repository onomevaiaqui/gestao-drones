from django.db import migrations
from django.db.models import Max, Min


def corrigir_duracoes_dji(apps, schema_editor):
    ImportacaoLog = apps.get_model("core", "ImportacaoLog")
    for importacao in ImportacaoLog.objects.filter(
        status="concluida", origem="dji_flight_record"
    ).iterator():
        limites = importacao.pontos.exclude(segundos__isnull=True).aggregate(
            inicio=Min("segundos"), fim=Max("segundos")
        )
        if limites["inicio"] is None or limites["fim"] is None:
            continue
        duracao = max(0, int(round(limites["fim"] - limites["inicio"])))
        if importacao.duracao_segundos != duracao:
            importacao.duracao_segundos = duracao
            importacao.save(update_fields=["duracao_segundos"])


class Migration(migrations.Migration):
    dependencies = [("core", "0023_alter_voo_data_alter_voo_finalidade_and_more")]
    operations = [migrations.RunPython(corrigir_duracoes_dji, migrations.RunPython.noop)]
