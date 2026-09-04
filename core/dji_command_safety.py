"""Autorização e diagnóstico de comandos; este módulo nunca publica MQTT."""

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import DJIDockComando
from .permissoes import usuario_e_admin


@transaction.atomic
def autorizar_intencao(comando, usuario):
    if not usuario_e_admin(usuario):
        raise PermissionError("Somente o administrador pode confirmar comandos remotos.")
    comando = DJIDockComando.objects.select_for_update().get(pk=comando.pk)
    if comando.status in {"enviado", "confirmado", "erro", "cancelado"}:
        raise ValueError("Este comando não pode mais ser autorizado.")
    if comando.expira_em and comando.expira_em <= timezone.now():
        raise ValueError("Este comando expirou e deve ser criado novamente.")
    limite = timezone.now() - timezone.timedelta(seconds=settings.DJI_DOCK_COMMAND_RATE_LIMIT_SECONDS)
    if DJIDockComando.objects.filter(dock=comando.dock, autorizado_em__gte=limite).exclude(pk=comando.pk).exists():
        raise ValueError("Aguarde alguns segundos antes de autorizar outro comando nesta estação.")
    comando.autorizado_por = usuario
    comando.autorizado_em = timezone.now()
    comando.mensagem = "Confirmação humana registrada; publicação física permanece sujeita às travas técnicas."
    comando.save(update_fields=["autorizado_por", "autorizado_em", "mensagem"])
    return comando


def diagnosticar_publicacao(comando, *, runtime_resolvido=False):
    """Explica por que uma intenção ainda não poderia ser publicada."""
    bloqueios = []
    if not settings.DJI_DOCK_ENABLED:
        bloqueios.append("Integração da Dock desativada.")
    if not settings.DJI_DOCK_COMMANDS_ENABLED:
        bloqueios.append("Comandos remotos desativados.")
    if not settings.DJI_DOCK_PUBLISHER_ENABLED:
        bloqueios.append("Publicador MQTT desativado.")
    if settings.DJI_DOCK_EMERGENCY_STOP:
        bloqueios.append("Parada de emergência ativa.")
    if not comando.dock.ativo:
        bloqueios.append("Estação desativada no cadastro.")
    if not comando.dock.online:
        bloqueios.append("Estação sem estado online confirmado.")
    if comando.critico and not comando.autorizado_em:
        bloqueios.append("Confirmação humana pendente.")
    if comando.expira_em and comando.expira_em <= timezone.now():
        bloqueios.append("Comando expirado.")
    previa = comando.mensagem_mqtt or {}
    if not previa:
        bloqueios.append("Mensagem MQTT ainda não foi montada.")
    if not runtime_resolvido:
        for campo in previa.get("campos_runtime", []):
            bloqueios.append(f"Campo seguro de runtime pendente: {campo}.")
    if comando.status not in {"bloqueado", "pendente"}:
        bloqueios.append(f"Situação incompatível: {comando.get_status_display()}.")
    return {"apto": not bloqueios, "bloqueios": bloqueios}
