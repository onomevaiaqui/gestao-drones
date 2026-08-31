import csv
from collections import defaultdict
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Bateria, Componente, ImportacaoLog, Voo
from .telemetria_forms import ImportacaoLogForm
from .telemetria_service import processar_importacao
from .views import _base_context, _sincronizar_voo_com_calendario, usuario_e_admin, usuario_e_coordenador, usuario_tem_visao_global


def _voos_permitidos(user):
    qs = Voo.objects.select_related("piloto", "drone").annotate(total_logs=Count("importacoes_log"))
    if not usuario_tem_visao_global(user):
        qs = qs.filter(piloto__user=user)
    return qs


def _importacoes_permitidas(user):
    qs = ImportacaoLog.objects.select_related("voo__piloto", "voo__drone", "importado_por")
    if not usuario_tem_visao_global(user):
        qs = qs.filter(voo__piloto__user=user)
    return qs


def _resumir_pontos_por_minuto(pontos):
    grupos = defaultdict(list)
    for ponto in pontos:
        if ponto.segundos is not None:
            chave = int(float(ponto.segundos) // 60)
        elif ponto.instante:
            local = timezone.localtime(ponto.instante)
            chave = local.hour * 60 + local.minute
        else:
            chave = ponto.indice // 60
        grupos[chave].append(ponto)

    resumo = []
    termos_erro = ("erro", "error", "falha", "critical", "crítico", "critico", "perda", "lost", "desconect", "colisão", "colisao", "queda", "motor")
    for minuto, itens in sorted(grupos.items()):
        def media(campo):
            valores = [float(getattr(item, campo)) for item in itens if getattr(item, campo) is not None]
            return round(sum(valores) / len(valores), 2) if valores else None

        alertas = list(dict.fromkeys(item.alerta.strip() for item in itens if item.alerta.strip()))
        bateria = min((item.bateria_percentual for item in itens if item.bateria_percentual is not None), default=None)
        sinal = min((item.sinal_percentual for item in itens if item.sinal_percentual is not None), default=None)
        satelites = min((item.satelites for item in itens if item.satelites is not None), default=None)
        texto_alertas = " · ".join(alertas)
        erro = (
            (bateria is not None and bateria <= 15)
            or (sinal is not None and 0 < sinal <= 20)
            or (satelites is not None and satelites <= 5)
            or any(termo in texto_alertas.lower() for termo in termos_erro)
        )
        atencao = bool(texto_alertas) or (bateria is not None and bateria <= 30) or (sinal is not None and 0 < sinal <= 50) or (satelites is not None and satelites <= 9)
        status = "erro" if erro else "atencao" if atencao else "normal"
        motivos = []
        if texto_alertas:
            motivos.append(f"Alerta registrado pelo drone: {texto_alertas}")
        if bateria is not None and bateria <= 15:
            motivos.append(f"Bateria em nível crítico: {bateria}%.")
        elif bateria is not None and bateria <= 30:
            motivos.append(f"Bateria baixa: {bateria}%.")
        if sinal is not None and 0 < sinal <= 20:
            motivos.append(f"Sinal em nível crítico: {sinal}%.")
        elif sinal is not None and sinal <= 50 and sinal > 0:
            motivos.append(f"Sinal reduzido: {sinal}%.")
        if satelites is not None and satelites <= 5:
            motivos.append(f"Quantidade crítica de satélites conectados: {satelites}.")
        elif satelites is not None and satelites <= 9:
            motivos.append(f"Poucos satélites conectados: {satelites}.")
        if not motivos:
            motivos.append("Nenhuma anormalidade detectada nos parâmetros disponíveis.")
        instante = next((item.instante for item in itens if item.instante), None)
        resumo.append({
            "minuto": minuto,
            "instante": instante,
            "latitude": media("latitude"),
            "longitude": media("longitude"),
            "altitude": media("altitude_m"),
            "velocidade": media("velocidade_ms"),
            "bateria": bateria,
            "satelites": satelites,
            "sinal": sinal,
            "alerta": texto_alertas,
            "status": status,
            "status_label": {"erro": "Erro", "atencao": "Atenção", "normal": "Normal"}[status],
            "motivos": motivos,
        })
    return resumo


@login_required
def telemetria_lista(request):
    qs = _importacoes_permitidas(request.user)
    seriais_detectados = set(
        qs.filter(status="concluida").exclude(bateria_serial_detectada="")
        .values_list("bateria_serial_detectada", flat=True)
    )
    seriais_cadastrados = set(
        Bateria.objects.filter(numero_serie__in=seriais_detectados)
        .values_list("numero_serie", flat=True)
    )
    baterias_novas = []
    for serial in sorted(seriais_detectados - seriais_cadastrados):
        origem = qs.filter(bateria_serial_detectada=serial).select_related("voo__drone").first()
        if origem:
            baterias_novas.append({"serial": serial, "importacao": origem, "drone": origem.voo.drone})
    resumo = {
        "total": qs.count(), "concluidas": qs.filter(status="concluida").count(),
        "erros": qs.filter(status="erro").count(),
        "pontos": sum(qs.values_list("total_pontos", flat=True)),
    }
    ctx = {"importacoes": qs, "resumo": resumo, "baterias_novas": baterias_novas}
    ctx.update(_base_context(request))
    return render(request, "telemetria/lista.html", ctx)


@login_required
def telemetria_importar(request):
    if usuario_e_coordenador(request.user):
        messages.info(request, "No perfil de coordenador, a telemetria fica disponível somente para consulta.")
        return redirect("telemetria_lista")
    voos = _voos_permitidos(request.user).order_by("-data", "-hora_inicio", "-criado_em")
    form = ImportacaoLogForm(request.POST or None, request.FILES or None, voos=voos)
    if form.is_valid():
        voo_base = form.cleaned_data["voo"]
        arquivos = form.cleaned_data["arquivos"]
        importacoes, sucessos, erros = [], 0, 0
        for arquivo in arquivos:
            extensao = Path(arquivo.name).suffix.lower().lstrip(".")
            importacao = ImportacaoLog.objects.create(
                voo=voo_base, arquivo=arquivo, nome_original=arquivo.name[:255],
                formato=extensao or "autel-fr", importado_por=request.user,
            )
            importacoes.append(importacao)
            try:
                processar_importacao(importacao, atualizar_voo=True)
                _sincronizar_voo_com_calendario(importacao.voo, request.user)
                sucessos += 1
            except Exception as exc:
                importacao.status = "erro"
                importacao.mensagem_erro = str(exc)[:2000]
                importacao.save(update_fields=["status", "mensagem_erro"])
                erros += 1
        if len(importacoes) == 1:
            importacao = importacoes[0]
            if sucessos:
                messages.success(request, f"Log importado: {importacao.total_pontos} pontos reconhecidos.")
            else:
                messages.error(request, f"Não foi possível processar o log: {importacao.mensagem_erro}")
            return redirect("telemetria_detalhe", pk=importacao.pk)
        if sucessos:
            messages.success(request, f"Pasta processada: {sucessos} log(s) importado(s) com sucesso.")
        if erros:
            messages.error(request, f"{erros} arquivo(s) apresentaram erro. Abra os itens para consultar os detalhes.")
        return redirect("telemetria_lista")
    ctx = {"form": form}
    ctx.update(_base_context(request))
    return render(request, "telemetria/importar.html", ctx)


@login_required
def telemetria_detalhe(request, pk):
    importacao = get_object_or_404(_importacoes_permitidas(request.user), pk=pk)
    pontos = list(importacao.pontos.all())
    rota = [
        {
            "lat": float(p.latitude), "lon": float(p.longitude),
            "alt": float(p.altitude_m) if p.altitude_m is not None else None,
            "battery": p.bateria_percentual, "seconds": float(p.segundos) if p.segundos is not None else None,
            "alert": p.alerta,
        }
        for p in pontos if p.latitude is not None and p.longitude is not None
    ]
    alertas_mapa, alerta_anterior = [], ""
    for ponto in rota:
        alerta_atual = (ponto["alert"] or "").strip()
        if alerta_atual and alerta_atual != alerta_anterior:
            alertas_mapa.append(ponto)
        alerta_anterior = alerta_atual
    duracao = None
    if importacao.duracao_segundos is not None:
        horas, restante = divmod(importacao.duracao_segundos, 3600)
        minutos, segundos = divmod(restante, 60)
        duracao = f"{horas:02d}h {minutos:02d}min {segundos:02d}s"
    data_voo = timezone.localtime(importacao.inicio_registro).date() if importacao.inicio_registro else importacao.voo.data
    bateria_detectada = None
    if importacao.bateria_serial_detectada:
        bateria_detectada = Bateria.objects.filter(
            numero_serie=importacao.bateria_serial_detectada
        ).first()
    from .compatibilidade_componentes import componente_exige_cadastro
    componentes_detectados = []
    for detectado in importacao.componentes_detectados or []:
        serial = str(detectado.get("serial") or "").strip()
        cadastrado = Componente.objects.filter(numero_serie=serial).first() if serial else None
        exige_cadastro, motivo_filtro = componente_exige_cadastro(
            importacao.voo.drone, detectado, importacao.drone_modelo_detectado
        )
        componentes_detectados.append({
            **detectado, "cadastrado": cadastrado,
            "exige_cadastro": exige_cadastro, "motivo_filtro": motivo_filtro,
        })
    ctx = {
        "importacao": importacao, "amostra_minutos": _resumir_pontos_por_minuto(pontos), "rota": rota,
        "alertas_mapa": alertas_mapa, "duracao_formatada": duracao,
        "data_voo": data_voo,
        "bateria_detectada": bateria_detectada,
        "bateria_serial_nova": bool(importacao.bateria_serial_detectada and not bateria_detectada),
        "componentes_log": componentes_detectados,
        "componentes_novos": [
            item for item in componentes_detectados
            if item["exige_cadastro"] and not item["cadastrado"]
        ],
    }
    ctx.update(_base_context(request))
    return render(request, "telemetria/detalhe.html", ctx)


@login_required
@require_POST
def telemetria_excluir(request, pk):
    if usuario_e_coordenador(request.user):
        messages.info(request, "No perfil de coordenador, a telemetria fica disponível somente para consulta.")
        return redirect("telemetria_lista")
    importacao = get_object_or_404(_importacoes_permitidas(request.user), pk=pk)
    if importacao.arquivo:
        importacao.arquivo.delete(save=False)
    importacao.delete()
    messages.success(request, "Importação excluída.")
    return redirect("telemetria_lista")


@login_required
def telemetria_modelo_csv(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="modelo_telemetria.csv"'
    writer = csv.writer(response)
    writer.writerow(["timestamp", "latitude", "longitude", "altitude_m", "speed_ms", "battery_percent", "satellites", "signal_percent", "warning"])
    writer.writerow(["2026-08-24T10:00:00-03:00", "-25.5163000", "-54.5854000", "12.5", "3.2", "98", "18", "100", ""])
    return response
