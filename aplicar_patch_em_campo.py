from pathlib import Path
import shutil, subprocess, sys, re
from datetime import datetime

ROOT = Path(__file__).resolve().parent
FILES = {
    'models': ROOT/'core/models.py',
    'views': ROOT/'core/views.py',
    'template': ROOT/'templates/drones/lista.html',
    'css': ROOT/'static/css/sistema.css',
}

def fail(msg):
    print('\nERRO:', msg)
    sys.exit(1)

def backup():
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = ROOT/f'backup_patch_em_campo_{stamp}'
    for p in FILES.values():
        if p.exists():
            target = dest/p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    mig = ROOT/'core/migrations'
    if mig.exists():
        shutil.copytree(mig, dest/'core/migrations', dirs_exist_ok=True)
    print('Backup criado em:', dest)

def patch_models():
    p = FILES['models']
    t = p.read_text(encoding='utf-8')
    if '("em_campo", "Em campo")' not in t:
        new, n = re.subn(
            r'(STATUS_CHOICES\s*=\s*\[\s*\n\s*\("ativo",\s*"Ativo"\),)',
            r'\1\n        ("em_campo", "Em campo"),',
            t, count=1
        )
        if n != 1:
            fail('Não localizei STATUS_CHOICES da classe Drone.')
        p.write_text(new, encoding='utf-8')
    print('models.py atualizado.')

HELPER = '''\ndef _atualizar_status_drones_por_reserva():\n    agora = timezone.localtime()\n    reservas_ativas = (\n        Alocacao.objects\n        .filter(\n            status="reservado",\n            data=agora.date(),\n            hora_inicio__lte=agora.time(),\n            hora_fim__gt=agora.time(),\n        )\n        .select_related("drone")\n    )\n\n    drones_em_reserva = set()\n\n    for reserva in reservas_ativas:\n        drone = reserva.drone\n        drones_em_reserva.add(drone.pk)\n\n        if drone.status in ("manutencao", "indisponivel"):\n            continue\n\n        if drone.status != "em_campo":\n            anterior = drone.status\n            drone.status = "em_campo"\n            drone.save(update_fields=["status"])\n\n            DroneHistorico.objects.create(\n                drone=drone,\n                status_anterior=anterior,\n                status_novo="em_campo",\n                localizacao_anterior=getattr(drone, "localizacao", ""),\n                localizacao_nova=getattr(drone, "localizacao", ""),\n                alterado_por=None,\n                observacao="Status alterado automaticamente por reserva em andamento",\n            )\n\n    for drone in Drone.objects.filter(status="em_campo").exclude(pk__in=drones_em_reserva):\n        drone.status = "ativo"\n        drone.save(update_fields=["status"])\n\n        DroneHistorico.objects.create(\n            drone=drone,\n            status_anterior="em_campo",\n            status_novo="ativo",\n            localizacao_anterior=getattr(drone, "localizacao", ""),\n            localizacao_nova=getattr(drone, "localizacao", ""),\n            alterado_por=None,\n            observacao="Reserva finalizada. Status retornado automaticamente para Ativo",\n        )\n'''

STATUS_FUNC = '''\n@login_required\n@require_POST\ndef drone_status_atualizar(request, pk):\n    drone = get_object_or_404(Drone, pk=pk)\n    novo_status = request.POST.get("status")\n\n    validos = {v for v, _n in Drone.STATUS_CHOICES}\n    if novo_status not in validos:\n        messages.error(request, "Status inválido.")\n        return redirect("drones")\n\n    if novo_status == "em_campo":\n        messages.warning(request, "O status Em campo é automático.")\n        return redirect("drones")\n\n    agora = timezone.localtime()\n    reserva_ativa = Alocacao.objects.filter(\n        drone=drone,\n        status="reservado",\n        data=agora.date(),\n        hora_inicio__lte=agora.time(),\n        hora_fim__gt=agora.time(),\n    ).exists()\n\n    if novo_status == "ativo" and reserva_ativa:\n        _atualizar_status_drones_por_reserva()\n        messages.warning(request, "Este drone possui uma reserva em andamento e permanecerá Em campo.")\n        return redirect("drones")\n\n    anterior = drone.status\n    if anterior == novo_status:\n        return redirect("drones")\n\n    drone.status = novo_status\n    drone.save(update_fields=["status"])\n\n    DroneHistorico.objects.create(\n        drone=drone,\n        status_anterior=anterior,\n        status_novo=novo_status,\n        localizacao_anterior=getattr(drone, "localizacao", ""),\n        localizacao_nova=getattr(drone, "localizacao", ""),\n        alterado_por=request.user,\n        observacao="Alteração rápida de status",\n    )\n\n    messages.success(request, f"Status do drone {drone.nome} atualizado.")\n    return redirect("drones")\n'''

def replace_func(text, name, code):
    pattern = rf'(?ms)^(@[^\n]+\n)*def {name}\(.*?(?=^(@[^\n]+\n)*def |\Z)'
    m = re.search(pattern, text)
    if not m:
        fail(f'Não localizei a função {name} em views.py.')
    return text[:m.start()] + code.strip() + '\n\n' + text[m.end():]

def add_call(text, name):
    m = re.search(rf'(?m)^def {name}\(([^)]*)\):\s*$', text)
    if not m:
        fail(f'Não localizei {name} em views.py.')
    if '_atualizar_status_drones_por_reserva()' in text[m.end():m.end()+220]:
        return text
    return text[:m.end()] + '\n    _atualizar_status_drones_por_reserva()' + text[m.end():]

def patch_views():
    p = FILES['views']
    t = p.read_text(encoding='utf-8')
    if 'DroneHistorico' not in t:
        fail('views.py ainda não possui DroneHistorico.')

    if 'from django.utils import timezone' not in t:
        t = t.replace(
            'from django.template.loader import render_to_string',
            'from django.template.loader import render_to_string\nfrom django.utils import timezone'
        )

    if 'def _atualizar_status_drones_por_reserva(' not in t:
        marker = '# =========================================================\n# DASHBOARD'
        if marker not in t:
            fail('Não localizei a seção DASHBOARD em views.py.')
        t = t.replace(marker, HELPER + '\n\n' + marker, 1)

    t = replace_func(t, 'drone_status_atualizar', STATUS_FUNC)

    for fn in ('dashboard', 'drones', 'calendario', 'voos', 'voo_novo', 'alocacao_nova'):
        t = add_call(t, fn)

    p.write_text(t, encoding='utf-8')
    print('views.py atualizado.')

def patch_template():
    p = FILES['template']
    t = p.read_text(encoding='utf-8')
    if 'd.status == "em_campo"' in t:
        print('Template já possui suporte a Em campo.')
        return

    start = '''<td>\n        <form\n            method="post"\n            action="{% url 'drone_status_atualizar' d.pk %}"\n            class="status-inline-form"\n        >'''
    if start not in t:
        fail('Não localizei o seletor de status em lista.html.')

    t = t.replace(start, '''<td>\n        {% if d.status == "em_campo" %}\n            <span class="badge-soft purple">Em campo</span>\n            <div class="text-muted small mt-1">Atualização automática</div>\n        {% else %}\n        <form\n            method="post"\n            action="{% url 'drone_status_atualizar' d.pk %}"\n            class="status-inline-form"\n        >''', 1)

    end = '''            </select>\n        </form>\n    </td>'''
    if end not in t:
        fail('Não localizei o fechamento do seletor de status.')

    t = t.replace(end, '''            </select>\n        </form>\n        {% endif %}\n    </td>''', 1)
    p.write_text(t, encoding='utf-8')
    print('Template atualizado.')

def patch_css():
    p = FILES['css']
    t = p.read_text(encoding='utf-8')
    if '.badge-soft.purple' not in t:
        t += '\n.badge-soft.purple{background:#eee9ff;color:#6847d8;}\n'
        p.write_text(t, encoding='utf-8')
    print('CSS atualizado.')

def create_migration():
    mig = ROOT/'core/migrations'
    nums = []
    for p in mig.glob('[0-9][0-9][0-9][0-9]_*.py'):
        try:
            nums.append(int(p.name[:4]))
        except ValueError:
            pass
    if not nums:
        fail('Nenhuma migration existente encontrada.')

    maxnum = max(nums)
    prev = sorted(mig.glob(f'{maxnum:04d}_*.py'))[-1].stem
    n = maxnum + 1
    path = mig/f'{n:04d}_alter_drone_status_em_campo.py'

    if not path.exists():
        path.write_text(f'''from django.db import migrations, models\n\nclass Migration(migrations.Migration):\n    dependencies = [("core", "{prev}")]\n    operations = [\n        migrations.AlterField(\n            model_name="drone",\n            name="status",\n            field=models.CharField(\n                choices=[\n                    ("ativo","Ativo"),\n                    ("em_campo","Em campo"),\n                    ("manutencao","Em manutenção"),\n                    ("indisponivel","Indisponível"),\n                ],\n                default="ativo",\n                max_length=20,\n            ),\n        ),\n    ]\n''', encoding='utf-8')
        print('Migration criada:', path.name)

def run(*args):
    cmd = [sys.executable, 'manage.py', *args]
    print('>', ' '.join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        fail('Falha em: ' + ' '.join(args))

def main():
    if not (ROOT/'manage.py').exists():
        fail('Coloque este arquivo na raiz do projeto, ao lado de manage.py.')

    print('=== PATCH STATUS EM CAMPO ===')
    backup()
    patch_models()
    patch_views()
    patch_template()
    patch_css()
    create_migration()
    run('check')
    run('migrate')
    run('check')

    print('\nPATCH CONCLUÍDO COM SUCESSO.')
    print('Agora execute: python manage.py runserver')

if __name__ == '__main__':
    main()
