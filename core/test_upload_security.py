from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from .upload_security import ArquivoInseguro, verificar_clamav, verificar_arquivo_basico


@override_settings(SISMOD_CLAMAV_HOST="127.0.0.1", SISMOD_CLAMAV_PORT=3310, SISMOD_CLAMAV_REQUIRED=True)
class AntivirusTests(SimpleTestCase):
    def resposta(self, partes):
        conexao = MagicMock()
        conexao.__enter__.return_value = conexao
        conexao.recv.side_effect = partes
        return conexao

    def test_le_resposta_fragmentada_e_preserva_cursor(self):
        arquivo = SimpleUploadedFile("log.txt", b"dados completos")
        arquivo.seek(5)
        conexao = self.resposta([b"stream: ", b"OK\0"])
        with patch("core.upload_security.socket.create_connection", return_value=conexao):
            verificar_clamav(arquivo)
        self.assertEqual(arquivo.tell(), 5)
        self.assertIn(b"dados completos", conexao.sendall.call_args_list[1].args[0])

    def test_rejeita_ameaca_erro_e_resposta_incompleta(self):
        for partes in ([b"stream: Test FOUND\0"], [b"stream: NOT OK\0"], [b"stream: OK", b""]):
            with self.subTest(partes=partes):
                with patch("core.upload_security.socket.create_connection", return_value=self.resposta(partes)):
                    with self.assertRaises(ArquivoInseguro):
                        verificar_clamav(SimpleUploadedFile("log.txt", b"dados"))

    def test_indisponibilidade_obrigatoria_bloqueia(self):
        with patch("core.upload_security.socket.create_connection", side_effect=OSError):
            with self.assertRaises(ArquivoInseguro):
                verificar_clamav(SimpleUploadedFile("log.txt", b"dados"))

    @override_settings(SISMOD_CLAMAV_MAX_BYTES=3)
    def test_arquivo_acima_do_limite_nao_e_enviado_ao_daemon(self):
        with patch("core.upload_security.socket.create_connection") as conectar:
            with self.assertRaises(ArquivoInseguro):
                verificar_clamav(SimpleUploadedFile("log.txt", b"dados"))
            conectar.assert_not_called()

    @override_settings(SISMOD_CLAMAV_REQUIRED=False)
    def test_indisponibilidade_opcional_nao_bloqueia(self):
        with patch("core.upload_security.socket.create_connection", side_effect=OSError):
            verificar_clamav(SimpleUploadedFile("log.txt", b"dados"))

    def test_assinatura_verificada_desde_inicio(self):
        arquivo = SimpleUploadedFile("documento.txt", b"MZexecutavel")
        arquivo.seek(4)
        with self.assertRaises(ArquivoInseguro):
            verificar_arquivo_basico(arquivo)
        self.assertEqual(arquivo.tell(), 4)
