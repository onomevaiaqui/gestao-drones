# Preparação de produção — DJI Dock e livestream

**Estado: modelo de implantação ainda não homologado em servidor.** Os testes locais e validação sintática do Compose não certificam a integração completa. Antes de usar o roteiro abaixo, validar: cabeçalhos/hosts dos healthchecks e callback HTTP interno do MediaMTX diante do redirecionamento HTTPS do Django; disponibilidade do executável do healthcheck na imagem MediaMTX; montagem da CA MQTT; endereço público de objetos MinIO; proteção de tokens nos logs do proxy; autenticação dinâmica DJI com Mosquitto e renovação/revogação dos tokens de vídeo. Não ativar comandos físicos sem resolver esses pontos e realizar homologação em campo.

O arquivo `infra/compose.producao.yaml` reúne Django/Gunicorn, PostgreSQL, MinIO, MediaMTX, Coturn, Caddy, consumidor MQTT, watchdog e publicador. Nenhuma integração física é ativada automaticamente.

## O que já fica preparado

1. Stack de produção com volumes, healthchecks e reinício automático.
2. HTTPS no Caddy e ingestão RTMPS no MediaMTX.
3. Vídeo autenticado por tokens assinados e temporários validados pelo SISMOD.
4. STUN/TURN com Coturn, segredo compartilhado e relay TCP limitado.
5. Diagnóstico do Django, banco, armazenamento e MediaMTX.
6. Travas de comandos, parada de emergência, autorização humana, expiração e intervalo mínimo.
7. Testes com `verificar_implantacao` e `check --deploy`.
8. Modelo de configuração em `infra/.env.production.example`, sem segredos reais.

## Ativação no servidor

1. Aponte `SISMOD_DOMAIN` e `SISMOD_MEDIA_DOMAIN` para o servidor.
2. Copie `infra/.env.production.example` para `.env.production` na raiz e substitua todos os valores de exemplo.
3. Disponibilize o certificado e a chave da ingestão RTMPS nos caminhos indicados.
4. Abra 80/443 TCP/UDP, 1936 TCP, 8189 UDP, 3478 TCP e 49160–49200 TCP. Restrinja a ingestão às origens DJI quando possível.
5. Valide sem iniciar serviços com `powershell -ExecutionPolicy Bypass -File infra/validar-producao.ps1`. O script também confere Django e migrations.
6. Inicie sem a Dock real com `docker compose --env-file .env.production -f infra/compose.producao.yaml up -d --build`.
7. No contêiner web, execute `python manage.py verificar_implantacao` e `python manage.py check --deploy`.
8. Teste login, player e uma transmissão curta antes de configurar a Dock.

## Ordem segura para comandos

As flags começam fechadas. Valide primeiro a telemetria somente leitura. Em homologação física controlada, habilite as três flags DJI; mantenha `DJI_DOCK_EMERGENCY_STOP=true` até a confirmação final da equipe no local. Para interromper, restaure a parada e reinicie o publicador.

Ainda dependem do servidor: DNS, certificados, NAT/firewall, MQTT TLS e ACL, credenciais DJI, pareamento da Dock, teste de campo, backup externo e monitoramento corporativo.

## Mosquitto corporativo

A homologação usa `eclipse-mosquitto` sem acesso anônimo. `sismod-consumer` possui somente leitura nos tópicos de estado, telemetria, eventos e respostas; `sismod-publisher` possui escrita apenas nos tópicos de serviço/DRC e leitura das respostas. Em produção o Compose não cria outro broker: informe o Mosquitto corporativo por `ssl://host:8883`, CA confiável e credenciais separadas. A equipe de infraestrutura deve reproduzir as ACLs de `infra/mosquitto/acl.conf`, ajustar os tópicos confirmados na homologação DJI e negar todo o restante.

Referências: [MediaMTX authentication](https://mediamtx.org/docs/features/authentication), [MediaMTX WebRTC/STUN/TURN](https://mediamtx.org/docs/features/webrtc-specific-features) e [Coturn](https://github.com/coturn/coturn).
