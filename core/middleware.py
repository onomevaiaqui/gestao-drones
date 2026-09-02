from django.shortcuts import redirect
from django.http import HttpResponseForbidden

from .licenciamento import estado_licenca


class ModoAcessoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            piloto = getattr(request.user, "piloto", None)
            if piloto is not None and not piloto.ativo:
                request.session.flush()
                return redirect("login")
            modo = request.session.get("modo_acesso")
            request.user._modo_acesso = modo
            if modo == "pendente" and request.path not in ("/selecionar-perfil/", "/logout/"):
                return redirect("selecionar_modo_acesso")
            if modo in ("usuario", "coordenador") and request.path.startswith("/admin/"):
                return redirect("dashboard")
        return self.get_response(request)


class LicencaSISMODMiddleware:
    """Bloqueia somente alterações depois do fim da tolerância."""

    ROTAS_LIVRES = ("/login/", "/logout/", "/selecionar-perfil/", "/configuracao/licenca/", "/admin/login/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in ("GET", "HEAD", "OPTIONS") and not any(request.path.startswith(item) for item in self.ROTAS_LIVRES):
            estado = estado_licenca()
            if not estado.permite_alteracoes:
                return HttpResponseForbidden(
                    f"{estado.titulo}. {estado.mensagem} Um administrador deve ativar uma licença válida."
                )
        return self.get_response(request)
