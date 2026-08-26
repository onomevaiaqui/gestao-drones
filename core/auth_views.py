from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .views import usuario_e_coordenador, usuario_tem_perfil_admin


class LoginSistemaView(LoginView):
    template_name = "registration/login.html"

    def form_valid(self, form):
        resposta = super().form_valid(form)
        if usuario_tem_perfil_admin(self.request.user):
            self.request.session["modo_acesso"] = "pendente"
        elif usuario_e_coordenador(self.request.user):
            self.request.session["modo_acesso"] = "coordenador"
        else:
            self.request.session["modo_acesso"] = "usuario"
        return resposta

    def get_success_url(self):
        destino = super().get_success_url()
        if usuario_tem_perfil_admin(self.request.user):
            self.request.session["destino_apos_modo"] = destino
            return "/selecionar-perfil/"
        return destino


@login_required
def selecionar_modo_acesso(request):
    if not usuario_tem_perfil_admin(request.user):
        request.session["modo_acesso"] = "usuario"
        return redirect("dashboard")

    possui_perfil_usuario = bool(
        hasattr(request.user, "piloto") and request.user.piloto.ativo
    )
    if request.method == "POST":
        modo = request.POST.get("modo")
        if modo == "admin":
            request.session["modo_acesso"] = "admin"
        elif modo == "usuario" and possui_perfil_usuario:
            request.session["modo_acesso"] = "usuario"
        else:
            messages.error(request, "O perfil selecionado não está disponível para esta conta.")
            return redirect("selecionar_modo_acesso")
        destino = request.session.pop("destino_apos_modo", None) or "dashboard"
        return redirect(destino)

    return render(request, "registration/selecionar_perfil.html", {
        "possui_perfil_usuario": possui_perfil_usuario,
        "modo_atual": request.session.get("modo_acesso"),
    })
