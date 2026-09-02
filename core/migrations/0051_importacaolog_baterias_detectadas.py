from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0050_instalacaosismod_licencasismod")]

    operations = [
        migrations.AddField(
            model_name="importacaolog",
            name="baterias_detectadas",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
