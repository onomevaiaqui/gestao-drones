from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import EventoAuditoria, TentativaLogin


class Command(BaseCommand):
    help = "Remove eventos de auditoria além da retenção configurada."

    def add_arguments(self, parser):
        parser.add_argument("--confirmar", action="store_true")

    def handle(self, *args, **options):
        if not options["confirmar"]:
            raise CommandError("Use --confirmar após validar a política de retenção da empresa.")
        limite = timezone.now() - timezone.timedelta(days=settings.SISMOD_AUDIT_RETENTION_DAYS)
        auditoria, _ = EventoAuditoria.objects.filter(ocorrido_em__lt=limite).delete()
        tentativas, _ = TentativaLogin.objects.filter(ocorrida_em__lt=limite).delete()
        self.stdout.write(self.style.SUCCESS(f"Retenção aplicada: {auditoria} evento(s) e {tentativas} tentativa(s) removidos."))
