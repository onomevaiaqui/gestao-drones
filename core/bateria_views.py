from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from .bateria_forms import BateriaForm
from .models import Bateria
from .views import _base_context, admin_required


@login_required
def baterias(request):
    busca = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    queryset = Bateria.objects.select_related("drone").annotate(
        total_voos=Count("registros_pos_voo", filter=Q(registros_pos_voo__concluido=True), distinct=True)
    )
    if busca:
        queryset = queryset.filter(
            Q(codigo__icontains=busca) | Q(numero_serie__icontains=busca)
            | Q(fabricante__icontains=busca) | Q(modelo__icontains=busca)
        )
    if status:
        queryset = queryset.filter(status=status)
    resumo = {
        "total": Bateria.objects.count(),
        "disponiveis": Bateria.objects.filter(status="disponivel").count(),
        "atencao": Bateria.objects.filter(Q(saude_percentual__lt=80) | Q(status="manutencao")).count(),
        "descartadas": Bateria.objects.filter(status="descartada").count(),
    }
    ctx = {"baterias": queryset, "resumo": resumo, "busca": busca, "status_filtro": status, "status_choices": Bateria.STATUS_CHOICES}
    ctx.update(_base_context(request))
    return render(request, "baterias/lista.html", ctx)


@admin_required
def bateria_nova(request):
    form = BateriaForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Bateria cadastrada com sucesso.")
        return redirect("baterias")
    ctx = {"form": form, "titulo": "Nova bateria"}
    ctx.update(_base_context(request))
    return render(request, "baterias/form.html", ctx)


@admin_required
def bateria_editar(request, pk):
    bateria = get_object_or_404(Bateria, pk=pk)
    form = BateriaForm(request.POST or None, instance=bateria)
    if form.is_valid():
        form.save()
        messages.success(request, "Bateria atualizada com sucesso.")
        return redirect("bateria_detalhe", pk=bateria.pk)
    ctx = {"form": form, "titulo": "Editar bateria", "bateria": bateria}
    ctx.update(_base_context(request))
    return render(request, "baterias/form.html", ctx)


@login_required
def bateria_detalhe(request, pk):
    bateria = get_object_or_404(Bateria.objects.select_related("drone"), pk=pk)
    usos = bateria.registros_pos_voo.select_related(
        "alocacao__drone", "alocacao__piloto"
    ).order_by("-alocacao__data", "-hora_inicio_real")
    ctx = {"bateria": bateria, "usos": usos}
    ctx.update(_base_context(request))
    return render(request, "baterias/detalhe.html", ctx)
