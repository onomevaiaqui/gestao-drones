from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.models import ConfiguracaoSegurancaUsuario
from core.mfa_service import criptografar_segredo, descriptografar_segredo


class Command(BaseCommand):
    help = "Valida e recriptografa MFA com a primeira chave configurada. Simulação por padrão."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true")

    def handle(self, *args, **options):
        if not settings.SISMOD_MFA_ENCRYPTION_KEYS:
            raise CommandError("Configure SISMOD_MFA_ENCRYPTION_KEYS antes da rotação.")
        try:
            with transaction.atomic():
                registros = ConfiguracaoSegurancaUsuario.objects.select_for_update().filter(mfa_ativo=True)
                total = 0
                for registro in registros:
                    novo = criptografar_segredo(descriptografar_segredo(registro.segredo_mfa_criptografado))
                    if options["aplicar"]:
                        registro.segredo_mfa_criptografado = novo
                        registro.save(update_fields=["segredo_mfa_criptografado", "atualizado_em"])
                    total += 1
        except Exception as erro:
            raise CommandError("Não foi possível validar/rotacionar todas as chaves. Nenhuma alteração foi confirmada.") from erro
        self.stdout.write(f"{total} configuração(ões) {'rotacionadas' if options['aplicar'] else 'validadas; simulação sem alterações'}.")
