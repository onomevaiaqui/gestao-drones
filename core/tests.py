from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Bateria, Drone


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
