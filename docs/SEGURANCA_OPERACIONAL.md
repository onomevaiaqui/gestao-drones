# Segurança operacional — reforços de 04/09/2026

## 1. Tentativas de autenticação e proxies

O bloqueio considera a conta independentemente do IP (SISMOD_LOGIN_MAX_FAILURES, padrão 5) e o IP independentemente da conta (SISMOD_LOGIN_IP_MAX_FAILURES, padrão 50). Limites e janela precisam ser ajustados para o volume da empresa, pois bloquear contas também pode ser explorado para negar acesso. MFA utiliza a mesma infraestrutura, com identificador separado do login.

SISMOD_TRUSTED_PROXY_CIDRS deve conter somente os proxies administrados pela empresa. Por padrão nenhum proxy é confiável. Cabeçalhos Forwarded/X-Forwarded-* são removidos de origens não confiáveis, inclusive antes de avaliar HTTPS. A cadeia X-Forwarded-For é percorrida da direita para a esquerda até o primeiro endereço não confiável. Não configurar 0.0.0.0/0 ou redes corporativas inteiras.

O Compose de produção usa proxy em 172.30.50.10 e rede 172.30.50.0/24. Ajustar juntos SISMOD_PROXY_IP, SISMOD_DOCKER_SUBNET e SISMOD_TRUSTED_PROXY_CIDRS se houver conflito na rede do servidor.

## 2. Falhas de auditoria

Falhas ao gravar eventos geram AUDIT_WRITE_FAILED no logger sismod.security e um alerta crítico no painel administrativo, quando o banco ainda está disponível. Se nem o alerta puder ser salvo, é emitido AUDIT_ALERT_FAILED. Não são incluídos senha, token, corpo da requisição, SQL nem texto da exceção no fallback. Encaminhar os logs do processo/containers ao monitoramento corporativo. Não há envio de e-mail ou SIEM instalado automaticamente, nem garantia de imutabilidade da base.

## 3. Criptografia do MFA e rotação

SISMOD_MFA_ENCRYPTION_KEYS contém chaves Fernet separadas por vírgula: a primeira cifra e as demais permitem ler dados antigos. Não confundir essas chaves com o segredo do autenticador do usuário. Não incluir no Git, imagens Docker ou relatórios.

Para migrar uma instalação antiga sem perder MFA:

1. Gerar uma chave Fernet com `Fernet.generate_key()` e armazenar em cofre de segredos.
2. Configurar SISMOD_MFA_ENCRYPTION_KEYS e manter SISMOD_MFA_LEGACY_KEY_ENABLED=true durante a migração.
3. Reiniciar todos os processos; executar `python manage.py rotacionar_chaves_mfa` (somente validação).
4. Em janela de manutenção, executar `python manage.py rotacionar_chaves_mfa --aplicar`. Falha de qualquer registro reverte a transação.
5. Após sucesso, configurar SISMOD_MFA_LEGACY_KEY_ENABLED=false e reiniciar novamente.

Para rotação futura, colocar a chave nova antes da anterior, repetir validação/aplicação e retirar a antiga somente após validar todos os registros e a política de retenção de backups. A alteração da criptografia exige nova verificação nas sessões MFA existentes. Guardar as chaves necessárias para restaurar backups históricos.

Na máquina local foi gerada uma chave própria sem exibi-la; não existiam configurações MFA ativas durante a migração. A compatibilidade legada foi desligada no `.env` local. A chave principal do Django não foi alterada.

Referência: [Fernet e MultiFernet](https://cryptography.io/en/latest/fernet/).

## 4. Autorizações de vídeo

Tokens novos de vídeo contêm usuário, contexto do perfil e vínculo com a senha atual. O callback consulta novamente usuário ativo, piloto ativo, status da transmissão, restrições do planejamento e acesso à estação. Encerramento, desativação e troca de senha impedem novos acessos; tokens antigos sem identidade deixam de ser aceitos quando a autenticação MediaMTX está configurada.

Para conexões já abertas, `python manage.py reconciliar_acessos_video` informa quantas seriam encerradas; `--aplicar` encerra as conexões WebRTC/RTMPS sem autorização atual pela API interna. O serviço media-guard do Compose de produção executa essa checagem a cada 15 segundos (mais o tempo de consulta). Não funciona se o serviço/API estiver indisponível: monitorar suas falhas.

O prazo do token limita novas conexões. Uma conexão já estabelecida não é interrompida apenas porque esse prazo passou; continua sujeita à revalidação de assinatura, senha, usuário e permissões. Isso evita encerrar automaticamente um voo longo. O reconciliador é exclusivo de um MediaMTX dedicado ao SISMOD; conexões sem token também são removidas. Não foi ativado no servidor de demonstração local sem autenticação.

Referência: [API MediaMTX 1.20.1](https://github.com/bluenviron/mediamtx/blob/v1.20.1/api/openapi.yaml).

## 5. Arquivos e antivírus

Além da barreira HTTP, os backends ArquivosLocaisSeguros e ArquivosS3Seguros inspecionam o conteúdo antes da persistência. Isso cobre FileField, default_storage e tarefas que usam esses backends. A leitura de telemetria também inspeciona os arquivos existentes antes do processamento. Conteúdo recusado não é gravado como arquivo válido.

Não escrever diretamente no filesystem nem usar credenciais de upload direto S3/Dock para contornar essa barreira. Upload direto permanece dependente de uma futura quarentena/inspeção antes de disponibilização. Os testes de CI usam respostas simuladas do ClamAV; o teste real local é `verificar_antivirus`. Ver limites de tamanho e implantação em [ANTIVIRUS_UPLOADS.md](ANTIVIRUS_UPLOADS.md).

## 6. Infraestrutura e CI

Callbacks internos de healthcheck/autenticação de vídeo são exceções exatas ao redirecionamento HTTPS. O proxy continua redirecionando acessos públicos; o web não publica porta no Compose de produção. O healthcheck aceita token e o callback só libera tokens assinados válidos. Hosts internos web/localhost estão no exemplo de produção.

O healthcheck que dependia de wget na imagem MediaMTX foi substituído por uma consulta Python no media-guard. CA MQTT é montada somente para leitura. O armazenamento usa um domínio público próprio para URLs assinadas MinIO, mantendo o bucket privado. Cabeçalhos e URI são removidos dos logs Caddy para não registrar credenciais ou URLs assinadas. O protocolo clamd fica apenas na rede privada em produção.

O arquivo `.github/workflows/validacao.yml` executa dependências, check, migrations, testes e diff check em pushes e pull requests, sem credenciais DJI ou dados locais. Só será executado no GitHub após o próximo envio e depende de Actions habilitado. Não substitui análise de vulnerabilidades, pentest ou homologação física.

## 7. Backup e restauração

Ver [BACKUP_E_RESTAURACAO.md](BACKUP_E_RESTAURACAO.md). Não há agendamento nem transferência de dados para serviços externos nesta implementação.

## Validações locais desta etapa

- Suíte completa final em 04/09/2026: 204 testes aprovados em 230 segundos, incluindo armazenamento S3 simulado, restauração, corrupção e traversal. Esta execução usa o ambiente local; consultar a divergência cryptography e o aceite de instalação limpa em ENTREGA_DEVOPS.md.
- Django check, migrations pendentes e pip check sem inconsistências.
- Compose de produção validado com valores de exemplo, sem iniciar a stack; Caddy validado na imagem oficial.
- ClamAV reiniciado com os limites explícitos, healthy e teste real limpo/EICAR aprovado.
- Actions oficiais fixadas por SHA obtido dos repositórios oficiais. Execução remota pendente do próximo push.
- Alterações incluídas na entrega Git de 04/09/2026. Sem backup dos dados reais, restauração sobre o banco em uso ou conexão à Dock física nesta validação.
