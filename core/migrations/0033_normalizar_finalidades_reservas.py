import unicodedata

from django.db import migrations


def normalizar_finalidades(apps, schema_editor):
    SolicitacaoVoo = apps.get_model("core", "SolicitacaoVoo")
    opcoes = {
        "levantamento": "levantamento", "monitoramento": "monitoramento",
        "inspecao": "inspecao", "mapeamento": "mapeamento",
        "fotografia": "fotografia", "treinamento": "treinamento", "outro": "outro",
    }
    for reserva in SolicitacaoVoo.objects.all().only("pk", "finalidade"):
        texto = unicodedata.normalize("NFKD", reserva.finalidade or "")
        texto = "".join(c for c in texto if not unicodedata.combining(c)).lower().strip()
        valor = next((codigo for termo, codigo in opcoes.items() if termo in texto), "outro")
        if reserva.finalidade != valor:
            SolicitacaoVoo.objects.filter(pk=reserva.pk).update(finalidade=valor)


class Migration(migrations.Migration):
    dependencies = [("core", "0032_alter_solicitacaovoo_finalidade")]
    operations = [migrations.RunPython(normalizar_finalidades, migrations.RunPython.noop)]
