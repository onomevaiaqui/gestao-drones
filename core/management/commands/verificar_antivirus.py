from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.test.utils import override_settings

from core.upload_security import ArquivoInseguro, verificar_clamav


class Command(BaseCommand):
    help = "Testa ClamAV com conteúdo limpo e padrão inofensivo EICAR em memória. Não altera configurações."

    def add_arguments(self, parser):
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=3310)

    def handle(self, *args, **options):
        with override_settings(SISMOD_CLAMAV_HOST=options["host"],
                               SISMOD_CLAMAV_PORT=options["port"], SISMOD_CLAMAV_REQUIRED=True):
            try:
                verificar_clamav(SimpleUploadedFile("teste-limpo.txt", b"Teste SISMOD sem ameacas."))
            except ArquivoInseguro as erro:
                raise CommandError(f"Teste limpo falhou: {erro}") from erro
            # Padrão oficial de teste, sem código executável e sem arquivo no disco.
            eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
            try:
                verificar_clamav(SimpleUploadedFile("teste-eicar.txt", eicar))
            except ArquivoInseguro as erro:
                if str(erro) != "O arquivo foi recusado pela inspeção antivírus.":
                    raise CommandError(f"Teste EICAR inconclusivo: {erro}") from erro
            else:
                raise CommandError("O padrão EICAR não foi bloqueado.")
        self.stdout.write(self.style.SUCCESS("ClamAV validado: conteúdo limpo aceito e EICAR bloqueado."))
