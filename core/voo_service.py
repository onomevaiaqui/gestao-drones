from django.db.models import Q


def filtrar_voos_realizados(queryset):
    """Exclui reservas futuras e mantém operações com evidência de realização."""
    return queryset.filter(
        Q(importacoes_log__status="concluida")
        | Q(alocacao_calendario__status="concluido")
        | Q(
            alocacao_calendario__isnull=True,
            data__isnull=False,
            hora_inicio__isnull=False,
            hora_fim__isnull=False,
        )
    ).distinct()
