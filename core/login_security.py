import hashlib
import ipaddress

from django.conf import settings
from django.utils import timezone

from .models import TentativaLogin


def _hash_identificador(valor):
    normalizado = str(valor or "").strip().casefold()
    return hashlib.sha256(normalizado.encode("utf-8")).hexdigest()


def endereco_cliente(request):
    valor = request.META.get("REMOTE_ADDR", "")
    if getattr(settings, "SECURE_PROXY_SSL_HEADER", None):
        valor = (request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or valor)
    try:
        return str(ipaddress.ip_address(valor))
    except ValueError:
        return None


def esta_bloqueado(request, usuario):
    agora = timezone.now()
    janela = agora - timezone.timedelta(seconds=settings.SISMOD_LOGIN_WINDOW_SECONDS)
    bloqueio = agora - timezone.timedelta(seconds=settings.SISMOD_LOGIN_BLOCK_SECONDS)
    consulta = TentativaLogin.objects.filter(
        identificador_hash=_hash_identificador(usuario),
        endereco_ip=endereco_cliente(request),
        ocorrida_em__gte=min(janela, bloqueio),
    )
    falhas = list(consulta.order_by("-ocorrida_em")[: settings.SISMOD_LOGIN_MAX_FAILURES])
    return len(falhas) >= settings.SISMOD_LOGIN_MAX_FAILURES and falhas[0].ocorrida_em >= bloqueio


def registrar_falha(request, usuario):
    retencao = timezone.now() - timezone.timedelta(
        seconds=max(settings.SISMOD_LOGIN_WINDOW_SECONDS, settings.SISMOD_LOGIN_BLOCK_SECONDS) * 2
    )
    TentativaLogin.objects.filter(ocorrida_em__lt=retencao).delete()
    identificador = _hash_identificador(usuario)
    endereco = endereco_cliente(request)
    TentativaLogin.objects.create(identificador_hash=identificador, endereco_ip=endereco)
    janela = timezone.now() - timezone.timedelta(seconds=settings.SISMOD_LOGIN_WINDOW_SECONDS)
    total = TentativaLogin.objects.filter(
        identificador_hash=identificador, endereco_ip=endereco, ocorrida_em__gte=janela
    ).count()
    if total >= settings.SISMOD_LOGIN_MAX_FAILURES:
        from .models import AlertaSeguranca
        AlertaSeguranca.objects.get_or_create(
            tipo="bloqueio_login", endereco_ip=endereco, resolvido=False,
            defaults={"nivel": "alto", "mensagem": "Conta temporariamente bloqueada após tentativas inválidas."},
        )


def limpar_falhas(request, usuario):
    TentativaLogin.objects.filter(
        identificador_hash=_hash_identificador(usuario),
        endereco_ip=endereco_cliente(request),
    ).delete()
