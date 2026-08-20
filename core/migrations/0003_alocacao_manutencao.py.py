from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("core", "0002_alter_drone_options_alter_piloto_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Alocacao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("data", models.DateField()),
                ("hora_inicio", models.TimeField()),
                ("hora_fim", models.TimeField()),
                ("finalidade", models.CharField(max_length=100)),
                ("local", models.CharField(blank=True, max_length=200)),
                ("observacoes", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("reservado","Reservado"),("concluido","Concluído"),("cancelado","Cancelado")], default="reservado", max_length=20)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("criado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="auth.user")),
                ("drone", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.drone")),
                ("piloto", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.piloto")),
            ],
            options={"ordering": ["data","hora_inicio"]},
        ),
        migrations.CreateModel(
            name="Manutencao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(choices=[("preventiva","Preventiva"),("corretiva","Corretiva"),("inspecao","Inspeção"),("atualizacao","Atualização")], max_length=30)),
                ("data_inicio", models.DateField()),
                ("data_fim", models.DateField(blank=True, null=True)),
                ("descricao", models.TextField()),
                ("concluida", models.BooleanField(default=False)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("criado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="auth.user")),
                ("drone", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.drone")),
            ],
            options={"ordering": ["-data_inicio"]},
        ),
    ]
