from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_piloto_primeiro_acesso"),
    ]

    operations = [
        migrations.AddField(
            model_name="drone",
            name="localizacao",
            field=models.CharField(
                blank=True,
                default="",
                max_length=150,
            ),
        ),
    ]
