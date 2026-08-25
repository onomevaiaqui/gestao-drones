from datetime import date, time, timedelta
import tempfile

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .alerta_service import gerar_alertas, resumo_alertas
from .models import (
    Alocacao, AvaliacaoRisco, Bateria, ChecklistPreVoo, Componente, Documento, Drone, ExecucaoInspecao,
    DroneHistorico, ImportacaoLog, Incidente, Manutencao, Piloto, PlanoInspecao, PontoTelemetria,
    MovimentacaoComponente, QualificacaoPiloto, RegistroPosVoo, SolicitacaoVoo, Voo,
)
from .telemetria_service import processar_importacao


class SelecaoPerfilAcessoTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="admin_duplo", password="teste123")
        self.piloto_admin = Piloto.objects.create(
            user=self.admin, nome="Administrador Piloto", perfil="administrador",
            primeiro_acesso=False,
        )
        self.outro_user = User.objects.create_user(username="piloto_outro", password="teste123")
        self.outro_piloto = Piloto.objects.create(
            user=self.outro_user, nome="Piloto de Outro Usuário", primeiro_acesso=False,
        )
        self.drone = Drone.objects.create(nome="Drone Perfil Duplo", modelo="Modelo")
        self.voo_admin = Voo.objects.create(
            data=timezone.localdate(), piloto=self.piloto_admin, drone=self.drone,
            finalidade="outro", local="Área própria", hora_inicio=time(9), hora_fim=time(10),
            criado_por=self.admin,
        )
        self.voo_outro = Voo.objects.create(
            data=timezone.localdate(), piloto=self.outro_piloto, drone=self.drone,
            finalidade="outro", local="Área de outro usuário", hora_inicio=time(11), hora_fim=time(12),
            criado_por=self.outro_user,
        )
        self.reserva_outro = Alocacao.objects.create(
            data=timezone.localdate(), hora_inicio=time(13), hora_fim=time(14),
            piloto=self.outro_piloto, drone=self.drone, finalidade="Reserva de outro usuário",
            status="reservado", criado_por=self.outro_user,
        )

    def test_login_admin_exige_escolha_de_perfil(self):
        resposta = self.client.post(reverse("login"), {
            "username": "admin_duplo", "password": "teste123",
        })
        self.assertRedirects(resposta, reverse("selecionar_modo_acesso"))
        self.assertContains(self.client.get(reverse("selecionar_modo_acesso")), "Entrar como administrador")

    def test_modo_usuario_limita_dados_e_permissoes(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(reverse("selecionar_modo_acesso"), {"modo": "usuario"})
        self.assertRedirects(resposta, reverse("dashboard"))
        lista = self.client.get(reverse("voos"))
        self.assertContains(lista, "Administrador Piloto")
        self.assertNotContains(lista, "Piloto de Outro Usuário")
        self.assertNotContains(lista, "Pilotos / Usuários")
        self.assertRedirects(self.client.get(reverse("pilotos")), reverse("dashboard"))
        self.assertRedirects(self.client.get("/admin/"), reverse("dashboard"))
        painel = self.client.get(reverse("dashboard"))
        self.assertEqual(painel.context["reservas_hoje"], 0)

    def test_modo_admin_mantem_visao_global(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("selecionar_modo_acesso"), {"modo": "admin"})
        lista = self.client.get(reverse("voos"))
        self.assertContains(lista, "Administrador Piloto")
        self.assertContains(lista, "Piloto de Outro Usuário")
        self.assertEqual(self.client.get(reverse("pilotos")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard")).context["reservas_hoje"], 1)


class BateriaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="piloto_teste", password="teste123")
        self.drone = Drone.objects.create(nome="Drone teste", modelo="Modelo teste")
        self.bateria = Bateria.objects.create(
            codigo="BAT-001",
            numero_serie="SERIE-001",
            drone=self.drone,
            ciclos_informados=12,
            saude_percentual=91,
        )

    def test_bateria_calcula_ciclos_iniciais(self):
        self.assertEqual(self.bateria.ciclos_totais, 12)
        self.assertEqual(self.bateria.voos_registrados, 0)

    def test_lista_exige_login(self):
        resposta = self.client.get(reverse("baterias"))
        self.assertEqual(resposta.status_code, 302)

    def test_usuario_autenticado_visualiza_inventario(self):
        self.client.force_login(self.user)
        resposta = self.client.get(reverse("baterias"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "BAT-001")


class PlanoInspecaoTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="admin_teste", password="teste123")
        self.drone = Drone.objects.create(nome="Drone inspeção", modelo="Modelo teste")
        self.plano = PlanoInspecao.objects.create(
            nome="Inspeção a cada 10 dias",
            drone=self.drone,
            intervalo_dias=10,
            ultima_execucao=timezone.localdate() - timedelta(days=10),
            criado_por=self.admin,
        )

    def test_plano_vencido_por_data(self):
        self.assertGreaterEqual(self.plano.progresso, 100)
        self.assertEqual(self.plano.situacao, "vencido")

    def test_execucao_reinicia_plano(self):
        self.client.force_login(self.admin)
        hoje = timezone.localdate()
        resposta = self.client.post(
            reverse("plano_inspecao_executar", args=[self.plano.pk]),
            {"data": hoje.isoformat(), "observacoes": "Inspeção aprovada"},
        )
        self.assertRedirects(resposta, reverse("planos_inspecao"))
        self.plano.refresh_from_db()
        self.assertEqual(self.plano.ultima_execucao, hoje)
        self.assertEqual(self.plano.situacao, "em_dia")
        self.assertTrue(ExecucaoInspecao.objects.filter(plano=self.plano).exists())


class DocumentoTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="admin_documentos", password="teste123")
        self.drone = Drone.objects.create(nome="Drone documento", modelo="Modelo teste")

    def test_documento_identifica_vencimento(self):
        documento = Documento.objects.create(
            titulo="Registro vencido", tipo="registro_drone", drone=self.drone,
            data_validade=timezone.localdate() - timedelta(days=1), criado_por=self.admin,
        )
        self.assertEqual(documento.situacao, "vencido")
        self.assertEqual(documento.dias_para_vencer, -1)

    def test_documento_exige_um_unico_vinculo(self):
        documento = Documento(
            titulo="Vínculo inválido", tipo="outro", drone=self.drone,
            organizacional=True, criado_por=self.admin,
        )
        with self.assertRaises(ValidationError):
            documento.full_clean()

    def test_admin_visualiza_documentos(self):
        Documento.objects.create(
            titulo="Seguro da frota", tipo="seguro", organizacional=True,
            data_validade=timezone.localdate() + timedelta(days=20), criado_por=self.admin,
        )
        self.client.force_login(self.admin)
        resposta = self.client.get(reverse("documentos"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Seguro da frota")
        self.assertContains(resposta, "20 dias")


class CentralAlertasTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="admin_alertas", password="teste123")
        self.drone = Drone.objects.create(nome="Drone alerta", modelo="Modelo", status="indisponivel")
        self.bateria = Bateria.objects.create(
            codigo="BAT-ALERTA", numero_serie="SERIE-ALERTA",
            saude_percentual=55, criado_em=timezone.now(),
        )
        Documento.objects.create(
            titulo="Documento vencido", tipo="seguro", organizacional=True,
            data_validade=timezone.localdate() - timedelta(days=2), criado_por=self.admin,
        )

    def test_agrega_alertas_criticos(self):
        alertas = gerar_alertas()
        resumo = resumo_alertas(alertas)
        self.assertGreaterEqual(resumo["criticos"], 3)
        self.assertEqual(alertas[0]["prioridade"], "critico")
        self.assertTrue(any(a["categoria"] == "Baterias" for a in alertas))

    def test_admin_acessa_central(self):
        self.client.force_login(self.admin)
        resposta = self.client.get(reverse("alertas"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Documento vencido")
        self.assertContains(resposta, "BAT-ALERTA")


class SegurancaOperacionalTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="admin_seguranca", password="teste123")
        self.usuario = User.objects.create_user(username="piloto_seguranca", password="teste123")
        self.piloto = Piloto.objects.create(user=self.usuario, nome="Piloto Segurança", primeiro_acesso=False)
        self.drone = Drone.objects.create(nome="Drone Segurança", modelo="Modelo", status="ativo")
        self.solicitacao = SolicitacaoVoo.objects.create(
            piloto=self.piloto, drone=self.drone, data=timezone.localdate() + timedelta(days=3),
            hora_inicio="10:00", hora_fim="11:00", finalidade="Inspeção",
            local="Área teste", criado_por=self.usuario, requer_avaliacao_risco=True,
        )

    def test_calcula_risco_residual(self):
        avaliacao = AvaliacaoRisco.objects.create(
            solicitacao=self.solicitacao, perigos_identificados="Pessoas próximas",
            probabilidade_inicial=4, impacto_inicial=5, medidas_mitigadoras="Isolar área",
            probabilidade_residual=2, impacto_residual=3, preenchido_por=self.usuario,
        )
        self.assertEqual(avaliacao.risco_inicial, 20)
        self.assertEqual(avaliacao.risco_residual, 6)
        self.assertEqual(avaliacao.nivel_residual, "medio")

    def test_nao_existe_aprovacao_administrativa_separada(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(reverse("solicitacao_voo_aprovar", args=[self.solicitacao.pk]))
        self.assertRedirects(resposta, reverse("solicitacoes_voo"))
        self.solicitacao.refresh_from_db()
        self.assertEqual(self.solicitacao.status, "solicitado")

    def test_aprovacao_da_avaliacao_libera_voo_no_calendario_e_telemetria(self):
        avaliacao = AvaliacaoRisco.objects.create(
            solicitacao=self.solicitacao, perigos_identificados="Obstáculos",
            probabilidade_inicial=3, impacto_inicial=3, medidas_mitigadoras="Isolar área",
            probabilidade_residual=1, impacto_residual=2, status="submetida",
            preenchido_por=self.usuario,
        )
        self.client.force_login(self.admin)
        resposta = self.client.post(
            reverse("avaliacao_risco", args=[self.solicitacao.pk]),
            {"acao": "aprovar"},
        )
        self.assertRedirects(resposta, reverse("solicitacoes_voo"))
        self.solicitacao.refresh_from_db()
        avaliacao.refresh_from_db()
        self.assertEqual(avaliacao.status, "aprovada")
        self.assertEqual(self.solicitacao.status, "aprovado")
        self.assertIsNotNone(self.solicitacao.alocacao_id)
        voo = Voo.objects.get(
            data=self.solicitacao.data, piloto=self.piloto, drone=self.drone
        )
        self.assertEqual(voo.alocacao_calendario_id, self.solicitacao.alocacao_id)
        self.client.force_login(self.usuario)
        self.assertContains(self.client.get(reverse("calendario")), self.drone.nome)
        self.assertContains(self.client.get(reverse("telemetria_importar")), f"Voo #{voo.pk}")

    def test_solicitacao_sem_avaliacao_e_liberada_ao_ser_criada(self):
        data_voo = timezone.localdate() + timedelta(days=5)
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse("solicitacao_voo_nova"), {
            "data": data_voo.isoformat(), "hora_inicio": "14:00", "hora_fim": "15:00",
            "piloto": self.piloto.pk, "drone": self.drone.pk, "finalidade": "Fotografia",
            "local": "Área fotográfica", "observacoes": "",
        })
        self.assertRedirects(resposta, reverse("solicitacoes_voo"))
        solicitacao = SolicitacaoVoo.objects.get(data=data_voo, piloto=self.piloto)
        self.assertEqual(solicitacao.status, "aprovado")
        self.assertTrue(Voo.objects.filter(
            data=data_voo, piloto=self.piloto, drone=self.drone
        ).exists())

    def test_incidente_do_piloto_aparece_na_central(self):
        alocacao = Alocacao.objects.create(
            data=timezone.localdate(), hora_inicio="09:00", hora_fim="10:00",
            piloto=self.piloto, drone=self.drone, finalidade="Teste", local="Área",
            status="concluido", criado_por=self.admin,
        )
        incidente = Incidente.objects.create(
            alocacao=alocacao, tipo="queda", gravidade="grave", data_hora=timezone.now(),
            descricao="Colisão controlada", registrado_por=self.usuario,
        )
        alertas = gerar_alertas()
        self.assertTrue(any(a["chave"] == f"incidente-{incidente.pk}" and a["prioridade"] == "critico" for a in alertas))
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("incidentes"))
        self.assertContains(resposta, "Colisão controlada")


class QualificacaoPilotoTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="admin_qualificacao", password="teste123")
        self.usuario = User.objects.create_user(username="piloto_qualificado", password="teste123")
        self.piloto = Piloto.objects.create(user=self.usuario, nome="Piloto Qualificado", primeiro_acesso=False)
        self.drone = Drone.objects.create(nome="Drone Experiência", modelo="Modelo")
        Voo.objects.create(
            data=timezone.localdate(), piloto=self.piloto, drone=self.drone,
            finalidade="treinamento", local="Área", hora_inicio=time(10, 0),
            hora_fim=time(11, 30), criado_por=self.admin,
        )

    def test_perfil_calcula_experiencia(self):
        voo = Voo.objects.get(piloto=self.piloto)
        ImportacaoLog.objects.create(
            voo=voo, nome_original="treinamento.txt", formato="txt", importado_por=self.usuario,
            status="concluida", duracao_segundos=5400,
        )
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("meu_perfil_operacional"), follow=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "1h 30min 00s")
        self.assertContains(resposta, "Drone Experiência")

    def test_perfil_soma_logs_e_ignora_reserva_nao_realizada(self):
        voo = Voo.objects.get(piloto=self.piloto)
        ImportacaoLog.objects.create(
            voo=voo, nome_original="trecho-1.txt", formato="txt", importado_por=self.usuario,
            status="concluida", duracao_segundos=125,
        )
        ImportacaoLog.objects.create(
            voo=voo, nome_original="trecho-2.txt", formato="txt", importado_por=self.usuario,
            status="concluida", duracao_segundos=70,
        )
        alocacao_futura = Alocacao.objects.create(
            data=timezone.localdate() + timedelta(days=1), hora_inicio=time(8), hora_fim=time(18),
            piloto=self.piloto, drone=self.drone, finalidade="Reserva futura", status="reservado",
            criado_por=self.admin,
        )
        Voo.objects.create(
            data=alocacao_futura.data, piloto=self.piloto, drone=self.drone, finalidade="outro",
            local="Área futura", hora_inicio=time(8), hora_fim=time(18), criado_por=self.admin,
            alocacao_calendario=alocacao_futura,
        )
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("meu_perfil_operacional"), follow=True)
        self.assertContains(resposta, "0h 03min 15s")
        self.assertContains(resposta, ">1<", count=2)

    def test_perfil_nao_contabiliza_voo_sem_log(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("meu_perfil_operacional"), follow=True)
        self.assertContains(resposta, "0h 00min 00s")
        self.assertContains(resposta, "O piloto ainda não possui voos registrados")

    def test_qualificacao_vencida_gera_alerta(self):
        qualificacao = QualificacaoPiloto.objects.create(
            piloto=self.piloto, nome="Treinamento vencido", categoria="seguranca",
            nivel="avancado", data_validade=timezone.localdate() - timedelta(days=1),
            criado_por=self.admin,
        )
        self.assertEqual(qualificacao.situacao, "vencida")
        alertas = gerar_alertas()
        self.assertTrue(any(a["chave"] == f"qualificacao-{qualificacao.pk}" for a in alertas))

    def test_usuario_nao_acessa_perfil_de_outro_piloto(self):
        outro = Piloto.objects.create(nome="Outro piloto")
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("perfil_operacional", args=[outro.pk]))
        self.assertRedirects(resposta, reverse("dashboard"))


class TelemetriaTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.configuracao_media = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.configuracao_media.enable()
        self.usuario = User.objects.create_user(username="piloto_telemetria", password="teste123")
        self.piloto = Piloto.objects.create(user=self.usuario, nome="Piloto Telemetria", primeiro_acesso=False)
        self.drone = Drone.objects.create(nome="Drone Log", modelo="Modelo")
        self.voo = Voo.objects.create(
            data=timezone.localdate(), piloto=self.piloto, drone=self.drone,
            finalidade="mapeamento", local="Área", hora_inicio=time(10), hora_fim=time(11),
            criado_por=self.usuario,
        )

    def tearDown(self):
        self.configuracao_media.disable()
        self.media_dir.cleanup()

    def _importacao(self):
        conteudo = (
            "timestamp,latitude,longitude,altitude_m,speed_ms,battery_percent,warning\n"
            "2026-08-24T10:00:00-03:00,-25.5163000,-54.5854000,10,2.5,98,\n"
            "2026-08-24T10:00:10-03:00,-25.5164000,-54.5855000,15,4.5,94,Vento forte\n"
            "2026-08-24T10:00:20-03:00,-25.5165000,-54.5856000,12,3.0,90,\n"
        ).encode()
        return ImportacaoLog.objects.create(
            voo=self.voo,
            arquivo=SimpleUploadedFile("voo.csv", conteudo, content_type="text/csv"),
            nome_original="voo.csv", formato="csv", importado_por=self.usuario,
        )

    def test_processa_log_e_atualiza_resumo_do_voo(self):
        importacao = processar_importacao(self._importacao(), atualizar_voo=True)
        self.assertEqual(importacao.status, "concluida")
        self.assertEqual(importacao.total_pontos, 3)
        self.assertEqual(importacao.duracao_segundos, 20)
        self.assertEqual(importacao.bateria_inicial, 98)
        self.assertEqual(importacao.bateria_final, 90)
        self.assertEqual(importacao.total_alertas, 1)
        self.assertGreater(importacao.distancia_calculada_m, 0)
        self.assertEqual(PontoTelemetria.objects.filter(importacao=importacao).count(), 3)
        self.voo.refresh_from_db()
        self.assertEqual(self.voo.bateria_final, 90)

        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("telemetria_detalhe", args=[importacao.pk]))
        self.assertContains(resposta, "00h 00min 20s")
        self.assertContains(resposta, "telemetry-alerts")
        self.assertContains(resposta, "Vento forte")
        self.assertContains(resposta, "tiles.openfreemap.org")
        self.assertContains(resposta, "Data do voo")
        self.assertContains(resposta, "Amostra dos dados por minuto")
        self.assertEqual(len(resposta.context["amostra_minutos"]), 1)
        self.assertEqual(resposta.context["amostra_minutos"][0]["status"], "atencao")

    def test_resumo_por_minuto_classifica_normal_atencao_e_erro(self):
        from .telemetria_views import _resumir_pontos_por_minuto

        pontos = [
            PontoTelemetria(importacao_id=1, indice=0, segundos=0, bateria_percentual=90, sinal_percentual=100, satelites=15),
            PontoTelemetria(importacao_id=1, indice=1, segundos=60, bateria_percentual=25, sinal_percentual=70, satelites=12),
            PontoTelemetria(importacao_id=1, indice=2, segundos=120, bateria_percentual=10, sinal_percentual=15, satelites=4, alerta="Falha crítica"),
        ]
        resumo = _resumir_pontos_por_minuto(pontos)
        self.assertEqual([item["status"] for item in resumo], ["normal", "atencao", "erro"])

    def test_piloto_visualiza_apenas_telemetria_dos_proprios_voos(self):
        importacao = processar_importacao(self._importacao())
        outro_user = User.objects.create_user(username="outro_telemetria", password="teste123")
        outro_piloto = Piloto.objects.create(user=outro_user, nome="Outro Telemetria", primeiro_acesso=False)
        outro_voo = Voo.objects.create(
            data=timezone.localdate(), piloto=outro_piloto, drone=self.drone,
            finalidade="outro", local="Outra área", hora_inicio=time(12), hora_fim=time(13),
        )
        outro_log = ImportacaoLog.objects.create(voo=outro_voo, nome_original="oculto.csv", formato="csv", importado_por=outro_user)
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("telemetria_lista"))
        self.assertContains(resposta, importacao.nome_original)
        self.assertNotContains(resposta, outro_log.nome_original)
        self.assertEqual(self.client.get(reverse("telemetria_detalhe", args=[outro_log.pk])).status_code, 404)

    @override_settings(DJI_FLIGHT_RECORD_APP_KEY="")
    def test_log_nativo_dji_exige_chave_configurada(self):
        conteudo = b"\x29\x03\x00\x00" + bytes(range(256)) * 4
        importacao = ImportacaoLog.objects.create(
            voo=self.voo,
            arquivo=SimpleUploadedFile("DJIFlightRecord_2026-08-24_[14-57-10].txt", conteudo),
            nome_original="DJIFlightRecord_2026-08-24_[14-57-10].txt",
            formato="txt", importado_por=self.usuario,
        )
        with self.assertRaisesMessage(ValueError, "chave DJI não está configurada"):
            processar_importacao(importacao)
        self.assertEqual(PontoTelemetria.objects.filter(importacao=importacao).count(), 0)

    def test_importacao_de_pasta_vincula_todos_os_logs_ao_mesmo_voo(self):
        conteudo = (
            "timestamp,seconds,latitude,longitude,altitude,battery\n"
            "2026-08-24T13:00:00-03:00,0,-25.3000,-51.2700,10,95\n"
            "2026-08-24T13:00:10-03:00,10,-25.3001,-51.2701,20,90\n"
        ).encode()
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse("telemetria_importar"), {
            "voo": self.voo.pk, "modo": "pasta",
            "pasta": [
                SimpleUploadedFile("voo-1.csv", conteudo, content_type="text/csv"),
                SimpleUploadedFile("voo-2.csv", conteudo, content_type="text/csv"),
            ],
        })
        self.assertRedirects(resposta, reverse("telemetria_lista"))
        self.assertEqual(ImportacaoLog.objects.filter(status="concluida").count(), 2)
        self.assertEqual(Voo.objects.filter(piloto=self.piloto).count(), 1)
        self.assertEqual(ImportacaoLog.objects.values("voo_id").distinct().count(), 1)
        self.assertFalse(ImportacaoLog.objects.exclude(voo=self.voo).exists())
        self.voo.refresh_from_db()
        self.assertEqual(self.voo.data.isoformat(), "2026-08-24")
        self.assertEqual(self.voo.hora_inicio.strftime("%H:%M:%S"), "13:00:00")
        self.assertEqual(self.voo.hora_fim.strftime("%H:%M:%S"), "13:00:10")
        self.assertEqual(self.voo.bateria_inicial, 95)
        self.assertEqual(self.voo.bateria_final, 90)
        self.assertGreater(self.voo.distancia_m, 0)

    def test_seletor_exibe_voos_com_e_sem_telemetria_com_identificacao_clara(self):
        from .telemetria_forms import ImportacaoLogForm
        from .telemetria_views import _voos_permitidos

        processar_importacao(self._importacao())
        self.voo.data = date(2024, 1, 15)
        self.voo.save(update_fields=["data"])
        pendente = Voo.objects.create(
            piloto=self.piloto, drone=self.drone, finalidade="fotografia",
            local="Área 2", criado_por=self.usuario,
        )
        form = ImportacaoLogForm(voos=_voos_permitidos(self.usuario))
        self.assertIn(self.voo, form.fields["voo"].queryset)
        self.assertIn(pendente, form.fields["voo"].queryset)
        self.assertIn(f"Voo #{pendente.pk}", form.fields["voo"].label_from_instance(pendente))
        self.assertIn("15/01/2024 · 1 log", form.fields["voo"].label_from_instance(self.voo))

    def test_telemetria_consolida_mesmo_drone_piloto_e_dia(self):
        self.voo.data = date(2026, 8, 24)
        self.voo.save(update_fields=["data"])
        rascunho = Voo.objects.create(
            piloto=self.piloto, drone=self.drone, finalidade="fotografia",
            local="Área", criado_por=self.usuario,
        )
        conteudo = (
            "timestamp,seconds,latitude,longitude,altitude,battery\n"
            "2026-08-24T15:00:00-03:00,0,-25.30,-51.27,10,95\n"
            "2026-08-24T15:00:10-03:00,10,-25.31,-51.28,20,90\n"
        ).encode()
        importacao = ImportacaoLog.objects.create(
            voo=rascunho,
            arquivo=SimpleUploadedFile("trecho.csv", conteudo, content_type="text/csv"),
            nome_original="trecho.csv", formato="csv", importado_por=self.usuario,
        )
        processar_importacao(importacao, atualizar_voo=True)
        importacao.refresh_from_db()
        self.assertEqual(importacao.voo_id, self.voo.pk)
        self.assertFalse(Voo.objects.filter(pk=rascunho.pk).exists())
        self.assertEqual(Voo.objects.filter(data=date(2026, 8, 24), piloto=self.piloto, drone=self.drone).count(), 1)


class ComponenteTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="admin_componente", password="teste123")
        self.usuario = User.objects.create_user(username="usuario_componente", password="teste123")
        Piloto.objects.create(user=self.usuario, nome="Usuário Componente", primeiro_acesso=False)
        self.drone = Drone.objects.create(nome="Drone Componentes", modelo="Modelo")
        self.item = Componente.objects.create(
            codigo="CAM-001", nome="Câmera RGB", tipo="camera", status="disponivel", criado_por=self.admin,
        )

    def test_usuario_comum_visualiza_mas_nao_edita(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse("componentes")).status_code, 200)
        self.assertContains(self.client.get(reverse("componente_detalhe", args=[self.item.pk])), "CAM-001")
        self.assertEqual(self.client.get(reverse("componente_editar", args=[self.item.pk])).status_code, 302)

    def test_edicao_registra_instalacao_no_historico(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(reverse("componente_editar", args=[self.item.pk]), {
            "codigo": "CAM-001", "nome": "Câmera RGB", "tipo": "camera",
            "fabricante": "Fabricante", "modelo": "X1", "numero_serie": "SER-1",
            "drone": self.drone.pk, "status": "instalado", "data_aquisicao": "",
            "data_instalacao": timezone.localdate().isoformat(), "vida_util_horas": 500,
            "observacoes": "", "motivo_movimentacao": "Instalação para missão",
        })
        self.assertRedirects(resposta, reverse("componente_detalhe", args=[self.item.pk]))
        movimento = MovimentacaoComponente.objects.get(componente=self.item)
        self.assertEqual(movimento.drone_novo, self.drone)
        self.assertEqual(movimento.status_novo, "instalado")
        self.assertEqual(movimento.motivo, "Instalação para missão")

    def test_qr_code_aponta_para_ficha_protegida(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("componente_qr", args=[self.item.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "image/png")
        self.assertTrue(resposta.content.startswith(b"\x89PNG"))
        ficha = self.client.get(reverse("componente_por_qr", args=[self.item.qr_token]))
        self.assertContains(ficha, "Câmera RGB")


class PermissoesOperacionaisTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="admin_permissoes", password="teste123")
        self.usuario = User.objects.create_user(username="piloto_permissoes", password="teste123")
        self.piloto = Piloto.objects.create(user=self.usuario, nome="Piloto Permissões", primeiro_acesso=False)
        self.drone = Drone.objects.create(nome="Drone Permissões", modelo="Modelo", status="ativo")
        self.alocacao = Alocacao.objects.create(
            data=timezone.localdate(), hora_inicio=time(9), hora_fim=time(10),
            piloto=self.piloto, drone=self.drone, finalidade="Inspeção", local="Área",
            status="reservado", criado_por=self.admin,
        )

    def test_piloto_nao_altera_status_do_drone(self):
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse("drone_status_atualizar", args=[self.drone.pk]), {"status": "manutencao"})
        self.assertRedirects(resposta, reverse("dashboard"))
        self.drone.refresh_from_db()
        self.assertEqual(self.drone.status, "ativo")

    def test_usuario_staff_nao_e_administrador_operacional(self):
        self.usuario.is_staff = True
        self.usuario.save(update_fields=["is_staff"])
        RegistroPosVoo.objects.create(
            alocacao=self.alocacao, hora_inicio_real=time(9), hora_fim_real=time(10),
            resultado="concluido", observacoes="Original", concluido=True, preenchido_por=self.usuario,
        )
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse("registro_pos_voo", args=[self.alocacao.pk]), {
            "hora_inicio_real": "09:00", "hora_fim_real": "10:00", "resultado": "concluido",
            "baterias_utilizadas": 1, "observacoes": "Alterado", "concluido": "on",
        })
        self.assertContains(resposta, "Apenas administradores podem alterá-lo")
        self.assertEqual(RegistroPosVoo.objects.get(alocacao=self.alocacao).observacoes, "Original")

    def test_piloto_nao_reabre_checklist_concluido(self):
        checklist = ChecklistPreVoo.objects.create(
            alocacao=self.alocacao, bateria_ok=True, helices_ok=True, estrutura_ok=True,
            controle_ok=True, gps_ok=True, memoria_ok=True, area_segura=True,
            meteorologia_ok=True, concluido=True, preenchido_por=self.usuario,
        )
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse("checklist_pre_voo", args=[self.alocacao.pk]), {"observacoes": "Alterado"})
        self.assertRedirects(resposta, reverse("checklist_pre_voo", args=[self.alocacao.pk]))
        checklist.refresh_from_db()
        self.assertTrue(checklist.concluido)
        self.assertEqual(checklist.observacoes, "")

    def test_avaliacao_submetida_fica_bloqueada_para_piloto(self):
        solicitacao = SolicitacaoVoo.objects.create(
            piloto=self.piloto, drone=self.drone, data=timezone.localdate() + timedelta(days=1),
            hora_inicio=time(11), hora_fim=time(12), finalidade="Inspeção", local="Área",
            criado_por=self.usuario,
        )
        avaliacao = AvaliacaoRisco.objects.create(
            solicitacao=solicitacao, perigos_identificados="Risco original",
            probabilidade_inicial=3, impacto_inicial=3, medidas_mitigadoras="Isolar área",
            probabilidade_residual=1, impacto_residual=2, status="submetida", preenchido_por=self.usuario,
        )
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse("avaliacao_risco", args=[solicitacao.pk]), {
            "perigos_identificados": "Alterado", "probabilidade_inicial": 1, "impacto_inicial": 1,
            "medidas_mitigadoras": "Nenhuma", "probabilidade_residual": 1, "impacto_residual": 1,
            "acao": "salvar",
        })
        self.assertEqual(resposta.status_code, 200)
        avaliacao.refresh_from_db()
        self.assertEqual(avaliacao.perigos_identificados, "Risco original")

    def test_menu_oculta_areas_exclusivas_de_administradores(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("dashboard"))
        for nome_rota in ["manutencoes", "planos_inspecao", "documentos", "pilotos", "relatorios", "alertas"]:
            self.assertNotContains(resposta, f'href="{reverse(nome_rota)}"')

    def test_calendario_oculta_acoes_de_reservas_de_outro_piloto(self):
        outro_user = User.objects.create_user(username="outro_calendario", password="teste123")
        outro_piloto = Piloto.objects.create(user=outro_user, nome="Outro Calendário", primeiro_acesso=False)
        outra = Alocacao.objects.create(
            data=timezone.localdate(), hora_inicio=time(11), hora_fim=time(12),
            piloto=outro_piloto, drone=self.drone, finalidade="Outro", local="Área",
            status="reservado", criado_por=self.admin,
        )
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("calendario"))
        self.assertContains(resposta, reverse("checklist_pre_voo", args=[self.alocacao.pk]))
        self.assertContains(resposta, reverse("registro_pos_voo", args=[self.alocacao.pk]))
        self.assertNotContains(resposta, reverse("checklist_pre_voo", args=[outra.pk]))
        self.assertNotContains(resposta, reverse("registro_pos_voo", args=[outra.pk]))


class FluxoOperacionalCompletoTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="admin_fluxo", password="teste123")
        self.usuario = User.objects.create_user(username="piloto_fluxo", password="teste123")
        self.piloto = Piloto.objects.create(user=self.usuario, nome="Piloto Fluxo", primeiro_acesso=False)
        self.drone = Drone.objects.create(nome="Drone Fluxo", modelo="Modelo", status="ativo")
        self.solicitacao = SolicitacaoVoo.objects.create(
            piloto=self.piloto, drone=self.drone, data=timezone.localdate() + timedelta(days=1),
            hora_inicio=time(9), hora_fim=time(10), finalidade="inspecao", local="Área de teste",
            criado_por=self.usuario, requer_avaliacao_risco=True,
        )
        AvaliacaoRisco.objects.create(
            solicitacao=self.solicitacao, perigos_identificados="Obstáculos",
            probabilidade_inicial=3, impacto_inicial=3, medidas_mitigadoras="Isolar área",
            probabilidade_residual=1, impacto_residual=2, status="submetida",
            preenchido_por=self.usuario, analisado_por=self.admin,
        )

    def test_solicitacao_ate_pos_voo_com_manutencao(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(reverse("avaliacao_risco", args=[self.solicitacao.pk]), {"acao": "aprovar"})
        self.assertRedirects(resposta, reverse("solicitacoes_voo"))
        self.solicitacao.refresh_from_db()
        self.assertEqual(self.solicitacao.status, "aprovado")
        self.assertIsNotNone(self.solicitacao.alocacao_id)

        alocacao = self.solicitacao.alocacao
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse("checklist_pre_voo", args=[alocacao.pk]), {
            "bateria_ok": "on", "helices_ok": "on", "estrutura_ok": "on", "controle_ok": "on",
            "gps_ok": "on", "memoria_ok": "on", "area_segura": "on", "meteorologia_ok": "on",
            "observacoes": "Operação liberada",
        })
        self.assertRedirects(resposta, reverse("calendario"))
        self.assertTrue(ChecklistPreVoo.objects.get(alocacao=alocacao).concluido)

        resposta = self.client.post(reverse("registro_pos_voo", args=[alocacao.pk]), {
            "hora_inicio_real": "09:05", "hora_fim_real": "09:50", "resultado": "concluido",
            "baterias_utilizadas": 1, "bateria_inicial": 98, "bateria_final": 41,
            "distancia_m": "1250.50", "ocorrencias": "Vibração no gimbal",
            "danos": "Verificar suporte", "necessita_manutencao": "on",
            "observacoes": "Missão concluída", "concluido": "on",
        })
        self.assertRedirects(resposta, reverse("registro_pos_voo", args=[alocacao.pk]))
        registro = RegistroPosVoo.objects.get(alocacao=alocacao)
        self.assertTrue(registro.concluido)
        self.assertIsNotNone(registro.voo_id)
        alocacao.refresh_from_db()
        self.solicitacao.refresh_from_db()
        self.drone.refresh_from_db()
        self.assertEqual(alocacao.status, "concluido")
        self.assertEqual(self.solicitacao.status, "concluido")
        self.assertEqual(self.drone.status, "manutencao")
        self.assertTrue(Manutencao.objects.filter(drone=self.drone, tipo="inspecao", concluida=False).exists())
        self.assertTrue(DroneHistorico.objects.filter(drone=self.drone, status_novo="manutencao").exists())
        self.assertEqual(Voo.objects.get(pk=registro.voo_id).distancia_m, 1250.50)


class SincronizacaoCalendarioTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="admin_calendario", password="teste123")
        self.usuario = User.objects.create_user(username="piloto_calendario", password="teste123")
        self.piloto = Piloto.objects.create(user=self.usuario, nome="Piloto Calendário", primeiro_acesso=False)
        self.drone = Drone.objects.create(nome="Drone Calendário", prefixo="DC-01", modelo="Modelo", status="ativo")

    def test_voo_manual_cria_vinculo_e_exclusao_limpa_calendario(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(reverse("voo_novo"), {
            "piloto": self.piloto.pk, "drone": self.drone.pk,
            "finalidade": "fotografia", "local": "Área", "observacoes": "",
        })
        self.assertRedirects(resposta, reverse("voos"))
        voo = Voo.objects.get(piloto=self.piloto)
        self.assertIsNone(voo.data)
        self.assertIsNone(voo.hora_inicio)
        self.assertIsNone(voo.alocacao_calendario_id)
        self.assertEqual(voo.finalidade, "fotografia")
        self.client.post(reverse("voo_excluir", args=[voo.pk]))
        self.assertFalse(Voo.objects.filter(pk=voo.pk).exists())

    def test_formulario_manual_mantem_apenas_dados_nao_fornecidos_pela_telemetria(self):
        from .forms import VooForm

        self.assertEqual(
            list(VooForm().fields),
            ["piloto", "drone", "finalidade", "local", "observacoes"],
        )

    def test_piloto_solicita_em_vez_de_registrar_voo_direto(self):
        self.client.force_login(self.usuario)
        self.assertRedirects(self.client.get(reverse("voo_novo")), reverse("dashboard"))
        resposta = self.client.get(reverse("voos"))
        self.assertContains(resposta, "Solicitar novo voo")
        self.assertContains(resposta, "Pedidos futuros são feitos em Solicitações")

    def test_prefixo_aparece_no_inventario(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("drones")), "DC-01")


class PerfilUsuarioTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.configuracao_media = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.configuracao_media.enable()
        self.usuario = User.objects.create_user(username="perfil_usuario", password="teste123")
        self.piloto = Piloto.objects.create(user=self.usuario, nome="Nome Original", primeiro_acesso=False)

    def tearDown(self):
        self.configuracao_media.disable()
        self.media_dir.cleanup()

    def test_usuario_edita_proprio_perfil(self):
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse("perfil_usuario", args=[self.piloto.pk]), {
            "nome": "Nome Atualizado", "matricula": "MAT-10", "email": "piloto@example.com",
        })
        self.assertRedirects(resposta, reverse("perfil_usuario", args=[self.piloto.pk]))
        self.piloto.refresh_from_db()
        self.usuario.refresh_from_db()
        self.assertEqual(self.piloto.nome, "Nome Atualizado")
        self.assertEqual(self.usuario.email, "piloto@example.com")

    def test_usuario_adiciona_documento_ao_proprio_perfil(self):
        self.client.force_login(self.usuario)
        arquivo = SimpleUploadedFile("certificado.pdf", b"arquivo de teste", content_type="application/pdf")
        resposta = self.client.post(reverse("documento_perfil_novo", args=[self.piloto.pk]), {
            "titulo": "Certificado geral", "tipo": "treinamento", "numero": "CERT-1",
            "data_emissao": "", "data_validade": "", "observacoes": "Documento do piloto",
            "arquivo": arquivo,
        })
        self.assertRedirects(resposta, reverse("perfil_usuario", args=[self.piloto.pk]))
        documento = Documento.objects.get(piloto=self.piloto)
        self.assertEqual(documento.titulo, "Certificado geral")
        self.assertEqual(documento.criado_por, self.usuario)
