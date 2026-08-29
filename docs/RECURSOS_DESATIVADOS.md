# Recursos desativados e ativação

Este documento registra funções opcionais ou externas que não operam integralmente no ambiente local. Nunca coloque chaves, senhas ou tokens neste arquivo: valores reais pertencem exclusivamente ao `.env` do servidor.

## 1. DJI Open Platforms / Cloud API

**Situação:** implementada e desativada por padrão.

Permite conectar o DJI Pilot 2 ao SISMOD, identificar piloto, controle e aeronave e preparar MQTT e livestream. A importação manual de logs não depende dessa integração.

Antes de ativar:

1. publicar o SISMOD em domínio HTTPS;
2. usar banco de produção e configurar backup;
3. instalar e proteger um broker MQTT, sem acesso anônimo;
4. preencher no `.env` do servidor as credenciais Cloud API, UUID do workspace, URLs públicas e broker;
5. cadastrar o número de série de cada aeronave;
6. validar o portal no DJI Pilot 2;
7. alterar `DJI_CLOUD_ENABLED=true` e reiniciar a aplicação.

Não habilite a chave geral somente para testar em `localhost`: o controle precisa alcançar o domínio publicado.

## 2. Livestream DJI

**Situação:** implementada no SISMOD e desativada por padrão; depende de infraestrutura externa.

Mesmo desativados, o menu, os agendamentos no planejamento e o histórico podem ser validados localmente. O botão de início real permanece indisponível até que Open Platforms e servidor de mídia estejam prontos. Isso impede tentativa acidental de conexão externa durante desenvolvimento.

Antes de ativar:

1. concluir a ativação do DJI Open Platforms;
2. instalar MediaMTX, SRS ou serviço equivalente em um servidor público;
3. publicar ingestão RTMPS e reprodução WebRTC por HTTPS;
4. restringir publicação e visualização por autenticação, firewall e reverse proxy;
5. preencher:

```dotenv
DJI_LIVESTREAM_RTMP_BASE_URL=rtmps://midia.exemplo.com/live
DJI_LIVESTREAM_PLAYBACK_BASE_URL=https://midia.exemplo.com
DJI_LIVESTREAM_ENABLED=true
```

6. reiniciar a aplicação;
7. verificar **Integração DJI** no perfil administrador;
8. fazer um teste de curta duração com o controle, conferindo imagem, latência, consumo de dados e encerramento da sessão.

O endereço de ingestão é entregue somente ao DJI Pilot 2. Coordenadores recebem apenas o endereço de reprodução. A chave aleatória do stream não substitui autenticação do servidor de mídia.

## 3. Sincronização automática de logs DJI

**Situação:** ainda não implementada. O upload manual permanece como método oficial atual.

A fundação Open Platforms não deve ser confundida com sincronização de Flight Records. Para ativar futuramente será necessário implementar o consumidor MQTT, recebimento de eventos de mídia/log, armazenamento assíncrono, deduplicação e associação segura com voo, piloto e drone.

## 4. Integrações Autel

**Situação:** não implementadas.

Logs compatíveis podem continuar sendo enviados manualmente quando houver parser reconhecido. Sincronização e vídeo ao vivo exigirão integração própria com os produtos e SDKs Autel, testes por modelo e controle e credenciais separadas.

## 5. SARPAS

**Situação:** token/API não integrados.

O SISMOD produz planejamento, análise, avaliação de risco e Termo de Coordenação, mas não envia solicitações ao SARPAS. O procedimento oficial continua sendo realizado pelo usuário no sistema do DECEA. Só ativar uma futura integração depois de confirmar documentação, autorização, escopo do token e ambiente de homologação.

## 6. Ambiente de produção

O projeto local usa `DEBUG=True` e SQLite para desenvolvimento. Isso não é uma função a ser simplesmente ligada: antes da publicação é necessário criar configurações de produção com `DEBUG=False`, segredo Django externo, HTTPS, cookies seguros, banco multiusuário, armazenamento de mídia, servidor WSGI/ASGI, monitoramento e backups.

## Checklist antes de qualquer ativação

- [ ] O recurso está marcado como **implementado** neste documento?
- [ ] Existe servidor HTTPS acessível pelos equipamentos?
- [ ] Segredos estão somente no `.env` do servidor?
- [ ] Firewall, autenticação e logs de auditoria estão configurados?
- [ ] Backup e procedimento de retorno estão definidos?
- [ ] Migrações e `python manage.py check --deploy` foram executados?
- [ ] O teste foi feito primeiro com operação controlada e curta?
- [ ] A documentação técnica foi atualizada no mesmo commit?
