import json
import uuid
from urllib.parse import parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from core.dji_cloud_service import validar_token_mediamtx


def api(caminho, metodo="GET"):
    base = settings.SISMOD_MEDIAMTX_API_URL
    if not base or not settings.SISMOD_MEDIAMTX_AUTH_SECRET:
        raise CommandError("Configure API interna e autenticação MediaMTX antes da reconciliação.")
    with urlopen(Request(base + caminho, method=metodo), timeout=5) as resposta:
        return json.loads(resposta.read(4_000_000))


def reconciliar(aplicar=False):
    removidas = 0
    for tipo in ("webrtcsessions", "rtmpsconns"):
        # Primeiro coletar todos: remover durante paginação desloca os resultados.
        itens = []
        for pagina in range(1000):
            dados = api(f"/v3/{tipo}/list?page={pagina}&itemsPerPage=100")
            itens.extend(dados.get("items", []))
            if pagina + 1 >= dados.get("pageCount", 1):
                break
        else:
            raise CommandError("Limite de paginação atingido; revisão manual necessária.")
        for item in itens:
            if item.get("state") == "idle":
                continue
            token = (parse_qs(item.get("query", "")).get("token") or [""])[0]
            if not validar_token_mediamtx(token, item.get("path", ""), item.get("state", ""), conexao_ativa=True):
                identificador = str(uuid.UUID(item["id"]))
                if aplicar:
                    try:
                        api(f"/v3/{tipo}/kick/{identificador}", "POST")
                    except HTTPError as erro:
                        if erro.code != 404:
                            raise
                removidas += 1
    return removidas


class Command(BaseCommand):
    help = "Revoga conexões WebRTC/RTMPS sem autorização atual. Simulação por padrão."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true")

    def handle(self, *args, **options):
        try:
            total = reconciliar(options["aplicar"])
        except (OSError, ValueError, KeyError) as erro:
            raise CommandError("Falha na reconciliação de vídeo; verifique a API interna.") from erro
        self.stdout.write(f"{total} conexão(ões) {'revogadas' if options['aplicar'] else 'a revogar (simulação)' }.")
