from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent
VIEWS = ROOT / "core" / "views.py"
URLS = ROOT / "core" / "urls.py"
BASE = ROOT / "templates" / "base.html"
TPL = ROOT / "templates" / "agenda" / "minha_agenda.html"

def fail(msg):
    print("\nERRO:", msg)
    sys.exit(1)

def backup():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ROOT / ("backup_patch_minha_agenda_" + stamp)
    for p in (VIEWS, URLS, BASE, TPL):
        if p.exists():
            target = dest / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    print("Backup criado em:", dest)

AGENDA_VIEW = r'''
@login_required
def minha_agenda(request):
    _atualizar_reservas_vencidas()

    if "_atualizar_status_drones_por_reserva" in globals():
        _atualizar_status_drones_por_reserva()

    hoje = timezone.localdate()

    if usuario_e_admin(request.user):
        reservas = (
            Alocacao.objects
            .select_related("piloto", "drone")
            .filter(status="reservado", data__gte=hoje)
            .order_by("data", "hora_inicio")[:20]
        )
        voos_recentes = (
            Voo.objects
            .select_related("piloto", "drone")
            .order_by("-data", "-hora_inicio")[:10]
        )
        titulo = "Agenda Operacional"
        subtitulo = "Próximas reservas e voos recentes do sistema"
    else:
        try:
            piloto = request.user.piloto
        except Piloto.DoesNotExist:
            messages.error(request, "Seu usuário não está vinculado a um piloto.")
            return redirect("dashboard")

        reservas = (
            Alocacao.objects
            .select_related("piloto", "drone")
            .filter(
                piloto=piloto,
                status="reservado",
                data__gte=hoje,
            )
            .order_by("data", "hora_inicio")[:20]
        )
        voos_recentes = (
            Voo.objects
            .select_related("piloto", "drone")
            .filter(piloto=piloto)
            .order_by("-data", "-hora_inicio")[:10]
        )
        titulo = "Minha Agenda"
        subtitulo = "Suas próximas reservas e seus voos recentes"

    ctx = {
        "reservas": reservas,
        "voos_recentes": voos_recentes,
        "total_reservas": reservas.count(),
        "titulo": titulo,
        "subtitulo": subtitulo,
    }
    ctx.update(_base_context(request))
    return render(request, "agenda/minha_agenda.html", ctx)
'''

def patch_views():
    text = VIEWS.read_text(encoding="utf-8")
    if "def minha_agenda(" in text:
        print("views.py já contém minha_agenda.")
        return
    marker = "# =========================================================\n# VOOS\n# ========================================================="
    pos = text.find(marker)
    if pos == -1:
        fail("Não encontrei a seção VOOS em views.py.")
    text = text[:pos] + AGENDA_VIEW.strip() + "\n\n\n" + text[pos:]
    VIEWS.write_text(text, encoding="utf-8")
    print("views.py atualizado.")

def patch_urls():
    text = URLS.read_text(encoding="utf-8")
    if 'name="minha_agenda"' in text:
        print("urls.py já contém Minha Agenda.")
        return
    marker = 'path("", views.dashboard, name="dashboard"),'
    route = 'path("minha-agenda/", views.minha_agenda, name="minha_agenda"),'
    if marker not in text:
        fail("Não encontrei a rota dashboard em urls.py.")
    text = text.replace(marker, marker + "\n    " + route, 1)
    URLS.write_text(text, encoding="utf-8")
    print("urls.py atualizado.")

def patch_base():
    text = BASE.read_text(encoding="utf-8")
    if "{% url 'minha_agenda' %}" in text:
        print("base.html já contém Minha Agenda.")
        return

    idx = text.find("{% url 'calendario' %}")
    if idx == -1:
        idx = text.find('{% url "calendario" %}')
    if idx == -1:
        print("AVISO: menu não alterado; /minha-agenda/ continuará disponível.")
        return

    start = text.rfind("<a", 0, idx)
    end = text.find("</a>", idx)
    if start == -1 or end == -1:
        print("AVISO: não consegui inserir o item no menu automaticamente.")
        return
    end += 4

    menu = '''
        <a href="{% url 'minha_agenda' %}" class="nav-link">
            <span>Minha Agenda</span>
        </a>
'''
    text = text[:end] + "\n" + menu + text[end:]
    BASE.write_text(text, encoding="utf-8")
    print("base.html atualizado.")

def create_template():
    TPL.parent.mkdir(parents=True, exist_ok=True)
    html = r'''{% extends "base.html" %}
{% block title %}{{ titulo }}{% endblock %}
{% block content %}
<div class="page-header">
    <div>
        <h1>{{ titulo }}</h1>
        <p>{{ subtitulo }}</p>
    </div>
    <a class="btn btn-primary" href="{% url 'alocacao_nova' %}">
        + Nova Reserva
    </a>
</div>

<div class="kpi-grid">
    <div class="kpi-card">
        <div>
            <span>Próximas Reservas</span>
            <strong>{{ total_reservas }}</strong>
        </div>
    </div>
</div>

<div class="chart-grid main">
    <div class="panel">
        <div class="panel-title-row">
            <h3>Próximas Reservas</h3>
            <a href="{% url 'calendario' %}">Ver calendário</a>
        </div>
        <div class="table-responsive">
            <table class="modern-table">
                <thead>
                <tr>
                    <th>Data</th>
                    <th>Horário</th>
                    {% if eh_admin or user.is_superuser %}<th>Piloto</th>{% endif %}
                    <th>Drone</th>
                    <th>Finalidade</th>
                    <th>Local</th>
                </tr>
                </thead>
                <tbody>
                {% for r in reservas %}
                <tr>
                    <td>{{ r.data|date:"d/m/Y" }}</td>
                    <td>{{ r.hora_inicio|time:"H:i" }} - {{ r.hora_fim|time:"H:i" }}</td>
                    {% if eh_admin or user.is_superuser %}<td>{{ r.piloto.nome }}</td>{% endif %}
                    <td>{{ r.drone.nome }}</td>
                    <td>{{ r.finalidade }}</td>
                    <td>{{ r.local|default:"-" }}</td>
                </tr>
                {% empty %}
                <tr><td colspan="6">Nenhuma reserva futura.</td></tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="panel">
        <div class="panel-title-row">
            <h3>Voos Recentes</h3>
            <a href="{% url 'voos' %}">Ver todos</a>
        </div>
        <div class="table-responsive">
            <table class="modern-table">
                <thead>
                <tr>
                    <th>Data</th>
                    {% if eh_admin or user.is_superuser %}<th>Piloto</th>{% endif %}
                    <th>Drone</th>
                    <th>Finalidade</th>
                    <th>Duração</th>
                </tr>
                </thead>
                <tbody>
                {% for v in voos_recentes %}
                <tr>
                    <td>{{ v.data|date:"d/m/Y" }}</td>
                    {% if eh_admin or user.is_superuser %}<td>{{ v.piloto.nome }}</td>{% endif %}
                    <td>{{ v.drone.nome }}</td>
                    <td>{{ v.get_finalidade_display }}</td>
                    <td>{{ v.duracao_minutos }} min</td>
                </tr>
                {% empty %}
                <tr><td colspan="5">Nenhum voo registrado.</td></tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
{% endblock %}
'''
    TPL.write_text(html, encoding="utf-8")
    print("Template Minha Agenda criado.")

def run_check():
    result = subprocess.run([sys.executable, "manage.py", "check"], cwd=ROOT)
    if result.returncode != 0:
        fail("python manage.py check falhou. O backup foi preservado.")

def main():
    if not (ROOT / "manage.py").exists():
        fail("Copie este patch para a raiz do projeto, ao lado de manage.py.")
    for p in (VIEWS, URLS, BASE):
        if not p.exists():
            fail("Arquivo não encontrado: " + str(p))

    print("=== PATCH - MINHA AGENDA ===")
    backup()
    patch_views()
    patch_urls()
    patch_base()
    create_template()
    run_check()

    print("\nPATCH CONCLUÍDO COM SUCESSO.")
    print("Não precisa makemigrations nem migrate.")
    print("Agora execute: python manage.py runserver")

if __name__ == "__main__":
    main()
