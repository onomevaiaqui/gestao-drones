import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0054_dji_dock_comando"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="DJIDockMissao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("identificador", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("status", models.CharField(choices=[("rascunho", "Rascunho"), ("validacao", "Aguardando validação"), ("pronta", "Pronta para envio"), ("enviada", "Enviada"), ("executando", "Em execução"), ("concluida", "Concluída"), ("cancelada", "Cancelada"), ("erro", "Erro")], default="rascunho", max_length=20)),
                ("altura_m", models.PositiveIntegerField()),
                ("velocidade_ms", models.DecimalField(decimal_places=2, default=5, max_digits=5)),
                ("validacoes", models.JSONField(blank=True, default=list)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("atualizada_em", models.DateTimeField(auto_now=True)),
                ("criada_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="missoes_dock_criadas", to=settings.AUTH_USER_MODEL)),
                ("dock", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="missoes", to="core.djidock")),
                ("planejamento", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="missoes_dji_dock", to="core.planejamentovoo")),
            ],
            options={"ordering": ["-planejamento__data", "-planejamento__hora_inicio"]},
        ),
        migrations.AddConstraint(model_name="djidockmissao", constraint=models.UniqueConstraint(fields=("dock", "planejamento"), name="dock_planejamento_missao_unica")),
    ]
