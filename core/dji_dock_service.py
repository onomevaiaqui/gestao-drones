"""Ingestão segura e normalização inicial de mensagens da DJI Dock."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.conf import settings
from django.utils import timezone

from .models import DJIDock, DJIDockArquivo, DJIDockComando, DJIDockEvento, DJIDockMissao, Drone


CHAVES_SENSIVEIS = {"device_secret", "secret", "nonce", "password", "token", "app_key", "app_license"}


def remover_segredos(valor):
    """Remove credenciais recursivamente antes de qualquer persistência."""
    if isinstance(valor, dict):
        return {
            chave: "[REMOVIDO]" if str(chave).lower() in CHAVES_SENSIVEIS else remover_segredos(conteudo)
            for chave, conteudo in valor.items()
        }
    if isinstance(valor, list):
        return [remover_segredos(item) for item in valor]
    return valor


def serial_do_topico(topico):
    partes = [parte for parte in str(topico or "").split("/") if parte]
    if "product" in partes:
        indice = partes.index("product")
        if len(partes) > indice + 1:
            return partes[indice + 1][:100]
    return ""


def _decimal(valor):
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _nivel(dados):
    if dados.get("emergency_stop_state") not in (None, 0, "0", False):
        return "critico"
    if dados.get("rainfall") not in (None, 0, "0", False) or dados.get("cover_state") in (2, "2"):
        return "atencao"
    return "info"


def _inteiro(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _detectar_payload(dados):
    candidatos = dados.get("payloads") or dados.get("payload_info") or []
    if isinstance(candidatos, dict):
        candidatos = [candidatos]
    if not isinstance(candidatos, list):
        return {}
    item = next((valor for valor in candidatos if isinstance(valor, dict)), {})
    return {
        "tipo": _inteiro(item.get("type")),
        "subtipo": _inteiro(item.get("sub_type")),
        "posicao": _inteiro(item.get("gimbalindex") if item.get("gimbalindex") is not None else item.get("gimbal_index")),
    }


@transaction.atomic
def processar_mensagem_dock(topico, payload, *, origem="cloud_api"):
    """Persiste uma mensagem OSD/event e devolve (dock, evento, criado)."""
    if not isinstance(payload, dict):
        raise ValueError("A mensagem da Dock deve ser um objeto JSON.")
    serial = serial_do_topico(topico) or str(payload.get("gateway_sn") or payload.get("sn") or "").strip()[:100]
    if not serial:
        raise ValueError("Não foi possível identificar o número de série da Dock.")

    payload = remover_segredos(payload)
    dados = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    dock, _ = DJIDock.objects.get_or_create(
        numero_serie=serial,
        defaults={"nome": f"DJI Dock {serial[-6:]}", "modo": origem},
    )
    subdispositivos = dados.get("sub_devices") if isinstance(dados.get("sub_devices"), list) else []
    serial_topologia = next(
        (str(item.get("sn") or "").strip() for item in subdispositivos if isinstance(item, dict) and item.get("sn")),
        "",
    )
    aeronave_sn = str(dados.get("sub_device_sn") or dados.get("aircraft_sn") or serial_topologia or "").strip()
    aeronave_topologia = next((item for item in subdispositivos if isinstance(item, dict) and item.get("sn")), {})
    if aeronave_topologia:
        dock.aeronave_tipo_dji = _inteiro(aeronave_topologia.get("type"))
        dock.aeronave_subtipo_dji = _inteiro(aeronave_topologia.get("sub_type"))
    payload_detectado = _detectar_payload(dados)
    if payload_detectado.get("tipo") is not None:
        dock.payload_tipo_dji = payload_detectado["tipo"]
        dock.payload_subtipo_dji = payload_detectado["subtipo"]
        dock.payload_posicao_dji = payload_detectado["posicao"]
    if aeronave_sn and not dock.drone_id:
        dock.drone = Drone.objects.filter(numero_serie__iexact=aeronave_sn).first()

    latitude = _decimal(dados.get("latitude"))
    longitude = _decimal(dados.get("longitude"))
    if latitude is not None and -90 <= latitude <= 90:
        dock.latitude = latitude
    if longitude is not None and -180 <= longitude <= 180:
        dock.longitude = longitude
    dock.online = True
    dock.status = "alerta" if _nivel(dados) != "info" else "online"
    dock.modo = origem
    dock.ultima_telemetria = dados
    dock.ultimo_contato_em = timezone.now()
    dock.save()

    identificador = str(payload.get("tid") or payload.get("bid") or payload.get("id") or "")[:120]
    tipo = str(payload.get("method") or topico.rsplit("/", 1)[-1] or "telemetria")[:80]
    nivel = _nivel(dados)
    mensagem = "Telemetria recebida"
    if nivel == "critico":
        mensagem = "A Dock informou uma condição crítica"
    elif nivel == "atencao":
        mensagem = "A Dock informou uma condição que exige atenção"
    evento, criado = DJIDockEvento.objects.get_or_create(
        dock=dock,
        identificador_externo=identificador,
        defaults={"topico": str(topico)[:255], "tipo": tipo, "nivel": nivel, "mensagem": mensagem, "dados": dados},
    ) if identificador else (DJIDockEvento.objects.create(
        dock=dock, topico=str(topico)[:255], tipo=tipo, nivel=nivel,
        mensagem=mensagem, dados=dados,
    ), True)
    if criado:
        _processar_retorno_comando(dock, tipo, topico, payload, dados)
        _processar_retorno_missao(dock, tipo, dados)
    return dock, evento, criado


def _conteudo_saida(dados):
    saida = dados.get("output") if isinstance(dados.get("output"), dict) else dados
    return saida


def _processar_retorno_comando(dock, metodo, topico, payload, dados):
    """Correlaciona services_reply sem executar ou publicar qualquer comando."""
    if not str(topico).endswith("/services_reply"):
        return
    identificador = str(payload.get("tid") or "").strip()
    if not identificador:
        return
    comando = DJIDockComando.objects.filter(dock=dock, identificador=identificador).first()
    if not comando:
        return
    resultado = _inteiro(dados.get("result"))
    comando.status = "confirmado" if resultado == 0 else "erro"
    comando.concluido_em = timezone.now()
    comando.mensagem = (
        f"Resposta DJI confirmada para {metodo}."
        if resultado == 0 else f"A DJI recusou {metodo}; código de retorno {resultado}."
    )
    comando.save(update_fields=["status", "concluido_em", "mensagem"])

    missao_id = comando.parametros.get("missao_id") if isinstance(comando.parametros, dict) else None
    if not missao_id:
        return
    missao = DJIDockMissao.objects.filter(dock=dock, pk=missao_id).first()
    if not missao:
        return
    if resultado != 0:
        missao.status = "erro"
    elif metodo == "flighttask_prepare":
        missao.status = "enviada"
    elif metodo == "flighttask_execute":
        missao.status = "executando"
        missao.iniciada_em = missao.iniciada_em or timezone.now()
    elif metodo == "flighttask_undo":
        missao.status = "cancelada"
        missao.concluida_em = timezone.now()
    missao.save()


def _processar_retorno_missao(dock, metodo, dados):
    saida = _conteudo_saida(dados)
    ext = saida.get("ext") if isinstance(saida.get("ext"), dict) else {}
    flight_id = str(saida.get("flight_id") or ext.get("flight_id") or "").strip()
    if metodo == "flighttask_ready":
        ids = dados.get("flight_ids") if isinstance(dados.get("flight_ids"), list) else []
        DJIDockMissao.objects.filter(dock=dock, identificador__in=ids).update(status="pronta")
        return
    if metodo == "flighttask_progress" and flight_id:
        missao = DJIDockMissao.objects.filter(dock=dock, identificador=flight_id).first()
        if not missao:
            return
        progresso = saida.get("progress") if isinstance(saida.get("progress"), dict) else {}
        percentual = max(0, min(100, _inteiro(progresso.get("percent")) or 0))
        status_dji = str(saida.get("status") or "")
        mapa = {
            "sent": "enviada", "in_progress": "executando", "paused": "pausada",
            "ok": "concluida", "partially_done": "concluida",
            "canceled": "cancelada", "rejected": "erro", "failed": "erro", "timeout": "erro",
        }
        missao.status = mapa.get(status_dji, missao.status)
        missao.progresso_percentual = percentual
        missao.etapa_atual = _inteiro(progresso.get("current_step"))
        missao.waypoint_atual = _inteiro(ext.get("current_waypoint_index"))
        missao.quantidade_midias = _inteiro(ext.get("media_count")) or missao.quantidade_midias
        missao.resultado_dji = remover_segredos(dados)
        if missao.status == "executando" and not missao.iniciada_em:
            missao.iniciada_em = timezone.now()
        if missao.status in ("concluida", "cancelada", "erro"):
            missao.concluida_em = timezone.now()
        missao.save()
        return
    if metodo == "file_upload_callback":
        arquivo = dados.get("file") if isinstance(dados.get("file"), dict) else {}
        ext_arquivo = arquivo.get("ext") if isinstance(arquivo.get("ext"), dict) else {}
        flight_id = str(ext_arquivo.get("flight_id") or flight_id).strip()
        missao = DJIDockMissao.objects.filter(dock=dock, identificador=flight_id).first()
        object_key = str(arquivo.get("object_key") or "").strip()
        if not missao or not object_key:
            return
        nome = str(arquivo.get("name") or object_key.rsplit("/", 1)[-1])[:255]
        DJIDockArquivo.objects.update_or_create(
            missao=missao, object_key=object_key[:500],
            defaults={
                "nome": nome, "caminho_remoto": str(arquivo.get("path") or "")[:500],
                "extensao": nome.rsplit(".", 1)[-1][:30] if "." in nome else "",
                "original": bool(ext_arquivo.get("is_original")),
                "metadados": remover_segredos({
                    "ext": ext_arquivo,
                    "metadata": arquivo.get("metadata") if isinstance(arquivo.get("metadata"), dict) else {},
                }),
            },
        )
        quantidade_catalogada = missao.arquivos.count()
        if quantidade_catalogada > missao.quantidade_midias:
            missao.quantidade_midias = quantidade_catalogada
            missao.save(update_fields=["quantidade_midias", "atualizada_em"])


def registrar_intencao_comando(dock, tipo, usuario, parametros=None):
    """Audita a intenção; não publica comandos enquanto a trava estiver fechada."""
    tipos = {valor for valor, _ in DJIDockComando.TIPO_CHOICES}
    if tipo not in tipos:
        raise ValueError("Tipo de comando da Dock inválido.")
    habilitado = settings.DJI_DOCK_ENABLED and settings.DJI_DOCK_COMMANDS_ENABLED
    return DJIDockComando.objects.create(
        dock=dock,
        tipo=tipo,
        parametros=remover_segredos(parametros or {}),
        critico=tipo in DJIDockComando.COMANDOS_CRITICOS,
        solicitado_por=usuario,
        status="pendente" if habilitado else "bloqueado",
        mensagem=(
            "Aguardando publicador MQTT e confirmação operacional."
            if habilitado else "Comandos físicos desativados por configuração."
        ),
    )


def validar_planejamento_missao(dock, planejamento):
    validacoes = []
    if not planejamento.area_geojson or planejamento.area_geojson.get("type") not in ("Polygon", "MultiPolygon"):
        validacoes.append({"nivel": "erro", "mensagem": "Planejamento sem área poligonal válida."})
    if not dock.drone_id:
        validacoes.append({"nivel": "erro", "mensagem": "A Dock não possui aeronave vinculada."})
    elif not dock.drone.numero_serie:
        validacoes.append({"nivel": "erro", "mensagem": "A aeronave vinculada não possui número de série."})
    if planejamento.altura_maxima_m > 120:
        validacoes.append({"nivel": "atencao", "mensagem": "Altitude planejada superior a 120 m; confirme as autorizações aplicáveis."})
    if planejamento.status_meteorologico in ("desfavoravel", "indisponivel"):
        validacoes.append({"nivel": "atencao", "mensagem": f"Meteorologia: {planejamento.get_status_meteorologico_display()}."})
    termos_pendentes = planejamento.termos_coordenacao.filter(data_assinatura__isnull=True).count()
    if termos_pendentes:
        validacoes.append({"nivel": "atencao", "mensagem": f"{termos_pendentes} Termo(s) de Coordenação sem data de assinatura."})
    if dock.aeronave_tipo_dji is None:
        validacoes.append({"nivel": "pendente", "mensagem": "Aguardando o código oficial da aeronave enviado pela topologia DJI."})
    if dock.payload_tipo_dji is None:
        validacoes.append({"nivel": "pendente", "mensagem": "Aguardando o código oficial do payload enviado pela telemetria DJI."})
    validacoes.append({"nivel": "pendente", "mensagem": "O pacote WPML deverá ser validado no DJI Pilot 2 antes de qualquer liberação operacional."})
    return validacoes


def preparar_missao(dock, planejamento, usuario):
    validacoes = validar_planejamento_missao(dock, planejamento)
    missao, _ = DJIDockMissao.objects.update_or_create(
        dock=dock,
        planejamento=planejamento,
        defaults={
            "altura_m": planejamento.altura_maxima_m,
            "status": "validacao",
            "validacoes": validacoes,
            "criada_por": usuario,
        },
    )
    return missao
