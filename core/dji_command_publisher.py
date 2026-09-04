"""Reserva e finaliza envios MQTT; a conexão é responsabilidade do comando executor."""

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .dji_command_safety import diagnosticar_publicacao
from .dji_video_runtime import resolver_previa_runtime
from .models import DJIDockComando


@transaction.atomic
def reservar_para_publicacao(comando_id):
    comando = DJIDockComando.objects.select_for_update().select_related("dock").get(pk=comando_id)
    if comando.status != "pendente":
        raise ValueError("Somente comandos pendentes podem ser publicados.")
    previa = resolver_previa_runtime(comando)
    diagnostico = diagnosticar_publicacao(comando, runtime_resolvido=not previa.get("campos_runtime"))
    if not diagnostico["apto"]:
        raise ValueError(" ".join(diagnostico["bloqueios"]))
    if not previa.get("pronto_para_publicar", True):
        raise ValueError("A mensagem ainda depende de dados seguros de runtime.")
    topico = previa.get("topic")
    payload = previa.get("payload")
    # Mantém compatibilidade com a prévia de missão, ainda sem envelope/tópico completo.
    if not topico or not isinstance(payload, dict):
        raise ValueError("A prévia MQTT não possui tópico e envelope completos.")
    comando.status = "processando"
    comando.mensagem = "Reservado pelo publicador; aguardando confirmação do broker."
    comando.save(update_fields=["status", "mensagem"])
    return comando, topico, payload


def concluir_publicacao(comando_id):
    comando = DJIDockComando.objects.filter(pk=comando_id, status="processando").first()
    if not comando:
        return
    DJIDockComando.objects.filter(pk=comando_id).update(
        status="enviado", enviado_em=timezone.now(), mensagem="Mensagem aceita pelo broker MQTT; aguardando retorno da estação."
    )
    transmissao_id = comando.parametros.get("transmissao_id")
    if transmissao_id and comando.tipo == "iniciar_stream":
        from .models import TransmissaoAoVivo
        TransmissaoAoVivo.objects.filter(pk=transmissao_id, status="preparada").update(status="ao_vivo", iniciada_em=timezone.now())
    elif transmissao_id and comando.tipo == "parar_stream":
        from .models import TransmissaoAoVivo
        TransmissaoAoVivo.objects.filter(pk=transmissao_id).exclude(status="finalizada").update(status="finalizada", finalizada_em=timezone.now())


def falhar_publicacao(comando_id, mensagem):
    DJIDockComando.objects.filter(pk=comando_id, status="processando").update(
        status="erro", concluido_em=timezone.now(), mensagem=str(mensagem)[:255]
    )
