# Segurança e MQTT: estado de preparação

## Mosquitto

O ambiente local possui configuração para Eclipse Mosquitto com autenticação e ACL separando consumidor e publicador. O listener local fica limitado a 127.0.0.1. O Docker Desktop precisa estar em execução; a presença dos arquivos de configuração não significa que o broker esteja ativo.

Antes de iniciar, definir senhas próprias para SISMOD_MQTT_CONSUMER_PASSWORD e SISMOD_MQTT_PUBLISHER_PASSWORD no ambiente usado pelo Compose. Não reutilizar senhas descartáveis de teste nem versionar credenciais. Conferir os containers existentes antes de iniciar outro broker na mesma porta.

Para o broker corporativo ainda são necessários endereço, porta TLS, CA confiável, contas e ACL aprovadas pela empresa, além de teste de conexão e de negação de tópicos não autorizados. A configuração local não deve ser exposta diretamente à internet.

A autenticação dinâmica usada pelo provisionamento DJI não é automaticamente compatível com o arquivo de senhas do Mosquitto. Essa integração precisa de validação específica antes de conectar a Dock real. Não considerar o teste local de publicação como homologação da Dock.

## Segurança

- MFA disponível; obrigatoriedade administrativa depende de SISMOD_MFA_ADMIN_REQUIRED e cadastro dos administradores.
- A seleção de perfil permite concluir as telas MFA. Desativar MFA exige sessão verificada e senha atual.
- ClamAV local instalado e validado em 04/09/2026: conteúdo limpo aceito, EICAR bloqueado, container saudável. Por solicitação do usuário, o `.env` local foi configurado com SISMOD_CLAMAV_HOST=127.0.0.1, porta 3310 e SISMOD_CLAMAV_REQUIRED=true. Novos processos Django usam essa configuração; processos já abertos precisam ser reiniciados. O arquivo local permanece fora do Git. Ver [guia](ANTIVIRUS_UPLOADS.md), incluindo limites de cobertura.
- Configuração/verificação MFA e confirmação de comandos críticos limitam tentativas por conta e IP no banco, usando os limites SISMOD_LOGIN_*. Trocar de sessão não elimina o bloqueio. Permanecem necessárias revisão de recuperação de conta e rotação de chaves.
- A migração 0071 registra o último intervalo TOTP aceito. O código usado na ativação também é consumido; aguarde o próximo código para outro login. A atualização condicional no banco rejeita reutilização e intervalos anteriores, inclusive com objetos desatualizados. Códigos de recuperação são removidos por atualização condicional, impedindo consumo duplicado.
- Produção exige validação HTTPS, credenciais de mídia, rede, backups com restauração testada, retenção, monitoramento e auditoria independente. Os controles implementados não constituem certificação de segurança corporativa.

Na continuação de 04/09/2026, o Docker estava disponível e o container sismod-mosquitto-local estava saudável, publicado somente em 127.0.0.1:1883. Uma conexão sem credenciais foi recusada. Não foram enviados comandos à Dock, alteradas credenciais nem homologada a integração corporativa.
