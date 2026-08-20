from pathlib import Path
import shutil, subprocess, sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent
VIEWS = ROOT / "core/views.py"
URLS = ROOT / "core/urls.py"
TPL = ROOT / "templates/manutencoes/lista.html"

def fail(msg):
    print("\nERRO:", msg)
    sys.exit(1)

def backup():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ROOT / ("backup_patch_manutencao_" + stamp)
    for p in (VIEWS, URLS, TPL):
        if p.exists():
            target = dest / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    print("Backup:", dest)

def add_views():
    text = VIEWS.read_text(encoding="utf-8")
    marker = "@admin_required\ndef manutencao_nova(request):"
    if marker not in text:
        fail("Não encontrei manutencao_nova em views.py")

    editar = '''
@admin_required
def manutencao_editar(request, pk):
    manutencao = get_object_or_404(Manutencao, pk=pk)
    form = ManutencaoForm(request.POST or None, instance=manutencao)

    if form.is_valid():
        obj = form.save(commit=False)
        obj.criado_por = manutencao.criado_por
        obj.save()

        if not obj.concluida:
            if obj.drone.status != "manutencao":
                anterior = obj.drone.status
                obj.drone.status = "manutencao"
                obj.drone.save(update_fields=["status"])
                DroneHistorico.objects.create(
                    drone=obj.drone,
                    status_anterior=anterior,
                    status_novo="manutencao",
                    localizacao_anterior=getattr(obj.drone, "localizacao", ""),
                    localizacao_nova=getattr(obj.drone, "localizacao", ""),
                    alterado_por=request.user,
                    observacao="Status atualizado ao editar manutenção",
                )

        messages.success(request, "Manutenção atualizada com sucesso.")
        return redirect("manutencoes")

    ctx = {"form": form, "titulo": "Editar manutenção"}
    ctx.update(_base_context(request))
    return render(request, "form.html", ctx)
'''

    excluir = '''
@admin_required
@require_POST
def manutencao_excluir(request, pk):
    manutencao = get_object_or_404(Manutencao, pk=pk)
    drone = manutencao.drone
    estava_aberta = not manutencao.concluida

    manutencao.delete()

    if estava_aberta:
        outra_aberta = Manutencao.objects.filter(
            drone=drone,
            concluida=False
        ).exists()

        if not outra_aberta and drone.status == "manutencao":
            agora = timezone.localtime()
            reserva_ativa = Alocacao.objects.filter(
                drone=drone,
                status="reservado",
                data=agora.date(),
                hora_inicio__lte=agora.time(),
                hora_fim__gt=agora.time(),
            ).exists()

            novo_status = "em_campo" if reserva_ativa else "ativo"
            drone.status = novo_status
            drone.save(update_fields=["status"])

            DroneHistorico.objects.create(
                drone=drone,
                status_anterior="manutencao",
                status_novo=novo_status,
                localizacao_anterior=getattr(drone, "localizacao", ""),
                localizacao_nova=getattr(drone, "localizacao", ""),
                alterado_por=request.user,
                observacao="Drone liberado após exclusão de manutenção",
            )

    messages.success(request, "Manutenção excluída com sucesso.")
    return redirect("manutencoes")
'''

    if "def manutencao_editar(" not in text:
        text = text.replace(marker, editar + "\n" + marker, 1)
    if "def manutencao_excluir(" not in text:
        text = text.replace(marker, excluir + "\n" + marker, 1)

    VIEWS.write_text(text, encoding="utf-8")

def add_urls():
    text = URLS.read_text(encoding="utf-8")
    marker = 'path("manutencoes/nova/", views.manutencao_nova, name="manutencao_nova"),'
    if marker not in text:
        fail("Não encontrei manutencao_nova em urls.py")

    extras = []
    if "manutencao_editar" not in text:
        extras.append('path("manutencoes/<int:pk>/editar/", views.manutencao_editar, name="manutencao_editar"),')
    if "manutencao_excluir" not in text:
        extras.append('path("manutencoes/<int:pk>/excluir/", views.manutencao_excluir, name="manutencao_excluir"),')

    if extras:
        text = text.replace(marker, marker + "\n    " + "\n    ".join(extras), 1)
        URLS.write_text(text, encoding="utf-8")

def update_template():
    TPL.parent.mkdir(parents=True, exist_ok=True)
    html = '''{% extends "base.html" %}
{% block title %}Manutenções{% endblock %}
{% block content %}
<div class="page-header">
    <div><h1>Manutenções</h1><p>Histórico e acompanhamento dos equipamentos</p></div>
    <a class="btn btn-primary" href="{% url 'manutencao_nova' %}">+ Nova Manutenção</a>
</div>
<div class="panel">
<div class="table-responsive">
<table class="modern-table">
<thead><tr><th>Drone</th><th>Tipo</th><th>Início</th><th>Fim</th><th>Descrição</th><th>Status</th><th>Ações</th></tr></thead>
<tbody>
{% for m in manutencoes %}
<tr>
<td><strong>{{ m.drone.nome }}</strong><div class="text-muted small">{{ m.drone.modelo }}</div></td>
<td>{{ m.get_tipo_display }}</td>
<td>{{ m.data_inicio|date:"d/m/Y" }}</td>
<td>{% if m.data_fim %}{{ m.data_fim|date:"d/m/Y" }}{% else %}-{% endif %}</td>
<td>{{ m.descricao|truncatechars:70 }}</td>
<td>{% if m.concluida %}<span class="badge-soft green">Concluída</span>{% else %}<span class="badge-soft orange">Em andamento</span>{% endif %}</td>
<td class="actions">
<a href="{% url 'manutencao_editar' m.pk %}" class="icon-btn">Editar</a>
{% if not m.concluida %}
<form method="post" action="{% url 'manutencao_concluir' m.pk %}" onsubmit="return confirm('Concluir esta manutenção?');">{% csrf_token %}<button type="submit" class="icon-btn">Concluir</button></form>
{% endif %}
<form method="post" action="{% url 'manutencao_excluir' m.pk %}" onsubmit="return confirm('Excluir esta manutenção?');">{% csrf_token %}<button type="submit" class="icon-btn danger">Excluir</button></form>
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
'''
    TPL.write_text(html, encoding="utf-8")

def run_check():
    result = subprocess.run([sys.executable, "manage.py", "check"], cwd=ROOT)
    if result.returncode != 0:
        fail("python manage.py check falhou")

def main():
    if not (ROOT / "manage.py").exists():
        fail("Copie este arquivo para a raiz do projeto.")
    backup()
    add_views()
    add_urls()
    update_template()
    run_check()
    print("\nPATCH CONCLUÍDO.")
    print("Agora rode: python manage.py runserver")

if __name__ == "__main__":
    main()
