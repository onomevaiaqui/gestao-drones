from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import ImportacaoLog, Piloto, QualificacaoPiloto, Voo
from .qualificacao_forms import QualificacaoPilotoForm
from .views import _base_context, admin_required, usuario_e_admin
from .voo_service import filtrar_voos_realizados


def _duracao_voo_segundos(voo):
    logs = getattr(voo, "logs_concluidos", [])
    duracoes = [log.duracao_segundos for log in logs if log.duracao_segundos is not None]
    if duracoes:
        return sum(duracoes)
    return voo.duracao_minutos * 60


def _formatar_duracao(total_segundos):
    horas, restante = divmod(int(total_segundos), 3600)
    minutos, segundos = divmod(restante, 60)
    return f"{horas}h {minutos:02d}min {segundos:02d}s"


def _perfil_contexto(piloto):
    logs_concluidos = Prefetch(
        "importacoes_log",
        queryset=ImportacaoLog.objects.filter(status="concluida").order_by("inicio_registro"),
        to_attr="logs_concluidos",
    )
    voos = list(
        filtrar_voos_realizados(Voo.objects.select_related("drone", "alocacao_calendario"))
        .prefetch_related(logs_concluidos)
        .filter(piloto=piloto)
    )
    total_segundos = sum(_duracao_voo_segundos(v) for v in voos)
    por_drone = defaultdict(lambda: {"voos": 0, "segundos": 0})
    for voo in voos:
        por_drone[voo.drone.nome]["voos"] += 1
        por_drone[voo.drone.nome]["segundos"] += _duracao_voo_segundos(voo)
    experiencia = [
        {"drone": nome, "voos": dados["voos"], "duracao": _formatar_duracao(dados["segundos"])}
        for nome, dados in sorted(por_drone.items(), key=lambda item: -item[1]["segundos"])
    ]
    ultimo_voo = max((v.data for v in voos), default=None)
    dias_sem_voar = (timezone.localdate() - ultimo_voo).days if ultimo_voo else None
    qualificacoes = list(piloto.qualificacoes.select_related("documento"))
    return {
        "piloto": piloto, "qualificacoes": qualificacoes, "experiencia": experiencia,
        "total_voos_piloto": len(voos), "total_horas_piloto": _formatar_duracao(total_segundos),
        "ultimo_voo": ultimo_voo, "dias_sem_voar": dias_sem_voar,
        "qualificacoes_validas": sum(q.situacao == "valida" for q in qualificacoes),
        "qualificacoes_atencao": sum(q.situacao in ["vencendo", "vencida"] for q in qualificacoes),
    }


@login_required
def meu_perfil_operacional(request):
    if not hasattr(request.user, "piloto"):
        messages.error(request, "Seu usuário não está vinculado a um piloto.")
        return redirect("dashboard")
    return redirect("perfil_operacional", pk=request.user.piloto.pk)


@login_required
def perfil_operacional(request, pk):
    piloto = get_object_or_404(Piloto.objects.select_related("user"), pk=pk)
    if not usuario_e_admin(request.user) and piloto.user_id != request.user.id:
        messages.error(request, "Você só pode consultar o próprio perfil operacional.")
        return redirect("dashboard")
    ctx = _perfil_contexto(piloto)
    ctx.update(_base_context(request))
    return render(request, "qualificacoes/perfil.html", ctx)


@admin_required
def qualificacao_nova(request, piloto_id):
    piloto = get_object_or_404(Piloto, pk=piloto_id)
    form = QualificacaoPilotoForm(request.POST or None, piloto=piloto)
    if form.is_valid():
        qualificacao = form.save(commit=False)
        qualificacao.piloto = piloto
        qualificacao.criado_por = request.user
        qualificacao.save()
        messages.success(request, "Qualificação cadastrada.")
        return redirect("perfil_operacional", pk=piloto.pk)
    ctx = {"form": form, "piloto": piloto, "titulo": "Nova qualificação"}
    ctx.update(_base_context(request))
    return render(request, "qualificacoes/form.html", ctx)


@admin_required
def qualificacao_editar(request, pk):
    qualificacao = get_object_or_404(QualificacaoPiloto.objects.select_related("piloto"), pk=pk)
    form = QualificacaoPilotoForm(request.POST or None, instance=qualificacao, piloto=qualificacao.piloto)
    if form.is_valid():
        form.save()
        messages.success(request, "Qualificação atualizada.")
        return redirect("perfil_operacional", pk=qualificacao.piloto_id)
    ctx = {"form": form, "piloto": qualificacao.piloto, "titulo": "Editar qualificação"}
    ctx.update(_base_context(request))
    return render(request, "qualificacoes/form.html", ctx)
