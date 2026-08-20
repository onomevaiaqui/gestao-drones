from pathlib import Path
import shutil, subprocess, sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent
VIEWS = ROOT / "core/views.py"
URLS = ROOT / "core/urls.py"
TPL = ROOT / "templates/relatorios/relatorios.html"

def fail(msg):
    print("\nERRO:", msg)
    sys.exit(1)

def backup():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ROOT / ("backup_patch_relatorios_" + stamp)
    for p in (VIEWS, URLS, TPL):
        if p.exists():
            target = dest / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    print("Backup criado em:", dest)

def patch_views():
    text = VIEWS.read_text(encoding="utf-8")

    if "import csv" not in text:
        text = text.replace(
            "import calendar as pycalendar",
            "import calendar as pycalendar\nimport csv"
        )

    if "from django.http import HttpResponse" not in text:
        text = text.replace(
            "from django.shortcuts import render, redirect, get_object_or_404",
            "from django.shortcuts import render, redirect, get_object_or_404\nfrom django.http import HttpResponse"
        )

    start_marker = "# =========================================================\n# RELATÓRIOS\n# ========================================================="
    end_marker = "# =========================================================\n# MANUTENÇÕES\n# ========================================================="

    start = text.find(start_marker)
    end = text.find(end_marker)

    if start == -1 or end == -1 or end <= start:
        fail("Não encontrei as seções RELATÓRIOS/MANUTENÇÕES em views.py.")

    section = r'''
# =========================================================
# RELATÓRIOS
# =========================================================

def _filtrar_voos_relatorio(request):
    qs = Voo.objects.select_related(
        "piloto",
        "drone"
    )

    inicio = request.GET.get("inicio")
    fim = request.GET.get("fim")
    piloto_id = request.GET.get("piloto")
    drone_id = request.GET.get("drone")

    if inicio:
        qs = qs.filter(data__gte=inicio)

    if fim:
        qs = qs.filter(data__lte=fim)

    if piloto_id:
        qs = qs.filter(piloto_id=piloto_id)

    if drone_id:
        qs = qs.filter(drone_id=drone_id)

    return qs


@admin_required
def relatorios(request):
    voos_qs = _filtrar_voos_relatorio(request)

    total_minutos = sum(
        voo.duracao_minutos
        for voo in voos_qs
    )

    distancia_total_m = sum(
        float(voo.distancia_m or 0)
        for voo in voos_qs
    )

    por_piloto = []
    pilotos_ids = (
        voos_qs.values_list(
            "piloto_id",
            flat=True
        ).distinct()
    )

    for piloto in Piloto.objects.filter(
        pk__in=pilotos_ids
    ):
        voos_piloto = [
            voo
            for voo in voos_qs
            if voo.piloto_id == piloto.id
        ]

        minutos_piloto = sum(
            voo.duracao_minutos
            for voo in voos_piloto
        )

        por_piloto.append({
            "nome": piloto.nome,
            "voos": len(voos_piloto),
            "horas": round(
                minutos_piloto / 60,
                2
            ),
        })

    por_drone = []
    drones_ids = (
        voos_qs.values_list(
            "drone_id",
            flat=True
        ).distinct()
    )

    for drone in Drone.objects.filter(
        pk__in=drones_ids
    ):
        voos_drone = [
            voo
            for voo in voos_qs
            if voo.drone_id == drone.id
        ]

        minutos_drone = sum(
            voo.duracao_minutos
            for voo in voos_drone
        )

        por_drone.append({
            "nome": drone.nome,
            "voos": len(voos_drone),
            "horas": round(
                minutos_drone / 60,
                2
            ),
        })

    ctx = {
        "total_voos": voos_qs.count(),
        "total_horas": round(
            total_minutos / 60,
            2
        ),
        "distancia_km": round(
            distancia_total_m / 1000,
            2
        ),
        "por_piloto": por_piloto,
        "por_drone": por_drone,
        "pilotos": Piloto.objects.filter(
            ativo=True
        ),
        "drones": Drone.objects.all(),
        "filtros": request.GET,
        "voos_relatorio": voos_qs[:200],
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "relatorios/relatorios.html",
        ctx
    )


@admin_required
def relatorios_exportar_csv(request):
    voos_qs = _filtrar_voos_relatorio(request)

    response = HttpResponse(
        content_type="text/csv; charset=utf-8"
    )

    response[
        "Content-Disposition"
    ] = 'attachment; filename="relatorio_voos.csv"'

    response.write("\ufeff")

    writer = csv.writer(
        response,
        delimiter=";"
    )

    writer.writerow([
        "Data",
        "Piloto",
        "Matrícula",
        "Drone",
        "Modelo",
        "Finalidade",
        "Local",
        "Hora início",
        "Hora fim",
        "Duração (min)",
        "Bateria inicial (%)",
        "Bateria final (%)",
        "Distância (m)",
        "Observações",
    ])

    for voo in voos_qs:
        writer.writerow([
            voo.data.strftime("%d/%m/%Y"),
            voo.piloto.nome,
            voo.piloto.matricula,
            voo.drone.nome,
            voo.drone.modelo,
            voo.get_finalidade_display(),
            voo.local,
            voo.hora_inicio.strftime("%H:%M"),
            voo.hora_fim.strftime("%H:%M"),
            voo.duracao_minutos,
            voo.bateria_inicial
            if voo.bateria_inicial is not None
            else "",
            voo.bateria_final
            if voo.bateria_final is not None
            else "",
            voo.distancia_m
            if voo.distancia_m is not None
            else "",
            voo.observacoes,
        ])

    return response
'''

    new_text = (
        text[:start]
        + section.strip()
        + "\n\n\n"
        + text[end:]
    )

    VIEWS.write_text(
        new_text,
        encoding="utf-8"
    )
    print("views.py atualizado.")

def patch_urls():
    text = URLS.read_text(encoding="utf-8")

    marker = 'path("relatorios/", views.relatorios, name="relatorios"),'
    route = 'path("relatorios/exportar-csv/", views.relatorios_exportar_csv, name="relatorios_exportar_csv"),'

    if marker not in text:
        fail("Não encontrei a rota relatorios em urls.py.")

    if "relatorios_exportar_csv" not in text:
        text = text.replace(
            marker,
            marker + "\n    " + route,
            1
        )

    URLS.write_text(
        text,
        encoding="utf-8"
    )
    print("urls.py atualizado.")

def patch_template():
    TPL.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    html = '''{% extends "base.html" %}
{% block title %}Relatórios{% endblock %}

{% block content %}

<div class="page-header">
    <div>
        <h1>Relatórios</h1>
        <p>Resumo consolidado das operações</p>
    </div>
</div>

<div class="panel">
    <form method="get" class="filter-grid">
        <input
            class="form-control"
            type="date"
            name="inicio"
            value="{{ filtros.inicio }}"
        >

        <input
            class="form-control"
            type="date"
            name="fim"
            value="{{ filtros.fim }}"
        >

        <select
            class="form-select"
            name="piloto"
        >
            <option value="">
                Todos os pilotos
            </option>

            {% for p in pilotos %}
            <option
                value="{{ p.id }}"
                {% if filtros.piloto == p.id|stringformat:"s" %}
                selected
                {% endif %}
            >
                {{ p.nome }}
            </option>
            {% endfor %}
        </select>

        <select
            class="form-select"
            name="drone"
        >
            <option value="">
                Todos os drones
            </option>

            {% for d in drones %}
            <option
                value="{{ d.id }}"
                {% if filtros.drone == d.id|stringformat:"s" %}
                selected
                {% endif %}
            >
                {{ d.nome }}
            </option>
            {% endfor %}
        </select>

        <button class="btn btn-primary">
            Aplicar filtros
        </button>

        <a
            class="btn btn-light"
            href="{% url 'relatorios' %}"
        >
            Limpar
        </a>
    </form>
</div>

<div class="kpi-grid">
    <div class="kpi-card">
        <div>
            <span>Total de Voos</span>
            <strong>{{ total_voos }}</strong>
        </div>
    </div>

    <div class="kpi-card">
        <div>
            <span>Horas Totais</span>
            <strong>{{ total_horas }} h</strong>
        </div>
    </div>

    <div class="kpi-card">
        <div>
            <span>Distância Total</span>
            <strong>{{ distancia_km }} km</strong>
        </div>
    </div>
</div>

<div class="panel">
    <div class="panel-title-row">
        <h3>Voos do período</h3>

        <a
            class="btn btn-primary btn-sm"
            href="{% url 'relatorios_exportar_csv' %}?{{ request.GET.urlencode }}"
        >
            Exportar CSV
        </a>
    </div>

    <div class="table-responsive">
        <table class="modern-table">
            <thead>
            <tr>
                <th>Data</th>
                <th>Piloto</th>
                <th>Drone</th>
                <th>Finalidade</th>
                <th>Local</th>
                <th>Duração</th>
                <th>Distância</th>
            </tr>
            </thead>

            <tbody>
            {% for voo in voos_relatorio %}
            <tr>
                <td>{{ voo.data|date:"d/m/Y" }}</td>
                <td>{{ voo.piloto.nome }}</td>
                <td>{{ voo.drone.nome }}</td>
                <td>{{ voo.get_finalidade_display }}</td>
                <td>{{ voo.local }}</td>
                <td>{{ voo.duracao_minutos }} min</td>
                <td>
                    {% if voo.distancia_m %}
                        {{ voo.distancia_m }} m
                    {% else %}
                        -
                    {% endif %}
                </td>
            </tr>
            {% empty %}
            <tr>
                <td colspan="7">
                    Nenhum voo encontrado.
                </td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<div class="chart-grid main">

    <div class="panel">
        <h3>Resumo por Piloto</h3>

        <div class="table-responsive">
            <table class="modern-table">
                <thead>
                <tr>
                    <th>Piloto</th>
                    <th>Voos</th>
                    <th>Horas</th>
                </tr>
                </thead>

                <tbody>
                {% for p in por_piloto %}
                <tr>
                    <td>{{ p.nome }}</td>
                    <td>{{ p.voos }}</td>
                    <td>{{ p.horas }}</td>
                </tr>
                {% empty %}
                <tr>
                    <td colspan="3">
                        Sem dados.
                    </td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="panel">
        <h3>Resumo por Drone</h3>

        <div class="table-responsive">
            <table class="modern-table">
                <thead>
                <tr>
                    <th>Drone</th>
                    <th>Voos</th>
                    <th>Horas</th>
                </tr>
                </thead>

                <tbody>
                {% for d in por_drone %}
                <tr>
                    <td>{{ d.nome }}</td>
                    <td>{{ d.voos }}</td>
                    <td>{{ d.horas }}</td>
                </tr>
                {% empty %}
                <tr>
                    <td colspan="3">
                        Sem dados.
                    </td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

</div>

{% endblock %}
'''

    TPL.write_text(
        html,
        encoding="utf-8"
    )

    print(
        "relatorios.html atualizado."
    )

def run_check():
    result = subprocess.run(
        [
            sys.executable,
            "manage.py",
            "check"
        ],
        cwd=ROOT
    )

    if result.returncode != 0:
        fail(
            "python manage.py check falhou."
        )

def main():
    if not (
        ROOT / "manage.py"
    ).exists():
        fail(
            "Copie este patch para a raiz "
            "do projeto."
        )

    print(
        "=== PATCH - RELATÓRIOS E CSV ==="
    )

    backup()
    patch_views()
    patch_urls()
    patch_template()
    run_check()

    print(
        "\nPATCH CONCLUÍDO."
    )
    print(
        "Não há alteração no banco."
    )
    print(
        "Agora execute:"
    )
    print(
        "python manage.py runserver"
    )

if __name__ == "__main__":
    main()
