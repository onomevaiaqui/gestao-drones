from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.http import HttpResponse
from django.core.cache import cache
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import hashlib
from django.utils.text import slugify
from xml.sax.saxutils import escape

from .models import PlanejamentoVoo, Piloto
from .planejamento_forms import PlanejamentoVooForm
from .planejamento_service import consultar_previsao
from .planejamento_aeronautico_service import consultar_condicionantes_aeronauticas, camadas_aeronauticas_bbox
from .planejamento_sisclaten import classificar_sisclaten
from .views import _base_context, usuario_e_admin, usuario_e_coordenador, usuario_tem_visao_global


def _planejamentos_visiveis(request):
    qs = PlanejamentoVoo.objects.select_related("piloto", "criado_por")
    if usuario_tem_visao_global(request.user):
        return qs
    return qs.filter(piloto__user=request.user)


def _planejamentos_editaveis(request):
    qs = PlanejamentoVoo.objects.select_related("piloto", "criado_por")
    if usuario_e_admin(request.user):
        return qs
    if usuario_e_coordenador(request.user):
        return qs.none()
    return qs.filter(piloto__user=request.user)


def _atualizar_previsao(obj):
    resumo_atual = obj.resumo_meteorologico or {}
    try:
        resumo = consultar_previsao(obj)
    except Exception as erro:
        obj.status_meteorologico = "indisponivel"
        obj.resumo_meteorologico = {"erro": str(erro), "aeronautica": resumo_atual.get("aeronautica", {}), "sisclaten": classificar_sisclaten(obj)}
        obj.previsao_consultada_em = timezone.now()
        obj.save(update_fields=["status_meteorologico", "resumo_meteorologico", "previsao_consultada_em"])
        return False, str(erro)
    try:
        resumo["aeronautica"] = consultar_condicionantes_aeronauticas(obj)
    except Exception as erro:
        resumo["aeronautica"] = {"status":"indisponivel", "erro":str(erro), "itens":[], "geojson":{"type":"FeatureCollection", "features":[]}}
    resumo["sisclaten"] = classificar_sisclaten(obj)
    obj.status_meteorologico = resumo["status"]
    obj.resumo_meteorologico = resumo
    obj.previsao_consultada_em = timezone.now()
    obj.save(update_fields=["status_meteorologico", "resumo_meteorologico", "previsao_consultada_em"])
    return True, ""


@login_required
def planejamentos(request):
    ctx = {"planejamentos": _planejamentos_visiveis(request)}
    ctx.update(_base_context(request))
    return render(request, "planejamentos/lista.html", ctx)


def _form_planejamento(request, obj=None):
    eh_admin = usuario_e_admin(request.user)
    piloto = None
    if not eh_admin:
        piloto = getattr(request.user, "piloto", None)
        if not piloto:
            messages.error(request, "Seu usuário não está vinculado a um piloto.")
            return redirect("dashboard")
        if obj and obj.piloto_id != piloto.pk:
            messages.error(request, "Você só pode alterar seus próprios planejamentos.")
            return redirect("planejamentos")
    form = PlanejamentoVooForm(request.POST or None, request.FILES or None, instance=obj)
    if piloto:
        form.fields["piloto"].queryset = Piloto.objects.filter(pk=piloto.pk)
        form.fields["piloto"].initial = piloto
        form.fields["piloto"].disabled = True
    if form.is_valid():
        planejamento = form.save(commit=False)
        if piloto:
            planejamento.piloto = piloto
        if not planejamento.pk:
            planejamento.criado_por = request.user
        planejamento.save()
        sucesso, erro = _atualizar_previsao(planejamento)
        if sucesso:
            messages.success(request, "Planejamento salvo e previsão meteorológica atualizada.")
        else:
            messages.warning(request, f"Planejamento salvo, mas a previsão não pôde ser consultada: {erro}")
        return redirect("planejamento_detalhe", pk=planejamento.pk)
    ctx = {
        "form": form,
        "titulo": "Editar planejamento" if obj else "Novo planejamento de voo",
        "geometria_inicial": obj.area_geojson if obj else None,
    }
    ctx.update(_base_context(request))
    return render(request, "planejamentos/form.html", ctx)


@login_required
def planejamento_novo(request):
    if usuario_e_coordenador(request.user):
        messages.error(request, "O perfil de coordenador possui acesso somente para consulta.")
        return redirect("planejamentos")
    return _form_planejamento(request)


@login_required
def planejamento_editar(request, pk):
    obj = get_object_or_404(_planejamentos_editaveis(request), pk=pk)
    return _form_planejamento(request, obj)


@login_required
def planejamento_detalhe(request, pk):
    obj = get_object_or_404(_planejamentos_visiveis(request), pk=pk)
    meteo = obj.resumo_meteorologico or {}
    sisclaten = meteo.get("sisclaten") or classificar_sisclaten(obj)
    ctx = {"planejamento": obj, "meteo": meteo, "aeronautica": meteo.get("aeronautica", {}), "sisclaten": sisclaten}
    ctx.update(_base_context(request))
    return render(request, "planejamentos/detalhe.html", ctx)


@login_required
@require_POST
def planejamento_atualizar_previsao(request, pk):
    obj = get_object_or_404(_planejamentos_editaveis(request), pk=pk)
    sucesso, erro = _atualizar_previsao(obj)
    if sucesso:
        messages.success(request, "Previsão meteorológica atualizada.")
    else:
        messages.error(request, f"Não foi possível atualizar a previsão: {erro}")
    return redirect("planejamento_detalhe", pk=obj.pk)


@login_required
def planejamento_buscar_local(request):
    termo = request.GET.get("q", "").strip()
    if len(termo) < 3:
        return JsonResponse({"erro":"Informe ao menos três caracteres."}, status=400)
    chave = "geocode:" + hashlib.sha256(termo.casefold().encode()).hexdigest()
    dados = cache.get(chave)
    if dados is None:
        params = urlencode({"q":termo, "format":"jsonv2", "limit":1, "countrycodes":"br"})
        req = Request("https://nominatim.openstreetmap.org/search?" + params,
                      headers={"User-Agent":"GestaoDrones/1.0 (planejamento de voo)"})
        try:
            with urlopen(req, timeout=12) as resposta: resultado = json.loads(resposta.read().decode())
            dados = {"latitude":float(resultado[0]["lat"]), "longitude":float(resultado[0]["lon"]),
                     "nome":resultado[0]["display_name"]} if resultado else {}
            cache.set(chave, dados, 86400)
        except Exception:
            return JsonResponse({"erro":"Serviço de localização temporariamente indisponível."}, status=503)
    if not dados: return JsonResponse({"erro":"Local não encontrado."}, status=404)
    return JsonResponse(dados)


@login_required
def planejamento_camadas_aeronauticas(request):
    try:
        bbox = tuple(float(request.GET[n]) for n in ("oeste","sul","leste","norte"))
        if not (-180 <= bbox[0] < bbox[2] <= 180 and -90 <= bbox[1] < bbox[3] <= 90): raise ValueError
        if bbox[2]-bbox[0] > 2 or bbox[3]-bbox[1] > 2: raise ValueError
        return JsonResponse(camadas_aeronauticas_bbox(bbox))
    except ValueError:
        return JsonResponse({"erro":"Área de consulta inválida."}, status=400)
    except Exception:
        return JsonResponse({"erro":"Camadas do AISWEB temporariamente indisponíveis."}, status=503)


@login_required
def planejamento_baixar_kml(request, pk):
    obj = get_object_or_404(_planejamentos_visiveis(request), pk=pk)
    coordenadas = " ".join(
        f"{float(lon):.7f},{float(lat):.7f},0"
        for lon, lat in obj.area_geojson["coordinates"][0]
    )
    conteudo = f'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<name>{escape(obj.titulo)}</name><Placemark><name>{escape(obj.titulo)}</name>
<description>{escape(obj.local or "Área planejada")}</description>
<Polygon><outerBoundaryIs><LinearRing><coordinates>{coordenadas}</coordinates></LinearRing></outerBoundaryIs></Polygon>
</Placemark></Document></kml>'''
    resposta = HttpResponse(conteudo, content_type="application/vnd.google-earth.kml+xml; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="{slugify(obj.titulo) or "planejamento"}.kml"'
    return resposta
