from pathlib import Path
import shutil, subprocess, sys, re
from datetime import datetime

ROOT = Path(__file__).resolve().parent

FILES = {
    "views": ROOT / "core/views.py",
    "urls": ROOT / "core/urls.py",
    "template": ROOT / "templates/manutencoes/lista.html",
}

def fail(msg):
    print("\nERRO:", msg)
    sys.exit(1)

def backup():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ROOT / f"backup_patch_manutencao_{stamp}"
    for p in FILES.values():
        if p.exists():
            target = dest / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    print("Backup criado em:", dest)

def read(path):
    if not path.exists():
        fail(f"Arquivo não encontrado: {path}")
    return path.read_text(encoding="utf-8")

def write(path, text):
    path.write_text(text, encoding="utf-8")

CONCLUIR = r"""
@admin_required
@require_POST
def manutencao_concluir(request, pk):
    manutencao = get_object_or_404(Manutencao, pk=pk)

    if manutencao.concluida:
        messages.warning(request, "Esta manutenção já está concluída.")
        return redirect("manutencoes")

    manutencao.concluida = True

    if not manutencao.data_fim:
        manutencao.data_fim = timezone.localdate()

    manutencao.save(update_fields=["concluida", "data_fim"])

    drone = manutencao.drone
    status_anterior = drone.status
    agora = timezone.localtime()

    reserva_ativa = Alocacao.objects.filter(
        drone=drone,
        status="reservado",
        data=agora.date(),
        hora_inicio__lte=agora.time(),
        hora_fim__gt=agora.time(),
    ).exists()

    novo_status = "em_campo" if reserva_ativa else "ativo"

    if drone.status != novo_status:
        drone.status = novo_status
        drone.save(update_fields=["status"])

        DroneHistorico.objects.create(
            drone=drone,
            status_anterior=status_anterior,
            status_novo=novo_status,
            localizacao_anterior=getattr(drone, "localizacao", ""),
            localizacao_nova=getattr(drone, "localizacao", ""),
            alterado_por=request.user,
            observacao="Status atualizado ao concluir manutenção",
        )

    messages.success(request, "Manutenção concluída com sucesso.")
    return redirect("manutencoes")
"""

TEMPLATE = r"""{% extends "base.html" %}
{% block title %}Manutenções{% endblock %}

{% block content %}
<div class="page-header">
    <div>
        <h1>Manutenções</h1>
        <p>Histórico e acompanhamento dos equipamentos</p>
    </div>
    <a class="btn btn-primary" href="{% url 'manutencao_nova' %}">
        + Nova Manutenção
    </a>
</div>

<div class="panel">
<div class="table-responsive">
<table class="modern-table">
<thead>
<tr>
    <th>Drone</th>
    <th>Tipo</th>
    <th>Início</th>
    <th>Fim</th>
    <th>Descrição</th>
    <th>Status</th>
    <th>Ações</th>
</tr>
</thead>
<tbody>
{% for m in manutencoes %}
<tr>
    <td>
        <strong>{{ m.drone.nome }}</strong>
        <div class="text-muted small">{{ m.drone.modelo }}</div>
    </td>
    <td>{{ m.get_tipo_display }}</td>
    <td>{{ m.data_inicio|date:"d/m/Y" }}</td>
    <td>{% if m.data_fim %}{{ m.data_fim|date:"d/m/Y" }}{% else %}-{% endif %}</td>
    <td>{{ m.descricao|truncatechars:70 }}</td>
    <td>
        {% if m.concluida %}
            <span class="badge-soft green">Concluída</span>
        {% else %}
            <span class="badge-soft orange">Em andamento</span>
        {% endif %}
    </td>
    <td class="actions">
        {% if not m.concluida %}
        <form method="post" action="{% url 'manutencao_concluir' m.pk %}"
              onsubmit="return confirm('Concluir esta manutenção?');">
            {% csrf_token %}
            <button type="submit" class="icon-btn">Concluir</button>
        </form>
        {% else %}
            <span class="text-muted">Finalizada</span>
        {% endif %}
    </td>
</tr>
{% empty %}
<tr><td colspan="7">Nenhuma manutenção registrada.</td></tr>
{% endfor %}
</tbody>
</table>
</div>
</div>
{% endblock %}
"""

def patch_views():
    p = FILES["views"]
    t = read(p)

    if "def manutencao_concluir(" not in t:
        marker = "@admin_required\ndef manutencao_nova(request):"
        idx = t.find(marker)
        if idx == -1:
            fail("Não encontrei manutencao_nova em views.py.")
        t = t[:idx] + CONCLUIR.strip() + "\n\n\n" + t[idx:]
        write(p, t)
        print("views.py atualizado.")
    else:
        print("views.py já contém manutencao_concluir.")

def patch_urls():
    p = FILES["urls"]
    t = read(p)

    route = 'path("manutencoes/<int:pk>/concluir/", views.manutencao_concluir, name="manutencao_concluir"),'
    if "manutencao_concluir" not in t:
        marker = 'path("manutencoes/nova/", views.manutencao_nova, name="manutencao_nova"),'
        if marker not in t:
            fail("Não encontrei a rota manutencao_nova em urls.py.")
        t = t.replace(marker, marker + "\n    " + route, 1)
        write(p, t)
        print("urls.py atualizado.")
    else:
        print("urls.py já contém a rota.")

def patch_template():
    write(FILES["template"], TEMPLATE)
    print("Template atualizado.")

def run(*args):
    cmd = [sys.executable, "manage.py", *args]
    print(">", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        fail("Falha em: " + " ".join(args))

def main():
    if not (ROOT / "manage.py").exists():
        fail("Copie este patch para a raiz do projeto, ao lado de manage.py.")

    print("=== PATCH - CICLO DE MANUTENÇÃO ===")
    backup()
    patch_views()
    patch_urls()
    patch_template()
    run("check")

    print("\nPATCH CONCLUÍDO.")
    print("Não há alteração de banco.")
    print("Agora execute: python manage.py runserver")

if __name__ == "__main__":
    main()
