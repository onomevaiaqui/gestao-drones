from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent
MODELS = ROOT / 'core' / 'models.py'
URLS = ROOT / 'core' / 'urls.py'
BASE = ROOT / 'templates' / 'base.html'
FORMS_NEW = ROOT / 'core' / 'solicitacao_forms.py'
VIEWS_NEW = ROOT / 'core' / 'solicitacao_views.py'
TPL_DIR = ROOT / 'templates' / 'solicitacoes'

MODEL_BLOCK = r'''# =========================================================
# SOLICITAÇÕES DE VOO
# =========================================================

class SolicitacaoVoo(models.Model):
    STATUS_CHOICES = [
        ("solicitado", "Solicitado"),
        ("aprovado", "Aprovado"),
        ("rejeitado", "Rejeitado"),
        ("cancelado", "Cancelado"),
        ("concluido", "Concluído"),
    ]

    piloto = models.ForeignKey(Piloto, on_delete=models.PROTECT, related_name="solicitacoes_voo")
    drone = models.ForeignKey(Drone, on_delete=models.PROTECT, related_name="solicitacoes_voo")
    data = models.DateField()
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()
    finalidade = models.CharField(max_length=100)
    local = models.CharField(max_length=200, blank=True)
    observacoes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="solicitado")
    motivo_rejeicao = models.TextField(blank=True)
    criado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="solicitacoes_voo_criadas")
    analisado_por = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name="solicitacoes_voo_analisadas")
    alocacao = models.OneToOneField(Alocacao, on_delete=models.SET_NULL, null=True, blank=True, related_name="solicitacao_voo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data", "-hora_inicio", "-criado_em"]

    def __str__(self):
        return f"{self.data} - {self.piloto} - {self.drone} - {self.get_status_display()}"
'''

FORMS_CONTENT = r'''from django import forms
from django.db.models import Q
from .models import Piloto, Drone, Alocacao, SolicitacaoVoo

class SolicitacaoVooForm(forms.ModelForm):
    class Meta:
        model = SolicitacaoVoo
        fields = ["data", "hora_inicio", "hora_fim", "piloto", "drone", "finalidade", "local", "observacoes"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "piloto": forms.Select(attrs={"class": "form-select"}),
            "drone": forms.Select(attrs={"class": "form-select"}),
            "finalidade": forms.TextInput(attrs={"class": "form-control"}),
            "local": forms.TextInput(attrs={"class": "form-control"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["piloto"].queryset = Piloto.objects.filter(ativo=True)
        self.fields["drone"].queryset = Drone.objects.filter(status="ativo")
        if self.instance and self.instance.pk:
            self.fields["piloto"].queryset = Piloto.objects.filter(Q(ativo=True) | Q(pk=self.instance.piloto_id)).distinct()
            self.fields["drone"].queryset = Drone.objects.filter(Q(status="ativo") | Q(pk=self.instance.drone_id)).distinct()

    def clean(self):
        cleaned = super().clean()
        data = cleaned.get("data")
        inicio = cleaned.get("hora_inicio")
        fim = cleaned.get("hora_fim")
        drone = cleaned.get("drone")
        if inicio and fim and fim <= inicio:
            self.add_error("hora_fim", "A hora final deve ser posterior à hora inicial.")
        if data and inicio and fim and drone:
            conflito = Alocacao.objects.filter(
                data=data,
                drone=drone,
                status="reservado",
                hora_inicio__lt=fim,
                hora_fim__gt=inicio,
            ).exists()
            if conflito:
                self.add_error("drone", "Este drone já possui uma reserva nesse horário.")
        return cleaned
'''

VIEWS_CONTENT = r'''from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .models import Piloto, Alocacao, SolicitacaoVoo
from .solicitacao_forms import SolicitacaoVooForm
from .views import usuario_e_admin, admin_required, _base_context

@login_required
def solicitacoes_voo(request):
    if usuario_e_admin(request.user):
        qs = SolicitacaoVoo.objects.select_related("piloto", "drone", "criado_por", "analisado_por")
    else:
        try:
            piloto = request.user.piloto
        except Piloto.DoesNotExist:
            messages.error(request, "Seu usuário não está vinculado a um piloto.")
            return redirect("dashboard")
        qs = SolicitacaoVoo.objects.select_related("piloto", "drone").filter(piloto=piloto)
    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)
    ctx = {"solicitacoes": qs, "status_atual": status or "", "status_choices": SolicitacaoVoo.STATUS_CHOICES}
    ctx.update(_base_context(request))
    return render(request, "solicitacoes/lista.html", ctx)

@login_required
def solicitacao_voo_nova(request):
    form = SolicitacaoVooForm(request.POST or None)
    eh_admin = usuario_e_admin(request.user)
    if not eh_admin:
        try:
            piloto = request.user.piloto
        except Piloto.DoesNotExist:
            messages.error(request, "Seu usuário não está vinculado a um piloto.")
            return redirect("dashboard")
        form.fields["piloto"].queryset = Piloto.objects.filter(pk=piloto.pk)
        form.fields["piloto"].initial = piloto
        form.fields["piloto"].disabled = True
    if form.is_valid():
        obj = form.save(commit=False)
        if not eh_admin:
            obj.piloto = request.user.piloto
        obj.criado_por = request.user
        obj.status = "solicitado"
        obj.save()
        messages.success(request, "Solicitação de voo enviada com sucesso.")
        return redirect("solicitacoes_voo")
    ctx = {"form": form, "titulo": "Solicitar voo"}
    ctx.update(_base_context(request))
    return render(request, "solicitacoes/form.html", ctx)

@login_required
def solicitacao_voo_editar(request, pk):
    obj = get_object_or_404(SolicitacaoVoo, pk=pk)
    eh_admin = usuario_e_admin(request.user)
    if not eh_admin:
        try:
            piloto = request.user.piloto
        except Piloto.DoesNotExist:
            return redirect("dashboard")
        if obj.piloto_id != piloto.id:
            messages.error(request, "Você só pode editar suas próprias solicitações.")
            return redirect("solicitacoes_voo")
        if obj.status != "solicitado":
            messages.error(request, "Somente solicitações pendentes podem ser editadas.")
            return redirect("solicitacoes_voo")
    form = SolicitacaoVooForm(request.POST or None, instance=obj)
    if not eh_admin:
        form.fields["piloto"].queryset = Piloto.objects.filter(pk=request.user.piloto.pk)
        form.fields["piloto"].disabled = True
    if form.is_valid():
        obj = form.save(commit=False)
        if not eh_admin:
            obj.piloto = request.user.piloto
        obj.save()
        if eh_admin and obj.status == "aprovado" and obj.alocacao_id:
            aloc = obj.alocacao
            aloc.data = obj.data
            aloc.hora_inicio = obj.hora_inicio
            aloc.hora_fim = obj.hora_fim
            aloc.piloto = obj.piloto
            aloc.drone = obj.drone
            aloc.finalidade = obj.finalidade
            aloc.local = obj.local
            aloc.observacoes = obj.observacoes
            aloc.save()
        messages.success(request, "Solicitação atualizada.")
        return redirect("solicitacoes_voo")
    ctx = {"form": form, "titulo": "Editar solicitação de voo"}
    ctx.update(_base_context(request))
    return render(request, "solicitacoes/form.html", ctx)

@admin_required
@require_POST
def solicitacao_voo_aprovar(request, pk):
    obj = get_object_or_404(SolicitacaoVoo, pk=pk)
    if obj.status != "solicitado":
        messages.warning(request, "Esta solicitação já foi analisada.")
        return redirect("solicitacoes_voo")
    if obj.drone.status != "ativo":
        messages.error(request, "O drone selecionado não está disponível.")
        return redirect("solicitacoes_voo")
    conflito = Alocacao.objects.filter(
        data=obj.data,
        drone=obj.drone,
        status="reservado",
        hora_inicio__lt=obj.hora_fim,
        hora_fim__gt=obj.hora_inicio,
    ).exists()
    if conflito:
        messages.error(request, "Existe outra reserva para este drone no horário.")
        return redirect("solicitacoes_voo")
    aloc = Alocacao.objects.create(
        data=obj.data,
        hora_inicio=obj.hora_inicio,
        hora_fim=obj.hora_fim,
        piloto=obj.piloto,
        drone=obj.drone,
        finalidade=obj.finalidade,
        local=obj.local,
        observacoes=obj.observacoes,
        status="reservado",
        criado_por=request.user,
    )
    obj.status = "aprovado"
    obj.analisado_por = request.user
    obj.alocacao = aloc
    obj.save()
    messages.success(request, "Solicitação aprovada e adicionada ao calendário.")
    return redirect("solicitacoes_voo")

@admin_required
@require_POST
def solicitacao_voo_rejeitar(request, pk):
    obj = get_object_or_404(SolicitacaoVoo, pk=pk)
    if obj.status != "solicitado":
        messages.warning(request, "Esta solicitação já foi analisada.")
        return redirect("solicitacoes_voo")
    obj.status = "rejeitado"
    obj.analisado_por = request.user
    obj.save()
    messages.success(request, "Solicitação rejeitada.")
    return redirect("solicitacoes_voo")

@login_required
@require_POST
def solicitacao_voo_cancelar(request, pk):
    obj = get_object_or_404(SolicitacaoVoo, pk=pk)
    eh_admin = usuario_e_admin(request.user)
    if not eh_admin:
        try:
            piloto = request.user.piloto
        except Piloto.DoesNotExist:
            return redirect("dashboard")
        if obj.piloto_id != piloto.id:
            messages.error(request, "Você só pode cancelar suas próprias solicitações.")
            return redirect("solicitacoes_voo")
        if obj.status != "solicitado":
            messages.error(request, "Depois de aprovada, somente um administrador pode cancelar.")
            return redirect("solicitacoes_voo")
    if obj.alocacao_id and obj.alocacao.status != "concluido":
        obj.alocacao.status = "cancelado"
        obj.alocacao.save(update_fields=["status"])
    obj.status = "cancelado"
    if eh_admin:
        obj.analisado_por = request.user
    obj.save()
    messages.success(request, "Solicitação cancelada.")
    return redirect("solicitacoes_voo")
'''

FORM_HTML = r'''{% extends "base.html" %}
{% block title %}{{ titulo }}{% endblock %}
{% block content %}
<div class="page-header"><div><h1>{{ titulo }}</h1><p>Informe os dados da operação desejada</p></div></div>
<form method="post">{% csrf_token %}
<div class="panel"><div class="form-layout">
{% for field in form %}<div class="mb-3"><label>{{ field.label }}</label>{{ field }}{% for error in field.errors %}<div class="text-danger small">{{ error }}</div>{% endfor %}</div>{% endfor %}
</div><div class="form-actions"><a class="btn btn-light" href="{% url 'solicitacoes_voo' %}">Cancelar</a><button type="submit" class="btn btn-primary">Salvar solicitação</button></div></div>
</form>{% endblock %}
'''

LIST_HTML = r'''{% extends "base.html" %}
{% block title %}Solicitações de Voo{% endblock %}
{% block content %}
<div class="page-header"><div><h1>Solicitações de Voo</h1><p>Acompanhe e gerencie as solicitações.</p></div><a class="btn btn-primary" href="{% url 'solicitacao_voo_nova' %}">+ Solicitar Voo</a></div>
<div class="panel"><form method="get" class="filter-grid"><select class="form-select" name="status"><option value="">Todos os status</option>{% for valor,nome in status_choices %}<option value="{{ valor }}" {% if status_atual == valor %}selected{% endif %}>{{ nome }}</option>{% endfor %}</select><button class="btn btn-primary">Filtrar</button><a class="btn btn-light" href="{% url 'solicitacoes_voo' %}">Limpar</a></form></div>
<div class="panel"><div class="table-responsive"><table class="modern-table"><thead><tr><th>Data</th><th>Horário</th><th>Piloto</th><th>Drone</th><th>Finalidade</th><th>Local</th><th>Status</th><th>Ações</th></tr></thead><tbody>
{% for s in solicitacoes %}<tr><td>{{ s.data|date:"d/m/Y" }}</td><td>{{ s.hora_inicio|time:"H:i" }} - {{ s.hora_fim|time:"H:i" }}</td><td>{{ s.piloto.nome }}</td><td>{{ s.drone.nome }}</td><td>{{ s.finalidade }}</td><td>{{ s.local|default:"-" }}</td><td>{{ s.get_status_display }}</td><td class="actions">
{% if eh_admin or user.is_superuser %}<a href="{% url 'solicitacao_voo_editar' s.pk %}" class="icon-btn">Editar</a>{% if s.status == "solicitado" %}<form method="post" action="{% url 'solicitacao_voo_aprovar' s.pk %}">{% csrf_token %}<button type="submit" class="icon-btn">Aprovar</button></form><form method="post" action="{% url 'solicitacao_voo_rejeitar' s.pk %}">{% csrf_token %}<button type="submit" class="icon-btn danger">Rejeitar</button></form>{% elif s.status == "aprovado" %}<form method="post" action="{% url 'solicitacao_voo_cancelar' s.pk %}">{% csrf_token %}<button type="submit" class="icon-btn danger">Cancelar</button></form>{% endif %}
{% else %}{% if s.status == "solicitado" %}<a href="{% url 'solicitacao_voo_editar' s.pk %}" class="icon-btn">Editar</a><form method="post" action="{% url 'solicitacao_voo_cancelar' s.pk %}">{% csrf_token %}<button type="submit" class="icon-btn danger">Cancelar</button></form>{% else %}<span class="text-muted">Somente consulta</span>{% endif %}{% endif %}</td></tr>{% empty %}<tr><td colspan="8">Nenhuma solicitação encontrada.</td></tr>{% endfor %}
</tbody></table></div></div>{% endblock %}
'''

def fail(msg):
    print("\nERRO:", msg)
    sys.exit(1)

def backup():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ROOT / f"backup_patch_solicitacoes_{stamp}"
    for p in (MODELS, URLS, BASE, FORMS_NEW, VIEWS_NEW):
        if p.exists():
            target = dest / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    mig = ROOT / 'core' / 'migrations'
    if mig.exists():
        shutil.copytree(mig, dest / 'core' / 'migrations', dirs_exist_ok=True)
    print("Backup criado em:", dest)

def patch_models():
    text = MODELS.read_text(encoding='utf-8')
    if 'class SolicitacaoVoo(' not in text:
        MODELS.write_text(text.rstrip() + "\n\n" + MODEL_BLOCK + "\n", encoding='utf-8')
        print("models.py atualizado.")

def write_new_files():
    FORMS_NEW.write_text(FORMS_CONTENT, encoding='utf-8')
    VIEWS_NEW.write_text(VIEWS_CONTENT, encoding='utf-8')
    TPL_DIR.mkdir(parents=True, exist_ok=True)
    (TPL_DIR / 'form.html').write_text(FORM_HTML, encoding='utf-8')
    (TPL_DIR / 'lista.html').write_text(LIST_HTML, encoding='utf-8')
    print("Arquivos de solicitações criados.")

def patch_urls():
    text = URLS.read_text(encoding='utf-8')
    if 'from . import solicitacao_views' not in text:
        text = text.replace('from . import views', 'from . import views\nfrom . import solicitacao_views', 1)
    if 'name="solicitacoes_voo"' not in text:
        marker = 'path("", views.dashboard, name="dashboard"),'
        if marker not in text:
            fail("Não encontrei a rota dashboard em urls.py.")
        routes = '''
    path("solicitacoes/", solicitacao_views.solicitacoes_voo, name="solicitacoes_voo"),
    path("solicitacoes/nova/", solicitacao_views.solicitacao_voo_nova, name="solicitacao_voo_nova"),
    path("solicitacoes/<int:pk>/editar/", solicitacao_views.solicitacao_voo_editar, name="solicitacao_voo_editar"),
    path("solicitacoes/<int:pk>/aprovar/", solicitacao_views.solicitacao_voo_aprovar, name="solicitacao_voo_aprovar"),
    path("solicitacoes/<int:pk>/rejeitar/", solicitacao_views.solicitacao_voo_rejeitar, name="solicitacao_voo_rejeitar"),
    path("solicitacoes/<int:pk>/cancelar/", solicitacao_views.solicitacao_voo_cancelar, name="solicitacao_voo_cancelar"),
'''
        text = text.replace(marker, marker + "\n" + routes, 1)
    URLS.write_text(text, encoding='utf-8')
    print("urls.py atualizado.")

def patch_base():
    text = BASE.read_text(encoding='utf-8')
    if "{% url 'solicitacoes_voo' %}" in text:
        return
    for target in ("{% url 'minha_agenda' %}", "{% url 'calendario' %}"):
        idx = text.find(target)
        if idx != -1:
            end = text.find('</a>', idx)
            if end != -1:
                end += 4
                menu = '\n        <a href="{% url \'solicitacoes_voo\' %}" class="nav-link"><span>Solicitações de Voo</span></a>\n'
                text = text[:end] + menu + text[end:]
                BASE.write_text(text, encoding='utf-8')
                print("base.html atualizado.")
                return
    print("AVISO: link não inserido no menu. /solicitacoes/ continuará funcionando.")

def run_manage(*args):
    cmd = [sys.executable, 'manage.py', *args]
    print('>', ' '.join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        fail('Falha em: python manage.py ' + ' '.join(args))

def main():
    if not (ROOT / 'manage.py').exists():
        fail('Copie este patch para a raiz do projeto.')
    for p in (MODELS, URLS, BASE):
        if not p.exists():
            fail('Arquivo não encontrado: ' + str(p))
    print('=== PATCH - SOLICITAÇÕES DE VOO ===')
    backup()
    patch_models()
    write_new_files()
    patch_urls()
    patch_base()
    run_manage('makemigrations', 'core')
    run_manage('migrate')
    run_manage('check')
    print('\nPATCH CONCLUÍDO COM SUCESSO.')
    print('Agora execute: python manage.py runserver')

if __name__ == '__main__':
    main()
