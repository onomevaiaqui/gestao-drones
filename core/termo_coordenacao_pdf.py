from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def gerar_termo_coordenacao_pdf(termo):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=14*mm, rightMargin=14*mm, topMargin=13*mm, bottomMargin=13*mm)
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle("TCoTitulo", parent=styles["Title"], fontSize=14, leading=17, textColor=colors.HexColor("#0C2238"), spaceAfter=6)
    normal = ParagraphStyle("TCoNormal", parent=styles["Normal"], fontSize=7.5, leading=9.5)
    secao = ParagraphStyle("TCoSecao", parent=normal, fontName="Helvetica-Bold", textColor=colors.white, alignment=1)

    def p(valor):
        return Paragraph(escape(str(valor or "—")).replace("\n", "<br/>"), normal)

    def tabela_secao(nome, linhas):
        dados = [[Paragraph(escape(nome), secao), ""]] + [[p(a), p(b)] for a, b in linhas]
        tabela = Table(dados, colWidths=[91*mm, 91*mm], repeatRows=1)
        tabela.setStyle(TableStyle([
            ("SPAN", (0,0), (1,0)), ("BACKGROUND", (0,0), (1,0), colors.HexColor("#0C2238")),
            ("GRID", (0,0), (-1,-1), .45, colors.HexColor("#8B98A7")),
            ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 5),
            ("RIGHTPADDING", (0,0), (-1,-1), 5), ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        return tabela

    elementos = [Paragraph("TERMO DE COORDENAÇÃO PARA OPERAÇÃO UAS", titulo), p("Todos os campos devem ser conferidos antes da assinatura e do envio no SARPAS."), Spacer(1, 3*mm)]
    elementos += [tabela_secao("INFORMAÇÕES DO OPERADOR UAS", [
        (f"Nome completo: {termo.operador_nome}", f"Código SARPAS: {termo.operador_sarpas}"),
        (f"Endereço: {termo.operador_endereco}", f"Telefone: {termo.operador_telefone}"),
        (f"E-mail: {termo.operador_email}", ""),
    ]), Spacer(1,2*mm)]
    elementos += [tabela_secao("RESPONSÁVEL PELA ÁREA / ÓRGÃO ATS", [
        (f"Nome: {termo.responsavel_nome}", f"Função: {termo.responsavel_funcao}"),
        (f"Endereço: {termo.responsavel_endereco}", f"Telefone: {termo.responsavel_telefone}"),
        (f"E-mail: {termo.responsavel_email}", ""),
    ]), Spacer(1,2*mm)]
    elementos += [tabela_secao("AERÓDROMO / HELIPONTO / EAC", [
        (f"Código/identificação: {termo.local_codigo}", f"Natureza/finalidade: {termo.local_natureza}"),
        (f"Funcionamento/ativação: {termo.local_funcionamento}", f"Observações: {termo.local_observacoes}"),
    ]), Spacer(1,2*mm)]
    elementos += [tabela_secao("ÁREA E OPERAÇÃO", [
        (f"Limites verticais: {termo.limites_verticais}", f"Limites laterais: {termo.limites_laterais}"),
        (f"Coordenadas WGS84: {termo.coordenadas_wgs84}", f"Objetivo: {termo.objetivo_operacao}"),
        (f"Período: {termo.periodo_operacao}", f"Horários: {termo.horarios_operacao}"),
        (f"Frequência/duração: {termo.frequencia_duracao}", f"Tipo: {termo.tipo_operacao}"),
        (f"Observações: {termo.operacao_observacoes}", ""),
    ]), Spacer(1,2*mm)]

    perguntas = [
        ("Contato prévio com o responsável pela área", termo.contato_previo),
        ("Informação de início e término da operação", termo.informar_inicio_termino),
        ("Pessoa dedicada ao atendimento dos contatos", termo.pessoal_dedicado_contatos),
        ("Prerrogativa de suspensão por segurança", termo.suspensao_por_seguranca),
        ("Informação de contingência/emergência acionada", termo.informar_contingencia),
        ("Procedimentos de emergência/contingência acordados", termo.procedimentos_emergencia),
    ]
    respostas = [[p("CONDIÇÕES DE COORDENAÇÃO"), p("RESPOSTA")]] + [[p(texto), p("SIM" if valor is True else "NÃO" if valor is False else "NÃO PREENCHIDO")] for texto, valor in perguntas]
    tabela = Table(respostas, colWidths=[150*mm, 32*mm], repeatRows=1)
    tabela.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0C2238")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.45,colors.HexColor("#8B98A7")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    elementos += [tabela, Spacer(1,2*mm), tabela_secao("DETALHAMENTO E VALIDADE", [
        (f"Descrição da coordenação: {termo.descricao_coordenacao}", f"Validade: {termo.validade_meses} mês(es)"),
        (f"Local/data: {termo.local_assinatura} - {termo.data_assinatura.strftime('%d/%m/%Y') if termo.data_assinatura else '—'}", ""),
        (f"Operador UAS: {termo.representante_operador}", f"Órgão ATS/Administrador: {termo.representante_ats}"),
    ])]
    doc.build(elementos)
    return buffer.getvalue()
