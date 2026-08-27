from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q

from .models import Piloto, Alocacao, SolicitacaoVoo, PlanejamentoVoo
from .solicitacao_service import LiberacaoVooErro, liberar_solicitacao
from .solicitacao_forms import SolicitacaoVooForm
from .views import usuario_e_admin, usuario_e_coordenador, usuario_tem_visao_global, admin_required, _base_context


def _planejamento_exige_risco(planejamento):
    return bool(planejamento and (
        planejamento.status_meteorologico in ("atencao", "desfavoravel")
        or planejamento.resumo_meteorologico.get("aeronautica", {}).get("status") in ("atencao", "desfavoravel")
        or planejamento.resumo_meteorologico.get("sisclaten", {}).get("status") in ("aafa_necessaria", "confirmar")
    ))

@login_required
def solicitacoes_voo(request):
    if usuario_tem_visao_global(request.user):
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
    if usuario_e_coordenador(request.user):
        messages.info(request, "No perfil de coordenador, as reservas ficam disponíveis somente para consulta.")
        return redirect("solicitacoes_voo")
    eh_admin = usuario_e_admin(request.user)
    planejamento_inicial = None
    if request.method == "GET" and request.GET.get("planejamento"):
        planejamento_inicial = PlanejamentoVoo.objects.filter(pk=request.GET["planejamento"]).first()
    initial = {}
    if planejamento_inicial:
        initial = {"planejamento": planejamento_inicial, "data": planejamento_inicial.data,
                   "data_fim": planejamento_inicial.data_final,
                   "hora_inicio": planejamento_inicial.hora_inicio, "hora_fim": planejamento_inicial.hora_fim,
                   "piloto": planejamento_inicial.piloto, "local": planejamento_inicial.local,
                   "finalidade": planejamento_inicial.finalidade}
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
        form.fields["planejamento"].queryset = PlanejamentoVoo.objects.filter(piloto=piloto)
    else:
        form.fields["planejamento"].queryset = PlanejamentoVoo.objects.all()
    if form.is_valid():
        base = form.save(commit=False)
        if not eh_admin:
            base.piloto = request.user.piloto
        drones = list(form.cleaned_data["drones"])
        criadas = []
        with transaction.atomic():
            for drone in drones:
                obj = SolicitacaoVoo.objects.create(
                    planejamento=base.planejamento, data=base.data, data_fim=base.data_fim,
                    hora_inicio=base.hora_inicio, hora_fim=base.hora_fim, piloto=base.piloto,
                    drone=drone, finalidade=base.finalidade, local=base.local,
                    observacoes=base.observacoes, requer_avaliacao_risco=(base.requer_avaliacao_risco or _planejamento_exige_risco(base.planejamento)),
                    status="solicitado", criado_por=request.user,
                )
                criadas.append(obj)
                if not obj.requer_avaliacao_risco:
                    liberar_solicitacao(obj, request.user)
        if any(obj.requer_avaliacao_risco for obj in criadas):
            messages.success(request, f"{len(criadas)} reserva(s) registrada(s). Preencha as avaliações de risco pendentes.")
        else:
            messages.success(request, f"{len(criadas)} drone(s) reservado(s) e adicionados ao calendário.")
        return redirect("solicitacoes_voo")
    ctx = {"form": form, "titulo": "Reservar drone"}
    ctx.update(_base_context(request))
    return render(request, "solicitacoes/form.html", ctx)

@login_required
def solicitacao_voo_editar(request, pk):
    if usuario_e_coordenador(request.user):
        messages.info(request, "No perfil de coordenador, as reservas ficam disponíveis somente para consulta.")
        return redirect("solicitacoes_voo")
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
    form.fields["planejamento"].queryset = PlanejamentoVoo.objects.all()
    if not eh_admin:
        form.fields["piloto"].queryset = Piloto.objects.filter(pk=request.user.piloto.pk)
        form.fields["piloto"].disabled = True
        form.fields["planejamento"].queryset = form.fields["planejamento"].queryset.filter(piloto=request.user.piloto)
    if form.is_valid():
        obj = form.save(commit=False)
        drones = list(form.cleaned_data["drones"])
        obj.drone = drones[0]
        if not eh_admin:
            obj.piloto = request.user.piloto
        if _planejamento_exige_risco(obj.planejamento):
            obj.requer_avaliacao_risco = True
        obj.save()
        for drone in drones[1:]:
            adicional = SolicitacaoVoo.objects.create(
                planejamento=obj.planejamento, data=obj.data, data_fim=obj.data_fim,
                hora_inicio=obj.hora_inicio, hora_fim=obj.hora_fim, piloto=obj.piloto,
                drone=drone, finalidade=obj.finalidade, local=obj.local, observacoes=obj.observacoes,
                requer_avaliacao_risco=obj.requer_avaliacao_risco, status="solicitado", criado_por=request.user,
            )
            if not adicional.requer_avaliacao_risco:
                liberar_solicitacao(adicional, request.user)
        if obj.status == "solicitado" and not obj.requer_avaliacao_risco:
            try:
                liberar_solicitacao(obj, request.user)
            except LiberacaoVooErro as erro:
                messages.error(request, f"A reserva foi atualizada, mas a operação não pôde ser liberada: {erro}")
                return redirect("solicitacoes_voo")
        if eh_admin and obj.status == "aprovado" and obj.alocacao_id:
            aloc = obj.alocacao
            aloc.data = obj.data
            aloc.data_fim = obj.data_final
            aloc.hora_inicio = obj.hora_inicio
            aloc.hora_fim = obj.hora_fim
            aloc.piloto = obj.piloto
            aloc.drone = obj.drone
            aloc.finalidade = obj.finalidade
            aloc.local = obj.local
            aloc.observacoes = obj.observacoes
            aloc.save()
        messages.success(request, "Reserva atualizada.")
        return redirect("solicitacoes_voo")
    ctx = {"form": form, "titulo": "Editar reserva de drone"}
    ctx.update(_base_context(request))
    return render(request, "solicitacoes/form.html", ctx)

@admin_required
@require_POST
def solicitacao_voo_aprovar(request, pk):
    obj = get_object_or_404(SolicitacaoVoo, pk=pk)
    if obj.status != "solicitado":
        messages.warning(request, "Esta reserva já foi analisada.")
        return redirect("solicitacoes_voo")
    messages.info(request, "A liberação agora é automática. Quando exigida, aprove somente a avaliação de risco.")
    return redirect("solicitacoes_voo")

@admin_required
@require_POST
def solicitacao_voo_rejeitar(request, pk):
    obj = get_object_or_404(SolicitacaoVoo, pk=pk)
    if obj.status != "solicitado":
        messages.warning(request, "Esta reserva já foi analisada.")
        return redirect("solicitacoes_voo")
    obj.status = "rejeitado"
    obj.analisado_por = request.user
    obj.save()
    messages.success(request, "Reserva rejeitada.")
    return redirect("solicitacoes_voo")

@login_required
@require_POST
def solicitacao_voo_cancelar(request, pk):
    if usuario_e_coordenador(request.user):
        messages.info(request, "No perfil de coordenador, as reservas ficam disponíveis somente para consulta.")
        return redirect("solicitacoes_voo")
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
            messages.error(request, "Depois de reservada, somente um administrador pode cancelar.")
            return redirect("solicitacoes_voo")
    if obj.alocacao_id and obj.alocacao.status != "concluido":
        obj.alocacao.status = "cancelado"
        obj.alocacao.save(update_fields=["status"])
    obj.status = "cancelado"
    if eh_admin:
        obj.analisado_por = request.user
    obj.save()
    messages.success(request, "Reserva cancelada.")
    return redirect("solicitacoes_voo")
