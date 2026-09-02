"""Armazenamento de mídias da Dock usando o backend padrão do Django."""

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from .models import DJIDockArquivo


EXTENSOES_PERMITIDAS = {"jpg", "jpeg", "png", "tif", "tiff", "mp4", "mov", "obs", "rtk", "mrk", "nav", "dat", "log", "zip"}
LIMITE_BYTES = 5 * 1024 * 1024 * 1024


def diagnostico_armazenamento():
    tipo = settings.SISMOD_MEDIA_STORAGE
    itens = {"tipo": tipo, "configurado": True, "mensagem": "Armazenamento local disponível."}
    if tipo in ("s3", "minio"):
        opcoes = settings.STORAGES["default"]["OPTIONS"]
        faltantes = [chave for chave in ("bucket_name", "access_key", "secret_key") if not opcoes.get(chave)]
        if tipo == "minio" and not opcoes.get("endpoint_url"):
            faltantes.append("endpoint_url")
        itens["configurado"] = not faltantes
        itens["mensagem"] = "Configuração pronta." if not faltantes else "Campos ausentes: " + ", ".join(faltantes)
    return itens


def armazenar_upload_missao(missao, upload):
    extensao = Path(upload.name).suffix.lower().lstrip(".")
    if extensao not in EXTENSOES_PERMITIDAS:
        raise ValueError("Tipo de arquivo não permitido para mídia da Dock.")
    if upload.size > LIMITE_BYTES:
        raise ValueError("O arquivo excede o limite de 5 GB.")
    digest = sha256()
    for trecho in upload.chunks():
        digest.update(trecho)
    upload.seek(0)
    item = DJIDockArquivo(
        missao=missao, object_key=f"manual/{uuid4()}/{Path(upload.name).name}",
        nome=Path(upload.name).name[:255], extensao=extensao,
        backend=settings.SISMOD_MEDIA_STORAGE, status="recebendo",
        tamanho_bytes=upload.size, checksum=digest.hexdigest(),
    )
    try:
        item.arquivo.save(item.nome, upload, save=False)
        item.status = "concluido"
        item.armazenado_em = timezone.now()
        item.save()
    except Exception as erro:
        item.status = "erro"
        item.mensagem_erro = str(erro)[:255]
        item.save()
        raise
    return item
