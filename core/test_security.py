from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch
from types import SimpleNamespace

from .models import TentativaLogin
from .mfa_service import (codigo_totp, gerar_segredo, validar_totp,
    consumir_totp, criptografar_segredo, consumir_codigo_recuperacao,
    gerar_codigos_recuperacao, marcar_sessao_mfa, sessao_mfa_valida)
from .models import AlertaSeguranca, ConfiguracaoSegurancaUsuario, EventoAuditoria


@override_settings(SISMOD_LOGIN_MAX_FAILURES=3, SISMOD_LOGIN_WINDOW_SECONDS=600, SISMOD_LOGIN_BLOCK_SECONDS=600)
class LoginSecurityTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("seguranca", password="Senha-Segura-2026")

    def test_bloqueia_apos_tres_falhas_sem_guardar_usuario_aberto(self):
        for _ in range(3):
            self.client.post(reverse("login"), {"username": "seguranca", "password": "incorreta"})
        resposta = self.client.post(reverse("login"), {"username": "seguranca", "password": "Senha-Segura-2026"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Usuário ou senha inválidos")
        self.assertFalse(resposta.wsgi_request.user.is_authenticated)
        self.assertEqual(TentativaLogin.objects.count(), 3)
        self.assertFalse(TentativaLogin.objects.filter(identificador_hash__icontains="seguranca").exists())
        self.assertEqual(AlertaSeguranca.objects.filter(tipo="bloqueio_login", resolvido=False).count(), 1)

    def test_login_valido_limpa_falhas_anteriores(self):
        self.client.post(reverse("login"), {"username": "seguranca", "password": "incorreta"})
        resposta = self.client.post(reverse("login"), {"username": "seguranca", "password": "Senha-Segura-2026"})
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(TentativaLogin.objects.exists())

    def test_validadores_rejeitam_senha_comum(self):
        with self.assertRaises(ValidationError):
            validate_password("password", self.usuario)

    def test_totp_compativel_e_rejeita_codigo_incorreto(self):
        segredo = gerar_segredo()
        codigo = codigo_totp(segredo, instante=1_700_000_000)
        self.assertTrue(validar_totp(segredo, codigo, instante=1_700_000_000))
        self.assertFalse(validar_totp(segredo, "000000", instante=1_700_000_000))

    def test_totp_nao_pode_ser_reutilizado_com_objeto_desatualizado(self):
        segredo = gerar_segredo()
        configuracao = ConfiguracaoSegurancaUsuario.objects.create(
            usuario=self.usuario, mfa_ativo=True,
            segredo_mfa_criptografado=criptografar_segredo(segredo),
        )
        instante = 1_700_000_000
        codigo = codigo_totp(segredo, instante)
        self.assertTrue(consumir_totp(configuracao, codigo, instante))
        self.assertFalse(consumir_totp(configuracao, codigo, instante))
        self.assertTrue(consumir_totp(configuracao, codigo_totp(segredo, instante + 30), instante + 30))
        self.assertFalse(consumir_totp(configuracao, codigo_totp(segredo, instante - 30), instante))

    def test_codigo_recuperacao_so_e_consumido_uma_vez(self):
        codigos, hashes = gerar_codigos_recuperacao(2)
        configuracao = ConfiguracaoSegurancaUsuario.objects.create(
            usuario=self.usuario, mfa_ativo=True, codigos_recuperacao=hashes,
        )
        self.assertTrue(consumir_codigo_recuperacao(configuracao, codigos[0]))
        self.assertFalse(consumir_codigo_recuperacao(configuracao, codigos[0]))
        configuracao.refresh_from_db()
        self.assertEqual(len(configuracao.codigos_recuperacao), 1)
        self.assertTrue(consumir_codigo_recuperacao(configuracao, codigos[1]))

    def configurar_sessao_verificada(self):
        configuracao = ConfiguracaoSegurancaUsuario.objects.create(
            usuario=self.usuario, mfa_ativo=True,
            segredo_mfa_criptografado=criptografar_segredo(gerar_segredo()),
        )
        self.client.force_login(self.usuario)
        sessao = self.client.session
        # O helper troca a chave; atualizar o cookie como o middleware faria.
        from django.conf import settings
        marcar_sessao_mfa(sessao, configuracao)
        sessao.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = sessao.session_key
        return configuracao

    def test_alteracao_mfa_bloqueia_sessao_anterior_e_limpa_acao_critica(self):
        configuracao = self.configurar_sessao_verificada()
        self.assertEqual(self.client.get(reverse("seguranca_conta")).status_code, 200)
        sessao = self.client.session
        sessao["reauth_em"] = 123
        sessao["acao_critica_pendente"] = {"tipo": "teste"}
        sessao.save()
        configuracao.segredo_mfa_criptografado = criptografar_segredo(gerar_segredo())
        configuracao.save()
        resposta = self.client.get(reverse("seguranca_conta"))
        self.assertEqual(resposta.url, reverse("mfa_verificar"))
        self.assertNotIn("reauth_em", self.client.session)
        self.assertNotIn("acao_critica_pendente", self.client.session)

    def test_sessao_antiga_nao_pode_desativar_novo_mfa(self):
        configuracao = self.configurar_sessao_verificada()
        configuracao.segredo_mfa_criptografado = criptografar_segredo(gerar_segredo())
        configuracao.save()
        resposta = self.client.post(reverse("mfa_desativar"), {"senha": "Senha-Segura-2026"})
        self.assertEqual(resposta.url, reverse("mfa_verificar"))
        configuracao.refresh_from_db()
        self.assertTrue(configuracao.mfa_ativo)

    def test_contador_de_codigo_nao_invalida_sessao(self):
        configuracao = self.configurar_sessao_verificada()
        configuracao.ultimo_contador_mfa += 1
        configuracao.save()
        self.assertTrue(sessao_mfa_valida(self.client.session, configuracao))

    def test_sessao_legada_exige_verificacao_novamente(self):
        configuracao = self.configurar_sessao_verificada()
        sessao = self.client.session
        sessao.pop("mfa_versao")
        sessao.save()
        self.assertFalse(sessao_mfa_valida(sessao, configuracao))
        resposta = self.client.get(reverse("seguranca_conta"))
        self.assertEqual(resposta.url, reverse("mfa_verificar"))

    @override_settings(SISMOD_MFA_ADMIN_REQUIRED=True)
    def test_admin_configura_mfa_antes_de_acessar_sistema(self):
        self.usuario.is_staff = True
        self.usuario.is_superuser = True
        self.usuario.save(update_fields=["is_staff", "is_superuser"])
        self.client.force_login(self.usuario)
        bloqueada = self.client.get(reverse("dashboard"))
        self.assertRedirects(bloqueada, reverse("mfa_configurar"))
        self.client.get(reverse("mfa_configurar"))
        segredo = self.client.session["mfa_segredo_pendente"]
        resposta = self.client.post(reverse("mfa_configurar"), {"codigo": codigo_totp(segredo)})
        self.assertRedirects(resposta, reverse("seguranca_conta"))
        self.assertTrue(ConfiguracaoSegurancaUsuario.objects.get(usuario=self.usuario).mfa_ativo)

    def test_middleware_audita_operacao_sem_salvar_campos_do_formulario(self):
        self.client.post(reverse("login"), {"username": "seguranca", "password": "incorreta-secreta"})
        evento = EventoAuditoria.objects.filter(acao="login").latest("ocorrido_em")
        self.assertEqual(evento.metodo, "POST")
        self.assertEqual(evento.detalhes, {})
        self.assertNotIn("incorreta", evento.caminho)

    @override_settings(SISMOD_MFA_ADMIN_REQUIRED=True)
    def test_login_admin_pendente_permite_configurar_mfa(self):
        self.usuario.is_superuser = True
        self.usuario.is_staff = True
        self.usuario.save()
        self.client.post(reverse("login"), {"username": self.usuario.username, "password": "Senha-Segura-2026"})
        resposta = self.client.get(reverse("mfa_configurar"))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("mfa_segredo_pendente", self.client.session)

    def test_desativar_mfa_exige_segundo_fator(self):
        configuracao = ConfiguracaoSegurancaUsuario.objects.create(usuario=self.usuario, mfa_ativo=True)
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse("mfa_desativar"), {"senha": "Senha-Segura-2026"})
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("mfa_verificar"))
        configuracao.refresh_from_db()
        self.assertTrue(configuracao.mfa_ativo)

    def test_mfa_bloqueia_tentativas_inclusive_apos_nova_sessao(self):
        self.client.force_login(self.usuario)
        for _ in range(3):
            resposta = self.client.post(reverse("mfa_configurar"), {"codigo": "invalido"})
            self.assertEqual(resposta.status_code, 200)
        self.client.logout()
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse("mfa_configurar"), {"codigo": "invalido"})
        self.assertEqual(resposta.status_code, 429)

    def test_licenca_expirada_nao_impede_autenticacao_mfa(self):
        self.client.force_login(self.usuario)
        with patch("core.middleware.estado_licenca", return_value=SimpleNamespace(
            permite_alteracoes=False, titulo="Expirada", mensagem="Renove a licença."
        )):
            resposta = self.client.post(reverse("mfa_configurar"), {"codigo": "invalido"})
        self.assertEqual(resposta.status_code, 200)

    def test_upload_executavel_disfarcado_e_bloqueado(self):
        resposta = self.client.post(reverse("login"), {
            "username": "seguranca", "password": "incorreta",
            "arquivo": SimpleUploadedFile("relatorio.txt", b"MZconteudo"),
        })
        self.assertEqual(resposta.status_code, 400)
        self.assertTrue(AlertaSeguranca.objects.filter(tipo="upload_bloqueado").exists())

    def test_admin_exporta_auditoria_com_csv_seguro(self):
        self.usuario.is_superuser = True
        self.usuario.is_staff = True
        self.usuario.save(update_fields=["is_superuser", "is_staff"])
        EventoAuditoria.objects.create(usuario=self.usuario, acao="=FORMULA", metodo="POST", caminho="rota", status_http=200)
        self.client.force_login(self.usuario)
        self.client.session["modo_acesso"] = "admin"
        resposta = self.client.get(reverse("auditoria_exportar"))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("'=FORMULA", resposta.content.decode("utf-8-sig"))
