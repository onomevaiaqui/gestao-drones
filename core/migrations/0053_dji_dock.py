from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0052_sincronizar_usuarios_inativos")]

    operations = [
        migrations.CreateModel(
            name="DJIDock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=150)),
                ("numero_serie", models.CharField(max_length=100, unique=True)),
                ("modelo", models.CharField(default="DJI Dock 2", max_length=100)),
                ("localizacao", models.CharField(blank=True, max_length=200)),
                ("latitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("status", models.CharField(choices=[("desconhecido", "Desconhecido"), ("online", "Online"), ("offline", "Offline"), ("alerta", "Com alerta")], default="desconhecido", max_length=20)),
                ("online", models.BooleanField(default=False)),
                ("modo", models.CharField(choices=[("simulacao", "Simulação"), ("cloud_api", "Cloud API")], default="simulacao", max_length=20)),
                ("ultima_telemetria", models.JSONField(blank=True, default=dict)),
                ("ultimo_contato_em", models.DateTimeField(blank=True, null=True)),
                ("ativo", models.BooleanField(default=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("drone", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="docks_dji", to="core.drone")),
            ],
            options={"verbose_name": "DJI Dock", "verbose_name_plural": "DJI Docks", "ordering": ["nome"]},
        ),
        migrations.CreateModel(
            name="DJIDockEvento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("identificador_externo", models.CharField(blank=True, max_length=120)),
                ("topico", models.CharField(max_length=255)),
                ("tipo", models.CharField(default="telemetria", max_length=80)),
                ("nivel", models.CharField(choices=[("info", "Informação"), ("atencao", "Atenção"), ("critico", "Crítico")], default="info", max_length=20)),
                ("mensagem", models.CharField(blank=True, max_length=255)),
                ("dados", models.JSONField(blank=True, default=dict)),
                ("recebido_em", models.DateTimeField(auto_now_add=True)),
                ("dock", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="eventos", to="core.djidock")),
            ],
            options={"ordering": ["-recebido_em"]},
        ),
        migrations.AddConstraint(
            model_name="djidockevento",
            constraint=models.UniqueConstraint(condition=~models.Q(("identificador_externo", "")), fields=("dock", "identificador_externo"), name="dock_evento_externo_unico"),
        ),
    ]
