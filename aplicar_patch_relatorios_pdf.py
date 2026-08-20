from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent
VIEWS = ROOT / "core" / "views.py"
URLS = ROOT / "core" / "urls.py"
TPL = ROOT / "templates" / "relatorios" / "relatorios.html"

def fail(msg):
    print("\nERRO:", msg)
    sys.exit(1)

def backup():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ROOT / ("backup_patch_relatorios_pdf_" + stamp)
    for p in (VIEWS, URLS, TPL):
        if p.exists():
            target = dest / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    print("Backup criado em:", dest)

def ensure_reportlab():
    try:
        import reportlab
        print("ReportLab já está instalado.")
    except ImportError:
        print("Instalando ReportLab...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "reportlab"],
            cwd=ROOT,
        )
        if result.returncode != 0:
            fail("Não foi possível instalar o ReportLab.")

PDF_FUNCTION = '''
@admin_required
def relatorios_exportar_pdf(request):
    voos_qs = _filtrar_voos_relatorio(request)

    total_voos = voos_qs.count()
    total_minutos = sum(voo.duracao_minutos for voo in voos_qs)
    total_horas = round(total_minutos / 60, 2)
    distancia_total_m = sum(float(voo.distancia_m or 0) for voo in voos_qs)
    distancia_total_km = round(distancia_total_m / 1000, 2)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="relatorio_voos.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle(
        "TituloRelatorio",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        spaceAfter=10,
    )

    subtitulo_style = ParagraphStyle(
        "SubtituloRelatorio",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#536273"),
        spaceAfter=8,
    )

    normal_small = ParagraphStyle(
        "NormalSmall",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
    )

    elementos = [
        Paragraph("Relatório de Operações com Drones", titulo_style)
    ]

    inicio = request.GET.get("inicio") or "-"
    fim = request.GET.get("fim") or "-"
    piloto_id = request.GET.get("piloto")
    drone_id = request.GET.get("drone")

    piloto_nome = "Todos"
    drone_nome = "Todos"

    if piloto_id:
        piloto_obj = Piloto.objects.filter(pk=piloto_id).first()
        if piloto_obj:
            piloto_nome = piloto_obj.nome

    if drone_id:
        drone_obj = Drone.objects.filter(pk=drone_id).first()
        if drone_obj:
            drone_nome = drone_obj.nome

    elementos.append(
        Paragraph(
            f"Período: {inicio} até {fim} | Piloto: {piloto_nome} | Drone: {drone_nome}",
            subtitulo_style,
        )
    )

    resumo = Table(
        [
            ["Total de Voos", "Horas Totais", "Distância Total"],
            [str(total_voos), f"{total_horas} h", f"{distancia_total_km} km"],
        ],
        colWidths=[55 * mm, 55 * mm, 55 * mm],
    )

    resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0C2238")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F4F7FB")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9E1EA")),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    elementos.extend([resumo, Spacer(1, 8 * mm)])

    dados = [[
        "Data", "Piloto", "Drone", "Finalidade", "Local",
        "Início", "Fim", "Duração", "Distância"
    ]]

    for voo in voos_qs:
        dados.append([
            Paragraph(voo.data.strftime("%d/%m/%Y"), normal_small),
            Paragraph(voo.piloto.nome, normal_small),
            Paragraph(voo.drone.nome, normal_small),
            Paragraph(voo.get_finalidade_display(), normal_small),
            Paragraph(voo.local or "-", normal_small),
            Paragraph(voo.hora_inicio.strftime("%H:%M"), normal_small),
            Paragraph(voo.hora_fim.strftime("%H:%M"), normal_small),
            Paragraph(f"{voo.duracao_minutos} min", normal_small),
            Paragraph(
                f"{voo.distancia_m} m" if voo.distancia_m is not None else "-",
                normal_small
            ),
        ])

    if len(dados) == 1:
        dados.append(["", "", "", "", "Nenhum voo encontrado.", "", "", "", ""])

    tabela = Table(
        dados,
        repeatRows=1,
        colWidths=[
            20 * mm, 34 * mm, 29 * mm, 30 * mm, 50 * mm,
            16 * mm, 16 * mm, 19 * mm, 23 * mm
        ],
    )

    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0C2238")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E1EA")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white,
            colors.HexColor("#F8FAFC"),
        ]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    elementos.append(tabela)
    elementos.append(Spacer(1, 5 * mm))

    gerado_em = timezone.localtime().strftime("%d/%m/%Y %H:%M")
    elementos.append(
        Paragraph(
            f"Gerado pelo Sistema de Gestão de Drones em {gerado_em}.",
            subtitulo_style,
        )
    )

    doc.build(elementos)
    return response
'''

def patch_views():
    text = VIEWS.read_text(encoding="utf-8")

    imports = (
        "from reportlab.lib import colors\n"
        "from reportlab.lib.pagesizes import A4, landscape\n"
        "from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle\n"
        "from reportlab.lib.units import mm\n"
        "from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle\n"
    )

    if "from reportlab.lib import colors" not in text:
        anchor = "from django.views.decorators.http import require_POST"
        if anchor not in text:
            fail("Não encontrei o bloco de imports esperado em views.py.")
        text = text.replace(anchor, anchor + "\n\n" + imports.rstrip(), 1)

    start = text.find("@admin_required\ndef relatorios_exportar_csv")
    if start != -1:
        end = text.find(
            "# =========================================================\n# MANUTENÇÕES",
            start
        )
        if end == -1:
            fail("Não encontrei o final da seção de relatórios.")
        text = text[:start] + PDF_FUNCTION.strip() + "\n\n\n" + text[end:]
    elif "def relatorios_exportar_pdf(" not in text:
        marker = "# =========================================================\n# MANUTENÇÕES"
        pos = text.find(marker)
        if pos == -1:
            fail("Não encontrei a seção MANUTENÇÕES em views.py.")
        text = text[:pos] + PDF_FUNCTION.strip() + "\n\n\n" + text[pos:]

    VIEWS.write_text(text, encoding="utf-8")
    print("views.py atualizado.")

def patch_urls():
    text = URLS.read_text(encoding="utf-8")

    csv_route = 'path("relatorios/exportar-csv/", views.relatorios_exportar_csv, name="relatorios_exportar_csv"),'
    pdf_route = 'path("relatorios/exportar-pdf/", views.relatorios_exportar_pdf, name="relatorios_exportar_pdf"),'

    if csv_route in text:
        text = text.replace(csv_route, pdf_route, 1)
    elif "relatorios_exportar_pdf" not in text:
        marker = 'path("relatorios/", views.relatorios, name="relatorios"),'
        if marker not in text:
            fail("Não encontrei a rota relatorios em urls.py.")
        text = text.replace(marker, marker + "\n    " + pdf_route, 1)

    URLS.write_text(text, encoding="utf-8")
    print("urls.py atualizado.")

def patch_template():
    text = TPL.read_text(encoding="utf-8")
    text = text.replace(
        "{% url 'relatorios_exportar_csv' %}",
        "{% url 'relatorios_exportar_pdf' %}"
    )
    text = text.replace("Exportar CSV", "Exportar PDF")
    TPL.write_text(text, encoding="utf-8")
    print("relatorios.html atualizado.")

def run_check():
    result = subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=ROOT
    )
    if result.returncode != 0:
        fail("python manage.py check falhou. O backup foi preservado.")

def main():
    if not (ROOT / "manage.py").exists():
        fail("Copie este patch para a raiz do projeto, ao lado de manage.py.")

    for p in (VIEWS, URLS, TPL):
        if not p.exists():
            fail("Arquivo não encontrado: " + str(p))

    print("=== PATCH - EXPORTAÇÃO PDF ===")
    backup()
    ensure_reportlab()
    patch_views()
    patch_urls()
    patch_template()
    run_check()

    print("\nPATCH CONCLUÍDO COM SUCESSO.")
    print("Não precisa makemigrations nem migrate.")
    print("Agora execute: python manage.py runserver")

if __name__ == "__main__":
    main()
