from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.db.models import Q

from .models import Piloto, Alocacao, SolicitacaoVoo, PlanejamentoVoo
from .solicitacao_service import LiberacaoVooErro, liberar_solicitacao
from .solicitacao_forms import SolicitacaoVooForm
from .views import usuario_e_admin, admin_required, _base_context

@login_required
def solicitacoes_voo(request):
    if usuario_e_admin(request.user):
        qs = SolicitacaoVoo.objects.select_related("piloto", "drone", "criado_por", "analisado_por")
    else:
        try:
            piloto = request.user.piloto
        except Piloto.DoesNotExist:
            messages.error(request, "Seu usuário não está vinculado a um piloto.")
            return redirect("dashboard")
        qs = SolicitacaoVoo.objects.select_related("piloto", "drone").filter(piloto=piloto)
    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)
    ctx = {"solicitacoes": qs, "status_atual": status or "", "status_choices": SolicitacaoVoo.STATUS_CHOICES}
    ctx.update(_base_context(request))
    return render(request, "solicitacoes/lista.html", ctx)

@login_required
def solicitacao_voo_nova(request):
    eh_admin = usuario_e_admin(request.user)
    planejamento_inicial = None
    if request.method == "GET" and request.GET.get("planejamento"):
        planejamento_inicial = PlanejamentoVoo.objects.filter(pk=request.GET["planejamento"]).first()
    initial = {}
    if planejamento_inicial:
        initial = {"planejamento": planejamento_inicial, "data": planejamento_inicial.data,
                   "hora_inicio": planejamento_inicial.hora_inicio, "hora_fim": planejamento_inicial.hora_fim,
                   "piloto": planejamento_inicial.piloto}
    form = SolicitacaoVooForm(request.POST or None, initial=initial)
    if not eh_admin:
        try:
            piloto = request.user.piloto
        except Piloto.DoesNotExist:
            messages.error(request, "Seu usuário não está vinculado a um piloto.")
            return redirect("dashboard")
        form.fields["piloto"].queryset = Piloto.objects.filter(pk=piloto.pk)
        form.fields["piloto"].initial = piloto
        form.fields["piloto"].disabled = True
        form.fields["planejamento"].queryset = PlanejamentoVoo.objects.filter(
            piloto=piloto, solicitacao_voo__isnull=True
        )
    else:
        form.fields["planejamento"].queryset = PlanejamentoVoo.objects.filter(solicitacao_voo__isnull=True)
    if form.is_valid():
        obj = form.save(commit=False)
        if not eh_admin:
            obj.piloto = request.user.piloto
        obj.criado_por = request.user
        if obj.planejamento and obj.planejamento.status_meteorologico in ("atencao", "desfavoravel"):
            obj.requer_avaliacao_risco = True
        obj.status = "solicitado"
        obj.save()
        if obj.requer_avaliacao_risco:
            messages.success(request, "Solicitação registrada. Preencha a avaliação de risco para liberar o voo.")
        else:
            try:
                liberar_solicitacao(obj, request.user)
                messages.success(request, "Voo registrado e adicionado ao calendário.")
            except LiberacaoVooErro as erro:
                messages.error(request, f"A solicitação foi salva, mas o voo não pôde ser liberado: {erro}")
        return redirect("solicitacoes_voo")
    ctx = {"form": form, "titulo": "Solicitar voo"}
    ctx.update(_base_context(request))
    return render(request, "solicitacoes/form.html", ctx)

@login_required
def solicitacao_voo_editar(request, pk):
    obj = get_object_or_404(SolicitacaoVoo, pk=pk)
    eh_admin = usuario_e_admin(request.user)
    if not eh_admin:
        try:
            piloto = request.user.piloto
        except Piloto.DoesNotExist:
            return redirect("dashboard")
        if obj.piloto_id != piloto.id:
            messages.error(request, "Você só pode editar suas próprias solicitações.")
            return redirect("solicitacoes_voo")
        if obj.status != "solicitado":
            messages.error(request, "Somente solicitações pendentes podem ser editadas.")
            return redirect("solicitacoes_voo")
    form = SolicitacaoVooForm(request.POST or None, instance=obj)
    form.fields["planejamento"].queryset = PlanejamentoVoo.objects.filter(
        Q(solicitacao_voo__isnull=True) | Q(pk=obj.planejamento_id)
    )
    if not eh_admin:
        form.fields["piloto"].queryset = Piloto.objects.filter(pk=request.user.piloto.pk)
        form.fields["piloto"].disabled = True
        form.fields["planejamento"].queryset = form.fields["planejamento"].queryset.filter(piloto=request.user.piloto)
    if form.is_valid():
        obj = form.save(commit=False)
        if not eh_admin:
            obj.piloto = request.user.piloto
        if obj.planejamento and obj.planejamento.status_meteorologico in ("atencao", "desfavoravel"):
            obj.requer_avaliacao_risco = True
        obj.save()
        if obj.status == "solicitado" and not obj.requer_avaliacao_risco:
            try:
                liberar_solicitacao(obj, request.user)
            except LiberacaoVooErro as erro:
                messages.error(request, f"A solicitação foi atualizada, mas o voo não pôde ser liberado: {erro}")
                return redirect("solicitacoes_voo")
        if eh_admin and obj.status == "aprovado" and obj.alocacao_id:
            aloc = obj.alocacao
            aloc.data = obj.data
            aloc.hora_inicio = obj.hora_inicio
            aloc.hora_fim = obj.hora_fim
            aloc.piloto = obj.piloto
            aloc.drone = obj.drone
            aloc.finalidade = obj.finalidade
            aloc.local = obj.local
            aloc.observacoes = obj.observacoes
            aloc.save()
        messages.success(request, "Solicitação atualizada.")
        return redirect("solicitacoes_voo")
    ctx = {"form": form, "titulo": "Editar solicitação de voo"}
    ctx.update(_base_context(request))
    return render(request, "solicitacoes/form.html", ctx)

@admin_required
@require_POST
def solicitacao_voo_aprovar(request, pk):
    obj = get_object_or_404(SolicitacaoVoo, pk=pk)
    if obj.status != "solicitado":
        messages.warning(request, "Esta solicitação já foi analisada.")
        return redirect("solicitacoes_voo")
    messages.info(request, "A liberação agora é automática. Quando exigida, aprove somente a avaliação de risco.")
    return redirect("solicitacoes_voo")

@admin_required
@require_POST
def solicitacao_voo_rejeitar(request, pk):
    obj = get_object_or_404(SolicitacaoVoo, pk=pk)
    if obj.status != "solicitado":
        messages.warning(request, "Esta solicitação já foi analisada.")
        return redirect("solicitacoes_voo")
    obj.status = "rejeitado"
    obj.analisado_por = request.user
    obj.save()
    messages.success(request, "Solicitação rejeitada.")
    return redirect("solicitacoes_voo")

@login_required
@require_POST
def solicitacao_voo_cancelar(request, pk):
    obj = get_object_or_404(SolicitacaoVoo, pk=pk)
    eh_admin = usuario_e_admin(request.user)
    if not eh_admin:
        try:
            piloto = request.user.piloto
        except Piloto.DoesNotExist:
            return redirect("dashboard")
        if obj.piloto_id != piloto.id:
            messages.error(request, "Você só pode cancelar suas próprias solicitações.")
            return redirect("solicitacoes_voo")
        if obj.status != "solicitado":
            messages.error(request, "Depois de aprovada, somente um administrador pode cancelar.")
            return redirect("solicitacoes_voo")
    if obj.alocacao_id and obj.alocacao.status != "concluido":
        obj.alocacao.status = "cancelado"
        obj.alocacao.save(update_fields=["status"])
    obj.status = "cancelado"
    if eh_admin:
        obj.analisado_por = request.user
    obj.save()
    messages.success(request, "Solicitação cancelada.")
    return redirect("solicitacoes_voo")
