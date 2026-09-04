import hashlib
import ipaddress

from django.conf import settings
from django.utils import timezone

from .models import TentativaLogin


def _hash_identificador(valor):
    normalizado = str(valor or "").strip().casefold()
    return hashlib.sha256(normalizado.encode("utf-8")).hexdigest()


def proxy_confiavel(valor):
    try:
        endereco = ipaddress.ip_address(valor)
        return any(endereco in ipaddress.ip_network(rede, strict=False) for rede in settings.SISMOD_TRUSTED_PROXY_CIDRS)
    except ValueError:
        return False


def endereco_cliente(request):
    valor = request.META.get("REMOTE_ADDR", "")
    if proxy_confiavel(valor):
        cadeia = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
        for item in reversed(cadeia):
            if not proxy_confiavel(valor):
                break
            try:
                valor = str(ipaddress.ip_address(item.strip()))
            except ValueError:
                return None
    try:
        return str(ipaddress.ip_address(valor))
    except ValueError:
        return None


def esta_bloqueado(request, usuario):
    agora = timezone.now()
    janela = agora - timezone.timedelta(seconds=settings.SISMOD_LOGIN_WINDOW_SECONDS)
    bloqueio = agora - timezone.timedelta(seconds=settings.SISMOD_LOGIN_BLOCK_SECONDS)
    consulta = TentativaLogin.objects.filter(ocorrida_em__gte=min(janela, bloqueio))
    for filtro, limite in (
        ({"identificador_hash": _hash_identificador(usuario)}, settings.SISMOD_LOGIN_MAX_FAILURES),
        ({"endereco_ip": endereco_cliente(request)}, settings.SISMOD_LOGIN_IP_MAX_FAILURES),
    ):
        falhas = list(consulta.filter(**filtro).order_by("-ocorrida_em")[:max(1, limite)])
        if len(falhas) >= max(1, limite) and falhas[0].ocorrida_em >= bloqueio:
            return True
    return False


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
        identificador_hash=identificador, ocorrida_em__gte=janela
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
    ).delete()
