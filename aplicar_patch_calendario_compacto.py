from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent
CAL = ROOT / "templates" / "calendario" / "calendario.html"
CSS = ROOT / "static" / "css" / "sistema.css"

def fail(msg):
    print("\nERRO:", msg)
    sys.exit(1)

def backup():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ROOT / f"backup_patch_calendario_compacto_{stamp}"

    for p in (CAL, CSS):
        if p.exists():
            target = dest / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)

    print("Backup criado em:", dest)

def patch_template():
    html = r"""{% extends "base.html" %}
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

<div class="panel calendar-panel">

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
        <div class="calendar-cell compact {% if not dia.mes_atual %}muted{% endif %}">

            <div class="calendar-day-header">
                <span class="day-number">
                    {{ dia.data.day }}
                </span>
            </div>

            <div class="calendar-compact-events">

                {% for a in dia.alocacoes|slice:":3" %}
                <button
                    type="button"
                    class="
                        calendar-compact-event
                        {% if a.status == 'concluido' %}
                            event-done
                        {% elif a.status == 'cancelado' %}
                            event-cancelled
                        {% else %}
                            event-reserved
                        {% endif %}
                    "
                    onclick="abrirDiaModal('dia-{{ dia.data|date:"Ymd" }}')"
                >
                    <span class="event-time">
                        {{ a.hora_inicio|time:"H:i" }}
                    </span>

                    <span class="event-title">
                        {{ a.drone.nome }}
                    </span>
                </button>
                {% endfor %}

                {% if dia.quantidade > 3 %}
                <button
                    type="button"
                    class="calendar-more"
                    onclick="abrirDiaModal('dia-{{ dia.data|date:"Ymd" }}')"
                >
                    +{{ dia.quantidade|add:"-3" }}
                </button>
                {% endif %}

            </div>

        </div>
        {% endfor %}

    </div>
    {% endfor %}

</div>


{% for semana in semanas %}
    {% for dia in semana %}
        {% if dia.quantidade > 0 %}

        <div
            id="dia-{{ dia.data|date:"Ymd" }}"
            class="calendar-day-modal-backdrop"
            onclick="fecharDiaModal(event, 'dia-{{ dia.data|date:"Ymd" }}')"
        >
            <div class="calendar-day-modal" onclick="event.stopPropagation()">

                <div class="calendar-day-modal-header">
                    <div>
                        <h3>
                            {{ dia.data|date:"d/m/Y" }}
                        </h3>

                        <span>
                            {{ dia.quantidade }}
                            {% if dia.quantidade == 1 %}
                                reserva
                            {% else %}
                                reservas
                            {% endif %}
                        </span>
                    </div>

                    <button
                        type="button"
                        class="calendar-modal-close"
                        onclick="document.getElementById('dia-{{ dia.data|date:"Ymd" }}').classList.remove('show')"
                    >
                        ×
                    </button>
                </div>

                <div class="calendar-day-modal-body">

                    {% for a in dia.alocacoes %}
                    <div class="
                        calendar-day-item
                        {% if a.status == 'concluido' %}
                            event-done
                        {% elif a.status == 'cancelado' %}
                            event-cancelled
                        {% else %}
                            event-reserved
                        {% endif %}
                    ">

                        <div class="calendar-day-item-main">
                            <div class="calendar-day-item-time">
                                {{ a.hora_inicio|time:"H:i" }}
                                -
                                {{ a.hora_fim|time:"H:i" }}
                            </div>

                            <strong>
                                {{ a.drone.nome }}
                            </strong>
                        </div>

                        <div class="calendar-day-item-meta">
                            <span>
                                Piloto: {{ a.piloto.nome }}
                            </span>

                            <span>
                                Finalidade: {{ a.finalidade }}
                            </span>

                            {% if a.local %}
                            <span>
                                Local: {{ a.local }}
                            </span>
                            {% endif %}

                            <span>
                                Status: {{ a.get_status_display }}
                            </span>
                        </div>

                        <div class="calendar-day-item-actions">

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
                                        type="submit"
                                        class="icon-btn danger"
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
                                            type="submit"
                                            class="icon-btn danger"
                                        >
                                            Excluir
                                        </button>
                                    </form>

                                {% endif %}

                            {% endif %}

                        </div>

                    </div>
                    {% endfor %}

                </div>

            </div>
        </div>

        {% endif %}
    {% endfor %}
{% endfor %}


<div class="panel calendar-list-panel">
    <div class="panel-title-row">
        <h3>Reservas do período</h3>
    </div>

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
            </tr>
            </thead>

            <tbody>
            {% for a in lista_alocacoes %}
            <tr>
                <td>{{ a.data|date:"d/m/Y" }}</td>
                <td>
                    {{ a.hora_inicio|time:"H:i" }}
                    -
                    {{ a.hora_fim|time:"H:i" }}
                </td>
                <td>{{ a.piloto.nome }}</td>
                <td>{{ a.drone.nome }}</td>
                <td>{{ a.finalidade }}</td>
                <td>{{ a.get_status_display }}</td>
            </tr>
            {% empty %}
            <tr>
                <td colspan="6">
                    Nenhuma reserva neste período.
                </td>
            </tr>
            {% endfor %}
            </tbody>

        </table>
    </div>
</div>

{% endblock %}


{% block scripts %}
{{ block.super }}

<script>
function abrirDiaModal(id) {
    const modal = document.getElementById(id);

    if (!modal) {
        return;
    }

    modal.classList.add("show");
}

function fecharDiaModal(event, id) {
    if (event.target.id !== id) {
        return;
    }

    const modal = document.getElementById(id);

    if (modal) {
        modal.classList.remove("show");
    }
}

document.addEventListener("keydown", function(event) {
    if (event.key === "Escape") {
        document
            .querySelectorAll(".calendar-day-modal-backdrop.show")
            .forEach(function(modal) {
                modal.classList.remove("show");
            });
    }
});
</script>

{% endblock %}
"""

    CAL.write_text(html, encoding="utf-8")
    print("calendario.html atualizado.")

def patch_css():
    text = CSS.read_text(encoding="utf-8")

    css = r"""
/* =========================================================
   CALENDÁRIO COMPACTO
   ========================================================= */

.calendar-panel{
    overflow:hidden;
}

.calendar-cell.compact{
    min-height:118px;
    padding:8px;
    overflow:hidden;
}

.calendar-cell.compact .calendar-day-header{
    min-height:22px;
    margin-bottom:5px;
}

.calendar-compact-events{
    display:flex;
    flex-direction:column;
    gap:3px;
}

.calendar-compact-event{
    display:flex;
    align-items:center;
    gap:6px;
    width:100%;
    height:24px;
    padding:0 7px;
    border:0;
    border-radius:5px;
    text-align:left;
    cursor:pointer;
    overflow:hidden;
    font-size:11px;
    line-height:1;
}

.calendar-compact-event .event-time{
    flex:0 0 auto;
    font-variant-numeric:tabular-nums;
    opacity:.9;
}

.calendar-compact-event .event-title{
    min-width:0;
    overflow:hidden;
    text-overflow:ellipsis;
    white-space:nowrap;
    font-weight:700;
}

.calendar-compact-event.event-reserved{
    background:#dce8ff;
    color:#184fa8;
}

.calendar-compact-event.event-done{
    background:#dff4e8;
    color:#21744f;
}

.calendar-compact-event.event-cancelled{
    background:#ffe4e7;
    color:#a73743;
}

.calendar-more{
    width:100%;
    height:24px;
    border:0;
    border-radius:5px;
    background:#edf1f6;
    color:#536273;
    font-size:11px;
    font-weight:700;
    cursor:pointer;
}

.calendar-more:hover{
    background:#e2e8f0;
}

.calendar-day-modal-backdrop{
    position:fixed;
    inset:0;
    z-index:9999;
    display:none;
    align-items:center;
    justify-content:center;
    padding:24px;
    background:rgba(10, 18, 30, .50);
}

.calendar-day-modal-backdrop.show{
    display:flex;
}

.calendar-day-modal{
    width:min(720px, 96vw);
    max-height:82vh;
    overflow:hidden;
    background:#fff;
    border-radius:14px;
    box-shadow:0 22px 70px rgba(0, 0, 0, .22);
}

.calendar-day-modal-header{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:16px;
    padding:18px 20px;
    border-bottom:1px solid #e5eaf0;
}

.calendar-day-modal-header h3{
    margin:0 0 3px;
}

.calendar-day-modal-header span{
    color:#758397;
    font-size:12px;
}

.calendar-modal-close{
    width:34px;
    height:34px;
    border:0;
    border-radius:8px;
    background:#eef2f6;
    color:#4c596a;
    font-size:22px;
    line-height:1;
    cursor:pointer;
}

.calendar-day-modal-body{
    display:flex;
    flex-direction:column;
    gap:8px;
    max-height:calc(82vh - 76px);
    overflow-y:auto;
    padding:14px 20px 20px;
}

.calendar-day-item{
    padding:12px 14px;
    border-radius:9px;
    border:1px solid #dfe5ec;
}

.calendar-day-item.event-reserved{
    border-left:4px solid #3976d9;
}

.calendar-day-item.event-done{
    border-left:4px solid #359267;
}

.calendar-day-item.event-cancelled{
    border-left:4px solid #c6535f;
}

.calendar-day-item-main{
    display:flex;
    align-items:center;
    gap:12px;
    margin-bottom:7px;
}

.calendar-day-item-time{
    min-width:88px;
    font-weight:700;
    font-variant-numeric:tabular-nums;
}

.calendar-day-item-meta{
    display:flex;
    flex-wrap:wrap;
    gap:6px 14px;
    color:#68778a;
    font-size:12px;
}

.calendar-day-item-actions{
    display:flex;
    align-items:center;
    gap:7px;
    margin-top:10px;
}

.calendar-list-panel{
    margin-top:18px;
}
"""

    marker = "/* =========================================================\n   CALENDÁRIO COMPACTO"

    if marker in text:
        text = text[:text.find(marker)]

    text = text.rstrip() + "\n\n" + css.strip() + "\n"

    CSS.write_text(text, encoding="utf-8")
    print("CSS atualizado.")

def run_check():
    result = subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=ROOT,
    )

    if result.returncode != 0:
        fail(
            "python manage.py check falhou. "
            "O backup foi preservado."
        )

def main():
    if not (ROOT / "manage.py").exists():
        fail(
            "Copie este patch para a raiz do projeto, "
            "ao lado de manage.py."
        )

    if not CAL.exists():
        fail("calendario.html não encontrado.")

    if not CSS.exists():
        fail("sistema.css não encontrado.")

    print("=== PATCH - CALENDÁRIO COMPACTO ===")

    backup()
    patch_template()
    patch_css()
    run_check()

    print("\nPATCH CONCLUÍDO COM SUCESSO.")
    print("Não precisa makemigrations nem migrate.")
    print("Agora execute:")
    print("python manage.py runserver")

if __name__ == "__main__":
    main()
