from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Alocacao, AvaliacaoRisco, Incidente, Piloto, SolicitacaoVoo
from .seguranca_forms import AvaliacaoRiscoForm, IncidenteForm
from .solicitacao_service import LiberacaoVooErro, liberar_solicitacao
from .views import _base_context, usuario_e_admin


def _pode_acessar_solicitacao(user, solicitacao):
    return usuario_e_admin(user) or solicitacao.piloto.user_id == user.id


@login_required
def avaliacao_risco(request, solicitacao_id):
    solicitacao = get_object_or_404(SolicitacaoVoo.objects.select_related("piloto__user", "drone"), pk=solicitacao_id)
    if not _pode_acessar_solicitacao(request.user, solicitacao):
        messages.error(request, "Você não pode acessar esta avaliação.")
        return redirect("solicitacoes_voo")
    avaliacao = AvaliacaoRisco.objects.filter(solicitacao=solicitacao).first()
    eh_admin = usuario_e_admin(request.user)
    somente_leitura = bool(
        avaliacao and avaliacao.status in ["submetida", "aprovada"] and not eh_admin
    )

    if request.method == "POST" and not somente_leitura:
        acao = request.POST.get("acao", "salvar")
        if eh_admin and avaliacao and acao in ["aprovar", "revisao"]:
            avaliacao.status = "aprovada" if acao == "aprovar" else "revisao"
            avaliacao.analisado_por = request.user
            avaliacao.analisado_em = timezone.now()
            avaliacao.save(update_fields=["status", "analisado_por", "analisado_em", "atualizado_em"])
            if acao == "aprovar":
                try:
                    liberar_solicitacao(solicitacao, request.user)
                    messages.success(request, "Avaliação aprovada, voo liberado e adicionado ao calendário.")
                except LiberacaoVooErro as erro:
                    messages.error(request, f"Avaliação aprovada, mas o voo não pôde ser liberado: {erro}")
            else:
                messages.success(request, "Avaliação devolvida para revisão.")
            return redirect("solicitacoes_voo")
        form = AvaliacaoRiscoForm(request.POST, instance=avaliacao)
        if form.is_valid():
            avaliacao = form.save(commit=False)
            avaliacao.solicitacao = solicitacao
            if not avaliacao.pk:
                avaliacao.preenchido_por = request.user
            avaliacao.status = "submetida" if acao == "submeter" else "rascunho"
            avaliacao.analisado_por = None
            avaliacao.analisado_em = None
            avaliacao.save()
            messages.success(request, "Avaliação enviada para análise." if acao == "submeter" else "Rascunho salvo.")
            return redirect("avaliacao_risco", solicitacao_id=solicitacao.pk)
    else:
        form = AvaliacaoRiscoForm(instance=avaliacao)
    ctx = {"form": form, "solicitacao": solicitacao, "avaliacao": avaliacao, "somente_leitura": somente_leitura}
    ctx.update(_base_context(request))
    return render(request, "seguranca/avaliacao_risco.html", ctx)


@login_required
def incidentes(request):
    eh_admin = usuario_e_admin(request.user)
    qs = Incidente.objects.select_related("alocacao__drone", "alocacao__piloto", "registrado_por")
    if not eh_admin:
        qs = qs.filter(alocacao__piloto__user=request.user)
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    resumo = {"total": qs.count(), "abertos": qs.filter(status="aberto").count(), "investigacao": qs.filter(status="investigacao").count(), "graves": qs.filter(gravidade__in=["grave", "critico"]).exclude(status="encerrado").count()}
    ctx = {"incidentes": qs, "resumo": resumo, "status_filtro": status, "status_choices": Incidente.STATUS_CHOICES}
    ctx.update(_base_context(request))
    return render(request, "seguranca/incidentes_lista.html", ctx)


@login_required
def incidente_novo(request):
    eh_admin = usuario_e_admin(request.user)
    form = IncidenteForm(request.POST or None, request.FILES or None, eh_admin=eh_admin)
    if not eh_admin:
        form.fields["alocacao"].queryset = Alocacao.objects.filter(piloto__user=request.user).order_by("-data")
    if form.is_valid():
        incidente = form.save(commit=False)
        incidente.registrado_por = request.user
        if not eh_admin:
            incidente.status = "aberto"
        if incidente.gravidade == "critico" or incidente.houve_lesao or incidente.houve_dano_terceiro:
            incidente.notificacao_obrigatoria = True
        incidente.save()
        messages.success(request, "Incidente registrado.")
        return redirect("incidentes")
    ctx = {"form": form, "titulo": "Registrar incidente"}
    ctx.update(_base_context(request))
    return render(request, "seguranca/incidente_form.html", ctx)


@login_required
def incidente_editar(request, pk):
    incidente = get_object_or_404(Incidente, pk=pk)
    eh_admin = usuario_e_admin(request.user)
    if not eh_admin and (incidente.alocacao.piloto.user_id != request.user.id or incidente.status != "aberto"):
        messages.error(request, "Este incidente não pode ser alterado por você.")
        return redirect("incidentes")
    form = IncidenteForm(request.POST or None, request.FILES or None, instance=incidente, eh_admin=eh_admin)
    if not eh_admin:
        form.fields["alocacao"].queryset = Alocacao.objects.filter(piloto__user=request.user)
    if form.is_valid():
        obj = form.save(commit=False)
        if not eh_admin:
            obj.status = incidente.status
        if obj.gravidade == "critico" or obj.houve_lesao or obj.houve_dano_terceiro:
            obj.notificacao_obrigatoria = True
        obj.save()
        messages.success(request, "Incidente atualizado.")
        return redirect("incidentes")
    ctx = {"form": form, "titulo": "Analisar incidente", "incidente": incidente}
    ctx.update(_base_context(request))
    return render(request, "seguranca/incidente_form.html", ctx)
