from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.utils import timezone

from .models import Alocacao, AvaliacaoRisco, ConfiguracaoPapelTimbrado, Incidente, Piloto, SolicitacaoVoo
from .seguranca_forms import AvaliacaoRiscoForm, IncidenteForm
from .solicitacao_service import LiberacaoVooErro, liberar_solicitacao
from .views import _base_context, usuario_e_admin
from .avaliacao_risco_service import dados_automaticos_avaliacao
from .avaliacao_risco_pdf import gerar_pdf_avaliacao
from .papel_timbrado import PapelTimbradoRiscoForm, aplicar_papel_timbrado


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
    configuracao_timbre = ConfiguracaoPapelTimbrado.atual()
    timbre_form = PapelTimbradoRiscoForm(instance=configuracao_timbre)
    if request.method == "POST" and request.POST.get("acao") == "salvar_timbre" and eh_admin:
        timbre_form = PapelTimbradoRiscoForm(request.POST, request.FILES, instance=configuracao_timbre)
        if timbre_form.is_valid():
            configuracao = timbre_form.save(commit=False)
            configuracao.atualizado_por = request.user
            configuracao.save()
            messages.success(request, "Modelo de papel timbrado da avaliação atualizado.")
            return redirect("avaliacao_risco", solicitacao_id=solicitacao.pk)
    solicitou_edicao = request.GET.get("editar") == "1" or request.POST.get("modo_edicao") == "1"
    pode_corrigir = bool(avaliacao and avaliacao.status == "aprovada" and not eh_admin and solicitacao.piloto.user_id == request.user.id and solicitou_edicao)
    somente_leitura = bool(eh_admin or (avaliacao and avaliacao.status == "aprovada" and not pode_corrigir))

    if request.method == "POST" and not somente_leitura:
        form = AvaliacaoRiscoForm(request.POST, instance=avaliacao, initial=dados_automaticos_avaliacao(solicitacao))
        if form.is_valid():
            avaliacao = form.save(commit=False)
            avaliacao.solicitacao = solicitacao
            avaliacao.preenchido_por = request.user
            acao = request.POST.get("acao", "aceitar")
            ja_aceita = bool(avaliacao.pk and AvaliacaoRisco.objects.filter(pk=avaliacao.pk, status="aprovada").exists())
            avaliacao.status = "aprovada" if acao == "aceitar" or ja_aceita else "rascunho"
            if avaliacao.status == "aprovada":
                avaliacao.aceito_em = timezone.now()
            avaliacao.analisado_por = None
            avaliacao.analisado_em = None
            avaliacao.save()
            if avaliacao.status == "rascunho":
                messages.success(request, "Avaliação salva. Agora você pode visualizar o PDF, continuar editando ou aceitar o risco.")
                return redirect("avaliacao_risco", solicitacao_id=solicitacao.pk)
            try:
                liberar_solicitacao(solicitacao, request.user)
                messages.success(request, "Avaliação salva e aceita. Drone reservado e operação adicionada ao calendário.")
            except LiberacaoVooErro as erro:
                messages.error(request, f"Avaliação salva, mas a reserva não pôde ser liberada: {erro}")
            return redirect("avaliacao_risco", solicitacao_id=solicitacao.pk)
    else:
        form = AvaliacaoRiscoForm(instance=avaliacao, initial=dados_automaticos_avaliacao(solicitacao) if not avaliacao else None)
    ctx = {"form": form, "solicitacao": solicitacao, "avaliacao": avaliacao, "somente_leitura": somente_leitura, "pode_corrigir": pode_corrigir, "timbre_form": timbre_form, "configuracao_timbre": configuracao_timbre}
    ctx.update(_base_context(request))
    return render(request, "seguranca/avaliacao_risco.html", ctx)


@login_required
def avaliacao_risco_pdf(request, solicitacao_id):
    solicitacao = get_object_or_404(SolicitacaoVoo.objects.select_related("piloto__user", "drone"), pk=solicitacao_id)
    if not _pode_acessar_solicitacao(request.user, solicitacao):
        return HttpResponse(status=403)
    avaliacao = get_object_or_404(AvaliacaoRisco, solicitacao=solicitacao)
    conteudo = aplicar_papel_timbrado(gerar_pdf_avaliacao(avaliacao), ConfiguracaoPapelTimbrado.atual().modelo_avaliacao_risco)
    resposta = HttpResponse(conteudo, content_type="application/pdf")
    resposta["Content-Disposition"] = f'attachment; filename="avaliacao-risco-{solicitacao.pk}.pdf"'
    return resposta


@login_required
def avaliacao_risco_imprimir(request, solicitacao_id):
    solicitacao = get_object_or_404(SolicitacaoVoo.objects.select_related("piloto__user", "drone"), pk=solicitacao_id)
    if not _pode_acessar_solicitacao(request.user, solicitacao):
        return HttpResponse(status=403)
    avaliacao = get_object_or_404(AvaliacaoRisco, solicitacao=solicitacao)
    conteudo = aplicar_papel_timbrado(gerar_pdf_avaliacao(avaliacao), ConfiguracaoPapelTimbrado.atual().modelo_avaliacao_risco)
    resposta = HttpResponse(conteudo, content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="avaliacao-risco-{solicitacao.pk}.pdf"'
    return resposta


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
