from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0069_configuracaosegurancausuario_eventoauditoria"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AlertaSeguranca",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(db_index=True, max_length=50)),
                ("nivel", models.CharField(choices=[("atencao", "Atenção"), ("alto", "Alto"), ("critico", "Crítico")], default="atencao", max_length=10)),
                ("mensagem", models.CharField(max_length=255)),
                ("endereco_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("detalhes", models.JSONField(blank=True, default=dict)),
                ("resolvido", models.BooleanField(db_index=True, default=False)),
                ("criado_em", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("resolvido_em", models.DateTimeField(blank=True, null=True)),
                ("resolvido_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="alertas_seguranca_resolvidos", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["resolvido", "-criado_em"]},
        ),
    ]
