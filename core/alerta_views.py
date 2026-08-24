from django.shortcuts import render

from .alerta_service import gerar_alertas, resumo_alertas
from .views import _base_context, admin_required


@admin_required
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
