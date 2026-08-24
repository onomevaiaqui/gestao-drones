from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .inspecao_forms import ExecucaoInspecaoForm, PlanoInspecaoForm
from .models import PlanoInspecao
from .views import _base_context, admin_required


@admin_required
def planos_inspecao(request):
    planos = list(PlanoInspecao.objects.select_related("drone", "bateria", "bateria__drone"))
    planos.sort(key=lambda p: ({"vencido": 0, "proximo": 1, "em_dia": 2, "inativo": 3}[p.situacao], -p.progresso))
    resumo = {
        "total": len(planos),
        "vencidos": sum(p.situacao == "vencido" for p in planos),
        "proximos": sum(p.situacao == "proximo" for p in planos),
        "em_dia": sum(p.situacao == "em_dia" for p in planos),
    }
    ctx = {"planos": planos, "resumo": resumo}
    ctx.update(_base_context(request))
    return render(request, "inspecoes/lista.html", ctx)


@admin_required
def plano_inspecao_novo(request):
    form = PlanoInspecaoForm(request.POST or None)
    if form.is_valid():
        plano = form.save(commit=False)
        plano.criado_por = request.user
        plano.atualizar_bases(plano.ultima_execucao)
        plano.save()
        messages.success(request, "Plano de inspeção criado.")
        return redirect("planos_inspecao")
    ctx = {"form": form, "titulo": "Novo plano de inspeção"}
    ctx.update(_base_context(request))
    return render(request, "inspecoes/form.html", ctx)


@admin_required
def plano_inspecao_editar(request, pk):
    plano = get_object_or_404(PlanoInspecao, pk=pk)
    form = PlanoInspecaoForm(request.POST or None, instance=plano)
    if form.is_valid():
        form.save()
        messages.success(request, "Plano de inspeção atualizado.")
        return redirect("planos_inspecao")
    ctx = {"form": form, "titulo": "Editar plano de inspeção", "plano": plano}
    ctx.update(_base_context(request))
    return render(request, "inspecoes/form.html", ctx)


@admin_required
@transaction.atomic
def plano_inspecao_executar(request, pk):
    plano = get_object_or_404(PlanoInspecao, pk=pk)
    form = ExecucaoInspecaoForm(request.POST or None)
    if form.is_valid():
        execucao = form.save(commit=False)
        execucao.plano = plano
        execucao.executado_por = request.user
        execucao.save()
        plano.atualizar_bases(execucao.data)
        plano.save(update_fields=["ultima_execucao", "voos_base", "minutos_base", "ciclos_base"])
        messages.success(request, "Execução registrada e contadores reiniciados.")
        return redirect("planos_inspecao")
    ctx = {"form": form, "plano": plano, "execucoes": plano.execucoes.select_related("executado_por")[:20]}
    ctx.update(_base_context(request))
    return render(request, "inspecoes/executar.html", ctx)
