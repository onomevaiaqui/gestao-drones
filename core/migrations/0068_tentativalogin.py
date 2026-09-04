from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0067_djidockcanalvideo_transmissao_atual")]

    operations = [
        migrations.CreateModel(
            name="TentativaLogin",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("identificador_hash", models.CharField(db_index=True, max_length=64)),
                ("endereco_ip", models.GenericIPAddressField(blank=True, db_index=True, null=True)),
                ("ocorrida_em", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={"ordering": ["-ocorrida_em"]},
        ),
        migrations.AddIndex(
            model_name="tentativalogin",
            index=models.Index(fields=["identificador_hash", "endereco_ip", "ocorrida_em"], name="core_tentat_identif_255a4b_idx"),
        ),
    ]
