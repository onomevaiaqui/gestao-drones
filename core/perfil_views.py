from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Piloto
from .perfil_forms import DocumentoPerfilForm, PerfilUsuarioForm
from .views import _base_context, usuario_e_admin


def _pode_editar(user, piloto):
    return usuario_e_admin(user) or piloto.user_id == user.id


@login_required
def perfil_usuario(request, pk=None):
    if pk is None:
        if not hasattr(request.user, "piloto"):
            messages.error(request, "Seu usuário não está vinculado a um piloto.")
            return redirect("dashboard")
        piloto = request.user.piloto
    else:
        piloto = get_object_or_404(Piloto.objects.select_related("user"), pk=pk)
    if not _pode_editar(request.user, piloto):
        messages.error(request, "Você não pode editar este perfil.")
        return redirect("dashboard")
    form = PerfilUsuarioForm(request.POST or None, request.FILES or None, instance=piloto)
    if form.is_valid():
        form.save()
        messages.success(request, "Perfil atualizado com sucesso.")
        return redirect("perfil_usuario", pk=piloto.pk)
    ctx = {"piloto": piloto, "form": form, "documentos": piloto.documentos.filter(ativo=True), "documento_form": DocumentoPerfilForm()}
    ctx.update(_base_context(request))
    return render(request, "perfis/editar.html", ctx)


@login_required
def documento_perfil_novo(request, pk):
    piloto = get_object_or_404(Piloto, pk=pk)
    if not _pode_editar(request.user, piloto):
        messages.error(request, "Você não pode adicionar documentos a este perfil.")
        return redirect("dashboard")
    if request.method != "POST":
        return redirect("perfil_usuario", pk=piloto.pk)
    form = DocumentoPerfilForm(request.POST, request.FILES)
    form.instance.piloto = piloto
    form.instance.criado_por = request.user
    if form.is_valid():
        documento = form.save(commit=False)
        documento.ativo = True
        documento.save()
        messages.success(request, "Documento adicionado ao perfil.")
    else:
        messages.error(request, "Não foi possível adicionar o documento. Verifique os campos e o arquivo.")
    return redirect("perfil_usuario", pk=piloto.pk)
