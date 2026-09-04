# Antivírus dos uploads

O ambiente local opcional usa a imagem oficial ClamAV, fixada por digest em `infra/compose.antivirus.yaml`. A porta 3310 fica acessível somente em 127.0.0.1, pois o protocolo clamd não fornece autenticação ou criptografia. Não publicar essa porta na rede corporativa ou internet.

## Instalar e testar

Com Docker Desktop ativo, a partir da raiz do projeto:

```powershell
docker compose -f infra/compose.antivirus.yaml up -d
docker compose -f infra/compose.antivirus.yaml ps
python manage.py verificar_antivirus
```

Aguardar o estado healthy: a primeira inicialização e atualização das assinaturas podem levar alguns minutos. O teste envia conteúdo limpo e o padrão inofensivo EICAR em memória; não grava arquivos de teste nem altera o `.env`.

## Ativar no Django executado no Windows

Somente após o teste bem-sucedido, configurar e reiniciar o processo Django:

```dotenv
SISMOD_CLAMAV_HOST=127.0.0.1
SISMOD_CLAMAV_PORT=3310
SISMOD_CLAMAV_REQUIRED=true
```

Com REQUIRED=true, indisponibilidade do serviço bloqueia uploads. Com false, falha de conexão permite continuar sem inspeção: não considerar esse modo proteção garantida. Arquivos detectados e respostas inconclusivas são recusados. O limite de tamanho da inspeção é também imposto pelo daemon; verificar compatibilidade com logs grandes antes de produção.

O Compose define 256 MiB por arquivo/stream e 512 MiB de conteúdo total analisado, com AlertExceedsMax ligado. O Django usa SISMOD_CLAMAV_MAX_BYTES=268435456. Arquivos acima do limite ou cuja análise exceda os limites são recusados, não liberados como seguros. Isso se sobrepõe ao limite de 5 GB do cadastro de mídia da Dock; arquivos maiores exigem uma futura solução assíncrona/quarentena. Não aumentar somente um dos limites nem desligar a proteção para aceitar o arquivo.

Este Compose é independente da infraestrutura de produção. O Compose de produção já inclui serviço ClamAV privado e configura o web/worker com host clamav e inspeção obrigatória. Em Django dentro de container, 127.0.0.1 não aponta para o antivírus. Validar memória disponível (limite local de 3 GB), atualização das assinaturas e monitoramento. Além do middleware HTTP, os backends de armazenamento local/S3 inspecionam antes de persistir e a importação de telemetria reinspeciona antes de interpretar. Escrita direta no filesystem ou uploads diretos de terceiros no bucket não passam por esses backends; não habilitar upload direto sem quarentena e inspeção. Ver [segurança operacional](SEGURANCA_OPERACIONAL.md).

Para parar sem excluir assinaturas: `docker compose -f infra/compose.antivirus.yaml stop`.

Referência: [documentação oficial ClamAV Docker](https://docs.clamav.net/manual/Installing/Docker.html).
