from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent
VIEWS = ROOT / "core" / "views.py"
CAL = ROOT / "templates" / "calendario" / "calendario.html"
CSS = ROOT / "static" / "css" / "sistema.css"

def fail(msg):
    print("\nERRO:", msg)
    sys.exit(1)

def backup():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ROOT / ("backup_patch_calendario_v2_" + stamp)

    for p in (VIEWS, CAL, CSS):
        if p.exists():
            target = dest / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)

    print("Backup criado em:", dest)

CAL_VIEW = r'''
@login_required
def calendario(request):
    _atualizar_reservas_vencidas()

    if "_atualizar_status_drones_por_reserva" in globals():
        _atualizar_status_drones_por_reserva()

    hoje = timezone.localdate()

    try:
        ano = int(request.GET.get("ano", hoje.year))
        mes = int(request.GET.get("mes", hoje.month))
    except (TypeError, ValueError):
        ano = hoje.year
        mes = hoje.month

    mes = max(1, min(12, mes))

    cal = pycalendar.Calendar(firstweekday=6)
    semanas_datas = cal.monthdatescalendar(ano, mes)

    inicio_periodo = semanas_datas[0][0]
    fim_periodo = semanas_datas[-1][-1]

    alocacoes = (
        Alocacao.objects
        .select_related("piloto", "drone")
        .filter(
            data__gte=inicio_periodo,
            data__lte=fim_periodo,
        )
        .order_by(
            "data",
            "hora_inicio",
            "hora_fim",
            "id",
        )
    )

    por_dia = defaultdict(list)

    for reserva in alocacoes:
        por_dia[reserva.data].append(reserva)

    semanas = []

    for semana_datas in semanas_datas:
        semana = []

        for dia in semana_datas:
            reservas_do_dia = list(
                por_dia.get(dia, [])
            )

            semana.append({
                "data": dia,
                "mes_atual": dia.month == mes,
                "alocacoes": reservas_do_dia,
                "quantidade": len(reservas_do_dia),
            })

        semanas.append(semana)

    primeiro_dia = date(ano, mes, 1)
    anterior = primeiro_dia - timedelta(days=1)

    if mes == 12:
        proximo = date(ano + 1, 1, 1)
    else:
        proximo = date(ano, mes + 1, 1)

    lista_alocacoes = (
        Alocacao.objects
        .select_related("piloto", "drone")
        .filter(
            data__gte=inicio_periodo,
            data__lte=fim_periodo,
        )
        .order_by(
            "data",
            "hora_inicio",
            "hora_fim",
            "id",
        )
    )

    ctx = {
        "semanas": semanas,
        "mes": mes,
        "ano": ano,
        "anterior": anterior,
        "proximo": proximo,
        "lista_alocacoes": lista_alocacoes,
    }

    ctx.update(
        _base_context(request)
    )

    return render(
        request,
        "calendario/calendario.html",
        ctx
    )
'''

def patch_views():
    text = VIEWS.read_text(encoding="utf-8")

    start_marker = "@login_required\ndef calendario(request):"
    start = text.find(start_marker)

    if start == -1:
        fail("Não encontrei a função calendario em views.py.")

    next_marker = "\n\n@login_required\ndef alocacao_nova(request):"
    end = text.find(next_marker, start)

    if end == -1:
        fail("Não encontrei alocacao_nova após calendario em views.py.")

    new_text = (
        text[:start]
        + CAL_VIEW.strip()
        + text[end:]
    )

    VIEWS.write_text(
        new_text,
        encoding="utf-8"
    )

    print("views.py atualizado.")

def patch_template():
    html = r'''{% extends "base.html" %}
{% block title %}Calendário{% endblock %}

{% block content %}

<div class="page-header">
    <div>
        <h1>Calendário de Alocação</h1>
        <p>Reservas de pilotos e equipamentos</p>
    </div>

    <a class="btn btn-primary" href="{% url 'alocacao_nova' %}">
        + Reservar
    </a>
</div>

<div class="panel">

    <div class="calendar-toolbar">
        <a
            href="?ano={{ anterior.year }}&mes={{ anterior.month }}"
            class="btn btn-light"
        >
            ‹
        </a>

        <h3>{{ mes }}/{{ ano }}</h3>

        <a
            href="?ano={{ proximo.year }}&mes={{ proximo.month }}"
            class="btn btn-light"
        >
            ›
        </a>
    </div>

    <div class="calendar-grid calendar-head">
        <div>Dom</div>
        <div>Seg</div>
        <div>Ter</div>
        <div>Qua</div>
        <div>Qui</div>
        <div>Sex</div>
        <div>Sáb</div>
    </div>

    {% for semana in semanas %}
    <div class="calendar-grid">

        {% for dia in semana %}
        <div class="calendar-cell {% if not dia.mes_atual %}muted{% endif %}">

            <div class="calendar-day-header">
                <span class="day-number">
                    {{ dia.data.day }}
                </span>

                {% if dia.quantidade > 1 %}
                <span class="calendar-count">
                    {{ dia.quantidade }} reservas
                </span>
                {% elif dia.quantidade == 1 %}
                <span class="calendar-count">
                    1 reserva
                </span>
                {% endif %}
            </div>

            <div class="calendar-events-list">

                {% for a in dia.alocacoes %}
                <div class="
                    calendar-event
                    {% if a.status == 'concluido' %}
                        event-done
                    {% elif a.status == 'cancelado' %}
                        event-cancelled
                    {% endif %}
                ">

                    <strong>
                        {{ a.drone.nome }}
                    </strong>

                    <span>
                        {{ a.hora_inicio|time:"H:i" }}
                        -
                        {{ a.hora_fim|time:"H:i" }}
                    </span>

                    <small>
                        {{ a.piloto.nome }}
                    </small>

                    <small>
                        {{ a.get_status_display }}
                    </small>

                </div>
                {% empty %}
                {% endfor %}

            </div>

        </div>
        {% endfor %}

    </div>
    {% endfor %}

</div>

<div class="panel">
    <h3>Reservas</h3>

    <div class="table-responsive">
        <table class="modern-table">

            <thead>
            <tr>
                <th>Data</th>
                <th>Horário</th>
                <th>Piloto</th>
                <th>Drone</th>
                <th>Finalidade</th>
                <th>Status</th>
                <th>Ações</th>
            </tr>
            </thead>

            <tbody>
            {% for a in lista_alocacoes %}
            <tr>
                <td>
                    {{ a.data|date:"d/m/Y" }}
                </td>

                <td>
                    {{ a.hora_inicio|time:"H:i" }}
                    -
                    {{ a.hora_fim|time:"H:i" }}
                </td>

                <td>
                    {{ a.piloto }}
                </td>

                <td>
                    {{ a.drone }}
                </td>

                <td>
                    {{ a.finalidade }}
                </td>

                <td>
                    <span class="
                        badge-soft
                        {% if a.status == 'concluido' %}
                            green
                        {% elif a.status == 'cancelado' %}
                            red
                        {% else %}
                            blue
                        {% endif %}
                    ">
                        {{ a.get_status_display }}
                    </span>
                </td>

                <td class="actions">

                    {% if eh_admin or user.is_superuser %}

                        <a
                            href="{% url 'alocacao_editar' a.pk %}"
                            class="icon-btn"
                        >
                            Editar
                        </a>

                        <a
                            href="{% url 'alocacao_concluir' a.pk %}"
                            class="icon-btn"
                        >
                            {% if a.status == "concluido" %}
                                Registrar Voo
                            {% else %}
                                Concluir
                            {% endif %}
                        </a>

                        <form
                            method="post"
                            action="{% url 'alocacao_excluir' a.pk %}"
                            onsubmit="return confirm('Deseja excluir esta reserva?');"
                        >
                            {% csrf_token %}
                            <button
                                class="icon-btn danger"
                                type="submit"
                            >
                                Excluir
                            </button>
                        </form>

                    {% else %}

                        {% if a.status == "reservado" and a.piloto.user_id == user.id %}

                            <a
                                href="{% url 'alocacao_editar' a.pk %}"
                                class="icon-btn"
                            >
                                Editar
                            </a>

                            <form
                                method="post"
                                action="{% url 'alocacao_excluir' a.pk %}"
                                onsubmit="return confirm('Deseja excluir esta reserva?');"
                            >
                                {% csrf_token %}
                                <button
                                    class="icon-btn danger"
                                    type="submit"
                                >
                                    Excluir
                                </button>
                            </form>

                        {% else %}

                            <span class="text-muted">
                                Somente consulta
                            </span>

                        {% endif %}

                    {% endif %}

                </td>

            </tr>

            {% empty %}
            <tr>
                <td colspan="7">
                    Nenhuma reserva neste período.
                </td>
            </tr>
            {% endfor %}
            </tbody>

        </table>
    </div>
</div>

{% endblock %}
'''

    CAL.write_text(
        html,
        encoding="utf-8"
    )

    print("calendario.html substituído.")

def patch_css():
    text = CSS.read_text(encoding="utf-8")

    css = r'''
.calendar-cell{
    min-height:170px;
    padding:8px;
    overflow:hidden;
}

.calendar-day-header{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:6px;
    margin-bottom:6px;
}

.calendar-count{
    font-size:10px;
    color:#6c7a89;
    white-space:nowrap;
}

.calendar-events-list{
    display:flex;
    flex-direction:column;
    gap:5px;
    max-height:130px;
    overflow-y:auto;
    overflow-x:hidden;
    padding-right:3px;
}

.calendar-event{
    display:flex;
    flex-direction:column;
    gap:2px;
    width:100%;
    min-height:68px;
    box-sizing:border-box;
    flex-shrink:0;
}
'''

    if ".calendar-count" not in text:
        text += "\n" + css
        CSS.write_text(
            text,
            encoding="utf-8"
        )
        print("CSS atualizado.")
    else:
        print("CSS já possui regras do calendário.")

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
            "python manage.py check falhou. "
            "O backup foi preservado."
        )

def main():
    if not (
        ROOT / "manage.py"
    ).exists():
        fail(
            "Copie este patch para a raiz "
            "do projeto."
        )

    for p in (VIEWS, CAL, CSS):
        if not p.exists():
            fail(
                "Arquivo não encontrado: "
                + str(p)
            )

    print(
        "=== PATCH - CALENDÁRIO MÚLTIPLAS RESERVAS V2 ==="
    )

    backup()
    patch_views()
    patch_template()
    patch_css()
    run_check()

    print(
        "\nPATCH CONCLUÍDO COM SUCESSO."
    )
    print(
        "Agora execute:"
    )
    print(
        "python manage.py runserver"
    )

if __name__ == "__main__":
    main()
