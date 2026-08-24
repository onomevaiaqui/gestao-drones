from datetime import time, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .alerta_service import gerar_alertas, resumo_alertas
from .models import (
    Alocacao, AvaliacaoRisco, Bateria, Documento, Drone, ExecucaoInspecao,
    Incidente, Piloto, PlanoInspecao, QualificacaoPiloto, SolicitacaoVoo, Voo,
)


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
            local="Área teste", criado_por=self.usuario,
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

    def test_aprovacao_exige_risco_aprovado(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(reverse("solicitacao_voo_aprovar", args=[self.solicitacao.pk]))
        self.assertRedirects(resposta, reverse("avaliacao_risco", kwargs={"solicitacao_id": self.solicitacao.pk}))
        self.solicitacao.refresh_from_db()
        self.assertEqual(self.solicitacao.status, "solicitado")

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
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("meu_perfil_operacional"), follow=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "1,5 h")
        self.assertContains(resposta, "Drone Experiência")

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
