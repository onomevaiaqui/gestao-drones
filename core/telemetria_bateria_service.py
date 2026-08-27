"""Integração entre seriais detectados na telemetria e o cadastro de baterias."""

from .models import Bateria


def seriais_bateria_do_voo(voo):
    return list(
        voo.importacoes_log.filter(status="concluida")
        .exclude(bateria_serial_detectada="")
        .order_by("bateria_serial_detectada")
        .values_list("bateria_serial_detectada", flat=True)
        .distinct()
    )


def baterias_e_seriais_novos(voo):
    seriais = seriais_bateria_do_voo(voo)
    cadastradas = list(Bateria.objects.filter(numero_serie__in=seriais).order_by("codigo"))
    cadastrados = {item.numero_serie for item in cadastradas}
    return cadastradas, [serial for serial in seriais if serial not in cadastrados]


def resumo_pos_voo_telemetria(alocacao):
    voo = getattr(alocacao, "voo_sincronizado", None)
    if voo is None:
        return {
            "voo": None, "tem_telemetria": False, "distancia_m": None,
            "quantidade_baterias": 0, "baterias": [], "seriais_novos": [],
        }
    tem_telemetria = voo.importacoes_log.filter(status="concluida").exists()
    baterias, seriais_novos = baterias_e_seriais_novos(voo)
    return {
        "voo": voo,
        "tem_telemetria": tem_telemetria,
        "distancia_m": voo.distancia_m if tem_telemetria else None,
        "quantidade_baterias": len(baterias) + len(seriais_novos),
        "baterias": baterias,
        "seriais_novos": seriais_novos,
    }


def sincronizar_registro_pos_voo(voo):
    """Atualiza um pós-voo existente quando novos logs são importados."""
    alocacao = voo.alocacao_calendario
    if alocacao is None:
        return None
    registro = getattr(alocacao, "registro_pos_voo", None)
    if registro is None:
        return None
    resumo = resumo_pos_voo_telemetria(alocacao)
    registro.distancia_m = resumo["distancia_m"]
    registro.baterias_utilizadas = resumo["quantidade_baterias"]
    registro.save(update_fields=["distancia_m", "baterias_utilizadas", "atualizado_em"])
    registro.baterias.set(resumo["baterias"])
    return registro
