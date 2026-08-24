from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .documento_forms import DocumentoForm
from .models import Documento
from .views import _base_context, admin_required


@admin_required
def documentos(request):
    busca = request.GET.get("q", "").strip()
    situacao = request.GET.get("situacao", "").strip()
    documentos_lista = list(Documento.objects.select_related("piloto", "drone", "bateria"))
    if busca:
        termo = busca.casefold()
        documentos_lista = [d for d in documentos_lista if termo in f"{d.titulo} {d.numero} {d.alvo}".casefold()]
    if situacao:
        documentos_lista = [d for d in documentos_lista if d.situacao == situacao]
    documentos_lista.sort(key=lambda d: ({"vencido": 0, "vencendo": 1, "valido": 2, "sem_validade": 3, "inativo": 4}[d.situacao], d.data_validade or d.criado_em.date()))
    todos = list(Documento.objects.all())
    resumo = {
        "total": len(todos),
        "vencidos": sum(d.situacao == "vencido" for d in todos),
        "vencendo": sum(d.situacao == "vencendo" for d in todos),
        "validos": sum(d.situacao == "valido" for d in todos),
    }
    ctx = {"documentos": documentos_lista, "resumo": resumo, "busca": busca, "situacao_filtro": situacao}
    ctx.update(_base_context(request))
    return render(request, "documentos/lista.html", ctx)


@admin_required
def documento_novo(request):
    form = DocumentoForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        documento = form.save(commit=False)
        documento.criado_por = request.user
        documento.save()
        messages.success(request, "Documento cadastrado com sucesso.")
        return redirect("documentos")
    ctx = {"form": form, "titulo": "Novo documento"}
    ctx.update(_base_context(request))
    return render(request, "documentos/form.html", ctx)


@admin_required
def documento_editar(request, pk):
    documento = get_object_or_404(Documento, pk=pk)
    form = DocumentoForm(request.POST or None, request.FILES or None, instance=documento)
    if form.is_valid():
        form.save()
        messages.success(request, "Documento atualizado com sucesso.")
        return redirect("documentos")
    ctx = {"form": form, "titulo": "Editar documento", "documento": documento}
    ctx.update(_base_context(request))
    return render(request, "documentos/form.html", ctx)


@admin_required
@require_POST
def documento_excluir(request, pk):
    documento = get_object_or_404(Documento, pk=pk)
    if documento.arquivo:
        documento.arquivo.delete(save=False)
    documento.delete()
    messages.success(request, "Documento excluído.")
    return redirect("documentos")
