from django.shortcuts import redirect


class ModoAcessoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            modo = request.session.get("modo_acesso")
            request.user._modo_acesso = modo
            if modo == "pendente" and request.path not in ("/selecionar-perfil/", "/logout/"):
                return redirect("selecionar_modo_acesso")
            if modo in ("usuario", "coordenador") and request.path.startswith("/admin/"):
                return redirect("dashboard")
        return self.get_response(request)
