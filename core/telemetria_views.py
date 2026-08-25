import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import ImportacaoLog, Voo
from .telemetria_forms import ImportacaoLogForm
from .telemetria_service import processar_importacao
from .views import _base_context, _sincronizar_voo_com_calendario, usuario_e_admin


def _voos_permitidos(user):
    qs = Voo.objects.select_related("piloto", "drone")
    if not usuario_e_admin(user):
        qs = qs.filter(piloto__user=user)
    return qs


def _importacoes_permitidas(user):
    qs = ImportacaoLog.objects.select_related("voo__piloto", "voo__drone", "importado_por")
    if not usuario_e_admin(user):
        qs = qs.filter(voo__piloto__user=user)
    return qs


@login_required
def telemetria_lista(request):
    qs = _importacoes_permitidas(request.user)
    resumo = {
        "total": qs.count(), "concluidas": qs.filter(status="concluida").count(),
        "erros": qs.filter(status="erro").count(),
        "pontos": sum(qs.values_list("total_pontos", flat=True)),
    }
    ctx = {"importacoes": qs, "resumo": resumo}
    ctx.update(_base_context(request))
    return render(request, "telemetria/lista.html", ctx)


@login_required
def telemetria_importar(request):
    voos = _voos_permitidos(request.user).order_by("-criado_em")
    form = ImportacaoLogForm(request.POST or None, request.FILES or None, voos=voos)
    if form.is_valid():
        voo_base = form.cleaned_data["voo"]
        arquivos = form.cleaned_data["arquivos"]
        importacoes, sucessos, erros = [], 0, 0
        for arquivo in arquivos:
            importacao = ImportacaoLog.objects.create(
                voo=voo_base, arquivo=arquivo, nome_original=arquivo.name[:255],
                formato=arquivo.name.rsplit(".", 1)[-1].lower(), importado_por=request.user,
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
    ctx = {
        "importacao": importacao, "pontos": pontos[:500], "rota": rota,
        "alertas_mapa": alertas_mapa, "duracao_formatada": duracao,
    }
    ctx.update(_base_context(request))
    return render(request, "telemetria/detalhe.html", ctx)


@login_required
@require_POST
def telemetria_excluir(request, pk):
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
