from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent
VIEWS = ROOT / "core" / "views.py"

def fail(msg):
    print("\nERRO:", msg)
    sys.exit(1)

def backup():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ROOT / f"backup_corrigir_dashboard_{stamp}"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(VIEWS, dest / "views.py")
    print("Backup criado em:", dest)

DASHBOARD_SECTION = r'''
# =========================================================
# DASHBOARD
# =========================================================

@login_required
def dashboard(request):
    _atualizar_reservas_vencidas()

    if "_atualizar_status_drones_por_reserva" in globals():
        _atualizar_status_drones_por_reserva()

    primeiro = _redirecionar_primeiro_acesso(request)
    if primeiro:
        return primeiro

    voos_qs = Voo.objects.select_related("piloto", "drone")

    inicio = request.GET.get("inicio")
    fim = request.GET.get("fim")

    if inicio:
        voos_qs = voos_qs.filter(data__gte=inicio)

    if fim:
        voos_qs = voos_qs.filter(data__lte=fim)

    total_voos = voos_qs.count()
    total_minutos = sum(voo.duracao_minutos for voo in voos_qs)
    horas = total_minutos // 60
    minutos = total_minutos % 60

    distancia_total_m = sum(
        float(voo.distancia_m or 0)
        for voo in voos_qs
    )

    media_minutos = round(total_minutos / total_voos) if total_voos else 0

    pilotos_data = []
    for piloto in Piloto.objects.filter(ativo=True):
        minutos_piloto = sum(
            voo.duracao_minutos
            for voo in voos_qs
            if voo.piloto_id == piloto.id
        )
        if minutos_piloto > 0:
            pilotos_data.append({
                "nome": piloto.nome,
                "horas": round(minutos_piloto / 60, 2),
            })

    drones_data = []
    for drone in Drone.objects.all():
        minutos_drone = sum(
            voo.duracao_minutos
            for voo in voos_qs
            if voo.drone_id == drone.id
        )
        if minutos_drone > 0:
            drones_data.append({
                "nome": drone.nome,
                "horas": round(minutos_drone / 60, 2),
            })

    finalidade_map = defaultdict(int)
    for voo in voos_qs:
        finalidade_map[voo.get_finalidade_display()] += voo.duracao_minutos

    finalidades_data = [
        {
            "nome": nome,
            "horas": round(minutos_finalidade / 60, 2),
        }
        for nome, minutos_finalidade in finalidade_map.items()
    ]

    dias = defaultdict(int)
    for voo in voos_qs:
        dias[voo.data.isoformat()] += voo.duracao_minutos

    tempo_data = [
        {
            "data": data_voo,
            "horas": round(minutos_dia / 60, 2),
        }
        for data_voo, minutos_dia in sorted(dias.items())
    ]

    status_drones = {
        "ativos": Drone.objects.filter(status="ativo").count(),
        "em_campo": Drone.objects.filter(status="em_campo").count(),
        "manutencao": Drone.objects.filter(status="manutencao").count(),
        "indisponiveis": Drone.objects.filter(status="indisponivel").count(),
    }

    agora_dashboard = timezone.localtime()

    reservas_hoje = Alocacao.objects.filter(
        data=agora_dashboard.date(),
        status="reservado",
    ).count()

    proximas_reservas = (
        Alocacao.objects
        .select_related("piloto", "drone")
        .filter(
            status="reservado",
            data__gte=agora_dashboard.date(),
        )
        .order_by("data", "hora_inicio")[:8]
    )

    ctx = {
        "total_voos": total_voos,
        "total_horas": f"{horas}h {minutos:02d}min",
        "distancia_total": round(distancia_total_m / 1000, 2),
        "media_minutos": media_minutos,
        "reservas_hoje": reservas_hoje,
        "drones_em_campo": status_drones["em_campo"],
        "drones_em_manutencao": status_drones["manutencao"],
        "pilotos_data": pilotos_data,
        "drones_data": drones_data,
        "finalidades_data": finalidades_data,
        "tempo_data": tempo_data,
        "status_drones": status_drones,
        "proximas_reservas": proximas_reservas,
        "ultimos_voos": voos_qs[:6],
        "inicio": inicio or "",
        "fim": fim or "",
    }

    ctx.update(_base_context(request))

    return render(
        request,
        "dashboard.html",
        ctx
    )
'''

def patch_views():
    if not VIEWS.exists():
        fail("core/views.py não foi encontrado.")

    text = VIEWS.read_text(encoding="utf-8")

    start_marker = (
        "# =========================================================\n"
        "# DASHBOARD\n"
        "# ========================================================="
    )

    end_marker = (
        "# =========================================================\n"
        "# VOOS\n"
        "# ========================================================="
    )

    start = text.find(start_marker)
    end = text.find(end_marker)

    if start == -1:
        fail("Não encontrei a seção DASHBOARD em core/views.py.")

    if end == -1 or end <= start:
        fail("Não encontrei a seção VOOS após o dashboard.")

    novo = (
        text[:start]
        + DASHBOARD_SECTION.strip()
        + "\n\n\n"
        + text[end:]
    )

    VIEWS.write_text(novo, encoding="utf-8")
    print("Função dashboard substituída com sucesso.")

def run_check():
    cmd = [sys.executable, "manage.py", "check"]
    print(">", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)

    if result.returncode != 0:
        fail("O Django ainda encontrou um erro. O backup foi preservado.")

def main():
    if not (ROOT / "manage.py").exists():
        fail("Copie este patch para a raiz do projeto, ao lado de manage.py.")

    print("=== CORREÇÃO DO DASHBOARD ===")
    backup()
    patch_views()
    run_check()

    print("\nCORREÇÃO CONCLUÍDA COM SUCESSO.")
    print("Agora execute:")
    print("python manage.py runserver")

if __name__ == "__main__":
    main()
