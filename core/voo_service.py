def filtrar_voos_realizados(queryset):
    """Mantém somente operações comprovadas por telemetria processada."""
    return queryset.filter(importacoes_log__status="concluida").distinct()
