from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0068_tentativalogin"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfiguracaoSegurancaUsuario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("mfa_ativo", models.BooleanField(default=False)),
                ("segredo_mfa_criptografado", models.TextField(blank=True)),
                ("codigos_recuperacao", models.JSONField(blank=True, default=list)),
                ("mfa_ativado_em", models.DateTimeField(blank=True, null=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("usuario", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="configuracao_seguranca", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Configuração de segurança do usuário", "verbose_name_plural": "Configurações de segurança dos usuários"},
        ),
        migrations.CreateModel(
            name="EventoAuditoria",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("acao", models.CharField(db_index=True, max_length=80)),
                ("metodo", models.CharField(max_length=10)),
                ("caminho", models.CharField(max_length=500)),
                ("status_http", models.PositiveSmallIntegerField()),
                ("endereco_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("detalhes", models.JSONField(blank=True, default=dict)),
                ("ocorrido_em", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("usuario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="eventos_auditoria", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-ocorrido_em"]},
        ),
        migrations.AddIndex(
            model_name="eventoauditoria",
            index=models.Index(fields=["usuario", "ocorrido_em"], name="core_audit_usuario_data_idx"),
        ),
    ]
