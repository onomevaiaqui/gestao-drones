# SISMOD — Sistema de Monitoramento de Drones

Aplicação web para planejar operações, reservar aeronaves, avaliar riscos, importar telemetria, controlar pilotos, frota, documentos, inspeções, manutenção e produzir relatórios.

## Início rápido no Windows

Requisitos: Python 3.12 e Git.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py criar_admin_inicial
python manage.py runserver
```

Acesse `http://127.0.0.1:8000/`.

Cada empresa utiliza uma instalação independente. O primeiro administrador é criado pelo comando acima e cria os demais usuários pela interface. Em produção, a licença anual offline é ativada em **Administração > Licença**; consulte o [guia de licenciamento e implantação](docs/LICENCIAMENTO_E_IMPLANTACAO.md).

Para ler logs binários DJI, preencha `DJI_FLIGHT_RECORD_APP_KEY` no arquivo `.env`. Nunca envie esse arquivo ao GitHub.

Registros de voo Autel podem ser importados em CSV exportado pelo aplicativo ou diretamente no formato binário sem extensão `AUTEL_FR` v3. A leitura binária foi validada com amostras reais do EVO II 640T e extrai horário, rota, altitude, velocidade e seriais confirmados. Arquivos `.LOG` de diagnóstico não são Flight Records. Valide outros modelos e firmwares com uma amostra real antes do uso operacional.

Controladoras Pixhawk são aceitas nos formatos nativos dos dois principais firmwares: DataFlash `.BIN` do ArduPilot e `.ULG` do PX4. As dependências `pymavlink` e `pyulog` fazem a leitura binária; a compatibilidade deve ser validada com um log real do firmware e da configuração utilizada.

WingtraOne/WingtraRAY usam registros `.ULG`. O SISMOD aceita também a variante Wingtra ULog v2 com CRC por mensagem, validada com um voo real do WingtraRAY. O tópico `bms_data` identifica separadamente as duas baterias físicas, incluindo serial, ciclos e saúde, e gera um alerta de cadastro para cada unidade nova. Importe o arquivo nomeado pelo voo, como `VooRGB Flight 01.ulg`; arquivos `sess*_fmu` e `sess*_fts` são registros técnicos complementares e não devem ser importados junto com o principal. O suporte ao senseFly eBee está desativado nesta etapa: os BB3 reais são proprietários e não serão aceitos sem um decodificador oficial confiável.

A conexão DJI Open Platforms é configurada por variáveis `DJI_CLOUD_*` descritas no `.env.example`. Ela permanece bloqueada por padrão com `DJI_CLOUD_ENABLED=false`, sem afetar a importação manual de logs. Depois de publicar o SISMOD em HTTPS e concluir a infraestrutura, o administrador poderá ativá-la pela variável de ambiente. As credenciais reais permanecem apenas no `.env` ou no gerenciador de segredos do servidor.

A base da DJI Dock 2 também pode ser validada localmente sem comandar equipamento. Defina `DJI_DOCK_SIMULATOR_ENABLED=true`, execute `python manage.py simular_dji_dock` e consulte **Estações Remotas > Monitoramento**. A conexão real permanece independente e desligada por `DJI_DOCK_ENABLED=false`.

O consumidor MQTT somente leitura é iniciado separadamente com `python manage.py consumir_dji_dock`. Ele exige `paho-mqtt`, broker, credenciais e tópicos configurados, e recusa iniciar enquanto `DJI_DOCK_ENABLED=false`.

Comandos físicos possuem uma segunda trava, `DJI_DOCK_COMMANDS_ENABLED=false`, e não têm publicador nesta versão. O processo `python manage.py atualizar_status_dji_docks` marca como offline equipamentos sem contato recente.

Planejamentos podem ser associados a uma Dock pela tela de detalhes e passam por validações preliminares. A geração de WPML executável permanece bloqueada até a confirmação do modelo de aeronave e payload exigidos pela especificação DJI.

Após receber esses identificadores, o administrador ou coordenador pode baixar um KMZ WPML de pré-validação. O arquivo deve ser importado e verificado no DJI Pilot 2 e nunca é enviado automaticamente nesta etapa.

O consumidor também reconhece os retornos oficiais `flighttask_ready`, `flighttask_progress`, `file_upload_callback` e respostas em `services_reply`. Assim, o SISMOD registra situação, percentual, etapa, waypoint e quantidade de mídias da missão, cataloga os metadados dos arquivos e fecha a auditoria de comandos correlacionando o `tid`. Nesta fase, os arquivos não são baixados e nenhum comando é publicado: armazenamento de objetos, credenciais temporárias e publicação continuam desativados até a implantação segura no servidor.

O arquivo WPML destinado à Dock possui geração determinística, fingerprint MD5 exigido pelo protocolo DJI e URL temporária assinada. O MD5 é usado apenas para conferir o conteúdo; a autorização depende da assinatura da URL. A URL somente é criada quando `DJI_CLOUD_PUBLIC_URL` começa com HTTPS e expira conforme `DJI_DOCK_WPML_URL_TTL_SECONDS`.

Antes de uma futura entrada na fila, o administrador deve confirmar em cada missão a altura de retorno, bateria mínima, armazenamento mínimo e comportamento em perda de sinal. O SISMOD monta os dados de `flighttask_prepare` somente após essa confirmação e continua sem publicá-los enquanto as travas da Dock estiverem desligadas.

As telas **Central de missões** e **Mídias das Docks** reúnem situação, progresso, impeditivos, prévias da fila e arquivos. Uploads manuais podem usar disco local, Amazon S3 ou MinIO por `SISMOD_MEDIA_STORAGE`. Arquivos permanecem privados e o download passa pelas permissões do SISMOD.

Para homologação completa em uma única máquina, `infra/compose.homologacao.yaml` prepara Django/Gunicorn, PostgreSQL, EMQX e MinIO. Copie e revise o `.env`, mantenha as travas DJI falsas e execute `docker compose -f infra/compose.homologacao.yaml up -d --build`. Depois, valide com `docker compose -f infra/compose.homologacao.yaml exec web python manage.py verificar_implantacao`.

Para iniciar o broker isolado de homologação, abra o Docker Desktop e execute `docker compose -f infra/dji-dock/compose.yaml up -d`. As portas MQTT `1883` e do painel `18083` ficam vinculadas somente a `127.0.0.1`; portanto, a Dock física ainda não consegue acessá-las. Essa exposição será alterada somente junto com TLS, autenticação e firewall.

## Validação

```powershell
python manage.py check
python manage.py test core
```

O simulador aceita `--cenario normal`, `chuva`, `falha`, `offline`, `missao` ou `midia`; os dois últimos exigem `--missao ID`. A rotina `python manage.py expirar_comandos_dji` encerra prévias de fila vencidas.

O menu **Estações Remotas** concentra Monitoramento, Central de missões, Cockpit Virtual e Mídias. Ele está disponível também para pilotos, que visualizam suas próprias missões, mídias e sessões; auditoria global e configuração permanecem administrativas. O cockpit prioriza o vídeo, apresenta mapa, telemetria sobreposta, painéis de missão/Dock e controles manuais compactos. Atualmente funciona exclusivamente em simulação, audita os canais DJI, mantém um único operador por Dock, neutraliza os manches ao encerrar e usa heartbeat. Execute `python manage.py encerrar_sessoes_drc` periodicamente como watchdog. Controle físico exige ativação conjunta e consciente de `DJI_DRC_ENABLED`, `DJI_DRC_COMMANDS_ENABLED` e `DJI_DOCK_ENABLED`, além da infraestrutura DRC real que ainda não está implementada.

## Documentação

- [Documentação técnica completa](docs/DOCUMENTACAO_TECNICA.md)
- [Política obrigatória de atualização](docs/MANUTENCAO_DOCUMENTACAO.md)
- [Inventário de arquivos legados](docs/ARQUIVOS_LEGADOS.md)
- [Licenciamento anual e implantação por empresa](docs/LICENCIAMENTO_E_IMPLANTACAO.md)

## Situação atual

O projeto usa Python 3.12, Django 5.2 e SQLite para desenvolvimento local. A configuração atual não deve ser usada diretamente em produção; consulte a seção de implantação e segurança da documentação técnica.
