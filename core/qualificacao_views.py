from collections import defaultdict
from io import BytesIO
from xml.sax.saxutils import escape

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import ConfiguracaoPapelTimbrado, ImportacaoLog, Piloto, QualificacaoPiloto, Voo
from .papel_timbrado import aplicar_papel_timbrado, tamanho_pagina_do_modelo
from .perfil_forms import DocumentoPerfilForm
from .qualificacao_forms import QualificacaoPilotoForm
from .views import _base_context, admin_required, usuario_e_admin, usuario_tem_visao_global, visao_global_required
from .voo_service import filtrar_voos_realizados


def _duracao_voo_segundos(voo):
    logs = getattr(voo, "logs_concluidos", [])
    duracoes = [log.duracao_segundos for log in logs if log.duracao_segundos is not None]
    if duracoes:
        return sum(duracoes)
    return 0


def _formatar_duracao(total_segundos):
    horas, restante = divmod(int(total_segundos), 3600)
    minutos, segundos = divmod(restante, 60)
    return f"{horas}h {minutos:02d}min {segundos:02d}s"


def _perfil_contexto(piloto):
    logs_concluidos = Prefetch(
        "importacoes_log",
        queryset=ImportacaoLog.objects.filter(status="concluida").order_by("inicio_registro"),
        to_attr="logs_concluidos",
    )
    voos = list(
        filtrar_voos_realizados(Voo.objects.select_related("drone", "alocacao_calendario"))
        .prefetch_related(logs_concluidos)
        .filter(piloto=piloto)
    )
    total_segundos = sum(_duracao_voo_segundos(v) for v in voos)
    por_drone = defaultdict(lambda: {"voos": 0, "segundos": 0})
    for voo in voos:
        por_drone[voo.drone.nome]["voos"] += 1
        por_drone[voo.drone.nome]["segundos"] += _duracao_voo_segundos(voo)
    experiencia = [
        {"drone": nome, "voos": dados["voos"], "duracao": _formatar_duracao(dados["segundos"])}
        for nome, dados in sorted(por_drone.items(), key=lambda item: -item[1]["segundos"])
    ]
    ultimo_voo = max((v.data for v in voos), default=None)
    dias_sem_voar = (timezone.localdate() - ultimo_voo).days if ultimo_voo else None
    qualificacoes = list(piloto.qualificacoes.select_related("documento"))
    documentos = list(piloto.documentos.filter(ativo=True))
    documentos_vinculados = {q.documento_id for q in qualificacoes if q.documento_id}
    qualificacoes_operacionais = []
    for q in qualificacoes:
        qualificacoes_operacionais.append({
            "titulo": q.nome, "detalhe": q.instituicao, "classificacao": q.get_categoria_display(),
            "data_emissao": q.data_conclusao, "data_validade": q.data_validade,
            "situacao": q.situacao, "dias_para_vencer": q.dias_para_vencer,
            "arquivo": q.documento.arquivo if q.documento_id and q.documento.arquivo else None,
            "qualificacao_id": q.pk, "documento_id": q.documento_id,
        })
    for documento in documentos:
        if documento.pk in documentos_vinculados:
            continue
        qualificacoes_operacionais.append({
            "titulo": documento.titulo, "detalhe": documento.numero,
            "classificacao": documento.get_tipo_display(), "data_emissao": documento.data_emissao,
            "data_validade": documento.data_validade, "situacao": documento.situacao,
            "dias_para_vencer": documento.dias_para_vencer, "arquivo": documento.arquivo,
            "qualificacao_id": None, "documento_id": documento.pk,
        })
    qualificacoes_operacionais.sort(key=lambda item: (item["titulo"] or "").lower())
    validas_operacionais = sum(item["situacao"] in ("valida", "valido", "sem_validade") for item in qualificacoes_operacionais)
    atencao_operacional = sum(item["situacao"] in ("vencendo", "vencida", "vencido") for item in qualificacoes_operacionais)
    return {
        "piloto": piloto, "qualificacoes": qualificacoes, "qualificacoes_operacionais": qualificacoes_operacionais,
        "documentos": documentos, "experiencia": experiencia,
        "total_voos_piloto": len(voos), "total_horas_piloto": _formatar_duracao(total_segundos),
        "ultimo_voo": ultimo_voo, "dias_sem_voar": dias_sem_voar,
        "qualificacoes_validas": validas_operacionais,
        "qualificacoes_atencao": atencao_operacional,
    }


def resumo_equipe_operacional(limite=None):
    equipe = []
    pilotos = Piloto.objects.filter(ativo=True).select_related("user").order_by("nome")
    for piloto in pilotos:
        perfil = _perfil_contexto(piloto)
        qualificacoes = perfil["qualificacoes"]
        vencidas = sum(q.situacao == "vencida" for q in qualificacoes)
        vencendo = sum(q.situacao == "vencendo" for q in qualificacoes)
        equipe.append({
            "piloto": piloto,
            "total_voos": perfil["total_voos_piloto"],
            "total_horas": perfil["total_horas_piloto"],
            "ultimo_voo": perfil["ultimo_voo"],
            "dias_sem_voar": perfil["dias_sem_voar"],
            "qualificacoes_validas": perfil["qualificacoes_validas"],
            "qualificacoes_vencendo": vencendo,
            "qualificacoes_vencidas": vencidas,
            "prioridade": (2 if vencidas else 1 if vencendo else 0),
        })
    equipe.sort(key=lambda item: (-item["prioridade"], item["piloto"].nome.lower()))
    return equipe[:limite] if limite else equipe


@login_required
def meu_perfil_operacional(request):
    if not hasattr(request.user, "piloto"):
        messages.error(request, "Seu usuário não está vinculado a um piloto.")
        return redirect("dashboard")
    return redirect("perfil_operacional", pk=request.user.piloto.pk)


@login_required
def perfil_operacional(request, pk):
    piloto = get_object_or_404(Piloto.objects.select_related("user"), pk=pk)
    if not usuario_tem_visao_global(request.user) and piloto.user_id != request.user.id:
        messages.error(request, "Você só pode consultar o próprio perfil operacional.")
        return redirect("dashboard")
    ctx = _perfil_contexto(piloto)
    ctx["perfil_proprio"] = piloto.user_id == request.user.id
    ctx["documento_form"] = DocumentoPerfilForm()
    ctx["pode_editar_perfil_operacional"] = usuario_e_admin(request.user) or ctx["perfil_proprio"]
    ctx.update(_base_context(request))
    return render(request, "qualificacoes/perfil.html", ctx)


@login_required
def perfil_operacional_pdf(request, pk):
    piloto = get_object_or_404(Piloto.objects.select_related("user"), pk=pk)
    if not usuario_e_admin(request.user) and piloto.user_id != request.user.id:
        return HttpResponse(status=403)

    contexto = _perfil_contexto(piloto)
    documentos = list(piloto.documentos.filter(ativo=True))
    configuracao = ConfiguracaoPapelTimbrado.atual()
    pagina = tamanho_pagina_do_modelo(configuracao.modelo_relatorios, A4)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=pagina, leftMargin=20 * mm, rightMargin=17 * mm,
        topMargin=32 * mm, bottomMargin=24 * mm,
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("PerfilTitulo", parent=estilos["Title"], fontSize=17, leading=20, textColor=colors.HexColor("#0C2238"))
    secao = ParagraphStyle("PerfilSecao", parent=estilos["Heading2"], fontSize=11, leading=14, textColor=colors.HexColor("#0C2238"), spaceBefore=8, spaceAfter=6)
    pequeno = ParagraphStyle("PerfilPequeno", parent=estilos["Normal"], fontSize=8, leading=10)
    elementos = [Paragraph("Relatório do Perfil Operacional", titulo), Spacer(1, 3 * mm)]

    dados_pessoais = [
        ["Piloto", piloto.nome], ["Usuário", piloto.user.username],
        ["E-mail", piloto.user.email or "Não informado"], ["Matrícula", piloto.matricula or "Não informada"],
        ["CPF", piloto.cpf or "Não informado"], ["Código SARPAS", piloto.codigo_sarpas or "Não informado"],
    ]
    tabela_dados = Table(dados_pessoais, colWidths=[38 * mm, 122 * mm])
    tabela_dados.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF0F7")), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#D8E1EB")), ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 5)]))
    elementos.extend([Paragraph("Identificação", secao), tabela_dados])

    resumo = Table([["Voos com telemetria", "Horas comprovadas", "Último voo"], [str(contexto["total_voos_piloto"]), contexto["total_horas_piloto"], contexto["ultimo_voo"].strftime("%d/%m/%Y") if contexto["ultimo_voo"] else "Sem voos"]], colWidths=[53 * mm] * 3)
    resumo.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0C2238")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#D8E1EB")), ("FONTSIZE", (0, 0), (-1, -1), 8), ("PADDING", (0, 0), (-1, -1), 6)]))
    elementos.extend([Paragraph("Resumo operacional", secao), resumo])

    experiencia = [["Aeronave", "Voos", "Tempo de voo"]] + [[escape(item["drone"]), str(item["voos"]), item["duracao"]] for item in contexto["experiencia"]]
    if len(experiencia) == 1:
        experiencia.append(["Nenhuma experiência registrada", "—", "—"])
    tabela_experiencia = Table(experiencia, repeatRows=1, colWidths=[80 * mm, 35 * mm, 45 * mm])
    tabela_experiencia.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0C2238")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#D8E1EB")), ("FONTSIZE", (0, 0), (-1, -1), 8), ("PADDING", (0, 0), (-1, -1), 5)]))
    elementos.extend([Paragraph("Experiência por aeronave", secao), tabela_experiencia])

    qualificacoes = [["Qualificação / curso", "Categoria", "Conclusão", "Validade", "Situação"]]
    for item in contexto["qualificacoes"]:
        qualificacoes.append([Paragraph(escape(item.nome), pequeno), item.get_categoria_display(), item.data_conclusao.strftime("%d/%m/%Y") if item.data_conclusao else "—", item.data_validade.strftime("%d/%m/%Y") if item.data_validade else "Sem validade", item.situacao.title()])
    if len(qualificacoes) == 1:
        qualificacoes.append(["Nenhuma qualificação cadastrada", "—", "—", "—", "—"])
    tabela_qualificacoes = Table(qualificacoes, repeatRows=1, colWidths=[55 * mm, 35 * mm, 25 * mm, 25 * mm, 20 * mm])
    tabela_qualificacoes.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0C2238")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#D8E1EB")), ("FONTSIZE", (0, 0), (-1, -1), 7), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 4)]))
    elementos.extend([Paragraph("Qualificações e treinamentos", secao), tabela_qualificacoes])

    docs = [["Documento", "Tipo", "Emissão", "Validade", "Situação"]]
    for item in documentos:
        docs.append([Paragraph(escape(item.titulo), pequeno), item.get_tipo_display(), item.data_emissao.strftime("%d/%m/%Y") if item.data_emissao else "Não possui", item.data_validade.strftime("%d/%m/%Y") if item.data_validade else "Não possui", item.situacao.replace("_", " ").title()])
    if len(docs) == 1:
        docs.append(["Nenhum documento cadastrado", "—", "—", "—", "—"])
    tabela_docs = Table(docs, repeatRows=1, colWidths=[55 * mm, 38 * mm, 24 * mm, 24 * mm, 20 * mm])
    tabela_docs.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0C2238")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#D8E1EB")), ("FONTSIZE", (0, 0), (-1, -1), 7), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 4)]))
    elementos.extend([Paragraph("Documentos operacionais", secao), tabela_docs, Spacer(1, 5 * mm), Paragraph(f"Relatório gerado pelo SISMOD em {timezone.localtime().strftime('%d/%m/%Y %H:%M')}.", pequeno)])
    doc.build(elementos)
    conteudo = aplicar_papel_timbrado(buffer.getvalue(), configuracao.modelo_relatorios)
    resposta = HttpResponse(conteudo, content_type="application/pdf")
    modo = "inline" if request.GET.get("modo") == "visualizar" else "attachment"
    resposta["Content-Disposition"] = f'{modo}; filename="perfil_operacional_{piloto.pk}.pdf"'
    return resposta


@visao_global_required
def equipe_operacional(request):
    ctx = {"equipe": resumo_equipe_operacional()}
    ctx.update(_base_context(request))
    return render(request, "qualificacoes/equipe.html", ctx)


@admin_required
def qualificacao_nova(request, piloto_id):
    piloto = get_object_or_404(Piloto, pk=piloto_id)
    form = QualificacaoPilotoForm(request.POST or None, piloto=piloto)
    if form.is_valid():
        qualificacao = form.save(commit=False)
        qualificacao.piloto = piloto
        qualificacao.criado_por = request.user
        qualificacao.save()
        messages.success(request, "Qualificação cadastrada.")
        return redirect("perfil_operacional", pk=piloto.pk)
    ctx = {"form": form, "piloto": piloto, "titulo": "Nova qualificação"}
    ctx.update(_base_context(request))
    return render(request, "qualificacoes/form.html", ctx)


@login_required
def qualificacao_editar(request, pk):
    qualificacao = get_object_or_404(QualificacaoPiloto.objects.select_related("piloto"), pk=pk)
    if not usuario_e_admin(request.user) and qualificacao.piloto.user_id != request.user.id:
        messages.error(request, "Você só pode editar suas próprias qualificações.")
        return redirect("dashboard")
    form = QualificacaoPilotoForm(request.POST or None, instance=qualificacao, piloto=qualificacao.piloto)
    if form.is_valid():
        form.save()
        messages.success(request, "Qualificação atualizada.")
        return redirect("perfil_operacional", pk=qualificacao.piloto_id)
    ctx = {"form": form, "piloto": qualificacao.piloto, "titulo": "Editar qualificação"}
    ctx.update(_base_context(request))
    return render(request, "qualificacoes/form.html", ctx)
