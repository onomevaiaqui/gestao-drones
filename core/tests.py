from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Bateria, Drone, ExecucaoInspecao, PlanoInspecao


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
