import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0056_dji_dock_tipos_wpml")]

    operations = [
        migrations.AlterField(model_name="djidockmissao", name="status", field=models.CharField(choices=[("rascunho", "Rascunho"), ("validacao", "Aguardando validação"), ("pronta", "Pronta para envio"), ("enviada", "Enviada"), ("executando", "Em execução"), ("pausada", "Pausada"), ("concluida", "Concluída"), ("cancelada", "Cancelada"), ("erro", "Erro")], default="rascunho", max_length=20)),
        migrations.AddField(model_name="djidockmissao", name="progresso_percentual", field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name="djidockmissao", name="etapa_atual", field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="djidockmissao", name="waypoint_atual", field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="djidockmissao", name="quantidade_midias", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="djidockmissao", name="resultado_dji", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="djidockmissao", name="iniciada_em", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="djidockmissao", name="concluida_em", field=models.DateTimeField(blank=True, null=True)),
        migrations.CreateModel(
            name="DJIDockArquivo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("object_key", models.CharField(max_length=500)),
                ("nome", models.CharField(max_length=255)),
                ("caminho_remoto", models.CharField(blank=True, max_length=500)),
                ("extensao", models.CharField(blank=True, max_length=30)),
                ("original", models.BooleanField(default=False)),
                ("metadados", models.JSONField(blank=True, default=dict)),
                ("informado_em", models.DateTimeField(auto_now_add=True)),
                ("missao", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="arquivos", to="core.djidockmissao")),
            ],
            options={"ordering": ["nome"]},
        ),
        migrations.AddConstraint(model_name="djidockarquivo", constraint=models.UniqueConstraint(fields=("missao", "object_key"), name="dock_missao_arquivo_unico")),
    ]
