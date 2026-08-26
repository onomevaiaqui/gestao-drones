from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _texto(valor):
    return escape(str(valor or "Não informado")).replace("\n", "<br/>")


def gerar_pdf_avaliacao(avaliacao):
    out = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="DocTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=16, leading=19, textColor=colors.HexColor("#0B2B55"), alignment=TA_CENTER, spaceAfter=6))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor("#0B2B55"), spaceBefore=8, spaceAfter=6))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=7.5, leading=10))
    styles.add(ParagraphStyle(name="BodyDoc", parent=styles["BodyText"], fontSize=8.5, leading=12))
    doc = SimpleDocTemplate(out, pagesize=A4, rightMargin=14*mm, leftMargin=14*mm, topMargin=17*mm, bottomMargin=18*mm,
                            title="Avaliação de Risco Operacional")

    def footer(canvas, document):
        canvas.saveState(); canvas.setFont("Helvetica", 7); canvas.setFillColor(colors.HexColor("#52657A"))
        canvas.drawString(14*mm, 9*mm, "Rubrica: ____________________")
        canvas.drawRightString(A4[0]-14*mm, 9*mm, f"Página {document.page}")
        canvas.restoreState()

    def section(title, body):
        return [Paragraph(title, styles["Section"]), Paragraph(_texto(body), styles["BodyDoc"])]

    s = avaliacao.solicitacao
    story = [Paragraph("AVALIAÇÃO DE RISCO OPERACIONAL", styles["DocTitle"]),
             Paragraph("Modelo estruturado com base no Apêndice B da IS E94-003A da ANAC", styles["Small"]), Spacer(1, 4*mm)]
    ident = [[Paragraph("Operador / responsável", styles["Small"]), Paragraph("CPF/CNPJ", styles["Small"])],
             [Paragraph(_texto(avaliacao.operador_nome), styles["BodyDoc"]), Paragraph(_texto(avaliacao.operador_documento), styles["BodyDoc"])],
             [Paragraph("Aeronave / cadastro / série", styles["Small"]), Paragraph("Piloto", styles["Small"])],
             [Paragraph(_texto(avaliacao.aeronave_identificacao), styles["BodyDoc"]), Paragraph(_texto(s.piloto.nome), styles["BodyDoc"])]]
    t = Table(ident, colWidths=[112*mm, 55*mm]); t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.4,colors.HexColor("#B8C5D3")),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#EAF1F8")),("BACKGROUND",(0,2),(-1,2),colors.HexColor("#EAF1F8")),("VALIGN",(0,0),(-1,-1),"TOP"),("PADDING",(0,0),(-1,-1),5)])); story += [t]
    story += section("1. Cenário operacional", avaliacao.cenario_operacional)
    story += section("2. Aspectos gerais da operação", avaliacao.aspectos_gerais)
    story += section("3. Legislação e documentos aplicáveis", avaliacao.legislacao_aplicavel)
    prep = f"Operação distante de terceiros: {avaliacao.get_area_distante_terceiros_display() or 'Não informado'}\nPessoas expostas: {'Sim' if avaliacao.pessoas_expostas else 'Não'}\nÁrea operacional controlada: {'Sim' if avaliacao.area_controlada else 'Não'}\nTreinamento específico requerido: {'Sim' if avaliacao.treinamento_requerido else 'Não'}\nTreinamento/capacitação: {avaliacao.descricao_treinamento or 'Não informado'}"
    story += section("4. Requisitos de preparação e treinamento", prep)
    story += section("5. Condições meteorológicas previstas", avaliacao.condicoes_meteorologicas)
    story += section("6. Procedimento em acidente com lesão", avaliacao.procedimento_acidente)
    story += [PageBreak(), Paragraph("7. Situações de risco e medidas mitigadoras", styles["Section"])]
    for idx, item in enumerate(avaliacao.situacoes_risco, 1):
        dados = [[Paragraph(f"{idx}. {_texto(item.get('titulo'))}", styles["Small"]), "", "", ""],
                 [Paragraph("Perigo / consequência", styles["Small"]), Paragraph(_texto(item.get("perigo")), styles["Small"]), Paragraph("Risco inicial", styles["Small"]), Paragraph(f"{_texto(item.get('risco'))} — {_texto(item.get('tolerabilidade'))}", styles["Small"])],
                 [Paragraph("Medidas mitigadoras", styles["Small"]), Paragraph(_texto(item.get("medidas")), styles["Small"]), Paragraph("Risco residual", styles["Small"]), Paragraph(f"{_texto(item.get('risco_residual'))} — {_texto(item.get('tolerabilidade_residual'))}", styles["Small"])]]
        tab = Table(dados, colWidths=[30*mm, 87*mm, 25*mm, 25*mm])
        tab.setStyle(TableStyle([("SPAN",(0,0),(-1,0)),("GRID",(0,0),(-1,-1),.4,colors.HexColor("#B8C5D3")),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#DCEAF7")),("VALIGN",(0,0),(-1,-1),"TOP"),("PADDING",(0,0),(-1,-1),3)])); story += [KeepTogether([tab, Spacer(1, 2*mm)])]
    matrix = [["Prob. / Severidade", "A", "B", "C", "D", "E"], ["5", "Extremo", "Extremo", "Alto", "Moderado", "Moderado"], ["4", "Extremo", "Alto", "Moderado", "Moderado", "Baixo"], ["3", "Alto", "Moderado", "Moderado", "Baixo", "Baixo"], ["2", "Moderado", "Moderado", "Baixo", "Baixo", "Muito baixo"], ["1", "Moderado", "Baixo", "Baixo", "Muito baixo", "Muito baixo"]]
    mt = Table(matrix, colWidths=[35*mm]+[26*mm]*5); mt.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.4,colors.grey),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#DCEAF7")),("ALIGN",(0,0),(-1,-1),"CENTER"),("FONTSIZE",(0,0),(-1,-1),7),("PADDING",(0,0),(-1,-1),4)]))
    story += [Paragraph("8. Matriz de risco adotada", styles["Section"]), mt, Spacer(1, 4*mm)]
    story += section("9. Observações", avaliacao.observacoes)
    declaracao = "Declaro que conheço e cumprirei a legislação aplicável à operação, que revisei as situações de risco e as medidas mitigadoras descritas e que aceito o risco residual declarado."
    story += [Paragraph("10. Declaração", styles["Section"]), Paragraph(declaracao, styles["BodyDoc"]), Spacer(1, 4*mm)]
    data = avaliacao.data_avaliacao.strftime("%d/%m/%Y") if avaliacao.data_avaliacao else "____/____/________"
    validade = avaliacao.validade_ate.strftime("%d/%m/%Y") if avaliacao.validade_ate else "Não informada"
    assinatura = Table([[f"Data: {data}", f"Validade: {validade}"], ["\n________________________________________", "\n________________________________________"], [avaliacao.responsavel_informacoes or "Responsável pelas informações", "Assinatura do piloto/responsável"]], colWidths=[83.5*mm]*2)
    assinatura.setStyle(TableStyle([("ALIGN",(0,0),(-1,-1),"CENTER"),("FONTSIZE",(0,0),(-1,-1),8),("VALIGN",(0,0),(-1,-1),"BOTTOM")]))
    story += [assinatura]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()
