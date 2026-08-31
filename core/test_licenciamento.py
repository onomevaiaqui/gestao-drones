import base64
import json
import uuid
from datetime import date, timedelta

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from unittest.mock import patch

from core.licenciamento import ErroLicenca, ativar_licenca, estado_licenca
from core.models import InstalacaoSISMOD, Piloto


class LicenciamentoTests(TestCase):
    def setUp(self):
        self.privada = Ed25519PrivateKey.generate()
        publica = self.privada.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.publica_b64 = base64.b64encode(publica).decode()
        self.instalacao = InstalacaoSISMOD.atual()
        self.admin = User.objects.create_superuser("admin", "admin@empresa.test", "senha-forte")

    def documento(self, expira_em=None, instalacao_id=None):
        payload = {
            "schema": 1,
            "license_id": str(uuid.uuid4()),
            "installation_id": str(instalacao_id or self.instalacao.identificador),
            "company_name": "Empresa Teste",
            "company_cnpj": "00.000.000/0001-00",
            "issued_at": date.today().isoformat(),
            "expires_at": (expira_em or date.today() + timedelta(days=365)).isoformat(),
            "grace_days": 15,
            "features": ["core"],
        }
        canonico = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        return json.dumps({"payload": payload, "signature": base64.b64encode(self.privada.sign(canonico)).decode()}).encode()

    def test_ativa_licenca_assinada(self):
        with override_settings(SISMOD_LICENSE_ENFORCEMENT=True, SISMOD_LICENSE_PUBLIC_KEY=self.publica_b64):
            licenca = ativar_licenca(self.documento(), self.admin)
            self.assertEqual(estado_licenca().codigo, "ativa")
            self.assertEqual(licenca.empresa_nome, "Empresa Teste")

    def test_rejeita_licenca_de_outra_instalacao(self):
        with override_settings(SISMOD_LICENSE_ENFORCEMENT=True, SISMOD_LICENSE_PUBLIC_KEY=self.publica_b64):
            with self.assertRaises(ErroLicenca):
                ativar_licenca(self.documento(instalacao_id=uuid.uuid4()), self.admin)

    def test_detecta_adulteracao_no_banco(self):
        with override_settings(SISMOD_LICENSE_ENFORCEMENT=True, SISMOD_LICENSE_PUBLIC_KEY=self.publica_b64):
            licenca = ativar_licenca(self.documento(), self.admin)
            licenca.conteudo["company_name"] = "Alterada"
            licenca.save(update_fields=["conteudo"])
            self.assertEqual(estado_licenca().codigo, "invalida")

    def test_tolerancia_e_bloqueio_final(self):
        with override_settings(SISMOD_LICENSE_ENFORCEMENT=True, SISMOD_LICENSE_PUBLIC_KEY=self.publica_b64):
            ativar_licenca(self.documento(expira_em=date.today() + timedelta(days=1)), self.admin)
            self.assertEqual(estado_licenca(hoje=date.today() + timedelta(days=10)).codigo, "tolerancia")
            self.assertEqual(estado_licenca(hoje=date.today() + timedelta(days=20)).codigo, "expirada")


class AdminInicialTests(TestCase):
    def test_cria_primeiro_admin_sem_interacao(self):
        valores = {
            "SISMOD_INITIAL_ADMIN_USERNAME": "primeiro.admin",
            "SISMOD_INITIAL_ADMIN_EMAIL": "admin@empresa.test",
            "SISMOD_INITIAL_ADMIN_NAME": "Primeiro Admin",
            "SISMOD_INITIAL_ADMIN_PASSWORD": "senha-segura-123",
        }
        with patch.dict("os.environ", valores, clear=False):
            call_command("criar_admin_inicial", "--noinput")
        self.assertTrue(User.objects.get(username="primeiro.admin").is_superuser)
        self.assertEqual(Piloto.objects.get(nome="Primeiro Admin").perfil, "administrador")
        with self.assertRaises(CommandError):
            call_command("criar_admin_inicial", "--noinput")
