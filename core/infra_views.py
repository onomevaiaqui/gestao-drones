import json
from urllib.parse import parse_qs

from django.conf import settings
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .dji_cloud_service import validar_token_mediamtx


def _token_da_consulta(dados):
    if dados.get("token"):
        return dados["token"]
    consulta = (dados.get("query") or "").lstrip("?")
    return (parse_qs(consulta).get("token") or [""])[0]


@csrf_exempt
@require_POST
def mediamtx_auth(request):
    try:
        dados = json.loads(request.body or b"{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return HttpResponse(status=400)
    permitido = validar_token_mediamtx(
        _token_da_consulta(dados), dados.get("path", ""), dados.get("action", "")
    )
    return HttpResponse(status=204 if permitido else 401)


@require_GET
def healthcheck(request):
    token = settings.SISMOD_HEALTHCHECK_TOKEN
    if token and request.headers.get("X-SISMOD-Health") != token:
        return HttpResponse(status=403)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "erro", "database": False}, status=503)
    return JsonResponse({"status": "ok", "database": True})
