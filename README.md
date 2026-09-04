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

O consumidor MQTT somente leitura é iniciado separadamente com `python manage.py consumir_dji_dock`. O ambiente de homologação usa Eclipse Mosquitto com acesso anônimo desativado e ACLs distintas para consumidor e publicador. Em produção, configure o endereço TLS do Mosquitto corporativo em `DJI_CLOUD_MQTT_HOST`; o SISMOD continua recusando iniciar enquanto `DJI_DOCK_ENABLED=false`.

Comandos físicos possuem as travas independentes `DJI_DOCK_COMMANDS_ENABLED=false` e `DJI_DOCK_PUBLISHER_ENABLED=false`, além da parada geral `DJI_DOCK_EMERGENCY_STOP=true`. Intenções críticas também exigem confirmação humana auditada. O publicador de lote existe, porém recusa operar com qualquer trava fechada, estação offline, comando vencido/incompleto ou sem a opção explícita `--confirm-real-publication`. Não o utilize fora de uma homologação física controlada. O processo `python manage.py atualizar_status_dji_docks` marca como offline equipamentos sem contato recente.

Planejamentos podem ser associados a uma Dock pela tela de detalhes e passam por validações preliminares. A geração de WPML executável permanece bloqueada até a confirmação do modelo de aeronave e payload exigidos pela especificação DJI.

Após receber esses identificadores, o administrador ou coordenador pode baixar um KMZ WPML de pré-validação. O arquivo deve ser importado e verificado no DJI Pilot 2 e nunca é enviado automaticamente nesta etapa.

O consumidor também reconhece os retornos oficiais `flighttask_ready`, `flighttask_progress`, `file_upload_callback` e respostas em `services_reply`. Assim, o SISMOD registra situação, percentual, etapa, waypoint e quantidade de mídias da missão, cataloga os metadados dos arquivos e fecha a auditoria de comandos correlacionando o `tid`. Nesta fase, os arquivos não são baixados e nenhum comando é publicado: armazenamento de objetos, credenciais temporárias e publicação continuam desativados até a implantação segura no servidor.

O arquivo WPML destinado à Dock possui geração determinística, fingerprint MD5 exigido pelo protocolo DJI e URL temporária assinada. O MD5 é usado apenas para conferir o conteúdo; a autorização depende da assinatura da URL. A URL somente é criada quando `DJI_CLOUD_PUBLIC_URL` começa com HTTPS e expira conforme `DJI_DOCK_WPML_URL_TTL_SECONDS`.

Antes de uma futura entrada na fila, o administrador deve confirmar em cada missão a altura de retorno, bateria mínima, armazenamento mínimo e comportamento em perda de sinal. O SISMOD monta os dados de `flighttask_prepare` somente após essa confirmação e continua sem publicá-los enquanto as travas da Dock estiverem desligadas.

As telas **Central de missões** e **Mídias das Docks** reúnem situação, progresso, impeditivos, prévias da fila e arquivos. Uploads manuais podem usar disco local, Amazon S3 ou MinIO por `SISMOD_MEDIA_STORAGE`. Arquivos permanecem privados e o download passa pelas permissões do SISMOD.

Para homologação completa em uma única máquina, `infra/compose.homologacao.yaml` prepara Django/Gunicorn, PostgreSQL, EMQX e MinIO. Copie e revise o `.env`, mantenha as travas DJI falsas e execute `docker compose -f infra/compose.homologacao.yaml up -d --build`. Depois, valide com `docker compose -f infra/compose.homologacao.yaml exec web python manage.py verificar_implantacao`.

A infraestrutura definitiva pode ser preparada com `infra/compose.producao.yaml`. Ela inclui HTTPS, MediaMTX autenticado, STUN/TURN, healthchecks e processos da Dock, mantendo a integração física fechada. Consulte [Implantação DJI Dock](docs/IMPLANTACAO_DJI_DOCK.md).

Para iniciar o broker isolado de homologação, abra o Docker Desktop e execute `docker compose -f infra/dji-dock/compose.yaml up -d`. As portas MQTT `1883` e do painel `18083` ficam vinculadas somente a `127.0.0.1`; portanto, a Dock física ainda não consegue acessá-las. Essa exposição será alterada somente junto com TLS, autenticação e firewall.

## Validação

```powershell
python manage.py check
python manage.py test core
```

Cada usuário pode ativar MFA e revisar sessões em **Segurança da conta**. Em produção, depois que todos os administradores cadastrarem o autenticador, defina `SISMOD_MFA_ADMIN_REQUIRED=true`. A tela administrativa **Auditoria** registra alterações e downloads sem armazenar senhas ou conteúdos enviados.

Comandos críticos exigem nova confirmação de senha, e uploads executáveis são recusados. A inspeção ClamAV pode ser habilitada por `SISMOD_CLAMAV_HOST`; use `SISMOD_CLAMAV_REQUIRED=true` somente depois de validar o serviço antivírus no servidor.

O simulador aceita `--cenario normal`, `chuva`, `falha`, `offline`, `missao` ou `midia`; os dois últimos exigem `--missao ID`. A rotina `python manage.py expirar_comandos_dji` encerra prévias de fila vencidas.

O menu **Estações Remotas** concentra Monitoramento, Central de missões, Cockpit Virtual e Mídias. Ele está disponível também para pilotos autorizados pelo administrador em cada estação. O acesso pode ser somente de monitoramento ou incluir operação do cockpit; pilotos visualizam apenas suas próprias missões, mídias e sessões, enquanto auditoria global e configuração permanecem administrativas. O cockpit prioriza o vídeo, apresenta mapa, telemetria sobreposta, painéis de missão/Dock e controles manuais compactos. Atualmente funciona exclusivamente em simulação, audita os canais DJI, mantém um único operador por Dock, neutraliza os manches ao encerrar e usa heartbeat. Os controles de vídeo geram prévias MQTT sanitizadas e correlacionáveis, sem publicar comandos e sem persistir URL, token ou senha de ingestão. Em execução manual, use `python manage.py encerrar_sessoes_drc` como watchdog; o ambiente Docker de homologação já inclui o processo contínuo `drc-watchdog`. Controle físico exige ativação conjunta e consciente de `DJI_DRC_ENABLED`, `DJI_DRC_COMMANDS_ENABLED` e `DJI_DOCK_ENABLED`, além da infraestrutura DRC real que ainda não está implementada.

Cada início de vídeo da estação cria ou reutiliza uma `TransmissaoAoVivo` vinculada ao piloto, aeronave e canal. Quando todas as travas forem habilitadas em servidor, o publicador monta a URL RTMPS apenas em memória, publica o envelope e conserva no banco somente a referência da sessão e a prévia sem URL. A confirmação do broker altera a sessão para ao vivo; o comando de parada a finaliza.

O cockpit possui dois players independentes: vídeo principal da aeronave e câmera fixa da estação. Eles recebem somente endereços públicos HTTPS e apenas quando a sessão correspondente está `ao_vivo`; nos demais estados, a interface mostra o canal e a situação sem criar o iframe externo.

Para uma demonstração exclusivamente local, abra o Docker Desktop e use `docker compose --profile livestream-demo -f infra/compose.homologacao.yaml up -d mediamtx livestream-demo`. No `.env` local, mantenha todas as travas de comando físico desligadas e configure `DJI_LIVESTREAM_ENABLED=true`, `DJI_LIVESTREAM_ALLOW_INSECURE_LOCAL=true`, `DJI_LIVESTREAM_RTMP_BASE_URL=rtmp://127.0.0.1:1935`, `DJI_LIVESTREAM_PLAYBACK_BASE_URL=http://127.0.0.1:8889` e `SISMOD_MEDIAMTX_API_URL=http://127.0.0.1:9997`. Depois, execute `python manage.py preparar_demo_livestream --canal ID --usuario USUARIO`. A exceção HTTP/RTMP só funciona com `DEBUG=True`, flag local explícita e host loopback; não é aceita em produção.

Quando a estação anuncia `live_capacity`, o SISMOD cataloga automaticamente os canais de vídeo da aeronave e da própria Dock, incluindo identificador DJI, câmera, lente atual e lentes alternativas. Usuários com autorização de operação podem simular início, parada, qualidade e troca de lente; cada ação fica na auditoria de comandos. O catálogo e esses controles apenas preparam os players: streams reais permanecem bloqueados até a implantação do servidor de mídia e do publicador MQTT.

## Documentação

- [Documentação técnica completa](docs/DOCUMENTACAO_TECNICA.md)
- [Política obrigatória de atualização](docs/MANUTENCAO_DOCUMENTACAO.md)
- [Inventário de arquivos legados](docs/ARQUIVOS_LEGADOS.md)
- [Licenciamento anual e implantação por empresa](docs/LICENCIAMENTO_E_IMPLANTACAO.md)
- [Implantação DJI Dock e livestream](docs/IMPLANTACAO_DJI_DOCK.md)

## Situação atual

O projeto usa Python 3.12, Django 5.2 e SQLite para desenvolvimento local. A configuração atual não deve ser usada diretamente em produção; consulte a seção de implantação e segurança da documentação técnica.
# Antivírus opcional dos uploads

Instalação local, teste e ativação do ClamAV: [guia de antivírus](docs/ANTIVIRUS_UPLOADS.md). A instalação não altera automaticamente o `.env`.
