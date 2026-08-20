from pathlib import Path
import shutil, subprocess, sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent
MODELS = ROOT / "core/models.py"
URLS = ROOT / "core/urls.py"
CSS = ROOT / "static/css/sistema.css"
FORMS = ROOT / "core/checklist_forms.py"
VIEWS_NEW = ROOT / "core/checklist_views.py"
TPL = ROOT / "templates/checklist/pre_voo.html"
CAL = ROOT / "templates/calendario/calendario.html"

MODEL_BLOCK = '# =========================================================\n# CHECKLIST PRÉ-VOO\n# =========================================================\n\nclass ChecklistPreVoo(models.Model):\n    alocacao = models.OneToOneField(\n        Alocacao,\n        on_delete=models.CASCADE,\n        related_name="checklist_pre_voo",\n    )\n    bateria_ok = models.BooleanField(default=False)\n    helices_ok = models.BooleanField(default=False)\n    estrutura_ok = models.BooleanField(default=False)\n    controle_ok = models.BooleanField(default=False)\n    gps_ok = models.BooleanField(default=False)\n    memoria_ok = models.BooleanField(default=False)\n    area_segura = models.BooleanField(default=False)\n    meteorologia_ok = models.BooleanField(default=False)\n    observacoes = models.TextField(blank=True)\n    concluido = models.BooleanField(default=False)\n    preenchido_por = models.ForeignKey(\n        User,\n        on_delete=models.PROTECT,\n        null=True,\n        blank=True,\n        related_name="checklists_pre_voo",\n    )\n    atualizado_em = models.DateTimeField(auto_now=True)\n\n    def atualizar_status(self):\n        self.concluido = all([\n            self.bateria_ok,\n            self.helices_ok,\n            self.estrutura_ok,\n            self.controle_ok,\n            self.gps_ok,\n            self.memoria_ok,\n            self.area_segura,\n            self.meteorologia_ok,\n        ])\n\n    def __str__(self):\n        return f"Checklist - {self.alocacao}"\n'
FORMS_CONTENT = 'from django import forms\nfrom .models import ChecklistPreVoo\n\nclass ChecklistPreVooForm(forms.ModelForm):\n    class Meta:\n        model = ChecklistPreVoo\n        fields = [\n            "bateria_ok", "helices_ok", "estrutura_ok", "controle_ok",\n            "gps_ok", "memoria_ok", "area_segura", "meteorologia_ok",\n            "observacoes",\n        ]\n        labels = {\n            "bateria_ok": "Bateria inspecionada e carregada",\n            "helices_ok": "Hélices sem danos e corretamente fixadas",\n            "estrutura_ok": "Estrutura e braços sem danos",\n            "controle_ok": "Controle remoto e comunicação verificados",\n            "gps_ok": "GPS/GNSS disponível e funcionando",\n            "memoria_ok": "Armazenamento disponível",\n            "area_segura": "Área de decolagem/pouso segura",\n            "meteorologia_ok": "Condições meteorológicas adequadas",\n            "observacoes": "Observações",\n        }\n        widgets = {\n            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 4}),\n        }\n'
VIEWS_CONTENT = 'from django.contrib import messages\nfrom django.contrib.auth.decorators import login_required\nfrom django.shortcuts import render, redirect, get_object_or_404\n\nfrom .models import Piloto, Alocacao, ChecklistPreVoo\nfrom .checklist_forms import ChecklistPreVooForm\nfrom .views import usuario_e_admin, _base_context\n\n@login_required\ndef checklist_pre_voo(request, pk):\n    alocacao = get_object_or_404(\n        Alocacao.objects.select_related("piloto", "drone"),\n        pk=pk\n    )\n\n    permitido = usuario_e_admin(request.user)\n    if not permitido:\n        try:\n            permitido = alocacao.piloto_id == request.user.piloto.id\n        except Piloto.DoesNotExist:\n            permitido = False\n\n    if not permitido:\n        messages.error(request, "Você não tem permissão para este checklist.")\n        return redirect("calendario")\n\n    checklist, _ = ChecklistPreVoo.objects.get_or_create(alocacao=alocacao)\n    form = ChecklistPreVooForm(request.POST or None, instance=checklist)\n\n    if form.is_valid():\n        checklist = form.save(commit=False)\n        checklist.preenchido_por = request.user\n        checklist.atualizar_status()\n        checklist.save()\n\n        if checklist.concluido:\n            messages.success(request, "Checklist pré-voo concluído.")\n        else:\n            messages.warning(request, "Checklist salvo com itens pendentes.")\n\n        return redirect("calendario")\n\n    ctx = {\n        "form": form,\n        "alocacao": alocacao,\n        "checklist": checklist,\n    }\n    ctx.update(_base_context(request))\n    return render(request, "checklist/pre_voo.html", ctx)\n'
TEMPLATE_CONTENT = '{% extends "base.html" %}\n{% block title %}Checklist Pré-Voo{% endblock %}\n{% block content %}\n\n<div class="page-header">\n    <div>\n        <h1>Checklist Pré-Voo</h1>\n        <p>{{ alocacao.data|date:"d/m/Y" }} · {{ alocacao.hora_inicio|time:"H:i" }} - {{ alocacao.hora_fim|time:"H:i" }}</p>\n    </div>\n    <a class="btn btn-light" href="{% url \'calendario\' %}">Voltar</a>\n</div>\n\n<div class="panel">\n    <div class="checklist-summary">\n        <div><span>Drone</span><strong>{{ alocacao.drone.nome }}</strong></div>\n        <div><span>Piloto</span><strong>{{ alocacao.piloto.nome }}</strong></div>\n        <div><span>Local</span><strong>{{ alocacao.local|default:"-" }}</strong></div>\n        <div>\n            <span>Status</span>\n            {% if checklist.concluido %}\n            <strong>Concluído</strong>\n            {% else %}\n            <strong>Pendente</strong>\n            {% endif %}\n        </div>\n    </div>\n\n    <form method="post">\n        {% csrf_token %}\n        <div class="checklist-grid">\n            {% for field in form %}\n                {% if field.name != "observacoes" %}\n                <label class="checklist-item">\n                    {{ field }}\n                    <span>{{ field.label }}</span>\n                </label>\n                {% endif %}\n            {% endfor %}\n        </div>\n\n        <div class="mb-3">\n            <label>{{ form.observacoes.label }}</label>\n            {{ form.observacoes }}\n        </div>\n\n        <div class="form-actions">\n            <a class="btn btn-light" href="{% url \'calendario\' %}">Cancelar</a>\n            <button type="submit" class="btn btn-primary">Salvar Checklist</button>\n        </div>\n    </form>\n</div>\n{% endblock %}\n'
CSS_BLOCK = '.checklist-summary{\n    display:grid;\n    grid-template-columns:repeat(4,minmax(0,1fr));\n    gap:12px;\n    margin-bottom:20px;\n}\n.checklist-summary>div{\n    padding:12px 14px;\n    border:1px solid #e2e8f0;\n    border-radius:10px;\n    background:#f8fafc;\n}\n.checklist-summary span{\n    display:block;\n    font-size:11px;\n    color:#718096;\n    margin-bottom:4px;\n}\n.checklist-grid{\n    display:grid;\n    grid-template-columns:repeat(2,minmax(0,1fr));\n    gap:10px;\n    margin-bottom:18px;\n}\n.checklist-item{\n    display:flex;\n    align-items:flex-start;\n    gap:10px;\n    padding:12px 14px;\n    border:1px solid #e1e7ef;\n    border-radius:9px;\n    cursor:pointer;\n}\n@media(max-width:900px){\n    .checklist-summary,.checklist-grid{grid-template-columns:1fr;}\n}\n'

def fail(msg):
    print("\nERRO:", msg)
    sys.exit(1)

def backup():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ROOT / ("backup_patch_checklist_" + stamp)
    for p in (MODELS, URLS, CSS, FORMS, VIEWS_NEW, TPL, CAL):
        if p.exists():
            target = dest / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    mig = ROOT / "core/migrations"
    if mig.exists():
        shutil.copytree(mig, dest / "core/migrations", dirs_exist_ok=True)
    print("Backup criado em:", dest)

def patch_models():
    text = MODELS.read_text(encoding="utf-8")
    if "class ChecklistPreVoo(" not in text:
        MODELS.write_text(text.rstrip() + "\n\n" + MODEL_BLOCK + "\n", encoding="utf-8")

def write_files():
    FORMS.write_text(FORMS_CONTENT, encoding="utf-8")
    VIEWS_NEW.write_text(VIEWS_CONTENT, encoding="utf-8")
    TPL.parent.mkdir(parents=True, exist_ok=True)
    TPL.write_text(TEMPLATE_CONTENT, encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    if ".checklist-summary" not in css:
        CSS.write_text(css.rstrip() + "\n\n" + CSS_BLOCK + "\n", encoding="utf-8")

def patch_urls():
    text = URLS.read_text(encoding="utf-8")
    if "from . import checklist_views" not in text:
        text = text.replace("from . import views", "from . import views\nfrom . import checklist_views", 1)
    if 'name="checklist_pre_voo"' not in text:
        marker = 'path("calendario/", views.calendario, name="calendario"),'
        if marker not in text:
            fail("Rota calendario não encontrada.")
        route = 'path("calendario/<int:pk>/checklist/", checklist_views.checklist_pre_voo, name="checklist_pre_voo"),'
        text = text.replace(marker, marker + "\n    " + route, 1)
    URLS.write_text(text, encoding="utf-8")

def patch_calendar():
    if not CAL.exists():
        return
    text = CAL.read_text(encoding="utf-8")
    if "{% url 'checklist_pre_voo' a.pk %}" in text:
        return
    marker = '<div class="calendar-day-item-actions">'
    if marker in text:
        button = '''\n<a href="{% url 'checklist_pre_voo' a.pk %}" class="icon-btn">Checklist</a>\n'''
        text = text.replace(marker, marker + button, 1)
        CAL.write_text(text, encoding="utf-8")

def run_manage(*args):
    cmd = [sys.executable, "manage.py", *args]
    print(">", " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        fail("Falha em: python manage.py " + " ".join(args))

def main():
    if not (ROOT / "manage.py").exists():
        fail("Copie este patch para a raiz do projeto.")
    for p in (MODELS, URLS, CSS):
        if not p.exists():
            fail("Arquivo não encontrado: " + str(p))

    print("=== PATCH - CHECKLIST PRÉ-VOO ===")
    backup()
    patch_models()
    write_files()
    patch_urls()
    patch_calendar()
    run_manage("makemigrations", "core")
    run_manage("migrate")
    run_manage("check")
    print("\nPATCH CONCLUÍDO COM SUCESSO.")
    print("Agora execute: python manage.py runserver")

if __name__ == "__main__":
    main()
