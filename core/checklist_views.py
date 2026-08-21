from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .models import Piloto, Alocacao, ChecklistPreVoo
from .checklist_forms import ChecklistPreVooForm
from .views import usuario_e_admin, _base_context

@login_required
def checklist_pre_voo(request, pk):
    alocacao = get_object_or_404(
        Alocacao.objects.select_related("piloto", "drone"),
        pk=pk
    )

    permitido = usuario_e_admin(request.user)
    if not permitido:
        try:
            permitido = alocacao.piloto_id == request.user.piloto.id
        except Piloto.DoesNotExist:
            permitido = False

    if not permitido:
        messages.error(request, "Você não tem permissão para este checklist.")
        return redirect("calendario")

    checklist, _ = ChecklistPreVoo.objects.get_or_create(alocacao=alocacao)
    form = ChecklistPreVooForm(request.POST or None, instance=checklist)

    if form.is_valid():
        checklist = form.save(commit=False)
        checklist.preenchido_por = request.user
        checklist.atualizar_status()
        checklist.save()

        if checklist.concluido:
            messages.success(request, "Checklist pré-voo concluído.")
        else:
            messages.warning(request, "Checklist salvo com itens pendentes.")

        return redirect("calendario")

    ctx = {
        "form": form,
        "alocacao": alocacao,
        "checklist": checklist,
    }
    ctx.update(_base_context(request))
    return render(request, "checklist/pre_voo.html", ctx)
