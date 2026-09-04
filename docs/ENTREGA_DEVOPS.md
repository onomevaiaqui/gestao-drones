# SISMOD — entrega para DevOps

Revisão: 04/09/2026. Inventário conferido no código e nos arquivos de infraestrutura. Uma instalação independente por empresa, com administrador inicial, usuários e licença anual. Este documento não declara homologação de produção nem certificação de segurança.

## 1. Arquitetura e bibliotecas

| Tecnologia | Uso |
|---|---|
| Python 3.12, Django 5.x | Aplicação, autenticação, permissões, formulários, ORM, migrations, administração e testes |
| HTML, CSS, JavaScript e templates Django | Interface renderizada pelo servidor; não exige build Node/React |
| Bootstrap 5.3.3 | Componentes e estilos da interface |
| Chart.js | Gráficos; atualmente carregado por CDN sem versão fixada |
| Leaflet 1.9.4, Leaflet-Geoman Free 2.18.0 | Mapas, trajetos e desenho de áreas; o código atual usa Leaflet, não MapLibre |
| SQLite / PostgreSQL 17 | Banco local / banco previsto no Compose de produção |
| psycopg[binary] | Conexão Python com PostgreSQL |
| Gunicorn 23, WhiteNoise | WSGI em Linux e entrega de arquivos estáticos |
| python-dotenv | Configuração por variáveis de ambiente |
| ReportLab, pypdf | Relatórios PDF, avaliação de risco e aplicação do papel timbrado |
| qrcode[pil], Pillow | QR codes para MFA e processamento de imagens |
| cryptography | Criptografia Fernet/MultiFernet para MFA e assinaturas de licença |
| dji-flightlog-parser | Flight Records DJI; revisão Git fixada em requirements.txt |
| pymavlink, pyulog | Logs ArduPilot/Pixhawk e PX4/Wingtra |
| paho-mqtt | Consumidor e publicador MQTT DJI |
| django-storages[s3], boto3 | Armazenamento privado S3/MinIO |
| Docker Engine/Compose, Git/GitHub Actions | Empacotamento, serviços e testes automatizados |

Autel AUTEL_FR v3 possui interpretação própria validada com EVO II 640T. eBee BB3 permanece fora do suporte. Dados ausentes nos logs não devem ser considerados medições reais. Os perfis são usuário, coordenador e administrador; horas oficiais são obtidas da telemetria, não do período reservado.

Dependências transitivas incluem asgiref/sqlparse/tzdata (Django), botocore/s3transfer/jmespath (S3), cffi/pycparser (criptografia), numpy/lxml/fastcrc (parsers), httpx/httpcore/anyio, pydantic e suas dependências. A lista exata da imagem deve ser registrada por `python -m pip freeze` e SBOM no pipeline; requirements.txt contém faixas, não um lock reproduzível completo.

**Divergência detectada no ambiente local:** cryptography instalado é 50.0.0, enquanto requirements.txt limita a versão a >=43,<46. `pip check` não verifica essa divergência com o arquivo. A suíte local não comprova o ambiente de instalação limpa. Antes da promoção, executar o CI/uma instalação limpa com requirements.txt, revisar a faixa e fixar a resolução aprovada. Não copiar o venv Windows para Linux. Django instalado localmente: 5.2.17.

## 2. Serviços de infraestrutura

| Serviço | Definição atual | Observações |
|---|---|---|
| Aplicação | python:3.12-slim; Gunicorn, 3 workers, timeout 120 s | Dockerfile executa collectstatic; web executa migrate no início |
| PostgreSQL | postgres:17-alpine | Volume persistente; não publicar 5432 |
| MinIO + mc | releases 2025-07-23 / 2025-07-21 | Bucket privado sismod-media; não publicar console 9001 |
| Caddy | 2.10-alpine | HTTPS e proxy; três domínios |
| ClamAV | Imagem fixada por digest no Compose | Assinaturas persistentes; limite de memória 3 GB |
| Eclipse Mosquitto | 2.0.22 em homologação | Produção usa broker corporativo externo com TLS/ACL |
| MediaMTX | 1.20.1 | RTMPS/WebRTC; callback de autorização SISMOD |
| Coturn | 4.6.3-r3-alpine | Transporte TURN deve ser homologado; ver ressalva de rede |
| media-guard | Processo Django a cada 15 s | Revoga conexões que perderam autorização; API privada |
| drc-watchdog | Processo Django | Encerra sessões vencidas; não implementa controle físico |
| dock-consumer / command-publisher | Perfil Compose dock-real | Não iniciar antes de homologação e configuração das travas |

FFmpeg é usado apenas na demonstração local, não é necessário para a operação básica. Redis, Celery e Kubernetes não são requisitos atuais. Não existe fila assíncrona geral para processar logs: dimensionar e testar importações grandes frente ao timeout do servidor.

## 3. Rede, domínios e dependências externas

- `sismod.empresa`: aplicação HTTPS; `midia.sismod.empresa`: vídeo; `arquivos.sismod.empresa`: objetos privados com URLs assinadas.
- Caddy publica 80/TCP e 443/TCP+UDP. MediaMTX publica 1936/TCP (RTMPS) e 8189/UDP (WebRTC).
- O Compose atual publica Coturn 3478/TCP e 49160–49200/TCP. Há uma configuração STUN em MediaMTX, mas Coturn está com `--no-udp`, `--no-tls` e `--no-dtls`: **não considerar STUN/UDP ou TURN/TLS prontos**. DevOps deve alinhar transporte, portas de relay, IP externo/NAT e candidatos ICE antes de liberar vídeo externo. Não basta abrir portas sem teste entre redes diferentes.
- MQTT corporativo: conexão de saída TLS, normalmente 8883/TCP. Não expor o broker local 1883 à Internet.
- Não publicar banco, ClamAV 3310, API MediaMTX 9997, métricas 9998 ou console MinIO. A API de mídia não possui autenticação independente no modelo atual: restringir a rede interna e os serviços com acesso.
- DNS, NTP e saída HTTPS são necessários. Fontes usadas incluem Open-Meteo (meteorologia), GeoAISWEB/DECEA (dados aeronáuticos), OpenStreetMap/Nominatim (mapas/busca), DJI Flight Record e CDNs jsDelivr/unpkg. Validar allowlist de egress com os endpoints efetivamente utilizados.
- O navegador também acessa CDNs e mapas. Para rede corporativa restrita, planejar hospedagem interna das bibliotecas, versões fixas e fornecedor de mapas adequado; isso ainda não está implementado.
- Confirmar termos, cotas e contratação das APIs/mapas para uso comercial. A análise SISMOD não substitui autorização SARPAS/SISCLATEN ou decisão do piloto.

## 4. Configuração e segredos

Usar `.env.example` como catálogo completo e `infra/.env.production.example` como base do servidor. Nunca reutilizar valores `troque`/`gere-*`, credenciais de demonstração ou publicar `.env` no Git. O Compose de produção força PostgreSQL em `db`, MinIO, endpoint HTTPS e ClamAV obrigatório, sobrepondo esses valores do arquivo.

Configurar em cofre/arquivo protegido:

1. `SISMOD_SECRET_KEY`, hosts e origens CSRF exatos; `SISMOD_DEBUG=false`.
2. Cookies seguros, redirecionamento HTTPS e HSTS após validar os domínios. Conferir todos os subdomínios antes de habilitar includeSubDomains.
3. `SISMOD_TRUSTED_PROXY_CIDRS` somente para o proxy. Ajustar junto com `SISMOD_PROXY_IP` e `SISMOD_DOCKER_SUBNET`; não confiar em 0.0.0.0/0.
4. Senha PostgreSQL e credenciais privadas S3/MinIO. O Compose usa credenciais root MinIO também para a aplicação: separar conta de serviço com privilégio mínimo antes da produção corporativa.
5. `SISMOD_MFA_ENCRYPTION_KEYS`, com chave Fernet própria; migrar instalações antigas conforme SEGURANCA_OPERACIONAL.md. Preservar chaves de backups históricos.
6. `SISMOD_HEALTHCHECK_TOKEN`. Para vídeo: `SISMOD_MEDIAMTX_AUTH_SECRET`, `SISMOD_TURN_SECRET` distintos e certificados/chave RTMPS montados somente para leitura. A renovação automática do Caddy não atualiza por si só os arquivos montados no MediaMTX; configurar renovação e recarga.
7. `DJI_FLIGHT_RECORD_APP_KEY` para logs DJI que exigem a API. Credenciais Cloud API e MQTT apenas quando esses recursos forem homologados; CA MQTT em `/certificados`, contas consumidor/publicador separadas.
8. Licença: somente chave pública do fornecedor em `SISMOD_LICENSE_PUBLIC_KEY`, `SISMOD_LICENSE_ENFORCEMENT=true` e licença anual válida. Nunca instalar chave privada de emissão no cliente.

Antivírus obrigatório: no modelo de produção uploads ficam indisponíveis até ClamAV estar pronto. Limite efetivo por arquivo: 256 MiB. Mídias maiores exigem projeto de quarentena/inspeção assíncrona; não desabilitar o antivírus como solução.

## 5. Ordem de implantação

1. Preparar homologação Linux isolada, Docker/Compose, disco persistente, DNS/TLS e cofre. Dimensionar por usuários, volume de logs e transmissões simultâneas; não há benchmark de capacidade que estabeleça mínimo garantido.
2. Definir modo de armazenamento: disco local, S3 ou MinIO. O Compose fornecido força MinIO; para outro modo é necessário alterar a configuração/volumes antes de subir, não apenas o .env. Banco e arquivos devem ter backup coordenado.
3. Copiar o exemplo para `.env.production` na raiz e preencher os valores. Conferir o arquivo efetivamente usado por Compose e por `SISMOD_ENV_FILE`; variáveis já exportadas no processo têm precedência sobre dotenv.
4. Validar a configuração (não publicar a saída interpolada com segredos): `docker compose --env-file .env.production -f infra/compose.producao.yaml config --quiet`.
5. Fazer build e subir primeiro a homologação. O Compose completo exige domínios/certificados de vídeo mesmo se as funções DJI estiverem desligadas; para implantação básica sem vídeo, DevOps deve preparar uma variante excluindo mídia/Coturn/media-guard e ajustando o proxy.
6. Executar no serviço web: `python manage.py check --deploy`, `python manage.py makemigrations --check --dry-run`, `python manage.py verificar_implantacao`, `python manage.py verificar_antivirus`. Revisar cada aviso; não ignorar genericamente.
7. Criar administrador com `python manage.py criar_admin_inicial`, ativar licença e cadastrar usuários/perfis. Cadastrar MFA dos administradores, guardar recuperação e só então ligar `SISMOD_MFA_ADMIN_REQUIRED=true`.
8. Migração dos dados locais: planejar janela, exportação controlada, importação PostgreSQL e cópia dos arquivos com verificação de vínculos. Subir o Compose não migra automaticamente SQLite nem media. Não executar comandos de limpeza de testes no banco real.
9. Testar usuário/coordenador/admin, isolamento de permissões, upload real de cada fabricante, bateria/componentes, calendário, pós-voo, planejamento, relatórios e PDFs. Revalidar cálculos, fuso horário e datas.
10. Configurar backup externo criptografado, retenção/RPO/RTO e realizar restauração em banco e bucket separados. O utilitário local de backup cobre SQLite+disco; PostgreSQL/S3 ainda exige ensaio de restauração da equipe.
11. Encaminhar logs ao monitoramento, alertar falhas de auditoria, antivírus, disco, banco, certificado, MQTT e media-guard. O healthcheck de media-guard só comprova alcance da API, não sucesso de toda reconciliação. Não existe SIEM ou e-mail de alerta instalado automaticamente.
12. Promover somente a imagem e a revisão aprovadas. Testar reversão com backup; rollback do código não desfaz migrations automaticamente. Em expansão para múltiplas réplicas, executar migrations em etapa única, não concorrentemente em cada web.

## 6. Ativar agora x manter desligado

| Recurso | Condição |
|---|---|
| Gestão, planejamento, reservas, relatórios, logs manuais | Fluxo principal; homologar no servidor com usuários reais |
| HTTPS, backup, ClamAV, monitoramento | Obrigatórios para operação corporativa |
| MFA administrativo | Ativar obrigatoriedade após cadastro/recuperação testados |
| Licença anual | Ativar na instalação comercial |
| DJI Cloud/Dock | Manter false até credenciais, TLS/MQTT e equipamento homologados |
| Livestream | Manter `DJI_LIVESTREAM_ENABLED=false` inicialmente, mesmo que o exemplo esteja true; liberar após autenticação, revogação e redes externas testadas |
| Comandos físicos/publicador | Manter false e `DJI_DOCK_EMERGENCY_STOP=true` até ensaio controlado |
| DRC/cockpit físico | Relay/autoridade ainda pendentes; não é recurso ativável só por flag |
| Simuladores e HTTP local | Desligados em produção |
| Upload direto de mídias Dock | Desligado até quarentena e inspeção |
| Sincronização automática DJI, API SARPAS, eBee BB3 | Ainda não implementados; manter método manual/procedimento externo |

A autenticação dinâmica exigida pelo equipamento DJI não é automaticamente atendida pelo arquivo de senhas estáticas Mosquitto. Validar a estratégia de autenticação do broker, ACL por estação e compatibilidade antes de conectar a Dock.

## 7. Pendências para aceite corporativo

Não declarar o sistema livre de vulnerabilidades porque os testes passaram. Ainda são necessários: CI limpo com dependências resolvidas, SCA/SBOM e análise de imagens/licenças, fixação de dependências/CDNs, revisão de privilégios dos containers e credenciais MinIO, pentest, carga, observabilidade, restauração PostgreSQL/S3, política de retenção/LGPD e homologação física quando aplicável. O Dockerfile atual não define usuário não-root. Esses pontos são critérios de aceite da implantação, não controles já concluídos.

## 8. Documentos complementares

- [Documentação técnica e referências oficiais](DOCUMENTACAO_TECNICA.md)
- [Licenciamento e implantação](LICENCIAMENTO_E_IMPLANTACAO.md)
- [Segurança operacional e rotação MFA](SEGURANCA_OPERACIONAL.md)
- [Backup e restauração](BACKUP_E_RESTAURACAO.md)
- [Antivírus](ANTIVIRUS_UPLOADS.md)
- [Implantação DJI Dock](IMPLANTACAO_DJI_DOCK.md)
- [Recursos desativados](RECURSOS_DESATIVADOS.md)
- [Pendências de segurança e MQTT](PENDENCIAS_SEGURANCA_MQTT.md)
