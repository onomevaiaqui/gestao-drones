import socket
import struct
from pathlib import Path

from django.conf import settings


EXTENSOES_NEGADAS = {
    ".exe", ".dll", ".com", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".jse",
    ".msi", ".scr", ".hta", ".jar", ".sh", ".php", ".py",
}
ASSINATURAS_EXECUTAVEIS = (b"MZ", b"\x7fELF", b"#!")


class ArquivoInseguro(ValueError):
    pass


def verificar_arquivo_basico(arquivo):
    extensao = Path(arquivo.name or "").suffix.casefold()
    if extensao in EXTENSOES_NEGADAS:
        raise ArquivoInseguro("O tipo de arquivo enviado não é permitido.")
    posicao = arquivo.tell()
    arquivo.seek(0)
    inicio = arquivo.read(4)
    arquivo.seek(posicao)
    if any(inicio.startswith(assinatura) for assinatura in ASSINATURAS_EXECUTAVEIS):
        raise ArquivoInseguro("O conteúdo executável não é permitido.")


def verificar_clamav(arquivo):
    if not settings.SISMOD_CLAMAV_HOST:
        if settings.SISMOD_CLAMAV_REQUIRED:
            raise ArquivoInseguro("A inspeção antivírus obrigatória está indisponível.")
        return
    posicao = arquivo.tell()
    try:
        if arquivo.size > settings.SISMOD_CLAMAV_MAX_BYTES:
            raise ArquivoInseguro("O arquivo excede o limite de inspeção antivírus; não foi aceito.")
        arquivo.seek(0)
        with socket.create_connection((settings.SISMOD_CLAMAV_HOST, settings.SISMOD_CLAMAV_PORT), timeout=8) as conexao:
            conexao.sendall(b"zINSTREAM\0")
            total = 0
            while True:
                bloco = arquivo.read(1024 * 64)
                if not bloco:
                    break
                total += len(bloco)
                if total > settings.SISMOD_CLAMAV_MAX_BYTES:
                    raise ArquivoInseguro("O arquivo excede o limite de inspeção antivírus; não foi aceito.")
                conexao.sendall(struct.pack(">I", len(bloco)) + bloco)
            conexao.sendall(struct.pack(">I", 0))
            resposta = b""
            while b"\0" not in resposta and len(resposta) < 4096:
                parte = conexao.recv(4096 - len(resposta))
                if not parte:
                    break
                resposta += parte
        if b"FOUND" in resposta:
            raise ArquivoInseguro("O arquivo foi recusado pela inspeção antivírus.")
        if resposta != b"stream: OK\0":
            raise ArquivoInseguro("A inspeção antivírus não pôde confirmar o arquivo.")
    except (OSError, socket.timeout) as erro:
        if settings.SISMOD_CLAMAV_REQUIRED:
            raise ArquivoInseguro("A inspeção antivírus obrigatória está indisponível.") from erro
    finally:
        arquivo.seek(posicao)


def verificar_uploads(arquivos):
    for arquivo in arquivos:
        verificar_arquivo_basico(arquivo)
        verificar_clamav(arquivo)
