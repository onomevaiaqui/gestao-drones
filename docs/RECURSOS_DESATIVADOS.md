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

## 2.1 DJI Dock 2

**Situação:** modelos, telas, normalização, deduplicação, simulador, consumidor MQTT somente leitura e acompanhamento de retornos de missão implementados; conexão e comandos físicos desativados por configuração.

O ambiente local pode testar o fluxo com `DJI_DOCK_SIMULATOR_ENABLED=true` e `python manage.py simular_dji_dock`. Para a conexão real, mantenha o simulador desligado, instale um broker MQTT 5 com TLS, publique o SISMOD em HTTPS, valide certificados e regras de rede, configure a Dock pelo DJI Pilot 2 e somente então altere `DJI_DOCK_ENABLED=true` e execute `python manage.py consumir_dji_dock` como serviço separado. A conta do consumidor deve ter acesso somente aos tópicos OSD/eventos. Comandos físicos serão implementados em uma fase posterior, com auditoria, confirmação e bloqueios operacionais.

A trava adicional `DJI_DOCK_COMMANDS_ENABLED=false` deve permanecer desligada. A estrutura de auditoria existe, mas não há publicador MQTT para comandos nesta versão; alterar a variável isoladamente não aciona a Dock.

Os retornos de progresso e o catálogo de mídias já podem ser simulados. O download das fotos, vídeos e arquivos PPK permanece desativado: a implantação deverá fornecer armazenamento de objetos privado, HTTPS, credenciais temporárias limitadas e política de retenção antes de habilitar a transferência real.

A entrega do KMZ já possui fingerprint e URL assinada de curta duração, mas não será anunciada ao equipamento enquanto o domínio HTTPS e a publicação de comandos estiverem desativados.

A central, triagem, revisão operacional e prévia da fila funcionam localmente. Toda prévia permanece com situação `bloqueado`, expira automaticamente e não é publicada. O catálogo e upload manual funcionam em armazenamento local, S3 ou MinIO; a emissão de credenciais temporárias para upload direto da Dock continua desativada.

## 3. Sincronização automática de logs DJI

**Situação:** ainda não implementada. O upload manual permanece como método oficial atual.

A fundação Open Platforms não deve ser confundida com sincronização de Flight Records. Para ativar futuramente será necessário implementar o consumidor MQTT, recebimento de eventos de mídia/log, armazenamento assíncrono, deduplicação e associação segura com voo, piloto e drone.

## 4. Integrações Autel

**Situação:** importação manual de CSV e `AUTEL_FR` v3 implementada; sincronização automática e vídeo ao vivo não implementados.

O CSV exportado pelo Autel Enterprise/Autel Sky e o Flight Record binário sem extensão `AUTEL_FR` v3 podem ser enviados pela tela normal. O binário foi validado com EVO II 640T e, por segurança, fornece apenas os campos confirmados nas amostras. Arquivos `.LOG` e pacotes de diagnóstico não são aceitos como registros de voo. Sincronização e vídeo ao vivo exigirão integração própria com Autel Cloud API/SDKs, testes por modelo e controle e credenciais separadas.

## 5. SARPAS

**Situação:** token/API não integrados.

O SISMOD produz planejamento, análise, avaliação de risco e Termo de Coordenação, mas não envia solicitações ao SARPAS. O procedimento oficial continua sendo realizado pelo usuário no sistema do DECEA. Só ativar uma futura integração depois de confirmar documentação, autorização, escopo do token e ambiente de homologação.

## 6. Ambiente de produção

O projeto local usa `DEBUG=True` e SQLite para desenvolvimento. Isso não é uma função a ser simplesmente ligada: antes da publicação é necessário criar configurações de produção com `DEBUG=False`, segredo Django externo, HTTPS, cookies seguros, banco multiusuário, armazenamento de mídia, servidor WSGI/ASGI, monitoramento e backups.

## 7. Fiscalização da licença anual

**Situação:** implementada e desligada no ambiente de desenvolvimento.

Para uma instalação comercial, configure a chave pública Ed25519 do fornecedor em `SISMOD_LICENSE_PUBLIC_KEY`, altere `SISMOD_LICENSE_ENFORCEMENT=true`, reinicie a aplicação e envie a licença anual pela tela administrativa. A chave privada nunca é instalada no cliente. O procedimento completo está em `docs/LICENCIAMENTO_E_IMPLANTACAO.md`.

## Checklist antes de qualquer ativação

- [ ] O recurso está marcado como **implementado** neste documento?
- [ ] Existe servidor HTTPS acessível pelos equipamentos?
- [ ] Segredos estão somente no `.env` do servidor?
- [ ] Firewall, autenticação e logs de auditoria estão configurados?
- [ ] Backup e procedimento de retorno estão definidos?
- [ ] Migrações e `python manage.py check --deploy` foram executados?
- [ ] O teste foi feito primeiro com operação controlada e curta?
- [ ] A documentação técnica foi atualizada no mesmo commit?
