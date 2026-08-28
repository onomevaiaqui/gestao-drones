from io import BytesIO

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .componente_forms import ComponenteForm
from .models import Componente, MovimentacaoComponente
from .views import _base_context, admin_required


@login_required
def componentes(request):
    busca = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    itens = Componente.objects.select_related("drone")
    if busca:
        itens = itens.filter(Q(codigo__icontains=busca) | Q(nome__icontains=busca) | Q(numero_serie__icontains=busca) | Q(modelo__icontains=busca) | Q(localizacao__icontains=busca) | Q(drone__nome__icontains=busca))
    if status:
        itens = itens.filter(status=status)
    resumo = {
        "total": Componente.objects.count(),
        "instalados": Componente.objects.filter(status="instalado").count(),
        "disponiveis": Componente.objects.filter(status="disponivel").count(),
        "atencao": Componente.objects.filter(status__in=["manutencao", "indisponivel"]).count(),
    }
    ctx = {"componentes": itens, "resumo": resumo, "busca": busca, "status_filtro": status, "status_choices": Componente.STATUS_CHOICES}
    ctx.update(_base_context(request))
    return render(request, "componentes/lista.html", ctx)


@admin_required
def componente_novo(request):
    serial = request.GET.get("numero_serie", "").strip()[:100]
    drone_id = request.GET.get("drone", "").strip()
    tipo = request.GET.get("tipo", "acessorio").strip()
    nome = request.GET.get("nome", "Acessório DJI detectado").strip()[:150]
    importacao_id = request.GET.get("importacao", "").strip()
    tipos_validos = {valor for valor, _ in Componente.TIPO_CHOICES}
    initial = {}
    if serial:
        initial.update({
            "codigo": f"EQP-{serial[-8:]}", "nome": nome, "tipo": tipo if tipo in tipos_validos else "acessorio",
            "fabricante": "DJI", "numero_serie": serial, "status": "instalado",
        })
    if drone_id.isdigit():
        initial["drone"] = drone_id
    form = ComponenteForm(request.POST or None, initial=initial)
    if form.is_valid():
        item = form.save(commit=False)
        item.criado_por = request.user
        item.save()
        MovimentacaoComponente.objects.create(
            componente=item, drone_novo=item.drone, status_novo=item.status,
            motivo=form.cleaned_data.get("motivo_movimentacao") or "Cadastro inicial", realizado_por=request.user,
        )
        messages.success(request, "Equipamento/componente cadastrado.")
        if importacao_id.isdigit():
            return redirect("telemetria_detalhe", pk=importacao_id)
        return redirect("componente_detalhe", pk=item.pk)
    ctx = {"form": form, "titulo": "Cadastrar equipamento identificado no log" if serial else "Novo equipamento ou componente"}
    ctx.update(_base_context(request))
    return render(request, "componentes/form.html", ctx)


@admin_required
def componente_editar(request, pk):
    item = get_object_or_404(Componente, pk=pk)
    drone_anterior, status_anterior = item.drone, item.status
    form = ComponenteForm(request.POST or None, instance=item)
    if form.is_valid():
        item = form.save()
        if item.drone_id != getattr(drone_anterior, "pk", None) or item.status != status_anterior:
            MovimentacaoComponente.objects.create(
                componente=item, drone_anterior=drone_anterior, drone_novo=item.drone,
                status_anterior=status_anterior, status_novo=item.status,
                motivo=form.cleaned_data.get("motivo_movimentacao") or "Alteração cadastral", realizado_por=request.user,
            )
        messages.success(request, "Equipamento/componente atualizado.")
        return redirect("componente_detalhe", pk=item.pk)
    ctx = {"form": form, "titulo": f"Editar {item.codigo}", "componente": item}
    ctx.update(_base_context(request))
    return render(request, "componentes/form.html", ctx)


@login_required
def componente_detalhe(request, pk=None, token=None):
    filtro = {"pk": pk} if pk is not None else {"qr_token": token}
    item = get_object_or_404(Componente.objects.select_related("drone", "criado_por"), **filtro)
    ctx = {"componente": item, "movimentacoes": item.movimentacoes.select_related("drone_anterior", "drone_novo", "realizado_por")}
    ctx.update(_base_context(request))
    return render(request, "componentes/detalhe.html", ctx)


@login_required
def componente_qr(request, pk):
    item = get_object_or_404(Componente, pk=pk)
    destino = request.build_absolute_uri(reverse("componente_por_qr", kwargs={"token": item.qr_token}))
    imagem = qrcode.make(destino)
    buffer = BytesIO()
    imagem.save(buffer, format="PNG")
    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="qr-{item.codigo}.png"'
    response["Cache-Control"] = "private, max-age=3600"
    return response
