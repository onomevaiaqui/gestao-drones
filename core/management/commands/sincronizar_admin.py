from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from core.models import Piloto


class Command(BaseCommand):
    help = "Vincula o superusuário existente a um Piloto administrador matrícula 0001."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            help="Username específico do superusuário. Se omitido, usa o primeiro superusuário criado.",
        )

    def handle(self, *args, **options):
        username = options.get("username")

        if username:
            try:
                user = User.objects.get(username=username, is_superuser=True)
            except User.DoesNotExist:
                raise CommandError(
                    f'Não foi encontrado superusuário com username "{username}".'
                )
        else:
            user = User.objects.filter(is_superuser=True).order_by("date_joined", "id").first()

        if not user:
            raise CommandError(
                "Nenhum superusuário foi encontrado. Crie um com: "
                "python manage.py createsuperuser"
            )

        # Se este usuário já estiver ligado a um piloto, atualiza esse cadastro.
        try:
            piloto = user.piloto
            criado = False
        except Piloto.DoesNotExist:
            # Tenta reaproveitar um cadastro matrícula 0001 sem usuário.
            piloto = Piloto.objects.filter(matricula="0001", user__isnull=True).first()

            if piloto:
                criado = False
            else:
                piloto = Piloto()
                criado = True

        nome = (user.get_full_name() or user.first_name or user.username).strip()

        piloto.user = user
        piloto.nome = nome
        piloto.matricula = "0001"
        piloto.perfil = "administrador"
        piloto.ativo = True
        piloto.save()

        user.is_active = True
        user.save(update_fields=["is_active"])

        acao = "criado" if criado else "atualizado"
        self.stdout.write(
            self.style.SUCCESS(
                f'Administrador {acao}: {piloto.nome} | '
                f'matrícula 0001 | login {user.username}'
            )
        )
