from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent
VIEWS = ROOT / "core" / "views.py"
CAL = ROOT / "templates" / "calendario" / "calendario.html"
AGENDA = ROOT / "templates" / "agenda" / "minha_agenda.html"

def fail(msg):
    print("\nERRO:", msg)
    sys.exit(1)

def backup():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ROOT / ("backup_patch_voo_calendario_" + stamp)
    for p in (VIEWS, CAL, AGENDA):
        if p.exists():
            target = dest / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    print("Backup criado em:", dest)

HELPER = r"""
def _sincronizar_voo_com_calendario(voo, usuario):
    agora = timezone.localtime()

    inicio_voo = timezone.make_aware(
        datetime.combine(voo.data, voo.hora_inicio),
        timezone.get_current_timezone(),
    )

    fim_voo = timezone.make_aware(
        datetime.combine(voo.data, voo.hora_fim),
        timezone.get_current_timezone(),
    )

    if fim_voo <= inicio_voo:
        fim_voo += timedelta(days=1)

    status_calendario = "concluido" if fim_voo <= agora else "reservado"

    finalidade_texto = (
        voo.get_finalidade_display()
        if hasattr(voo, "get_finalidade_display")
        else str(voo.finalidade)
    )

    alocacao = (
        Alocacao.objects
        .filter(
            piloto=voo.piloto,
            drone=voo.drone,
            data=voo.data,
            hora_inicio=voo.hora_inicio,
            hora_fim=voo.hora_fim,
        )
        .first()
    )

    if alocacao:
        alocacao.finalidade = finalidade_texto
        alocacao.local = voo.local or ""
        alocacao.observacoes = voo.observacoes or ""

        if alocacao.status != "cancelado":
            alocacao.status = status_calendario

        alocacao.save(
            update_fields=[
                "finalidade",
                "local",
                "observacoes",
                "status",
            ]
        )
        return alocacao

    return Alocacao.objects.create(
        data=voo.data,
        hora_inicio=voo.hora_inicio,
        hora_fim=voo.hora_fim,
        piloto=voo.piloto,
        drone=voo.drone,
        finalidade=finalidade_texto,
        local=voo.local or "",
        observacoes=voo.observacoes or "",
        status=status_calendario,
        criado_por=usuario,
    )
"""

def add_helper(text):
    if "def _sincronizar_voo_com_calendario(" in text:
        return text

    marker = "# =========================================================\n# VOOS\n# ========================================================="
    pos = text.find(marker)

    if pos == -1:
        fail("Não encontrei a seção VOOS em views.py.")

    return text[:pos] + HELPER.strip() + "\n\n\n" + text[pos:]

def patch_voo_novo(text):
    start = text.find("@login_required\ndef voo_novo(request):")
    if start == -1:
        fail("Não encontrei voo_novo em views.py.")

    end = text.find("\n\n@admin_required\ndef voo_editar", start)
    if end == -1:
        fail("Não encontrei voo_editar após voo_novo.")

    bloco = text[start:end]

    if "_sincronizar_voo_com_calendario(" in bloco:
        return text

    alvo = """        voo.save()

        messages.success(
            request,
            "Voo registrado com sucesso."
        )
"""

    novo = """        voo.save()

        _sincronizar_voo_com_calendario(
            voo,
            request.user
        )

        messages.success(
            request,
            "Voo registrado e calendário atualizado com sucesso."
        )
"""

    if alvo not in bloco:
        fail("Não encontrei o trecho esperado de salvamento em voo_novo.")

    bloco = bloco.replace(alvo, novo, 1)
    return text[:start] + bloco + text[end:]

def patch_voo_editar(text):
    start = text.find("@admin_required\ndef voo_editar(request, pk):")
    if start == -1:
        fail("Não encontrei voo_editar em views.py.")

    end = text.find("\n\n@admin_required\n@require_POST\ndef voo_excluir", start)
    if end == -1:
        fail("Não encontrei voo_excluir após voo_editar.")

    bloco = text[start:end]

    if "_sincronizar_voo_com_calendario(" in bloco:
        return text

    alvo = """    if form.is_valid():
        form.save()

        messages.success(
"""

    novo = """    if form.is_valid():
        voo = form.save()

        _sincronizar_voo_com_calendario(
            voo,
            request.user
        )

        messages.success(
"""

    if alvo not in bloco:
        fail("Não encontrei o trecho esperado de salvamento em voo_editar.")

    bloco = bloco.replace(alvo, novo, 1)
    return text[:start] + bloco + text[end:]

def patch_views():
    text = VIEWS.read_text(encoding="utf-8")
    text = add_helper(text)
    text = patch_voo_novo(text)
    text = patch_voo_editar(text)
    VIEWS.write_text(text, encoding="utf-8")
    print("views.py atualizado.")

def remove_button(path):
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")
    original = text

    variants = [
        '''    <a class="btn btn-primary" href="{% url 'alocacao_nova' %}">
        + Reservar
    </a>
''',
        '''    <a class="btn btn-primary" href="{% url 'alocacao_nova' %}">
        + Nova Reserva
    </a>
''',
        '''<a class="btn btn-primary" href="{% url 'alocacao_nova' %}">+ Reservar</a>''',
        '''<a class="btn btn-primary" href="{% url 'alocacao_nova' %}">+ Nova Reserva</a>''',
    ]

    for item in variants:
        text = text.replace(item, "")

    if text != original:
        path.write_text(text, encoding="utf-8")
        print(path.name, "atualizado.")

def run_check():
    result = subprocess.run([sys.executable, "manage.py", "check"], cwd=ROOT)
    if result.returncode != 0:
        fail("python manage.py check falhou. O backup foi preservado.")

def main():
    if not (ROOT / "manage.py").exists():
        fail("Copie este patch para a raiz do projeto.")

    if not VIEWS.exists():
        fail("core/views.py não encontrado.")

    print("=== PATCH - VOO SINCRONIZA CALENDÁRIO ===")
    backup()
    patch_views()
    remove_button(CAL)
    remove_button(AGENDA)
    run_check()

    print("\nPATCH CONCLUÍDO COM SUCESSO.")
    print("Não precisa makemigrations nem migrate.")
    print("Agora execute: python manage.py runserver")

if __name__ == "__main__":
    main()
