from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0055_dji_dock_missao")]

    operations = [
        migrations.AddField(model_name="djidock", name="aeronave_tipo_dji", field=models.PositiveIntegerField(blank=True, editable=False, null=True)),
        migrations.AddField(model_name="djidock", name="aeronave_subtipo_dji", field=models.PositiveIntegerField(blank=True, editable=False, null=True)),
        migrations.AddField(model_name="djidock", name="payload_tipo_dji", field=models.PositiveIntegerField(blank=True, editable=False, null=True)),
        migrations.AddField(model_name="djidock", name="payload_subtipo_dji", field=models.PositiveIntegerField(blank=True, editable=False, null=True)),
        migrations.AddField(model_name="djidock", name="payload_posicao_dji", field=models.PositiveSmallIntegerField(blank=True, editable=False, null=True)),
    ]
