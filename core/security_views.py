import csv

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .mfa_service import (
    consumir_codigo_recuperacao,
    consumir_totp,
    contador_totp_valido,
    criptografar_segredo,
    gerar_codigos_recuperacao,
    gerar_segredo,
    qr_data_uri,
)
from .models import ConfiguracaoSegurancaUsuario, EventoAuditoria
from .permissoes import admin_required, usuario_tem_perfil_admin
from .login_security import esta_bloqueado, registrar_falha, limpar_falhas


def _desafio_bloqueado(request, finalidade):
    identificador = f"desafio:{finalidade}:{request.user.pk}"
    if esta_bloqueado(request, identificador):
        return HttpResponse("Muitas tentativas inválidas. Aguarde antes de tentar novamente.", status=429)
    return None


@login_required
def mfa_configurar(request):
    if request.method == "POST":
        bloqueio = _desafio_bloqueado(request, "mfa")
        if bloqueio is not None:
            return bloqueio
    configuracao, _ = ConfiguracaoSegurancaUsuario.objects.get_or_create(usuario=request.user)
    if configuracao.mfa_ativo:
        return redirect("seguranca_conta")
    segredo = request.session.get("mfa_segredo_pendente") or gerar_segredo()
    request.session["mfa_segredo_pendente"] = segredo
    if request.method == "POST":
        contador = contador_totp_valido(segredo, request.POST.get("codigo"))
        if contador is not None:
            limpar_falhas(request, f"desafio:mfa:{request.user.pk}")
            codigos, hashes = gerar_codigos_recuperacao()
            configuracao.mfa_ativo = True
            configuracao.ultimo_contador_mfa = contador
            configuracao.segredo_mfa_criptografado = criptografar_segredo(segredo)
            configuracao.codigos_recuperacao = hashes
            configuracao.mfa_ativado_em = timezone.now()
            configuracao.save()
            request.session.pop("mfa_segredo_pendente", None)
            request.session["mfa_verificado"] = True
            request.session["mfa_codigos_novos"] = codigos
            messages.success(request, "Autenticação em duas etapas ativada.")
            return redirect("seguranca_conta")
        registrar_falha(request, f"desafio:mfa:{request.user.pk}")
        messages.error(request, "Código inválido. Confira o horário do dispositivo e tente novamente.")
    return render(request, "security/mfa_configurar.html", {
        "segredo": segredo,
        "qr_data_uri": qr_data_uri(request.user, segredo),
    })


@login_required
def mfa_verificar(request):
    configuracao = get_object_or_404(ConfiguracaoSegurancaUsuario, usuario=request.user, mfa_ativo=True)
    if request.method == "POST":
        bloqueio = _desafio_bloqueado(request, "mfa")
        if bloqueio is not None:
            return bloqueio
        codigo = request.POST.get("codigo")
        valido = consumir_totp(configuracao, codigo)
        valido = valido or consumir_codigo_recuperacao(configuracao, codigo)
        if valido:
            limpar_falhas(request, f"desafio:mfa:{request.user.pk}")
            request.session["mfa_verificado"] = True
            destino = request.session.pop("destino_apos_mfa", None) or "dashboard"
            return redirect(destino)
        registrar_falha(request, f"desafio:mfa:{request.user.pk}")
        messages.error(request, "Código de autenticação inválido.")
    return render(request, "security/mfa_verificar.html")


@login_required
def seguranca_conta(request):
    configuracao, _ = ConfiguracaoSegurancaUsuario.objects.get_or_create(usuario=request.user)
    sessoes = []
    for sessao in Session.objects.filter(expire_date__gt=timezone.now()):
        try:
            if str(sessao.get_decoded().get("_auth_user_id")) == str(request.user.pk):
                sessoes.append({"chave": sessao.session_key, "expira_em": sessao.expire_date, "atual": sessao.session_key == request.session.session_key})
        except Exception:
            continue
    codigos = request.session.pop("mfa_codigos_novos", None)
    return render(request, "security/conta.html", {"configuracao": configuracao, "sessoes": sessoes, "codigos": codigos})


@admin_required
def confirmar_acao_critica(request):
    pendente = request.session.get("acao_critica_pendente")
    if not pendente:
        messages.error(request, "Nenhuma ação crítica aguarda confirmação.")
        return redirect("dashboard")
    if request.method == "POST":
        bloqueio = _desafio_bloqueado(request, "comando")
        if bloqueio is not None:
            return bloqueio
        if not request.user.check_password(request.POST.get("senha", "")):
            registrar_falha(request, f"desafio:comando:{request.user.pk}")
            messages.error(request, "Senha atual inválida.")
        elif pendente.get("tipo") == "autorizar_comando_dock":
            limpar_falhas(request, f"desafio:comando:{request.user.pk}")
            from .dji_command_safety import autorizar_intencao
            from .models import DJIDockComando
            comando = get_object_or_404(DJIDockComando, pk=pendente.get("comando"), dock_id=pendente.get("dock"))
            try:
                autorizar_intencao(comando, request.user)
            except (PermissionError, ValueError) as erro:
                messages.error(request, str(erro))
            else:
                request.session["reauth_em"] = timezone.now().timestamp()
                request.session.pop("acao_critica_pendente", None)
                messages.success(request, "Identidade confirmada e intenção crítica autorizada. Nenhum comando foi publicado.")
            return redirect("dji_dock_detalhe", pk=comando.dock_id)
    return render(request, "security/confirmar_acao_critica.html")


@login_required
@require_POST
def sessao_revogar(request, chave):
    sessao = get_object_or_404(Session, session_key=chave)
    if str(sessao.get_decoded().get("_auth_user_id")) != str(request.user.pk):
        messages.error(request, "Sessão não encontrada.")
    elif chave == request.session.session_key:
        messages.error(request, "Use Sair para encerrar a sessão atual.")
    else:
        sessao.delete()
        messages.success(request, "Sessão encerrada.")
    return redirect("seguranca_conta")


@login_required
@require_POST
def mfa_desativar(request):
    if not request.session.get("mfa_verificado"):
        return redirect("mfa_verificar")
    configuracao = get_object_or_404(ConfiguracaoSegurancaUsuario, usuario=request.user, mfa_ativo=True)
    if not request.user.check_password(request.POST.get("senha", "")):
        messages.error(request, "Senha atual inválida.")
    elif usuario_tem_perfil_admin(request.user) and settings.SISMOD_MFA_ADMIN_REQUIRED:
        messages.error(request, "A autenticação em duas etapas é obrigatória para administradores.")
    else:
        configuracao.mfa_ativo = False
        configuracao.segredo_mfa_criptografado = ""
        configuracao.codigos_recuperacao = []
        configuracao.mfa_ativado_em = None
        configuracao.save()
        request.session.pop("mfa_verificado", None)
        messages.success(request, "Autenticação em duas etapas desativada.")
    return redirect("seguranca_conta")


@admin_required
def auditoria(request):
    eventos = EventoAuditoria.objects.select_related("usuario")[:500]
    from .models import AlertaSeguranca
    alertas = AlertaSeguranca.objects.filter(resolvido=False)[:100]
    return render(request, "security/auditoria.html", {"eventos": eventos, "alertas_seguranca": alertas})


def _celula_csv(valor):
    texto = str(valor or "")
    return "'" + texto if texto.startswith(("=", "+", "-", "@")) else texto


@admin_required
def auditoria_exportar(request):
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = 'attachment; filename="auditoria-sismod.csv"'
    resposta.write("\ufeff")
    escritor = csv.writer(resposta, delimiter=";")
    escritor.writerow(["Data", "Usuário", "Ação", "Método", "Rota", "HTTP", "IP"])
    eventos = EventoAuditoria.objects.select_related("usuario")[:10000]
    for evento in eventos:
        escritor.writerow([
            evento.ocorrido_em.isoformat(),
            _celula_csv(evento.usuario.username if evento.usuario else "Não autenticado"),
            _celula_csv(evento.acao), evento.metodo, _celula_csv(evento.caminho),
            evento.status_http, evento.endereco_ip or "",
        ])
    return resposta


@admin_required
@require_POST
def alerta_seguranca_resolver(request, pk):
    from .models import AlertaSeguranca
    alerta = get_object_or_404(AlertaSeguranca, pk=pk, resolvido=False)
    alerta.resolvido = True
    alerta.resolvido_em = timezone.now()
    alerta.resolvido_por = request.user
    alerta.save(update_fields=["resolvido", "resolvido_em", "resolvido_por"])
    messages.success(request, "Alerta de segurança marcado como resolvido.")
    return redirect("auditoria")
