"""Escopo de visualização e operação das estações remotas."""

from .models import DJIDock
from .permissoes import usuario_tem_visao_global


def docks_visiveis(user):
    consulta = DJIDock.objects.filter(ativo=True)
    if usuario_tem_visao_global(user):
        return consulta
    return consulta.filter(acessos__usuario=user, acessos__ativo=True).distinct()


def docks_operaveis(user):
    consulta = docks_visiveis(user)
    if usuario_tem_visao_global(user):
        return consulta
    return consulta.filter(acessos__usuario=user, acessos__ativo=True, acessos__pode_operar=True).distinct()


def pode_visualizar_dock(user, dock):
    return docks_visiveis(user).filter(pk=dock.pk).exists()


def pode_operar_dock(user, dock):
    return docks_operaveis(user).filter(pk=dock.pk).exists()
