from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import PlanejamentoVoo, Piloto
from .planejamento_forms import PlanejamentoVooForm
from .planejamento_service import consultar_previsao
from .views import _base_context, usuario_e_admin


def _planejamentos_do_usuario(request):
    qs = PlanejamentoVoo.objects.select_related("piloto", "criado_por", "solicitacao_voo")
    if usuario_e_admin(request.user):
        return qs
    return qs.filter(piloto__user=request.user)


def _atualizar_previsao(obj):
    try:
        resumo = consultar_previsao(obj)
    except Exception as erro:
        obj.status_meteorologico = "indisponivel"
        obj.resumo_meteorologico = {"erro": str(erro)}
        obj.previsao_consultada_em = timezone.now()
        obj.save(update_fields=["status_meteorologico", "resumo_meteorologico", "previsao_consultada_em"])
        return False, str(erro)
    obj.status_meteorologico = resumo["status"]
    obj.resumo_meteorologico = resumo
    obj.previsao_consultada_em = timezone.now()
    obj.save(update_fields=["status_meteorologico", "resumo_meteorologico", "previsao_consultada_em"])
    return True, ""


@login_required
def planejamentos(request):
    ctx = {"planejamentos": _planejamentos_do_usuario(request)}
    ctx.update(_base_context(request))
    return render(request, "planejamentos/lista.html", ctx)


def _form_planejamento(request, obj=None):
    eh_admin = usuario_e_admin(request.user)
    piloto = None
    if not eh_admin:
        piloto = getattr(request.user, "piloto", None)
        if not piloto:
            messages.error(request, "Seu usuário não está vinculado a um piloto.")
            return redirect("dashboard")
        if obj and obj.piloto_id != piloto.pk:
            messages.error(request, "Você só pode alterar seus próprios planejamentos.")
            return redirect("planejamentos")
    form = PlanejamentoVooForm(request.POST or None, instance=obj)
    if piloto:
        form.fields["piloto"].queryset = Piloto.objects.filter(pk=piloto.pk)
        form.fields["piloto"].initial = piloto
        form.fields["piloto"].disabled = True
    if form.is_valid():
        planejamento = form.save(commit=False)
        if piloto:
            planejamento.piloto = piloto
        if not planejamento.pk:
            planejamento.criado_por = request.user
        planejamento.save()
        sucesso, erro = _atualizar_previsao(planejamento)
        if sucesso:
            messages.success(request, "Planejamento salvo e previsão meteorológica atualizada.")
        else:
            messages.warning(request, f"Planejamento salvo, mas a previsão não pôde ser consultada: {erro}")
        return redirect("planejamento_detalhe", pk=planejamento.pk)
    ctx = {
        "form": form,
        "titulo": "Editar planejamento" if obj else "Novo planejamento de voo",
        "geometria_inicial": obj.area_geojson if obj else None,
    }
    ctx.update(_base_context(request))
    return render(request, "planejamentos/form.html", ctx)


@login_required
def planejamento_novo(request):
    return _form_planejamento(request)


@login_required
def planejamento_editar(request, pk):
    obj = get_object_or_404(_planejamentos_do_usuario(request), pk=pk)
    return _form_planejamento(request, obj)


@login_required
def planejamento_detalhe(request, pk):
    obj = get_object_or_404(_planejamentos_do_usuario(request), pk=pk)
    ctx = {"planejamento": obj, "meteo": obj.resumo_meteorologico or {}}
    ctx.update(_base_context(request))
    return render(request, "planejamentos/detalhe.html", ctx)


@login_required
@require_POST
def planejamento_atualizar_previsao(request, pk):
    obj = get_object_or_404(_planejamentos_do_usuario(request), pk=pk)
    sucesso, erro = _atualizar_previsao(obj)
    if sucesso:
        messages.success(request, "Previsão meteorológica atualizada.")
    else:
        messages.error(request, f"Não foi possível atualizar a previsão: {erro}")
    return redirect("planejamento_detalhe", pk=obj.pk)
