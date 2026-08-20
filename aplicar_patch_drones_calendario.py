from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent
BASE = ROOT / "templates" / "base.html"
DRONES = ROOT / "templates" / "drones" / "lista.html"
CAL = ROOT / "templates" / "calendario" / "calendario.html"
VIEWS = ROOT / "core" / "views.py"
CSS = ROOT / "static" / "css" / "sistema.css"

def fail(msg):
    print("\nERRO:", msg)
    sys.exit(1)

def backup():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ROOT / ("backup_patch_drones_calendario_" + stamp)
    for p in (BASE, DRONES, CAL, VIEWS, CSS):
        if p.exists():
            target = dest / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    print("Backup criado em:", dest)

def patch_views():
    text = VIEWS.read_text(encoding="utf-8")
    text = text.replace(
        "@admin_required\ndef drones(request):",
        "@login_required\ndef drones(request):"
    )
    text = text.replace(
        "@admin_required\n@require_POST\ndef drone_status_atualizar(request, pk):",
        "@login_required\n@require_POST\ndef drone_status_atualizar(request, pk):"
    )
    VIEWS.write_text(text, encoding="utf-8")
    print("views.py atualizado.")

def patch_base():
    text = BASE.read_text(encoding="utf-8")

    if "{% url 'drones' %}" in text or '{% url "drones" %}' in text:
        idx_if = text.find("{% if eh_admin or user.is_superuser %}")
        idx_drone = text.find("{% url 'drones' %}")
        if idx_drone == -1:
            idx_drone = text.find('{% url "drones" %}')

        if idx_if != -1 and idx_drone > idx_if:
            menu = '''
        <a href="{% url 'drones' %}" class="nav-link">
            <span>Drones</span>
        </a>

'''
            if menu.strip() not in text:
                text = text[:idx_if] + menu + text[idx_if:]
                BASE.write_text(text, encoding="utf-8")
                print("base.html atualizado.")
            else:
                print("Link Drones já disponível.")
        else:
            print("Drones já parece visível para usuários.")
    else:
        print("AVISO: link Drones não localizado no menu.")

def patch_drones():
    text = DRONES.read_text(encoding="utf-8")
    if "drone_status_atualizar" not in text:
        fail("O template de Drones não possui seletor de status rápido.")
    print("Template de Drones compatível com alteração rápida de status.")

def patch_calendar():
    text = CAL.read_text(encoding="utf-8")

    if "calendar-events-list" not in text:
        marker = "{% for a in dia.alocacoes %}"
        pos = text.find(marker)
        if pos == -1:
            fail("Não encontrei o loop dia.alocacoes no calendario.html.")

        text = text[:pos] + '<div class="calendar-events-list">\n            ' + text[pos:]

        endfor = text.find("{% endfor %}", pos)
        if endfor == -1:
            fail("Não encontrei o fechamento do loop de reservas.")

        endfor_end = endfor + len("{% endfor %}")
        text = text[:endfor_end] + "\n            </div>" + text[endfor_end:]

    CAL.write_text(text, encoding="utf-8")
    print("calendario.html atualizado.")

def patch_css():
    if not CSS.exists():
        print("AVISO: sistema.css não encontrado.")
        return

    text = CSS.read_text(encoding="utf-8")
    if ".calendar-events-list" not in text:
        text += '''
.calendar-events-list{
    display:flex;
    flex-direction:column;
    gap:4px;
    max-height:140px;
    overflow-y:auto;
    padding-right:2px;
}

.calendar-event{
    display:block;
    width:100%;
    box-sizing:border-box;
}
'''
        CSS.write_text(text, encoding="utf-8")
        print("CSS atualizado.")
    else:
        print("CSS já possui suporte a múltiplas reservas.")

def run_check():
    result = subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=ROOT
    )
    if result.returncode != 0:
        fail("python manage.py check falhou. O backup foi preservado.")

def main():
    if not (ROOT / "manage.py").exists():
        fail("Copie este patch para a raiz do projeto, ao lado de manage.py.")

    for p in (BASE, DRONES, CAL, VIEWS):
        if not p.exists():
            fail("Arquivo não encontrado: " + str(p))

    print("=== PATCH - DRONES + CALENDÁRIO ===")
    backup()
    patch_views()
    patch_base()
    patch_drones()
    patch_calendar()
    patch_css()
    run_check()

    print("\nPATCH CONCLUÍDO COM SUCESSO.")
    print("Não precisa makemigrations nem migrate.")
    print("Agora execute: python manage.py runserver")

if __name__ == "__main__":
    main()
