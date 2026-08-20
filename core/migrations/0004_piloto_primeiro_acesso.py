from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_alocacao_manutencao"),
    ]

    operations = [
        migrations.AddField(
            model_name="piloto",
            name="primeiro_acesso",
            field=models.BooleanField(default=True),
        ),
    ]
