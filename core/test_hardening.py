import io
import json
import sqlite3
import tempfile
import uuid
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.test import TestCase, SimpleTestCase, RequestFactory, override_settings
from django.urls import reverse
from core.login_security import endereco_cliente, registrar_falha, esta_bloqueado
from core.security_middleware import ProxyConfiavelMiddleware, AuditoriaMiddleware
from core.models import AlertaSeguranca, Piloto, TransmissaoAoVivo
from core.mfa_service import criptografar_segredo, descriptografar_segredo
from core.dji_cloud_service import token_mediamtx, validar_token_mediamtx
from core.backup_service import criar_backup, restaurar_backup
from core.secure_storage import ArquivosLocaisSeguros, InspecaoMixin
from core.upload_security import ArquivoInseguro


class ProxyTests(SimpleTestCase):
    @override_settings(SISMOD_TRUSTED_PROXY_CIDRS=["10.0.0.1/32"])
    def test_cabecalhos_falsos_ignorados(self):
        request = RequestFactory().get("/", REMOTE_ADDR="192.0.2.3", HTTP_X_FORWARDED_FOR="1.2.3.4", HTTP_X_FORWARDED_PROTO="https")
        ProxyConfiavelMiddleware(lambda r: HttpResponse())(request)
        self.assertEqual(endereco_cliente(request), "192.0.2.3")
        self.assertNotIn("HTTP_X_FORWARDED_PROTO", request.META)

    @override_settings(SISMOD_TRUSTED_PROXY_CIDRS=["10.0.0.0/24"])
    def test_cadeia_de_proxies_pela_direita(self):
        request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="1.2.3.4, 192.0.2.8, 10.0.0.2")
        self.assertEqual(endereco_cliente(request), "192.0.2.8")


@override_settings(SISMOD_LOGIN_MAX_FAILURES=3, SISMOD_LOGIN_IP_MAX_FAILURES=4)
class BloqueiosTests(TestCase):
    def test_trocar_ip_nao_contorna_bloqueio_da_conta(self):
        for i in range(3):
            registrar_falha(RequestFactory().get("/", REMOTE_ADDR=f"192.0.2.{i+1}"), "conta")
        self.assertTrue(esta_bloqueado(RequestFactory().get("/", REMOTE_ADDR="192.0.2.99"), "conta"))

    def test_ip_bloqueado_ao_alternar_contas(self):
        request = RequestFactory().get("/", REMOTE_ADDR="192.0.2.9")
        for i in range(4):
            registrar_falha(request, f"conta{i}")
        self.assertTrue(esta_bloqueado(request, "outra-conta"))

    def test_falha_auditoria_gera_log_e_alerta(self):
        request = RequestFactory().post("/rota/segredo-na-url")
        with patch("core.models.EventoAuditoria.objects.create", side_effect=RuntimeError("segredo")):
            with self.assertLogs("sismod.security", level="ERROR") as logs:
                AuditoriaMiddleware(lambda r: HttpResponse(status=201))(request)
        self.assertTrue(AlertaSeguranca.objects.filter(tipo="falha_auditoria").exists())
        self.assertNotIn("segredo", str(logs.output))


class CriptografiaTests(SimpleTestCase):
    def test_chave_mfa_independente_da_chave_django(self):
        chave = Fernet.generate_key().decode()
        with override_settings(SISMOD_MFA_ENCRYPTION_KEYS=[chave], SISMOD_MFA_LEGACY_KEY_ENABLED=False, SECRET_KEY="primeira"):
            cifrado = criptografar_segredo("SEGREDO")
        with override_settings(SISMOD_MFA_ENCRYPTION_KEYS=[chave], SISMOD_MFA_LEGACY_KEY_ENABLED=False, SECRET_KEY="segunda"):
            self.assertEqual(descriptografar_segredo(cifrado), "SEGREDO")

    def test_rotacao_mantem_leitura_com_chave_anterior(self):
        antiga, nova = Fernet.generate_key().decode(), Fernet.generate_key().decode()
        with override_settings(SISMOD_MFA_ENCRYPTION_KEYS=[antiga], SISMOD_MFA_LEGACY_KEY_ENABLED=False):
            cifrado = criptografar_segredo("SEGREDO")
        with override_settings(SISMOD_MFA_ENCRYPTION_KEYS=[nova, antiga], SISMOD_MFA_LEGACY_KEY_ENABLED=False):
            novo = criptografar_segredo(descriptografar_segredo(cifrado))
        with override_settings(SISMOD_MFA_ENCRYPTION_KEYS=[nova], SISMOD_MFA_LEGACY_KEY_ENABLED=False):
            self.assertEqual(descriptografar_segredo(novo), "SEGREDO")


@override_settings(SISMOD_MEDIAMTX_AUTH_SECRET="somente-teste")
class VideoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("video", password="Senha-Segura-2026")
        self.piloto = Piloto.objects.create(user=self.user, nome="Piloto")
        self.tx = TransmissaoAoVivo.objects.create(piloto=self.piloto, status="ao_vivo")
        self.token = token_mediamtx(self.tx, "read", self.user)

    def valido(self):
        return validar_token_mediamtx(self.token, str(self.tx.chave_stream), "read")

    def test_encerramento_revoga_token(self):
        self.assertTrue(self.valido())
        self.tx.status = "finalizada"
        self.tx.save()
        self.assertFalse(self.valido())

    def test_desativar_usuario_revoga_token(self):
        self.user.is_active = False
        self.user.save()
        self.assertFalse(self.valido())

    def test_troca_senha_revoga_token(self):
        self.user.set_password("Nova-Senha-2026")
        self.user.save()
        self.assertFalse(self.valido())

    def test_reconciliacao_expulsa_conexao_invalida(self):
        from core.management.commands.reconciliar_acessos_video import reconciliar
        identificador = str(uuid.uuid4())
        with patch("core.management.commands.reconciliar_acessos_video.api", side_effect=[
            {"items": [{"id": identificador, "state": "read", "query": "token=invalido", "path": str(self.tx.chave_stream)}]},
            {}, {"items": []},
        ]) as api:
            self.assertEqual(reconciliar(True), 1)
            api.assert_any_call(f"/v3/webrtcsessions/kick/{identificador}", "POST")

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_callback_interno_nao_redireciona_https(self):
        resposta = self.client.post(reverse("mediamtx_auth"), data=json.dumps({
            "token": self.token, "path": str(self.tx.chave_stream), "action": "read"
        }), content_type="application/json")
        self.assertEqual(resposta.status_code, 204)


class PersistenciaTests(SimpleTestCase):
    def test_backend_s3_inspeciona_antes_de_enviar(self):
        from core.secure_storage import ArquivosS3Seguros
        storage = ArquivosS3Seguros(bucket_name="teste", access_key="teste", secret_key="teste")
        with patch("core.secure_storage.verificar_uploads", side_effect=ArquivoInseguro("bloqueado")):
            with patch("storages.backends.s3.S3Storage._save") as salvar:
                with self.assertRaises(ArquivoInseguro):
                    storage.save("arquivo.txt", ContentFile(b"conteudo"))
                salvar.assert_not_called()

    def test_arquivo_fora_de_http_e_inspecionado(self):
        with tempfile.TemporaryDirectory() as pasta:
            storage = ArquivosLocaisSeguros(location=pasta)
            with patch("core.secure_storage.verificar_uploads", side_effect=ArquivoInseguro("bloqueado")):
                with self.assertRaises(ArquivoInseguro):
                    storage.save("arquivo.txt", ContentFile(b"conteudo"))
            self.assertEqual(list(Path(pasta).iterdir()), [])

    def test_backup_restaurado_com_banco_e_midia(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            banco = raiz / "origem.sqlite3"
            with closing(sqlite3.connect(banco)) as db, db:
                db.execute("CREATE TABLE teste (id INTEGER PRIMARY KEY, nome TEXT)")
                db.execute("INSERT INTO teste VALUES (1, 'preservado')")
            midia = raiz / "media"
            midia.mkdir()
            (midia / "documento.txt").write_bytes(b"documento de teste")
            pacote = raiz / "backup.zip"
            criar_backup(banco, midia, pacote)
            destino = raiz / "restaurado"
            self.assertEqual(restaurar_backup(pacote, destino), 2)
            self.assertEqual((destino / "media/documento.txt").read_bytes(), b"documento de teste")
            with closing(sqlite3.connect(destino / "database.sqlite3")) as db:
                self.assertEqual(db.execute("SELECT nome FROM teste").fetchone()[0], "preservado")
            with self.assertRaises(ValueError):
                restaurar_backup(pacote, destino)

    def test_restauracao_rejeita_traversal(self):
        with tempfile.TemporaryDirectory() as pasta:
            pacote = Path(pasta) / "ruim.zip"
            with zipfile.ZipFile(pacote, "w") as arquivo:
                arquivo.writestr("manifest.json", json.dumps({"versao": 1, "arquivos": {
                    "database.sqlite3": {"bytes": 0}, "media/../../fora.txt": {"bytes": 0}
                }}))
                arquivo.writestr("database.sqlite3", b"")
                arquivo.writestr("media/../../fora.txt", b"")
            with self.assertRaises(ValueError):
                restaurar_backup(pacote, Path(pasta) / "destino")

    def test_restauracao_rejeita_hash_corrompido_sem_criar_destino(self):
        with tempfile.TemporaryDirectory() as pasta:
            pacote = Path(pasta) / "corrompido.zip"
            with zipfile.ZipFile(pacote, "w") as arquivo:
                arquivo.writestr("manifest.json", json.dumps({"versao": 1, "arquivos": {
                    "database.sqlite3": {"bytes": 4, "sha256": "hash-incorreto"}
                }}))
                arquivo.writestr("database.sqlite3", b"dado")
            destino = Path(pasta) / "destino"
            with self.assertRaises(ValueError):
                restaurar_backup(pacote, destino)
            self.assertFalse(destino.exists())
