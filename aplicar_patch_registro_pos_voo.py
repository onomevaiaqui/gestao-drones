#!/usr/bin/env python
"""Patch incremental e idempotente para adicionar RegistroPosVoo ao app core."""
from __future__ import annotations

import ast
import datetime as dt
import os
import py_compile
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

MODEL_MARK = "# PATCH REGISTRO POS-VOO: MODELO"
FORM_MARK = "# PATCH REGISTRO POS-VOO: FORMULARIO"
VIEW_MARK = "# PATCH REGISTRO POS-VOO: VIEWS"
URL_MARK = "# PATCH REGISTRO POS-VOO: ROTA"
CAL_MARK = "<!-- PATCH REGISTRO POS-VOO: CALENDARIO -->"

MODEL_BLOCK = r'''

# PATCH REGISTRO POS-VOO: MODELO
class RegistroPosVoo(models.Model):
    RESULTADO_CHOICES = [
        ("concluido", "Concluído"),
        ("parcial", "Parcial"),
        ("abortado", "Abortado"),
    ]

    alocacao = models.OneToOneField(
        Alocacao, on_delete=models.CASCADE, related_name="registro_pos_voo"
    )
    voo = models.OneToOneField(
        Voo, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="registro_pos_voo",
    )
    hora_inicio_real = models.TimeField()
    hora_fim_real = models.TimeField()
    resultado = models.CharField(max_length=20, choices=RESULTADO_CHOICES)
    baterias_utilizadas = models.PositiveIntegerField(default=1)
    bateria_inicial = models.PositiveIntegerField(null=True, blank=True)
    bateria_final = models.PositiveIntegerField(null=True, blank=True)
    distancia_m = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    ocorrencias = models.TextField(blank=True)
    danos = models.TextField(blank=True)
    necessita_manutencao = models.BooleanField(default=False)
    observacoes = models.TextField(blank=True)
    concluido = models.BooleanField(default=False)
    preenchido_por = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="registros_pos_voo"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-alocacao__data", "-hora_inicio_real"]
        verbose_name = "Registro pós-voo"
        verbose_name_plural = "Registros pós-voo"

    def __str__(self):
        return f"Pós-voo - {self.alocacao}"

    @property
    def duracao_minutos(self):
        inicio = datetime.combine(self.alocacao.data, self.hora_inicio_real)
        fim = datetime.combine(self.alocacao.data, self.hora_fim_real)
        if fim < inicio:
            fim += timedelta(days=1)
        return int((fim - inicio).total_seconds() // 60)
'''

FORM_BLOCK = r'''

# PATCH REGISTRO POS-VOO: FORMULARIO
from django import forms as pos_voo_forms
from .models import RegistroPosVoo

class RegistroPosVooForm(pos_voo_forms.ModelForm):
    class Meta:
        model = RegistroPosVoo
        fields = [
            "hora_inicio_real", "hora_fim_real", "resultado",
            "baterias_utilizadas", "bateria_inicial", "bateria_final",
            "distancia_m", "ocorrencias", "danos", "necessita_manutencao",
            "observacoes", "concluido",
        ]
        widgets = {
            "hora_inicio_real": pos_voo_forms.TimeInput(attrs={"type": "time"}),
            "hora_fim_real": pos_voo_forms.TimeInput(attrs={"type": "time"}),
            "ocorrencias": pos_voo_forms.Textarea(attrs={"rows": 3}),
            "danos": pos_voo_forms.Textarea(attrs={"rows": 3}),
            "observacoes": pos_voo_forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        dados = super().clean()
        for campo in ("bateria_inicial", "bateria_final"):
            valor = dados.get(campo)
            if valor is not None and not 0 <= valor <= 100:
                self.add_error(campo, "Informe um percentual entre 0 e 100.")
        if dados.get("baterias_utilizadas") == 0:
            self.add_error("baterias_utilizadas", "Informe ao menos uma bateria.")
        return dados
'''

VIEW_BLOCK = r'''

# PATCH REGISTRO POS-VOO: VIEWS
from django.contrib import messages as pos_voo_messages
from django.contrib.auth.decorators import login_required as pos_voo_login_required
from django.core.exceptions import PermissionDenied as PosVooPermissionDenied
from django.db import transaction as pos_voo_transaction
from django.shortcuts import get_object_or_404 as pos_voo_get_object_or_404
from django.shortcuts import redirect as pos_voo_redirect
from django.shortcuts import render as pos_voo_render
from .forms import RegistroPosVooForm
from .models import Alocacao, DroneHistorico, Manutencao, RegistroPosVoo, Voo

def _pos_voo_admin(user):
    return bool(
        user.is_superuser or user.is_staff
        or getattr(getattr(user, "piloto", None), "perfil", "") == "administrador"
    )

def _pos_voo_pode_acessar(user, alocacao):
    return _pos_voo_admin(user) or alocacao.piloto.user_id == user.id

def _pos_voo_finalidade(valor):
    validas = {codigo for codigo, _ in Voo.FINALIDADE_CHOICES}
    return valor if valor in validas else "outro"

@pos_voo_login_required
@pos_voo_transaction.atomic
def registro_pos_voo(request, alocacao_id):
    alocacao = pos_voo_get_object_or_404(
        Alocacao.objects.select_related("piloto__user", "drone"), pk=alocacao_id
    )
    if not _pos_voo_pode_acessar(request.user, alocacao):
        raise PosVooPermissionDenied

    registro = RegistroPosVoo.objects.filter(alocacao=alocacao).first()
    if registro and registro.concluido and not _pos_voo_admin(request.user):
        return pos_voo_render(request, "core/registro_pos_voo.html", {
            "form": RegistroPosVooForm(instance=registro), "alocacao": alocacao,
            "registro": registro, "somente_leitura": True,
        })

    if request.method == "POST":
        form = RegistroPosVooForm(request.POST, instance=registro)
        if form.is_valid():
            registro = form.save(commit=False)
            registro.alocacao = alocacao
            if not registro.pk:
                registro.preenchido_por = request.user
            registro.save()

            if registro.concluido:
                voo_defaults = {
                    "data": alocacao.data, "piloto": alocacao.piloto,
                    "drone": alocacao.drone,
                    "finalidade": _pos_voo_finalidade(alocacao.finalidade),
                    "local": alocacao.local or "Não informado",
                    "hora_inicio": registro.hora_inicio_real,
                    "hora_fim": registro.hora_fim_real,
                    "bateria_inicial": registro.bateria_inicial,
                    "bateria_final": registro.bateria_final,
                    "distancia_m": registro.distancia_m,
                    "observacoes": "\n\n".join(filter(None, [
                        registro.observacoes,
                        "Ocorrências: " + registro.ocorrencias if registro.ocorrencias else "",
                        "Danos: " + registro.danos if registro.danos else "",
                    ])),
                    "criado_por": registro.preenchido_por,
                }
                if registro.voo_id:
                    for campo, valor in voo_defaults.items():
                        setattr(registro.voo, campo, valor)
                    registro.voo.save()
                    voo = registro.voo
                else:
                    voo = Voo.objects.create(**voo_defaults)
                    registro.voo = voo
                    registro.save(update_fields=["voo", "atualizado_em"])

                if alocacao.status != "concluido":
                    alocacao.status = "concluido"
                    alocacao.save(update_fields=["status"])
                try:
                    solicitacao = alocacao.solicitacao_voo
                except Exception:
                    solicitacao = None
                if solicitacao and solicitacao.status != "concluido":
                    solicitacao.status = "concluido"
                    solicitacao.save(update_fields=["status", "atualizado_em"])

                if registro.necessita_manutencao:
                    drone = alocacao.drone
                    status_anterior = drone.status
                    drone.status = "manutencao"
                    drone.save(update_fields=["status"])
                    DroneHistorico.objects.create(
                        drone=drone, status_anterior=status_anterior,
                        status_novo="manutencao",
                        localizacao_anterior=drone.localizacao,
                        localizacao_nova=drone.localizacao,
                        alterado_por=request.user,
                        observacao=f"Manutenção solicitada no pós-voo da alocação #{alocacao.pk}.",
                    )
                    if not Manutencao.objects.filter(drone=drone, concluida=False).exists():
                        Manutencao.objects.create(
                            drone=drone, concluida=False,
                            tipo="inspecao", data_inicio=alocacao.data,
                            descricao="Inspeção gerada automaticamente pelo registro pós-voo."
                            + (f" Danos: {registro.danos}" if registro.danos else ""),
                            criado_por=request.user,
                        )
            pos_voo_messages.success(request, "Registro pós-voo salvo com sucesso.")
            return pos_voo_redirect("registro_pos_voo", alocacao_id=alocacao.pk)
    else:
        form = RegistroPosVooForm(instance=registro, initial={
            "hora_inicio_real": alocacao.hora_inicio,
            "hora_fim_real": alocacao.hora_fim,
        })
    return pos_voo_render(request, "core/registro_pos_voo.html", {
        "form": form, "alocacao": alocacao, "registro": registro,
        "somente_leitura": False,
    })
'''

URL_BLOCK = r'''

# PATCH REGISTRO POS-VOO: ROTA
from . import views as pos_voo_views
urlpatterns += [
    path("alocacoes/<int:alocacao_id>/pos-voo/", pos_voo_views.registro_pos_voo, name="registro_pos_voo"),
]
'''

TEMPLATE = r'''{% extends "base.html" %}
{% block content %}
<div class="container py-4">
  <h2>Registro pós-voo</h2>
  <p><strong>Drone:</strong> {{ alocacao.drone }} &nbsp; <strong>Piloto:</strong> {{ alocacao.piloto }}</p>
  <p><strong>Data:</strong> {{ alocacao.data|date:"d/m/Y" }} &nbsp; <strong>Previsto:</strong> {{ alocacao.hora_inicio|time:"H:i" }}–{{ alocacao.hora_fim|time:"H:i" }}</p>
  {% if somente_leitura %}<div class="alert alert-info">Registro concluído. Apenas administradores podem alterá-lo.</div>{% endif %}
  <form method="post">{% csrf_token %}
    <fieldset {% if somente_leitura %}disabled{% endif %}>{{ form.as_p }}</fieldset>
    {% if not somente_leitura %}<button class="btn btn-primary" type="submit">Salvar registro</button>{% endif %}
  </form>
</div>
{% endblock %}
'''

CAL_BLOCK = r'''
<!-- PATCH REGISTRO POS-VOO: CALENDARIO -->
<script>
(function () {
  var urlModelo = "{% url 'registro_pos_voo' 999999999 %}";
  // Integração não intrusiva: funciona com detalhes/modal que exponham o id da alocação.
  function integrar(root) {
    (root || document).querySelectorAll('[data-alocacao-id]').forEach(function (el) {
      var id = el.getAttribute('data-alocacao-id');
      if (!id || el.querySelector('.acao-pos-voo')) return;
      var a = document.createElement('a');
      a.className = 'btn btn-success acao-pos-voo';
      a.href = urlModelo.replace('999999999', id);
      a.textContent = 'Pós-voo';
      el.appendChild(a);
    });
  }
  document.addEventListener('DOMContentLoaded', function () {
    integrar(document);
    new MutationObserver(function () { integrar(document); }).observe(document.body, {childList:true, subtree:true});
  });
})();
</script>
'''

def read(path):
    return path.read_text(encoding="utf-8")

def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")

def append_once(path, marker, block):
    content = read(path) if path.exists() else ""
    if marker not in content:
        write(path, content.rstrip() + "\n" + block.strip() + "\n")

def locate(root):
    manage = root / "manage.py"
    if not manage.exists():
        raise RuntimeError("Execute este arquivo na pasta que contém manage.py.")
    core = root / "core"
    required = [core / "models.py", core / "forms.py", core / "views.py", core / "urls.py"]
    missing = [str(p.relative_to(root)) for p in required if not p.exists()]
    if missing:
        raise RuntimeError("Arquivos não encontrados: " + ", ".join(missing))
    calendars = [p for p in root.rglob("*.html") if "calend" in p.name.lower()]
    if not calendars:
        raise RuntimeError("Template do calendário não encontrado (nome deve conter 'calend').")
    calendars.sort(key=lambda p: ("template" not in str(p).lower(), len(str(p))))
    return core, calendars[0]

def validate_python(paths):
    for path in paths:
        ast.parse(read(path), filename=str(path))
        py_compile.compile(str(path), doraise=True)

def template_root(root, calendar):
    current = calendar.parent
    while current != root and current.name.lower() != "templates":
        current = current.parent
    return current if current.name.lower() == "templates" else root / "templates"

def main():
    root = Path.cwd().resolve()
    core, calendar = locate(root)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = root / "backups" / f"antes_registro_pos_voo_{stamp}"
    targets = [core / "models.py", core / "forms.py", core / "views.py", core / "urls.py", calendar]
    for path in targets:
        destination = backup / path.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    created = []
    template = template_root(root, calendar) / "core" / "registro_pos_voo.html"
    if template.exists():
        destination = backup / template.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template, destination)
    else:
        created.append(template)

    try:
        append_once(core / "models.py", MODEL_MARK, MODEL_BLOCK)
        append_once(core / "forms.py", FORM_MARK, FORM_BLOCK)
        append_once(core / "views.py", VIEW_MARK, VIEW_BLOCK)
        append_once(core / "urls.py", URL_MARK, URL_BLOCK)
        write(template, TEMPLATE)
        append_once(calendar, CAL_MARK, CAL_BLOCK)
        validate_python([core / "models.py", core / "forms.py", core / "views.py", core / "urls.py"])
        commands = [
            [sys.executable, "manage.py", "makemigrations", "core"],
            [sys.executable, "manage.py", "migrate"],
            [sys.executable, "manage.py", "check"],
        ]
        for command in commands:
            print("\nExecutando:", " ".join(command))
            subprocess.run(command, cwd=root, check=True)
    except Exception:
        print("\nFalha detectada; restaurando arquivos do backup...")
        for path in targets:
            saved = backup / path.relative_to(root)
            if saved.exists():
                shutil.copy2(saved, path)
        saved_template = backup / template.relative_to(root)
        if saved_template.exists():
            shutil.copy2(saved_template, template)
        elif template in created and template.exists():
            template.unlink()
        traceback.print_exc()
        print("Backup preservado em:", backup)
        return 1
    print("\nPatch concluído e validado com sucesso.")
    print("Backup em:", backup)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
