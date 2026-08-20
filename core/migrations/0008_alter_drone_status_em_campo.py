from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("core", "0007_alter_alocacao_options_alter_drone_options_and_more")]
    operations = [
        migrations.AlterField(
            model_name="drone",
            name="status",
            field=models.CharField(
                choices=[
                    ("ativo","Ativo"),
                    ("em_campo","Em campo"),
                    ("manutencao","Em manutenção"),
                    ("indisponivel","Indisponível"),
                ],
                default="ativo",
                max_length=20,
            ),
        ),
    ]
