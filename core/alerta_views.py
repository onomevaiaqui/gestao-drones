from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .alerta_service import gerar_alertas, resumo_alertas
from .models import AlertaResolvido
from .permissoes import admin_required
from .views import _base_context, visao_global_required


@visao_global_required
def alertas(request):
    prioridade = request.GET.get("prioridade", "").strip()
    categoria = request.GET.get("categoria", "").strip()
    todos = gerar_alertas()
    categorias = sorted({a["categoria"] for a in todos})
    filtrados = todos
    if prioridade:
        filtrados = [a for a in filtrados if a["prioridade"] == prioridade]
    if categoria:
        filtrados = [a for a in filtrados if a["categoria"] == categoria]
    ctx = {
        "alertas": filtrados, "resumo": resumo_alertas(todos), "categorias": categorias,
        "prioridade_filtro": prioridade, "categoria_filtro": categoria,
    }
    ctx.update(_base_context(request))
    return render(request, "alertas/lista.html", ctx)


@admin_required
@require_POST
def alerta_resolver(request):
    chave = request.POST.get("chave", "").strip()[:255]
    titulo = request.POST.get("titulo", "").strip()[:255]
    if chave:
        AlertaResolvido.objects.update_or_create(
            chave=chave,
            defaults={"titulo": titulo, "resolvido_por": request.user},
        )
        messages.success(request, "Alerta marcado como resolvido.")
    return redirect("alertas")
