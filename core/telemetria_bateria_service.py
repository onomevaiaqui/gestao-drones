"""Integração entre seriais detectados na telemetria e o cadastro de baterias."""

from .models import Bateria


def baterias_detectadas_da_importacao(importacao):
    """Normaliza logs novos (várias baterias) e antigos (uma bateria)."""
    itens = []
    vistos = set()
    for detectada in importacao.baterias_detectadas or []:
        serial = str(detectada.get("serial") or "").strip()
        if not serial or serial in vistos:
            continue
        vistos.add(serial)
        itens.append({
            "serial": serial,
            "ciclos": detectada.get("ciclos"),
            "saude_percentual": detectada.get("saude_percentual"),
            "slot": detectada.get("slot"),
        })
    serial_legado = (importacao.bateria_serial_detectada or "").strip()
    if serial_legado and serial_legado not in vistos:
        itens.append({"serial": serial_legado, "ciclos": importacao.bateria_ciclos_detectados})
    return itens


def sincronizar_ciclos_bateria(importacao):
    """Atualiza ciclos e saúde de todas as baterias identificadas no log."""
    atualizadas = []
    for detectada in baterias_detectadas_da_importacao(importacao):
        bateria = Bateria.objects.filter(numero_serie=detectada["serial"]).first()
        if bateria is None:
            continue
        campos = []
        ciclos = detectada.get("ciclos")
        if ciclos is not None and (bateria.ciclos_detectados_log is None or ciclos > bateria.ciclos_detectados_log):
            bateria.ciclos_detectados_log = ciclos
            campos.append("ciclos_detectados_log")
        saude = detectada.get("saude_percentual")
        if saude is not None and bateria.saude_percentual != saude:
            bateria.saude_percentual = saude
            campos.append("saude_percentual")
        if campos:
            bateria.save(update_fields=campos + ["atualizado_em"])
        atualizadas.append(bateria)
    return atualizadas[0] if atualizadas else None


def seriais_bateria_do_voo(voo):
    seriais = {
        item["serial"]
        for importacao in voo.importacoes_log.filter(status="concluida")
        for item in baterias_detectadas_da_importacao(importacao)
    }
    return sorted(seriais)


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
