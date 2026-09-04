import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from core.models import DJIDock, DJIDockAcesso, DJIDockCanalVideo, TransmissaoAoVivo


CHAVE_DEMO = uuid.UUID("00000000-0000-4000-8000-000000000001")


class Command(BaseCommand):
    help = "Vincula o vídeo-padrão local a um canal da estação, somente em desenvolvimento."

    def add_arguments(self, parser):
        parser.add_argument("--canal", type=int)
        parser.add_argument("--usuario", required=True)
        parser.add_argument("--criar-cenario", action="store_true")

    def handle(self, *args, **opcoes):
        if not settings.DEBUG or not settings.DJI_LIVESTREAM_ALLOW_INSECURE_LOCAL:
            raise CommandError("A demonstração exige DEBUG e DJI_LIVESTREAM_ALLOW_INSECURE_LOCAL=true.")
        usuario = User.objects.select_related("piloto").filter(username=opcoes["usuario"], is_active=True).first()
        if not usuario or not hasattr(usuario, "piloto"):
            raise CommandError("Usuário ativo com perfil de piloto não encontrado.")
        canal = DJIDockCanalVideo.objects.select_related("dock__drone").filter(pk=opcoes["canal"], disponivel=True).first()
        if not canal and opcoes["criar_cenario"]:
            dock, _ = DJIDock.objects.get_or_create(
                numero_serie="DOCK-LIVESTREAM-DEMO",
                defaults={"nome": "Estação de demonstração local", "online": True, "status": "online"},
            )
            if not dock.online:
                dock.online, dock.status = True, "online"
                dock.save(update_fields=["online", "status"])
            canal, _ = DJIDockCanalVideo.objects.get_or_create(
                dock=dock, video_id="AIRCRAFT-DEMO/0-0-0/normal-0",
                defaults={
                    "origem": "aeronave", "dispositivo_serial": "AIRCRAFT-DEMO",
                    "camera_indice": "0-0-0", "video_indice": "normal-0",
                    "lente": "normal", "disponivel": True,
                },
            )
            DJIDockAcesso.objects.update_or_create(
                dock=dock, usuario=usuario,
                defaults={"ativo": True, "pode_operar": True, "concedido_por": usuario if usuario.is_superuser else None},
            )
        if not canal:
            raise CommandError("Canal disponível não encontrado. Informe --canal ou use --criar-cenario.")
        transmissao, _ = TransmissaoAoVivo.objects.update_or_create(
            chave_stream=CHAVE_DEMO,
            defaults={
                "piloto": usuario.piloto,
                "drone": canal.dock.drone,
                "origem": "avulsa",
                "aeronave_serial": canal.dispositivo_serial if canal.origem == "aeronave" else "",
                "status": "ao_vivo",
                "mensagem_erro": "",
            },
        )
        canal.transmissao_atual = transmissao
        canal.status = "simulado"
        canal.save(update_fields=["transmissao_atual", "status", "atualizado_em"])
        self.stdout.write(self.style.SUCCESS(f"Demo vinculada ao canal {canal.pk}. Abra o cockpit da estação."))
