import getpass
import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Piloto


class Command(BaseCommand):
    help = "Cria com segurança o primeiro administrador da instalação."

    def add_arguments(self, parser):
        parser.add_argument("--username")
        parser.add_argument("--email")
        parser.add_argument("--nome")
        parser.add_argument("--noinput", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if User.objects.filter(is_superuser=True).exists():
            raise CommandError("Já existe um administrador. Crie os demais usuários pela interface do SISMOD.")
        sem_interacao = options["noinput"]
        username = options["username"] or os.getenv("SISMOD_INITIAL_ADMIN_USERNAME")
        email = options["email"] or os.getenv("SISMOD_INITIAL_ADMIN_EMAIL")
        nome = options["nome"] or os.getenv("SISMOD_INITIAL_ADMIN_NAME")
        senha = os.getenv("SISMOD_INITIAL_ADMIN_PASSWORD") if sem_interacao else None
        if not sem_interacao:
            username = username or input("Usuário: ").strip()
            email = email or input("E-mail: ").strip()
            nome = nome or input("Nome completo: ").strip()
            senha = getpass.getpass("Senha: ")
            if senha != getpass.getpass("Confirme a senha: "):
                raise CommandError("As senhas não conferem.")
        if not all((username, email, nome, senha)):
            raise CommandError("Usuário, e-mail, nome e senha são obrigatórios.")
        user = User.objects.create_superuser(username=username, email=email, password=senha)
        Piloto.objects.create(user=user, nome=nome, perfil="administrador", ativo=True, primeiro_acesso=False)
        self.stdout.write(self.style.SUCCESS(f"Administrador inicial '{username}' criado."))
