import base64
import json
from dataclasses import dataclass
from datetime import date, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils.dateparse import parse_date

from .models import InstalacaoSISMOD, LicencaSISMOD


class ErroLicenca(ValueError):
    pass


@dataclass(frozen=True)
class EstadoLicenca:
    codigo: str
    titulo: str
    mensagem: str
    permite_alteracoes: bool
    dias_restantes: int | None = None
    licenca: object | None = None


def _canonico(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def validar_arquivo(dados, instalacao=None):
    try:
        documento = json.loads(dados.decode("utf-8") if isinstance(dados, bytes) else dados)
        payload = documento["payload"]
        assinatura = base64.b64decode(documento["signature"], validate=True)
        chave = base64.b64decode(settings.SISMOD_LICENSE_PUBLIC_KEY, validate=True)
        Ed25519PublicKey.from_public_bytes(chave).verify(assinatura, _canonico(payload))
    except (KeyError, TypeError, ValueError, InvalidSignature) as exc:
        raise ErroLicenca("Arquivo de licença inválido ou assinatura não reconhecida.") from exc
    obrigatorios = ("license_id", "installation_id", "company_name", "issued_at", "expires_at")
    if any(not payload.get(campo) for campo in obrigatorios):
        raise ErroLicenca("A licença não contém todos os campos obrigatórios.")
    instalacao = instalacao or InstalacaoSISMOD.atual()
    if str(instalacao.identificador) != str(payload["installation_id"]):
        raise ErroLicenca("Esta licença pertence a outra instalação do SISMOD.")
    emitida_em, valida_ate = parse_date(payload["issued_at"]), parse_date(payload["expires_at"])
    if not emitida_em or not valida_ate or valida_ate < emitida_em:
        raise ErroLicenca("O período de validade da licença é inválido.")
    return payload, documento["signature"]


@transaction.atomic
def ativar_licenca(dados, usuario):
    instalacao = InstalacaoSISMOD.atual()
    payload, assinatura = validar_arquivo(dados, instalacao)
    LicencaSISMOD.objects.filter(ativa=True).update(ativa=False)
    licenca, _ = LicencaSISMOD.objects.update_or_create(
        identificador=payload["license_id"],
        defaults={
            "instalacao": instalacao,
            "empresa_nome": payload["company_name"],
            "empresa_cnpj": payload.get("company_cnpj", ""),
            "emitida_em": parse_date(payload["issued_at"]),
            "valida_ate": parse_date(payload["expires_at"]),
            "tolerancia_dias": max(0, min(int(payload.get("grace_days", 15)), 90)),
            "recursos": payload.get("features", ["core"]),
            "conteudo": payload,
            "assinatura": assinatura,
            "ativa": True,
            "ativada_por": usuario,
        },
    )
    return licenca


def estado_licenca(hoje=None):
    if not settings.SISMOD_LICENSE_ENFORCEMENT:
        return EstadoLicenca("desativada", "Licenciamento desativado", "Ambiente sem bloqueio comercial.", True)
    if not settings.SISMOD_LICENSE_PUBLIC_KEY:
        return EstadoLicenca("configuracao", "Licenciamento não configurado", "A chave pública da licença não foi configurada.", False)
    try:
        licenca = LicencaSISMOD.objects.filter(ativa=True).first()
    except DatabaseError:
        return EstadoLicenca("configuracao", "Banco não preparado", "Execute as migrações do sistema.", False)
    if not licenca:
        return EstadoLicenca("ausente", "Licença não ativada", "Envie a licença anual desta instalação.", False)
    try:
        validar_arquivo(json.dumps({"payload": licenca.conteudo, "signature": licenca.assinatura}), licenca.instalacao)
    except ErroLicenca:
        return EstadoLicenca("invalida", "Licença inválida", "A assinatura ou os dados da licença foram alterados.", False, licenca=licenca)
    hoje = hoje or date.today()
    restantes = (licenca.valida_ate - hoje).days
    if restantes >= 0:
        codigo = "expirando" if restantes <= 60 else "ativa"
        mensagem = f"A licença vence em {restantes} dia(s)." if codigo == "expirando" else "Licença anual válida."
        return EstadoLicenca(codigo, "Licença válida", mensagem, True, restantes, licenca)
    fim_tolerancia = licenca.valida_ate + timedelta(days=licenca.tolerancia_dias)
    tolerancia = (fim_tolerancia - hoje).days
    if tolerancia >= 0:
        return EstadoLicenca("tolerancia", "Licença em tolerância", f"Renove em até {tolerancia} dia(s).", True, tolerancia, licenca)
    return EstadoLicenca("expirada", "Licença expirada", "Novos registros estão bloqueados; consultas e exportações permanecem disponíveis.", False, tolerancia, licenca)
