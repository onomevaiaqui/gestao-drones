from django.conf import settings
from django.shortcuts import redirect
from django.http import HttpResponseBadRequest

import logging
from django.db import transaction
from .login_security import endereco_cliente, proxy_confiavel
from .permissoes import usuario_tem_perfil_admin
from .mfa_service import sessao_mfa_valida, limpar_verificacao_mfa


class ProxyConfiavelMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not proxy_confiavel(request.META.get("REMOTE_ADDR", "")):
            for cabecalho in ("HTTP_X_FORWARDED_PROTO", "HTTP_X_FORWARDED_FOR", "HTTP_X_FORWARDED_HOST", "HTTP_FORWARDED"):
                request.META.pop(cabecalho, None)
        return self.get_response(request)


class SegurancaContaMiddleware:
    ROTAS_LIVRES = ("/login/", "/logout/", "/seguranca/mfa/", "/static/", "/infra/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if usuario and usuario.is_authenticated and not request.path.startswith(self.ROTAS_LIVRES):
            configuracao = getattr(usuario, "configuracao_seguranca", None)
            obrigatorio = settings.SISMOD_MFA_ADMIN_REQUIRED and usuario_tem_perfil_admin(usuario)
            if obrigatorio and not (configuracao and configuracao.mfa_ativo):
                return redirect("mfa_configurar")
            if configuracao and configuracao.mfa_ativo and not sessao_mfa_valida(request.session, configuracao):
                limpar_verificacao_mfa(request.session)
                request.session["destino_apos_mfa"] = request.get_full_path()
                return redirect("mfa_verificar")
        return self.get_response(request)


class UploadSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def process_exception(self, request, exception):
        from .upload_security import ArquivoInseguro
        if isinstance(exception, ArquivoInseguro):
            logging.getLogger("sismod.security").warning("UPLOAD_REJECTED: arquivo recusado antes da persistência")
            return HttpResponseBadRequest(str(exception))

    def __call__(self, request):
        eh_upload = (request.content_type or "").casefold().startswith("multipart/form-data")
        api_dji_sem_arquivo = request.path.startswith("/integracoes/dji/") and "/midias/upload/" not in request.path
        if request.method in {"POST", "PUT", "PATCH"} and eh_upload and not api_dji_sem_arquivo and request.FILES:
            from .models import AlertaSeguranca
            from .upload_security import ArquivoInseguro, verificar_uploads
            try:
                verificar_uploads(
                    arquivo for nome in request.FILES for arquivo in request.FILES.getlist(nome)
                )
            except ArquivoInseguro as erro:
                AlertaSeguranca.objects.create(
                    tipo="upload_bloqueado", nivel="alto", mensagem=str(erro),
                    endereco_ip=endereco_cliente(request),
                )
                return HttpResponseBadRequest(str(erro))
        return self.get_response(request)


class AuditoriaMiddleware:
    METODOS = {"POST", "PUT", "PATCH", "DELETE"}
    TERMOS_DOWNLOAD = ("download", "baixar", "pdf", "exportar")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        rota = getattr(getattr(request, "resolver_match", None), "route", "") or "rota_nao_resolvida"
        auditar = request.method in self.METODOS or any(termo in rota.casefold() for termo in self.TERMOS_DOWNLOAD)
        if auditar and not rota.startswith(("static/", "infra/health", "infra/mediamtx")):
            try:
                from .models import EventoAuditoria
                with transaction.atomic():
                    EventoAuditoria.objects.create(
                    usuario=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
                    acao=(getattr(getattr(request, "resolver_match", None), "url_name", "") or "requisicao")[:80],
                    metodo=request.method,
                    caminho=rota[:500],
                    status_http=response.status_code,
                    endereco_ip=endereco_cliente(request),
                )
            except Exception:
                # Não registrar exceção/SQL: podem conter informações sensíveis.
                logging.getLogger("sismod.security").error("AUDIT_WRITE_FAILED: falha ao persistir evento de auditoria")
                try:
                    from .models import AlertaSeguranca
                    AlertaSeguranca.objects.get_or_create(
                        tipo="falha_auditoria", resolvido=False,
                        defaults={"nivel": "critico", "mensagem": "Falha na gravação da auditoria. Verifique os logs e o banco."},
                    )
                except Exception:
                    logging.getLogger("sismod.security").critical("AUDIT_ALERT_FAILED: alerta não pôde ser persistido")
        return response
