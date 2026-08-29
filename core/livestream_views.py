from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from .dji_cloud_service import diagnostico_open_platforms, endereco_reproducao
from .models import PlanejamentoVoo, TransmissaoAoVivo
from .permissoes import usuario_e_admin, usuario_e_coordenador, usuario_tem_visao_global
from .views import _base_context


@login_required
def transmissoes_ao_vivo(request):
    aba = request.GET.get("aba", "ao-vivo")
    if aba not in {"ao-vivo", "agendadas", "historico", "configuracoes"}:
        aba = "ao-vivo"
    if aba == "configuracoes" and not usuario_e_admin(request.user):
        aba = "ao-vivo"

    sessoes = TransmissaoAoVivo.objects.select_related("piloto", "drone", "alocacao", "planejamento")
    planejamentos = PlanejamentoVoo.objects.filter(livestream_planejada=True).select_related("piloto")
    if not usuario_tem_visao_global(request.user):
        sessoes = sessoes.filter(piloto__user=request.user)
        planejamentos = planejamentos.filter(piloto__user=request.user)

    agora = timezone.localtime()
    agendadas = planejamentos.filter(
        Q(data_fim__gt=agora.date()) |
        Q(data_fim=agora.date(), hora_fim__gte=agora.time()) |
        Q(data_fim__isnull=True, data__gt=agora.date()) |
        Q(data_fim__isnull=True, data=agora.date(), hora_fim__gte=agora.time())
    ).order_by("data", "hora_inicio")

    ativas = []
    if settings.DJI_LIVESTREAM_ENABLED:
        ativas = [
            {"sessao": item, "playback_url": endereco_reproducao(item)}
            for item in sessoes.filter(status="ao_vivo").order_by("-iniciada_em")
            if item.planejamento_id is None or item.planejamento.livestream_acesso == "coordenacao" or usuario_e_admin(request.user)
        ]

    diagnostico = diagnostico_open_platforms()
    ctx = {
        "aba": aba,
        "transmissoes_ativas": ativas,
        "agendamentos_livestream": agendadas,
        "historico_livestream": sessoes.exclude(status__in=["preparada", "ao_vivo"]).order_by("-criada_em")[:100],
        "diagnostico_livestream": diagnostico,
        "livestream_pronta": diagnostico["livestream"]["pronto"],
        "pode_iniciar_livestream": not usuario_e_coordenador(request.user),
    }
    ctx.update(_base_context(request))
    return render(request, "livestream/lista.html", ctx)
