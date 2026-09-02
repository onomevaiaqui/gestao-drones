import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0053_dji_dock"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="DJIDockComando",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("identificador", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("tipo", models.CharField(choices=[("atualizar_estado", "Atualizar estado"), ("reiniciar", "Reiniciar Dock"), ("abrir_tampa", "Abrir tampa"), ("fechar_tampa", "Fechar tampa"), ("iniciar_missao", "Iniciar missão"), ("pausar_missao", "Pausar missão"), ("cancelar_missao", "Cancelar missão")], max_length=30)),
                ("status", models.CharField(choices=[("bloqueado", "Bloqueado"), ("pendente", "Pendente"), ("enviado", "Enviado"), ("confirmado", "Confirmado"), ("erro", "Erro"), ("cancelado", "Cancelado")], default="bloqueado", max_length=20)),
                ("parametros", models.JSONField(blank=True, default=dict)),
                ("critico", models.BooleanField(default=False)),
                ("solicitado_em", models.DateTimeField(auto_now_add=True)),
                ("enviado_em", models.DateTimeField(blank=True, null=True)),
                ("concluido_em", models.DateTimeField(blank=True, null=True)),
                ("mensagem", models.CharField(blank=True, max_length=255)),
                ("dock", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="comandos", to="core.djidock")),
                ("solicitado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="comandos_dock_solicitados", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Comando da DJI Dock", "verbose_name_plural": "Comandos das DJI Docks", "ordering": ["-solicitado_em"]},
        ),
    ]
