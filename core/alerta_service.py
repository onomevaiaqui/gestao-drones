from datetime import timedelta
from urllib.parse import urlencode

from django.urls import reverse
from django.utils import timezone

from .compatibilidade_componentes import componente_exige_cadastro
from .models import AlertaResolvido, Alocacao, AvaliacaoRisco, Bateria, Componente, Documento, Drone, ImportacaoLog, Incidente, Manutencao, PlanoInspecao, QualificacaoPiloto


ORDEM_PRIORIDADE = {"critico": 0, "alto": 1, "medio": 2, "baixo": 3}


def gerar_regularizacoes(piloto=None):
    operacoes = (
        Alocacao.objects.filter(voo_sincronizado__importacoes_log__status="concluida")
        .select_related(
            "piloto", "drone", "solicitacao_voo__planejamento",
            "checklist_pre_voo", "registro_pos_voo",
        )
        .distinct()
    )
    if piloto is not None:
        operacoes = operacoes.filter(piloto=piloto)
    pendencias = []
    for operacao in operacoes:
        solicitacao = getattr(operacao, "solicitacao_voo", None)
        planejamento = solicitacao.planejamento if solicitacao else None
        checklist = getattr(operacao, "checklist_pre_voo", None)
        pos_voo = getattr(operacao, "registro_pos_voo", None)
        if not planejamento:
            faltantes = "planejamento, checklist e registro pós-voo"
            url = f"{reverse('planejamento_novo')}?{urlencode({'regularizar': operacao.pk})}"
        elif not checklist or not checklist.concluido:
            faltantes = "checklist e registro pós-voo"
            url = reverse("checklist_pre_voo", args=[operacao.pk])
        elif not pos_voo or not pos_voo.concluido:
            faltantes = "registro pós-voo"
            url = reverse("registro_pos_voo", kwargs={"alocacao_id": operacao.pk})
        else:
            continue
        pendencias.append({
            "categoria": "Regularização", "prioridade": "alto",
            "titulo": f"Regularizar operação de {operacao.data.strftime('%d/%m/%Y')}",
            "descricao": f"{operacao.drone.nome} · pendente: {faltantes}.",
            "url": url, "chave": f"regularizacao-{operacao.pk}",
            "data": operacao.data, "alocacao": operacao,
        })
    return pendencias


def gerar_alertas():
    hoje = timezone.localdate()
    alertas = []

    def adicionar(categoria, prioridade, titulo, descricao, url, chave, data=None):
        alertas.append({
            "categoria": categoria, "prioridade": prioridade, "titulo": titulo,
            "descricao": descricao, "url": url, "chave": chave, "data": data,
        })

    alertas.extend(gerar_regularizacoes())

    for documento in Documento.objects.select_related("piloto", "drone", "bateria"):
        if documento.situacao == "vencido":
            adicionar("Documentos", "critico", f"Documento vencido: {documento.titulo}", f"{documento.alvo} · vencido há {abs(documento.dias_para_vencer)} dia(s)", reverse("documento_editar", args=[documento.pk]), f"documento-{documento.pk}", documento.data_validade)
        elif documento.situacao == "vencendo":
            adicionar("Documentos", "alto", f"Documento próximo do vencimento: {documento.titulo}", f"{documento.alvo} · vence em {documento.dias_para_vencer} dia(s)", reverse("documento_editar", args=[documento.pk]), f"documento-{documento.pk}", documento.data_validade)

    for plano in PlanoInspecao.objects.select_related("drone", "bateria"):
        if plano.situacao == "vencido":
            adicionar("Inspeções", "critico", f"Inspeção vencida: {plano.nome}", f"{plano.alvo} · limite em {plano.progresso}%", reverse("plano_inspecao_executar", args=[plano.pk]), f"plano-{plano.pk}")
        elif plano.situacao == "proximo":
            adicionar("Inspeções", "alto", f"Inspeção próxima: {plano.nome}", f"{plano.alvo} · limite em {plano.progresso}%", reverse("plano_inspecao_executar", args=[plano.pk]), f"plano-{plano.pk}")

    for bateria in Bateria.objects.select_related("drone").exclude(status="descartada"):
        if bateria.saude_percentual < 80:
            prioridade = "critico" if bateria.saude_percentual < 60 else "alto"
            adicionar("Baterias", prioridade, f"Saúde baixa: {bateria.codigo}", f"Saúde estimada em {bateria.saude_percentual}%", reverse("bateria_detalhe", args=[bateria.pk]), f"bateria-saude-{bateria.pk}")
        if bateria.status == "manutencao":
            adicionar("Baterias", "alto", f"Bateria em manutenção: {bateria.codigo}", str(bateria.drone or "Sem drone vinculado"), reverse("bateria_detalhe", args=[bateria.pk]), f"bateria-status-{bateria.pk}")

    seriais_cadastrados = set(
        Bateria.objects.exclude(numero_serie="").values_list("numero_serie", flat=True)
    )
    importacoes_com_bateria = (
        ImportacaoLog.objects.filter(status="concluida")
        .exclude(bateria_serial_detectada="")
        .select_related("voo__drone")
        .order_by("bateria_serial_detectada", "criado_em")
    )
    seriais_alertados = set()
    for importacao in importacoes_com_bateria:
        serial = importacao.bateria_serial_detectada.strip()
        if not serial or serial in seriais_cadastrados or serial in seriais_alertados:
            continue
        seriais_alertados.add(serial)
        parametros = urlencode({
            "numero_serie": serial,
            "drone": importacao.voo.drone_id,
            "importacao": importacao.pk,
        })
        adicionar(
            "Baterias", "alto", f"Nova bateria identificada: {serial}",
            f"Detectada na telemetria do {importacao.voo.drone.nome}; cadastro pendente.",
            f"{reverse('bateria_nova')}?{parametros}", f"bateria-nova-{serial}",
            importacao.voo.data,
        )

    componentes_cadastrados = set(
        Componente.objects.exclude(numero_serie="").values_list("numero_serie", flat=True)
    )
    componentes_alertados = set()
    for importacao in ImportacaoLog.objects.filter(status="concluida").exclude(componentes_detectados=[]).select_related("voo__drone"):
        for detectado in importacao.componentes_detectados or []:
            serial = str(detectado.get("serial") or "").strip()
            exige_cadastro, _ = componente_exige_cadastro(
                importacao.voo.drone, detectado, importacao.drone_modelo_detectado
            )
            if not exige_cadastro or not serial or serial in componentes_cadastrados or serial in componentes_alertados:
                continue
            componentes_alertados.add(serial)
            parametros = urlencode({
                "numero_serie": serial, "drone": importacao.voo.drone_id,
                "tipo": detectado.get("tipo", "acessorio"),
                "nome": detectado.get("nome", "Acessório DJI detectado"),
                "importacao": importacao.pk,
            })
            adicionar(
                "Equipamentos", "alto", f"Novo equipamento identificado: {serial}",
                f"{detectado.get('nome', 'Acessório DJI')} detectado no {importacao.voo.drone.nome}; cadastro pendente.",
                f"{reverse('componente_novo')}?{parametros}", f"componente-novo-{serial}", importacao.voo.data,
            )

    for drone in Drone.objects.exclude(status__in=["ativo", "em_campo"]):
        prioridade = "critico" if drone.status == "indisponivel" else "alto"
        adicionar("Frota", prioridade, f"Drone {drone.get_status_display().lower()}: {drone.nome}", drone.modelo, reverse("drone_historico", args=[drone.pk]), f"drone-{drone.pk}")

    for manutencao in Manutencao.objects.select_related("drone").filter(concluida=False):
        dias = (hoje - manutencao.data_inicio).days
        prioridade = "alto" if dias >= 7 else "medio"
        adicionar("Manutenções", prioridade, f"Manutenção aberta: {manutencao.drone.nome}", f"{manutencao.get_tipo_display()} · aberta há {max(dias, 0)} dia(s)", reverse("manutencao_editar", args=[manutencao.pk]), f"manutencao-{manutencao.pk}", manutencao.data_inicio)

    alocacoes = Alocacao.objects.select_related("drone", "piloto").filter(status="concluido", registro_pos_voo__isnull=True, data__lte=hoje)
    for alocacao in alocacoes:
        atraso = (hoje - alocacao.data).days
        adicionar("Pós-voo", "alto" if atraso <= 2 else "critico", f"Pós-voo pendente: {alocacao.drone.nome}", f"{alocacao.piloto.nome} · operação de {alocacao.data.strftime('%d/%m/%Y')}", reverse("registro_pos_voo", kwargs={"alocacao_id": alocacao.pk}), f"posvoo-{alocacao.pk}", alocacao.data)

    proximas = Alocacao.objects.select_related("drone", "piloto").filter(status="reservado", data__range=[hoje, hoje + timedelta(days=1)])
    for alocacao in proximas:
        checklist = getattr(alocacao, "checklist_pre_voo", None)
        if not checklist or not checklist.concluido:
            adicionar("Checklist", "alto" if alocacao.data == hoje else "medio", f"Checklist pendente: {alocacao.drone.nome}", f"{alocacao.piloto.nome} · {alocacao.data.strftime('%d/%m/%Y')} às {alocacao.hora_inicio.strftime('%H:%M')}", reverse("checklist_pre_voo", args=[alocacao.pk]), f"checklist-{alocacao.pk}", alocacao.data)


    for incidente in Incidente.objects.select_related("alocacao__drone", "alocacao__piloto").exclude(status="encerrado"):
        prioridade = "critico" if incidente.gravidade in ["grave", "critico"] else "alto"
        adicionar("Incidentes", prioridade, f"Incidente {incidente.get_gravidade_display().lower()}: {incidente.alocacao.drone.nome}", f"{incidente.get_tipo_display()} · {incidente.get_status_display()}", reverse("incidente_editar", args=[incidente.pk]), f"incidente-{incidente.pk}", incidente.data_hora.date())

    for qualificacao in QualificacaoPiloto.objects.select_related("piloto").filter(ativo=True):
        if qualificacao.situacao == "vencida":
            adicionar("Pilotos", "critico", f"Qualificação vencida: {qualificacao.piloto.nome}", qualificacao.nome, reverse("perfil_operacional", args=[qualificacao.piloto_id]), f"qualificacao-{qualificacao.pk}", qualificacao.data_validade)
        elif qualificacao.situacao == "vencendo":
            adicionar("Pilotos", "alto", f"Qualificação próxima do vencimento: {qualificacao.piloto.nome}", f"{qualificacao.nome} · {qualificacao.dias_para_vencer} dia(s)", reverse("perfil_operacional", args=[qualificacao.piloto_id]), f"qualificacao-{qualificacao.pk}", qualificacao.data_validade)

    chaves_resolvidas = set(AlertaResolvido.objects.values_list("chave", flat=True))
    alertas = [alerta for alerta in alertas if alerta["chave"] not in chaves_resolvidas]
    alertas.sort(key=lambda a: (ORDEM_PRIORIDADE[a["prioridade"]], a["data"] or hoje, a["titulo"]))
    return alertas


def resumo_alertas(alertas=None):
    alertas = alertas if alertas is not None else gerar_alertas()
    return {
        "total": len(alertas),
        "criticos": sum(a["prioridade"] == "critico" for a in alertas),
        "altos": sum(a["prioridade"] == "alto" for a in alertas),
        "medios": sum(a["prioridade"] == "medio" for a in alertas),
    }
