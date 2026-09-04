"""Inspeção na fronteira de persistência, inclusive fora de requisições HTTP."""
from django.core.files.storage import FileSystemStorage
from .upload_security import verificar_uploads


class InspecaoMixin:
    def _save(self, name, content):
        original = getattr(content, "name", None)
        try:
            content.name = name
            verificar_uploads([content])
        finally:
            content.name = original
        return super()._save(name, content)


class ArquivosLocaisSeguros(InspecaoMixin, FileSystemStorage):
    pass


# O backend S3 é carregado somente quando configurado, sem exigir boto3 no modo local.
def __getattr__(nome):
    if nome == "ArquivosS3Seguros":
        from storages.backends.s3 import S3Storage
        class ArquivosS3Seguros(InspecaoMixin, S3Storage):
            pass
        return ArquivosS3Seguros
    raise AttributeError(nome)
