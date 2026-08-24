from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .models import Piloto, Alocacao, SolicitacaoVoo
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
    form = SolicitacaoVooForm(request.POST or None)
    eh_admin = usuario_e_admin(request.user)
    if not eh_admin:
        try:
            piloto = request.user.piloto
        except Piloto.DoesNotExist:
            messages.error(request, "Seu usuário não está vinculado a um piloto.")
            return redirect("dashboard")
        form.fields["piloto"].queryset = Piloto.objects.filter(pk=piloto.pk)
        form.fields["piloto"].initial = piloto
        form.fields["piloto"].disabled = True
    if form.is_valid():
        obj = form.save(commit=False)
        if not eh_admin:
            obj.piloto = request.user.piloto
        obj.criado_por = request.user
        obj.status = "solicitado"
        obj.save()
        messages.success(request, "Solicitação de voo enviada com sucesso.")
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
    if not eh_admin:
        form.fields["piloto"].queryset = Piloto.objects.filter(pk=request.user.piloto.pk)
        form.fields["piloto"].disabled = True
    if form.is_valid():
        obj = form.save(commit=False)
        if not eh_admin:
            obj.piloto = request.user.piloto
        obj.save()
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
    avaliacao = getattr(obj, "avaliacao_risco", None)
    if not avaliacao or avaliacao.status != "aprovada":
        messages.error(request, "A avaliação de risco precisa ser preenchida e aprovada antes do voo.")
        return redirect("avaliacao_risco", solicitacao_id=obj.pk)
    if obj.drone.status != "ativo":
        messages.error(request, "O drone selecionado não está disponível.")
        return redirect("solicitacoes_voo")
    conflito = Alocacao.objects.filter(
        data=obj.data,
        drone=obj.drone,
        status="reservado",
        hora_inicio__lt=obj.hora_fim,
        hora_fim__gt=obj.hora_inicio,
    ).exists()
    if conflito:
        messages.error(request, "Existe outra reserva para este drone no horário.")
        return redirect("solicitacoes_voo")
    aloc = Alocacao.objects.create(
        data=obj.data,
        hora_inicio=obj.hora_inicio,
        hora_fim=obj.hora_fim,
        piloto=obj.piloto,
        drone=obj.drone,
        finalidade=obj.finalidade,
        local=obj.local,
        observacoes=obj.observacoes,
        status="reservado",
        criado_por=request.user,
    )
    obj.status = "aprovado"
    obj.analisado_por = request.user
    obj.alocacao = aloc
    obj.save()
    messages.success(request, "Solicitação aprovada e adicionada ao calendário.")
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
