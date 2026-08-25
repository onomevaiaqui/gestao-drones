import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import ImportacaoLog, Voo
from .telemetria_forms import ImportacaoLogForm
from .telemetria_service import processar_importacao
from .views import _base_context, usuario_e_admin


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
    voos = _voos_permitidos(request.user).order_by("-data", "-hora_inicio")
    form = ImportacaoLogForm(request.POST or None, request.FILES or None, voos=voos)
    if form.is_valid():
        importacao = form.save(commit=False)
        importacao.nome_original = form.cleaned_data["arquivo"].name[:255]
        importacao.formato = importacao.nome_original.rsplit(".", 1)[-1].lower()
        importacao.importado_por = request.user
        importacao.save()
        try:
            processar_importacao(importacao, atualizar_voo=form.cleaned_data["atualizar_voo"])
            messages.success(request, f"Log importado: {importacao.total_pontos} pontos reconhecidos.")
        except Exception as exc:
            importacao.status = "erro"
            importacao.mensagem_erro = str(exc)[:2000]
            importacao.save(update_fields=["status", "mensagem_erro"])
            messages.error(request, f"Não foi possível processar o log: {exc}")
        return redirect("telemetria_detalhe", pk=importacao.pk)
    ctx = {"form": form}
    ctx.update(_base_context(request))
    return render(request, "telemetria/importar.html", ctx)


@login_required
def telemetria_detalhe(request, pk):
    importacao = get_object_or_404(_importacoes_permitidas(request.user), pk=pk)
    pontos = list(importacao.pontos.all())
    rota = [
        {"lat": float(p.latitude), "lon": float(p.longitude), "alt": float(p.altitude_m) if p.altitude_m is not None else None, "battery": p.bateria_percentual}
        for p in pontos if p.latitude is not None and p.longitude is not None
    ]
    duracao = None
    if importacao.duracao_segundos is not None:
        duracao = f"{importacao.duracao_segundos // 60}min {importacao.duracao_segundos % 60:02d}s"
    ctx = {"importacao": importacao, "pontos": pontos[:500], "rota": rota, "duracao_formatada": duracao}
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
