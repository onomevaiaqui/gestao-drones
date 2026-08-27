"""Políticas de acesso compartilhadas pelos módulos do SISMOD."""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import Piloto


def usuario_tem_perfil_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        return user.piloto.perfil == "administrador" and user.piloto.ativo
    except Piloto.DoesNotExist:
        return False


def usuario_e_admin(user):
    if not usuario_tem_perfil_admin(user):
        return False
    return getattr(user, "_modo_acesso", None) not in ("usuario", "coordenador", "pendente")


def usuario_e_coordenador(user):
    if not user.is_authenticated:
        return False
    modo = getattr(user, "_modo_acesso", None)
    if usuario_tem_perfil_admin(user):
        return modo == "coordenador"
    try:
        return user.piloto.perfil == "coordenador" and user.piloto.ativo
    except Piloto.DoesNotExist:
        return False


def usuario_tem_visao_global(user):
    return usuario_e_admin(user) or usuario_e_coordenador(user)


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not usuario_e_admin(request.user):
            messages.error(request, "Você não tem permissão para acessar esta área.")
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)

    return wrapper


def visao_global_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not usuario_tem_visao_global(request.user):
            messages.error(request, "Você não tem permissão para acessar esta área.")
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)

    return wrapper
