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

Este Compose é independente da infraestrutura de produção. Em Django dentro de container, 127.0.0.1 não aponta para o antivírus: conectar ambos em rede Docker privada e usar o nome do serviço, sem publicar a porta. Validar memória disponível (limite local de 3 GB), atualização das assinaturas, monitoramento e todos os caminhos de entrada de arquivos, inclusive integrações e tarefas em segundo plano. O middleware atual cobre uploads multipart das rotas web; não garante inspeção de arquivos obtidos por outros meios.

Para parar sem excluir assinaturas: `docker compose -f infra/compose.antivirus.yaml stop`.

Referência: [documentação oficial ClamAV Docker](https://docs.clamav.net/manual/Installing/Docker.html).
