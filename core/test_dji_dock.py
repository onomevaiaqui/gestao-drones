from django.contrib.auth.models import User
from datetime import date, time
from io import BytesIO
import tempfile
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse

from .dji_dock_service import preparar_missao, processar_mensagem_dock, registrar_intencao_comando
from .dji_operacao_service import enfileirar_preparacao
from .dji_storage_service import armazenar_upload_missao
from .dji_wpml_service import dados_flighttask_prepare, descritor_publico_wpml, gerar_kmz_wpml
from .models import DJIDock, DJIDockArquivo, DJIDockEvento, DJIDockMissao, Drone, Piloto, PlanejamentoVoo


class DJIDockServiceTests(TestCase):
    def setUp(self):
        self.drone = Drone.objects.create(
            nome="Matrice 3D", modelo="M3D", numero_serie="AIRCRAFT-DOCK-1"
        )

    def test_osd_cria_dock_vincula_drone_e_atualiza_posicao(self):
        dock, evento, criado = processar_mensagem_dock(
            "thing/product/DOCK-001/osd",
            {"tid": "evt-1", "data": {"latitude": -25.5, "longitude": -54.5, "sub_device_sn": "AIRCRAFT-DOCK-1"}},
            origem="simulacao",
        )
        self.assertTrue(criado)
        self.assertEqual(dock.numero_serie, "DOCK-001")
        self.assertEqual(dock.drone, self.drone)
        self.assertTrue(dock.online)
        self.assertEqual(evento.nivel, "info")

    def test_mensagem_repetida_e_deduplicada(self):
        payload = {"tid": "repetido", "data": {"rainfall": 1}}
        processar_mensagem_dock("thing/product/DOCK-001/osd", payload)
        _, _, criado = processar_mensagem_dock("thing/product/DOCK-001/osd", payload)
        self.assertFalse(criado)
        self.assertEqual(DJIDockEvento.objects.count(), 1)
        self.assertEqual(DJIDock.objects.get().status, "alerta")

    def test_topologia_vincula_aeronave_e_nao_persiste_segredos(self):
        dock, evento, _ = processar_mensagem_dock(
            "sys/product/DOCK-TOPO/status",
            {"tid": "topo-1", "method": "update_topo", "data": {
                "device_secret": "segredo-da-dock", "nonce": "nonce-secreto",
                "sub_devices": [{"sn": "AIRCRAFT-DOCK-1", "type": 77, "sub_type": 0, "device_secret": "segredo-do-drone"}],
                "payloads": [{"type": 80, "sub_type": 0, "gimbalindex": 0}],
            }},
        )
        self.assertEqual(dock.drone, self.drone)
        self.assertNotIn("segredo", str(dock.ultima_telemetria))
        self.assertNotIn("segredo", str(evento.dados))
        self.assertEqual(evento.dados["device_secret"], "[REMOVIDO]")
        self.assertEqual(dock.aeronave_tipo_dji, 77)
        self.assertEqual(dock.payload_tipo_dji, 80)
        self.assertEqual(dock.payload_posicao_dji, 0)

    def test_intencao_de_comando_fica_bloqueada_e_auditada(self):
        usuario = User.objects.create_superuser("comando_dock", password="teste123")
        dock = DJIDock.objects.create(nome="Dock segura", numero_serie="DOCK-SEGURA")
        comando = registrar_intencao_comando(
            dock, "abrir_tampa", usuario, {"token": "nao-gravar", "motivo": "teste"}
        )
        self.assertEqual(comando.status, "bloqueado")
        self.assertTrue(comando.critico)
        self.assertEqual(comando.parametros["token"], "[REMOVIDO]")

    @override_settings(DJI_DOCK_ENABLED=True, DJI_DOCK_COMMANDS_ENABLED=True)
    def test_resposta_de_servico_confirma_comando_pendente(self):
        usuario = User.objects.create_superuser("resposta_dock", password="teste123")
        dock = DJIDock.objects.create(nome="Dock resposta", numero_serie="DOCK-RESPOSTA")
        comando = registrar_intencao_comando(dock, "atualizar_estado", usuario)
        self.assertEqual(comando.status, "pendente")
        processar_mensagem_dock(
            "thing/product/DOCK-RESPOSTA/services_reply",
            {"tid": str(comando.identificador), "method": "flighttask_prepare", "data": {"result": 0}},
        )
        comando.refresh_from_db()
        self.assertEqual(comando.status, "confirmado")
        self.assertIsNotNone(comando.concluido_em)

    @override_settings(DJI_DOCK_ENABLED=True, DJI_DOCK_COMMANDS_ENABLED=True)
    def test_resposta_de_servico_com_erro_fecha_auditoria(self):
        usuario = User.objects.create_superuser("erro_resposta_dock", password="teste123")
        dock = DJIDock.objects.create(nome="Dock erro", numero_serie="DOCK-ERRO")
        comando = registrar_intencao_comando(dock, "atualizar_estado", usuario)
        processar_mensagem_dock(
            "thing/product/DOCK-ERRO/services_reply",
            {"tid": str(comando.identificador), "method": "flighttask_prepare", "data": {"result": 321}},
        )
        comando.refresh_from_db()
        self.assertEqual(comando.status, "erro")
        self.assertIn("321", comando.mensagem)

    def test_missao_fica_em_validacao_sem_gerar_wpml_executavel(self):
        usuario = User.objects.create_superuser("missao_dock", password="teste123")
        piloto = Piloto.objects.create(user=usuario, nome="Piloto da missão")
        dock = DJIDock.objects.create(nome="Dock missão", numero_serie="DOCK-MISSAO", drone=self.drone)
        planejamento = PlanejamentoVoo.objects.create(
            titulo="Inspeção", piloto=piloto, data=date.today(), data_fim=date.today(),
            hora_inicio=time(8), hora_fim=time(9), altura_maxima_m=80,
            area_geojson={"type": "Polygon", "coordinates": [[[-54.6, -25.4], [-54.5, -25.4], [-54.5, -25.5], [-54.6, -25.4]]]},
            centro_latitude=-25.45, centro_longitude=-54.55, criado_por=usuario,
        )
        missao = preparar_missao(dock, planejamento, usuario)
        self.assertEqual(missao.status, "validacao")
        self.assertTrue(any("WPML" in item["mensagem"] for item in missao.validacoes))

    def test_pacote_wpml_contem_estrutura_kmz_e_xml_validos(self):
        usuario = User.objects.create_superuser("wpml_dock", password="teste123")
        piloto = Piloto.objects.create(user=usuario, nome="Piloto WPML")
        dock = DJIDock.objects.create(
            nome="Dock WPML", numero_serie="DOCK-WPML", drone=self.drone,
            aeronave_tipo_dji=77, aeronave_subtipo_dji=0,
            payload_tipo_dji=80, payload_subtipo_dji=0, payload_posicao_dji=0,
        )
        planejamento = PlanejamentoVoo.objects.create(
            titulo="Rota WPML", piloto=piloto, data=date.today(), data_fim=date.today(),
            hora_inicio=time(8), hora_fim=time(9), altura_maxima_m=70,
            area_geojson={"type": "Polygon", "coordinates": [[[-54.6, -25.4], [-54.5, -25.4], [-54.5, -25.5], [-54.6, -25.4]]]},
            centro_latitude=-25.45, centro_longitude=-54.55, criado_por=usuario,
        )
        missao = preparar_missao(dock, planejamento, usuario)
        pacote = gerar_kmz_wpml(missao)
        with ZipFile(BytesIO(pacote)) as arquivo:
            self.assertEqual(set(arquivo.namelist()), {"wpmz/template.kml", "wpmz/waylines.wpml"})
            ET.fromstring(arquivo.read("wpmz/template.kml"))
            ET.fromstring(arquivo.read("wpmz/waylines.wpml"))

    @override_settings(DJI_CLOUD_PUBLIC_URL="https://sismod.example", DJI_DOCK_WPML_URL_TTL_SECONDS=3600)
    def test_wpml_publico_e_deterministico_assinado_e_sem_sessao(self):
        usuario = User.objects.create_superuser("wpml_publico", password="teste123")
        piloto = Piloto.objects.create(user=usuario, nome="Piloto URL")
        dock = DJIDock.objects.create(
            nome="Dock URL", numero_serie="DOCK-URL", drone=self.drone,
            aeronave_tipo_dji=77, aeronave_subtipo_dji=0,
            payload_tipo_dji=80, payload_subtipo_dji=0, payload_posicao_dji=0,
        )
        planejamento = PlanejamentoVoo.objects.create(
            titulo="Rota URL", piloto=piloto, data=date.today(), data_fim=date.today(),
            hora_inicio=time(8), hora_fim=time(9), altura_maxima_m=70,
            area_geojson={"type": "Polygon", "coordinates": [[[-54.6, -25.4], [-54.5, -25.4], [-54.5, -25.5], [-54.6, -25.4]]]},
            centro_latitude=-25.45, centro_longitude=-54.55, criado_por=usuario,
        )
        missao = preparar_missao(dock, planejamento, usuario)
        self.assertEqual(gerar_kmz_wpml(missao), gerar_kmz_wpml(missao))
        descritor = descritor_publico_wpml(missao)
        caminho = descritor["file"]["url"].removeprefix("https://sismod.example")
        resposta = self.client.get(caminho)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.content, gerar_kmz_wpml(missao))
        self.assertEqual(len(descritor["file"]["fingerprint"]), 32)

    @override_settings(DJI_CLOUD_PUBLIC_URL="")
    def test_descritor_recusa_endereco_sem_https_publico(self):
        usuario = User.objects.create_superuser("wpml_sem_https", password="teste123")
        piloto = Piloto.objects.create(user=usuario, nome="Piloto sem HTTPS")
        dock = DJIDock.objects.create(
            nome="Dock sem HTTPS", numero_serie="DOCK-SEM-HTTPS", drone=self.drone,
            aeronave_tipo_dji=77, payload_tipo_dji=80,
        )
        planejamento = PlanejamentoVoo.objects.create(
            titulo="Rota sem HTTPS", piloto=piloto, data=date.today(), data_fim=date.today(),
            hora_inicio=time(8), hora_fim=time(9), altura_maxima_m=70,
            area_geojson={"type": "Polygon", "coordinates": [[[-54.6, -25.4], [-54.5, -25.4], [-54.5, -25.5], [-54.6, -25.4]]]},
            centro_latitude=-25.45, centro_longitude=-54.55, criado_por=usuario,
        )
        missao = preparar_missao(dock, planejamento, usuario)
        with self.assertRaisesMessage(ValueError, "HTTPS público"):
            descritor_publico_wpml(missao)

    @override_settings(DJI_CLOUD_PUBLIC_URL="https://sismod.example")
    def test_dados_de_preparacao_exigem_confirmacao_e_respeitam_parametros(self):
        usuario = User.objects.create_superuser("parametros_dock", password="teste123")
        piloto = Piloto.objects.create(user=usuario, nome="Piloto Parâmetros")
        dock = DJIDock.objects.create(
            nome="Dock parâmetros", numero_serie="DOCK-PARAMETROS", drone=self.drone,
            aeronave_tipo_dji=77, payload_tipo_dji=80,
        )
        planejamento = PlanejamentoVoo.objects.create(
            titulo="Rota parâmetros", piloto=piloto, data=date.today(), data_fim=date.today(),
            hora_inicio=time(8), hora_fim=time(9), altura_maxima_m=70,
            area_geojson={"type": "Polygon", "coordinates": [[[-54.6, -25.4], [-54.5, -25.4], [-54.5, -25.5], [-54.6, -25.4]]]},
            centro_latitude=-25.45, centro_longitude=-54.55, criado_por=usuario,
        )
        missao = preparar_missao(dock, planejamento, usuario)
        with self.assertRaisesMessage(ValueError, "Confirme os parâmetros"):
            dados_flighttask_prepare(missao)
        missao.parametros_confirmados = True
        missao.altura_retorno_m = 130
        missao.bateria_minima_percent = 65
        missao.armazenamento_minimo_mb = 2048
        missao.interromper_na_perda_sinal = True
        dados = dados_flighttask_prepare(missao)
        self.assertEqual(dados["rth_altitude"], 130)
        self.assertEqual(dados["ready_conditions"]["battery_capacity"], 65)
        self.assertEqual(dados["executable_conditions"]["storage_capacity"], 2048)
        self.assertEqual(dados["exit_wayline_when_rc_lost"], 1)
        self.assertEqual(dados["out_of_control_action"], 0)
        self.assertEqual(len(dados["file"]["fingerprint"]), 32)

    @override_settings(DJI_CLOUD_PUBLIC_URL="https://sismod.example")
    def test_fila_monta_previa_sem_publicar(self):
        usuario = User.objects.create_superuser("fila_dock", password="teste123")
        piloto = Piloto.objects.create(user=usuario, nome="Piloto Fila")
        dock = DJIDock.objects.create(
            nome="Dock fila", numero_serie="DOCK-FILA", drone=self.drone,
            aeronave_tipo_dji=77, payload_tipo_dji=80,
        )
        planejamento = PlanejamentoVoo.objects.create(
            titulo="Rota fila", piloto=piloto, data=date.today(), data_fim=date.today(),
            hora_inicio=time(8), hora_fim=time(9), altura_maxima_m=70, status_meteorologico="favoravel",
            area_geojson={"type": "Polygon", "coordinates": [[[-54.6, -25.4], [-54.5, -25.4], [-54.5, -25.5], [-54.6, -25.4]]]},
            centro_latitude=-25.45, centro_longitude=-54.55, criado_por=usuario,
        )
        missao = preparar_missao(dock, planejamento, usuario)
        missao.parametros_confirmados = True
        missao.save()
        comando, validacoes = enfileirar_preparacao(missao, usuario)
        self.assertFalse([item for item in validacoes if item["nivel"] == "bloqueio"])
        self.assertEqual(comando.status, "bloqueado")
        self.assertEqual(comando.mensagem_mqtt["method"], "flighttask_prepare")
        self.assertIsNotNone(comando.expira_em)

    def test_armazenamento_local_calcula_checksum(self):
        usuario = User.objects.create_superuser("storage_dock", password="teste123")
        piloto = Piloto.objects.create(user=usuario, nome="Piloto Storage")
        dock = DJIDock.objects.create(nome="Dock storage", numero_serie="DOCK-STORAGE", drone=self.drone)
        planejamento = PlanejamentoVoo.objects.create(
            titulo="Rota storage", piloto=piloto, data=date.today(), data_fim=date.today(),
            hora_inicio=time(8), hora_fim=time(9), altura_maxima_m=70,
            area_geojson={"type": "Polygon", "coordinates": [[[-54.6, -25.4], [-54.5, -25.4], [-54.5, -25.5], [-54.6, -25.4]]]},
            centro_latitude=-25.45, centro_longitude=-54.55, criado_por=usuario,
        )
        missao = preparar_missao(dock, planejamento, usuario)
        with tempfile.TemporaryDirectory() as pasta, override_settings(MEDIA_ROOT=pasta, SISMOD_MEDIA_STORAGE="local"):
            item = armazenar_upload_missao(missao, SimpleUploadedFile("foto.jpg", b"imagem-teste"))
            self.assertEqual(item.status, "concluido")
            self.assertEqual(item.tamanho_bytes, 12)
            self.assertEqual(len(item.checksum), 64)
            item.arquivo.delete(save=False)

    @override_settings(DJI_DOCK_SIMULATOR_ENABLED=True)
    def test_simulador_cria_cenario_de_falha(self):
        call_command("simular_dji_dock", serial="DOCK-CENARIO", cenario="falha")
        dock = DJIDock.objects.get(numero_serie="DOCK-CENARIO")
        self.assertEqual(dock.status, "alerta")
        self.assertEqual(dock.eventos.first().nivel, "critico")

    def test_retorno_dji_atualiza_progresso_e_conclusao_da_missao(self):
        usuario = User.objects.create_superuser("retorno_dock", password="teste123")
        piloto = Piloto.objects.create(user=usuario, nome="Piloto Retorno")
        dock = DJIDock.objects.create(nome="Dock retorno", numero_serie="DOCK-RETORNO", drone=self.drone)
        planejamento = PlanejamentoVoo.objects.create(
            titulo="Missão retorno", piloto=piloto, data=date.today(), data_fim=date.today(),
            hora_inicio=time(8), hora_fim=time(9), altura_maxima_m=60,
            area_geojson={"type": "Polygon", "coordinates": [[[-54.6, -25.4], [-54.5, -25.4], [-54.5, -25.5], [-54.6, -25.4]]]},
            centro_latitude=-25.45, centro_longitude=-54.55, criado_por=usuario,
        )
        missao = preparar_missao(dock, planejamento, usuario)
        processar_mensagem_dock(
            "thing/product/DOCK-RETORNO/events",
            {"tid": "progress-1", "method": "flighttask_progress", "data": {"output": {
                "flight_id": str(missao.identificador), "status": "in_progress",
                "progress": {"percent": 42, "current_step": 2},
                "ext": {"current_waypoint_index": 5, "media_count": 3},
            }}},
        )
        missao.refresh_from_db()
        self.assertEqual(missao.status, "executando")
        self.assertEqual(missao.progresso_percentual, 42)
        self.assertEqual(missao.waypoint_atual, 5)
        self.assertEqual(missao.quantidade_midias, 3)
        self.assertIsNotNone(missao.iniciada_em)

        processar_mensagem_dock(
            "thing/product/DOCK-RETORNO/events",
            {"tid": "progress-2", "method": "flighttask_progress", "data": {"output": {
                "flight_id": str(missao.identificador), "status": "ok", "progress": {"percent": 100},
            }}},
        )
        missao.refresh_from_db()
        self.assertEqual(missao.status, "concluida")
        self.assertEqual(missao.progresso_percentual, 100)
        self.assertIsNotNone(missao.concluida_em)

    def test_callback_de_arquivo_cataloga_metadados_sem_persistir_segredo(self):
        usuario = User.objects.create_superuser("arquivo_dock", password="teste123")
        piloto = Piloto.objects.create(user=usuario, nome="Piloto Arquivo")
        dock = DJIDock.objects.create(nome="Dock arquivo", numero_serie="DOCK-ARQUIVO", drone=self.drone)
        planejamento = PlanejamentoVoo.objects.create(
            titulo="Missão arquivo", piloto=piloto, data=date.today(), data_fim=date.today(),
            hora_inicio=time(8), hora_fim=time(9), altura_maxima_m=60,
            area_geojson={"type": "Polygon", "coordinates": [[[-54.6, -25.4], [-54.5, -25.4], [-54.5, -25.5], [-54.6, -25.4]]]},
            centro_latitude=-25.45, centro_longitude=-54.55, criado_por=usuario,
        )
        missao = preparar_missao(dock, planejamento, usuario)
        processar_mensagem_dock(
            "thing/product/DOCK-ARQUIVO/events",
            {"tid": "file-1", "method": "file_upload_callback", "data": {"file": {
                "object_key": "missions/photo-001.jpg", "name": "photo-001.jpg", "path": "remote/path",
                "ext": {"flight_id": str(missao.identificador), "is_original": True, "token": "secreto"},
                "metadata": {"relative_altitude": 42.5, "shoot_position": {"lat": -25.4, "lng": -54.5}},
            }}},
        )
        arquivo = DJIDockArquivo.objects.get(missao=missao)
        self.assertEqual(arquivo.nome, "photo-001.jpg")
        self.assertEqual(arquivo.extensao, "jpg")
        self.assertTrue(arquivo.original)
        self.assertEqual(arquivo.metadados["ext"]["token"], "[REMOVIDO]")
        self.assertEqual(arquivo.metadados["metadata"]["relative_altitude"], 42.5)
        missao.refresh_from_db()
        self.assertEqual(missao.quantidade_midias, 1)


@override_settings(DJI_DOCK_SIMULATOR_ENABLED=True)
class DJIDockViewsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin_dock", password="teste123")

    def test_admin_pode_simular_e_visualizar(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(
            reverse("dji_dock_simular"),
            data='{"topico":"thing/product/DOCK-SIM/osd","data":{"latitude":-25.4,"longitude":-54.6}}',
            content_type="application/json",
        )
        self.assertEqual(resposta.status_code, 200)
        lista = self.client.get(reverse("dji_docks"))
        self.assertContains(lista, "DOCK-SIM")

    def test_admin_confirma_parametros_sem_enviar_comando(self):
        self.client.force_login(self.admin)
        piloto = Piloto.objects.create(user=self.admin, nome="Administrador Dock")
        drone = Drone.objects.create(nome="Matrice 3D", modelo="M3D", numero_serie="AIR-PARAM")
        dock = DJIDock.objects.create(nome="Dock revisão", numero_serie="DOCK-REVISAO", drone=drone)
        planejamento = PlanejamentoVoo.objects.create(
            titulo="Revisão operacional", piloto=piloto, data=date.today(), data_fim=date.today(),
            hora_inicio=time(8), hora_fim=time(9), altura_maxima_m=70,
            area_geojson={"type": "Polygon", "coordinates": [[[-54.6, -25.4], [-54.5, -25.4], [-54.5, -25.5], [-54.6, -25.4]]]},
            centro_latitude=-25.45, centro_longitude=-54.55, criado_por=self.admin,
        )
        missao = preparar_missao(dock, planejamento, self.admin)
        resposta = self.client.post(reverse("dji_dock_missao_parametros", args=[missao.pk]), {
            "altura_retorno_m": 140, "bateria_minima_percent": 70,
            "armazenamento_minimo_mb": 1500, "interromper_na_perda_sinal": "on",
        })
        self.assertRedirects(resposta, reverse("dji_dock_detalhe", args=[dock.pk]))
        missao.refresh_from_db()
        self.assertTrue(missao.parametros_confirmados)
        self.assertEqual(missao.altura_retorno_m, 140)
        self.assertEqual(missao.parametros_confirmados_por, self.admin)
        self.assertFalse(dock.comandos.exists())

    def test_usuario_comum_nao_acessa_monitoramento(self):
        usuario = User.objects.create_user("usuario_dock", password="teste123")
        self.client.force_login(usuario)
        resposta = self.client.get(reverse("dji_docks"))
        self.assertRedirects(resposta, reverse("dashboard"))

    @override_settings(DJI_DOCK_SIMULATOR_ENABLED=False)
    def test_simulador_desativado_recusa_ingestao(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(reverse("dji_dock_simular"), data="{}", content_type="application/json")
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(DJIDock.objects.exists())
