import base64
import hashlib
import hmac
import secrets
import struct
import time
from io import BytesIO
from urllib.parse import quote

import qrcode
from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password


def gerar_segredo():
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _fernet():
    chave = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest())
    return Fernet(chave)


def criptografar_segredo(segredo):
    return _fernet().encrypt(segredo.encode("ascii")).decode("ascii")


def descriptografar_segredo(valor):
    return _fernet().decrypt(valor.encode("ascii")).decode("ascii")


def codigo_totp(segredo, instante=None):
    instante = int(instante if instante is not None else time.time())
    preenchido = segredo + "=" * ((8 - len(segredo) % 8) % 8)
    chave = base64.b32decode(preenchido, casefold=True)
    contador = struct.pack(">Q", instante // 30)
    resumo = hmac.new(chave, contador, hashlib.sha1).digest()
    deslocamento = resumo[-1] & 0x0F
    numero = struct.unpack(">I", resumo[deslocamento:deslocamento + 4])[0] & 0x7FFFFFFF
    return f"{numero % 1_000_000:06d}"


def validar_totp(segredo, codigo, instante=None):
    return contador_totp_valido(segredo, codigo, instante) is not None


def contador_totp_valido(segredo, codigo, instante=None):
    agora = int(instante if instante is not None else time.time())
    codigo = str(codigo or "").strip().replace(" ", "")
    if len(codigo) != 6 or not codigo.isascii() or not codigo.isdigit():
        return None
    for desvio in (1, 0, -1):
        instante_candidato = agora + desvio * 30
        if hmac.compare_digest(codigo_totp(segredo, instante_candidato), codigo):
            return instante_candidato // 30
    return None


def consumir_totp(configuracao, codigo, instante=None):
    contador = contador_totp_valido(
        descriptografar_segredo(configuracao.segredo_mfa_criptografado), codigo, instante
    )
    if contador is None:
        return False
    # A atualização condicional impede dois pedidos de consumirem o mesmo código.
    return bool(type(configuracao).objects.filter(
        pk=configuracao.pk, mfa_ativo=True,
        segredo_mfa_criptografado=configuracao.segredo_mfa_criptografado,
        ultimo_contador_mfa__lt=contador,
    ).update(ultimo_contador_mfa=contador))


def uri_totp(usuario, segredo):
    emissor = settings.SISMOD_MFA_ISSUER
    rotulo = quote(f"{emissor}:{usuario.get_username()}")
    return f"otpauth://totp/{rotulo}?secret={segredo}&issuer={quote(emissor)}&algorithm=SHA1&digits=6&period=30"


def qr_data_uri(usuario, segredo):
    imagem = qrcode.make(uri_totp(usuario, segredo))
    buffer = BytesIO()
    imagem.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def gerar_codigos_recuperacao(quantidade=8):
    codigos = [f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}" for _ in range(quantidade)]
    return codigos, [make_password(codigo) for codigo in codigos]


def consumir_codigo_recuperacao(configuracao, codigo):
    originais = list(configuracao.codigos_recuperacao)
    for indice, valor in enumerate(originais):
        if check_password(str(codigo or "").strip().upper(), valor):
            restantes = originais[:indice] + originais[indice + 1:]
            # Compare-and-swap também funciona no SQLite, sem depender de row locks.
            return bool(type(configuracao).objects.filter(
                pk=configuracao.pk, mfa_ativo=True,
                codigos_recuperacao=originais,
            ).update(codigos_recuperacao=restantes))
    return False
