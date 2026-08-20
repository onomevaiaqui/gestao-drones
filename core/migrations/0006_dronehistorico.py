from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_drone_localizacao"),
    ]

    operations = [
        migrations.CreateModel(
            name="DroneHistorico",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status_anterior",
                    models.CharField(
                        blank=True,
                        max_length=20,
                    ),
                ),
                (
                    "status_novo",
                    models.CharField(
                        max_length=20,
                    ),
                ),
                (
                    "localizacao_anterior",
                    models.CharField(
                        blank=True,
                        max_length=150,
                    ),
                ),
                (
                    "localizacao_nova",
                    models.CharField(
                        blank=True,
                        max_length=150,
                    ),
                ),
                (
                    "alterado_em",
                    models.DateTimeField(
                        auto_now_add=True,
                    ),
                ),
                (
                    "observacao",
                    models.CharField(
                        blank=True,
                        max_length=255,
                    ),
                ),
                (
                    "alterado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="auth.user",
                    ),
                ),
                (
                    "drone",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="historico",
                        to="core.drone",
                    ),
                ),
            ],
            options={
                "ordering": ["-alterado_em"],
            },
        ),
    ]
