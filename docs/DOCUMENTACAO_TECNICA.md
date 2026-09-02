# Documentação técnica do SISMOD

Versão documental: 1.5
Última revisão: 31/08/2026

## 1. Finalidade

O SISMOD — Sistema de Monitoramento de Drones — centraliza o ciclo operacional de aeronaves remotamente pilotadas:

1. planejamento geográfico e meteorológico;
2. reserva de aeronave;
3. avaliação de risco operacional quando necessária;
4. calendário e checklist pré-voo;
5. importação manual dos logs;
6. telemetria, rota, alertas e indicadores;
7. pós-voo, incidentes e manutenção;
8. pilotos, qualificações, documentos, baterias e componentes;
9. relatórios e dashboards gerenciais.

O sistema auxilia a gestão. As análises meteorológicas, aeronáuticas, SARPAS e SISCLATEN são triagens e não substituem autorizações, publicações oficiais ou verificação local.

## 2. Tecnologias e funções

### Plataforma

| Tecnologia | Versão usada | Função no SISMOD |
|---|---:|---|
| Python | 3.12 | Linguagem do servidor, regras de negócio, arquivos e testes. |
| Django | 5.2.x | Autenticação, banco, formulários, rotas, templates, migrations, CSRF e painel administrativo. |
| SQLite | biblioteca do Python | Banco de desenvolvimento e testes locais. `db.sqlite3` não é versionado. |
| HTML/CSS/JavaScript | navegador | Interface, formulários, tabelas, mapas e gráficos. |
| Git/GitHub | repositório | Histórico e recuperação do código; substitui backups locais de código. |

### Dependências Python diretas

| Pacote | Para que serve |
|---|---|
| `Django` | Framework da aplicação web e acesso ao banco pelo ORM. |
| `python-dotenv` | Carrega segredos e configurações locais do `.env`. |
| `dji-flightlog-parser` | Decodifica Flight Records binários DJI antes da normalização. |
| `pymavlink` | Lê logs DataFlash `.BIN` produzidos pelo ArduPilot em controladoras Pixhawk. |
| `pyulog` | Lê logs `.ULG` produzidos pelo PX4 em controladoras Pixhawk. |
| `reportlab` | Gera PDFs de relatórios e avaliações de risco. |
| `pypdf` | Lê, combina e aplica papel timbrado aos PDFs. |
| `qrcode[pil]` | Gera QR Codes de componentes. |
| `Pillow` | Suporte a imagens, fotos e QR Code. |
| `cryptography` | Valida assinaturas Ed25519 das licenças anuais offline. |

Pacotes como `asgiref`, `sqlparse`, `httpx` e `pydantic` são dependências transitivas instaladas pelos pacotes diretos. Não devem ser removidos manualmente do ambiente virtual.

### Interface e mapas

| Biblioteca/serviço | Para que serve |
|---|---|
| Bootstrap 5.3.3 | Componentes e layout responsivo. |
| Chart.js | Gráficos das dashboards. |
| Leaflet 1.9.4 | Mapas de telemetria, planejamento e operações. |
| Leaflet-Geoman 2.18 | Desenho/edição de polígonos no planejamento. |
| OpenStreetMap | Mapa-base cartográfico. |

Esses recursos são carregados por CDN. Sem internet, o servidor local abre, mas mapas, gráficos ou estilos externos podem ficar indisponíveis.

## 3. Integrações e fontes externas

| Fonte | Uso | Limite/observação |
|---|---|---|
| Open-Meteo | Vento, rajada, chuva, visibilidade e estimativa de neblina. | Previsão de modelo, não medição local. |
| Nominatim / OSM | Pesquisa de local e centralização do mapa. | Respeitar política de uso. |
| GeoAISWeb / DECEA | Aeródromos e áreas aeronáuticas de atenção. | Confirmar no AISWEB/SARPAS. |
| SARPAS | Link para consulta/autorização. | Token de integração ainda não implementado. |
| SISCLATEN | Triagem para aerolevantamento/AAFA. | Decisão oficial é do Ministério da Defesa. |
| DJI Flight Record Parsing | Decodificação mediante chave no ambiente. | Interpreta o arquivo; não realiza sincronização da conta. |
| DJI Open Platforms / Cloud API | Conexão do DJI Pilot 2 diretamente ao SISMOD. | Fundação implementada; broker e ingestão MQTT são a próxima etapa. |

KML/KMZ pode ser importado no planejamento; o maior polígono encontrado é usado. A área desenhada pode ser exportada em KML.

## 4. Estrutura do projeto

```text
gestao_drones/
├── config/                 configurações, URLs, WSGI e ASGI
├── core/                   domínio e regras do SISMOD
│   ├── models.py           estrutura persistida e propriedades
│   ├── *_forms.py          formulários e validação
│   ├── *_views.py          telas e permissões HTTP
│   ├── operacao_service.py períodos, conflitos e normalização operacional
│   ├── reserva_service.py  estado temporal de reservas e disponibilidade da frota
│   ├── permissoes.py       políticas de administrador, coordenador e usuário
│   ├── geo_utils.py        cálculos geográficos compartilhados
│   ├── *_service.py        demais regras reutilizáveis e integrações
│   ├── migrations/         evolução versionada do banco
│   ├── management/         comandos administrativos
│   └── tests.py            testes automatizados
├── templates/              páginas HTML por módulo
├── static/                 CSS, imagens e recursos locais
├── media/                  uploads; não versionados
├── docs/                   documentação mantida com o código
├── requirements.txt        dependências Python
├── .env.example            variáveis sem segredos
└── manage.py               comandos do Django
```

## 5. Módulos funcionais

### Autenticação e perfis

- login e primeiro acesso;
- alteração de senha e edição do perfil pessoal, foto, CPF, matrícula e código SARPAS;
- habilitações, certificados, cursos e registros estruturados anteriores são apresentados em uma única seção chamada **Qualificações Operacionais**;
- o piloto cadastra a qualificação anexando o comprovante e escolhendo uma classificação existente; emissão e validade são opcionais e controladas por seleções independentes;
- os relatórios não ficam dentro do perfil: a central **Relatórios**, em Segurança e conformidade, reúne relatório operacional, perfil operacional individual e relatório de incidentes;
- o próprio piloto e o administrador podem baixar ou visualizar o PDF individual, contendo identificação, experiência comprovada por telemetria, qualificações e documentos;
- administrador pode escolher o modo Administrador, Coordenador ou Usuário no mesmo login;
- coordenador nativo entra diretamente no modo de consulta.
- desativar um piloto também desativa a conta Django correspondente e encerra sessões ainda abertas; reativar o cadastro reabilita o login.

A identidade visual do menu autenticado reutiliza a mesma marca institucional branca apresentada na tela de login.

### Dashboard

O conteúdo é separado pelo modo de acesso, mantendo uma única regra de cálculo para horas, distância e voos comprovados:

- **Usuário/piloto:** próxima operação, pendências pessoais priorizadas, horas e distância provenientes da telemetria, situação das próprias qualificações, atalhos operacionais, evolução mensal e histórico recente;
- **Coordenador:** operações em andamento e futuras, mapa operacional clicável, situação da equipe, utilização das aeronaves, inspeções e documentos que exigem atenção, segurança operacional e indicadores comparativos;
- **Administrador:** visão executiva global, integridade dos registros, conformidade dos logs, frota e disponibilidade, manutenção, documentos, incidentes e diagnóstico técnico da integração DJI.

Regras comuns:

- métricas de atividade usam somente voos comprovados por logs processados;
- a linha da agenda do coordenador centraliza a área planejada no mapa;
- alertas de regularização permanecem visíveis até planejamento, checklist e pós-voo serem concluídos;
- os filtros de período alteram os gráficos sem alterar a identidade do perfil selecionado;
- dados de outros pilotos não são enviados à dashboard do modo Usuário.

### Planejamento de voo

- desenho de área fechada e cálculo aproximado;
- período completo com data/hora inicial e data/hora final;
- busca de cidades, endereços e pontos de interesse públicos (portos, igrejas, parques e outros locais do OpenStreetMap), além de importação/exportação KML/KMZ;
- meteorologia, estimativa de neblina e camadas aeronáuticas;
- raios de atenção e triagem SISCLATEN;
- camadas aeronáuticas são informativas durante o desenho e não bloqueiam o polígono; as interseções são avaliadas após salvar;
- data, horário, região e finalidade reaproveitados na reserva.

### Reservas, calendário e checklist

- reserva representa disponibilidade prevista, não voo realizado;
- possui data/hora inicial e data/hora final, inclusive para períodos com mais de um dia;
- permite escolher vários drones por caixas de seleção; é criada uma reserva independente por aeronave;
- reserva comum é liberada sem aprovação administrativa;
- quando exigida, a avaliação de risco é preenchida e aceita pelo piloto;
- calendário impede sobreposição de períodos da mesma aeronave e exibe reservas em todos os dias abrangidos;
- checklist concluído só pode ser alterado pelo administrador.
- criação e edição usam exclusivamente **Reservas de drones**; o calendário encaminha operações vinculadas para essa mesma origem, evitando divergência entre `SolicitacaoVoo` e `Alocacao`;
- alocações antigas sem solicitação vinculada continuam editáveis como registros legados até sua regularização.

As validações de período e conflito são únicas para formulário de reserva, calendário e liberação. A situação temporal da reserva também é a única fonte para atualizar automaticamente a disponibilidade do drone. Isso evita que telas diferentes interpretem a mesma operação de maneiras distintas.

### Cadastro da frota

- na edição de uma aeronave, alterações cadastrais e um novo documento são enviados pelo mesmo formulário;
- a gravação é atômica: drone e documento são salvos juntos, evitando atualização parcial;
- se houver erro no documento, os dados digitados no cadastro permanecem preenchidos para correção antes do novo envio;
- documentos já cadastrados continuam listados e podem ser consultados ou removidos separadamente.

### Baterias e ciclos

- o número de série do Flight Record vincula automaticamente cada uso à bateria cadastrada;
- voos detectados são contados pelos logs concluídos e distintos, sem depender de lançamento manual no pós-voo;
- quando o parser DJI fornece `BATTERY.cycleCount`, o SISMOD grava o contador real mais recente da própria bateria;
- ciclos anteriores informados manualmente e voos detectados formam uma estimativa separada, usada somente quando o log não fornece o contador real;
- a interface identifica claramente a origem como **ciclos reais pelo log** ou **ciclos estimados**; um voo não é apresentado como se fosse necessariamente um ciclo completo;
- o comando `python manage.py sincronizar_ciclos_baterias` relê, sem modificar a telemetria, os logs existentes das baterias ainda sem contador detectado.

### Equipamentos detectados nos logs

- equipamentos e componentes possuem localização física opcional, exibida no inventário e pesquisável pelo filtro geral;
- Flight Records DJI podem fornecer seriais de câmera/payload, gimbal, RTK e outros componentes reconhecidos pelo parser;
- cada serial é armazenado na importação e comparado com o inventário de equipamentos;
- antes do alerta, o sistema verifica a plataforma: câmeras/gimbals integrados das famílias Mavic 3, Mini 3/4, Matrice 4 e Matrice 30 não exigem cadastro separado; no Matrice 300/350 são tratados como payloads intercambiáveis;
- módulos RTK detectados continuam cadastráveis, enquanto controles remotos são ignorados porque não são payloads da aeronave;
- em modelos ainda não classificados, o aviso é preservado para não ocultar um equipamento real;
- um serial destacável ainda não cadastrado gera alerta persistente na central e na telemetria até o administrador concluir o cadastro;
- o formulário abre com serial, fabricante, aeronave, tipo e nome genérico já preenchidos; o administrador confirma o nome comercial, como Zenmuse L1 ou Manifold, quando o log não o informa;
- o cadastro por serial elimina o alerta sem criar automaticamente um equipamento potencialmente incorreto;
- `python manage.py sincronizar_componentes_logs` relê logs existentes e preenche apenas os metadados de acessórios, sem alterar pontos GPS ou trajetos.

Na Central de Alertas, **Resolver** abre a origem da pendência para correção. O botão **Resolvido** encerra o alerta imediatamente e registra a chave, o administrador e a data da ação, sem exigir a edição do cadastro de origem.

O piloto pode adicionar e editar as próprias qualificações operacionais, incluindo classificação, referência, datas, comprovante e observações. A verificação de propriedade impede a alteração de qualificações pertencentes a outro usuário; administradores mantêm acesso global.

Limitação: nem todo firmware registra acessórios externos, e o Flight Record frequentemente informa apenas a categoria e o serial, não o nome comercial. Assim, a ausência do Manifold ou de outro payload no log não comprova que ele não foi utilizado.

### Organização da navegação operacional

O menu segue o ciclo de trabalho, sem criar registros paralelos:

1. **Visão geral:** dashboard e agenda;
2. **Preparação:** planejamentos, reservas e calendário;
3. **Operações realizadas:** voos comprovados e logs/telemetria.

Na listagem de planejamentos, as operações são apresentadas da data e horário mais recentes para os mais antigos, mantendo os registros atuais no topo.

Ao selecionar um arquivo KML ou KMZ no formulário, o polígono é interpretado e exibido imediatamente no mapa, sem exigir o salvamento prévio. O piloto pode conferir ou ajustar a geometria antes de consultar a previsão.

Após salvar e consultar, a análise aeronáutica elimina aeródromos e helipontos que não intersectem a zona de triagem aplicável ao polígono e mantém apenas interseções com FRZ/EAC. Itens que exigem coordenação recebem marcador **T** no mapa e no cartão. O piloto pode abrir um Termo de Coordenação vinculado à condicionante, preencher os blocos do modelo oficial do DECEA e baixar o PDF para assinatura e envio no SARPAS. Áreas proibidas permanecem impeditivas: o termo não substitui a proibição.

O comando `python manage.py atualizar_condicionantes_planejamentos` reaplica essa regra aos planejamentos antigos, preservando geometria, meteorologia e SISCLATEN. Para atualizar apenas um registro, use `--planejamento ID`.

Em **Segurança e conformidade**, a navegação principal aponta para a central de relatórios. A gestão de incidentes continua disponível a partir do relatório de incidentes, evitando dois itens concorrentes no menu lateral.

O registro manual de voo permanece disponível internamente por compatibilidade administrativa, mas não é apresentado como ação principal. A ação normal para comprovar um voo é importar a telemetria vinculada à reserva.

### Transição e sincronização operacional

As transições que envolvem `SolicitacaoVoo`, `Alocacao`, `Voo`, `RegistroPosVoo`, `DroneHistorico` e `Manutencao` são executadas pelos serviços operacionais em transações de banco. A conclusão do pós-voo:

- reutiliza o voo já relacionado à reserva;
- conclui reserva e solicitação;
- atualiza a aeronave para manutenção quando indicado;
- registra a mudança de status apenas quando ela realmente ocorre;
- cria uma inspeção somente quando não existe outra manutenção aberta.

Repetir a gravação administrativa de um pós-voo não deve gerar outro voo, outro histórico idêntico ou outra manutenção aberta.

### Documentos

Documentos gerais, de pilotos e de aeronaves utilizam o mesmo modelo e a mesma validação de arquivo. Os formulários contextuais continuam distintos para ocultar campos que o usuário não precisa preencher, mas compartilham widgets, limite de 10 MB e mensagens de validação.

### Baterias reconhecidas pela telemetria

- a distância do pós-voo é preenchida pela soma dos logs concluídos vinculados ao voo;
- a quantidade de baterias corresponde aos números de série distintos encontrados nesses logs;
- baterias já cadastradas são vinculadas automaticamente ao registro pós-voo pelo número de série;
- um serial desconhecido gera aviso na telemetria e no pós-voo;
- o administrador pode abrir o cadastro com serial, fabricante, aeronave e sugestão de código já preenchidos;
- importar novos logs depois do pós-voo atualiza distância, quantidade e vínculos automaticamente.

O sistema não presume baterias que não estejam identificadas pelo arquivo. Alguns equipamentos podem usar conjuntos com várias unidades físicas, mas expor somente um serial no Flight Record; nesses casos, o indicador representa apenas os seriais efetivamente fornecidos pelo log.

### DJI Open Platforms

O portal fica em `/integracoes/dji/pilot/login/` e deve ser configurado no DJI Pilot 2 em **Cloud Service → Open Platforms**. A primeira etapa implementada contém:

Por segurança, a integração fica desativada por padrão com `DJI_CLOUD_ENABLED=false`. Nesse estado, o portal operacional e a autenticação MQTT recusam conexões, enquanto a importação manual de logs continua disponível. A variável somente deverá ser alterada para `true` depois da implantação com HTTPS, broker MQTT protegido e banco de dados de produção.

- diagnóstico administrativo em **Integração DJI**;
- login do piloto dentro do WebView do DJI Pilot 2;
- verificação de APP ID, APP Key e licença pelo JSBridge;
- definição do workspace e identificação visual do SISMOD;
- carregamento preparado dos módulos `api` e `thing`;
- leitura dos seriais do controle e da aeronave;
- correspondência da aeronave pelo `Drone.numero_serie`;
- token assinado e temporário para API e MQTT;
- endpoint de autenticação HTTP compatível com broker EMQX 5.

#### DJI Dock 2

A fundação de monitoramento da Dock foi implementada em modo seguro e somente leitura. `DJIDock` guarda serial, modelo, posição, aeronave vinculada, situação, modo de origem, último contato e o último retrato de telemetria. `DJIDockEvento` mantém o histórico bruto normalizado e deduplica mensagens que possuam `tid`, `bid` ou outro identificador externo.

O serviço reconhece tópicos nos padrões `sys/product/{gateway_sn}/status` e `thing/product/{gateway_sn}/...`, incluindo OSD, estado e eventos. Ele cria a Dock pelo serial, vincula a aeronave pela topologia ou número de série informado e classifica condições iniciais em informação, atenção ou crítica. Campos sensíveis como `device_secret`, `nonce`, senha, token, App Key e App License são removidos recursivamente antes da persistência. Coordenador e administrador podem consultar a lista e os detalhes; somente o administrador pode usar a entrada de simulação. Esta etapa não possui comandos físicos, criação de missão, abertura da tampa ou decolagem.

Para homologação local, configure `DJI_DOCK_SIMULATOR_ENABLED=true` e execute `python manage.py simular_dji_dock`. A chave deve permanecer falsa em produção. O consumidor MQTT 5 somente leitura é executado pelo processo separado `python manage.py consumir_dji_dock`, assina os tópicos OSD/event configurados e reconecta automaticamente. Ele recusa iniciar enquanto `DJI_DOCK_ENABLED=false` ou sem broker e credenciais completos.

O arquivo `infra/dji-dock/compose.yaml` sobe uma instância única do EMQX em contêiner com volumes persistentes. No perfil local, MQTT e painel ficam presos a `127.0.0.1`, e o acesso anônimo existe apenas para permitir o teste fechado na própria máquina. Essa composição não deve ser usada para uma Dock física nem em produção. Antes de expor à rede, será criada uma composição TLS com usuários, ACL por tópico e segredos externos.

`DJIDockComando` fornece a trilha de auditoria para futuras ações remotas, registrando identificador, tipo, criticidade, parâmetros sanitizados, operador, horários, situação e mensagem. A intenção permanece `bloqueado` enquanto `DJI_DOCK_ENABLED` ou `DJI_DOCK_COMMANDS_ENABLED` estiver falsa. Mesmo com ambas verdadeiras, o registro apenas fica pendente: esta versão não contém publicador de comandos físicos. Docks sem contato pelo período definido em `DJI_DOCK_OFFLINE_AFTER_SECONDS` são atualizadas por `python manage.py atualizar_status_dji_docks`.

`DJIDockMissao` vincula um planejamento existente a uma Dock e registra altitude, velocidade, situação e verificações. A preparação confere geometria, vínculo e serial da aeronave, altitude, meteorologia e Termos de Coordenação. A missão permanece em validação até que o modelo DJI e o payload sejam confirmados para gerar os valores enumerados exigidos pelo WPML. Nenhum KMZ executável é produzido ou enviado nesta fase, evitando uma rota aparentemente válida com configuração de aeronave incorreta.

Os identificadores `type`, `sub_type` e `gimbalindex` são capturados da topologia e da telemetria reais e armazenados separadamente como metadados DJI da Dock. O SISMOD não deduz esses códigos apenas pelo nome comercial do drone. Para a Dock 2, a compatibilidade oficial é restrita ao Matrice 3D/3TD e não admite payload de terceiros; a combinação observada ainda deverá ser validada no DJI Pilot 2.

Quando aeronave, payload e geometria estão disponíveis e não existem erros estruturais, o SISMOD gera localmente um KMZ com `wpmz/template.kml` e `wpmz/waylines.wpml`, namespace WPML 1.0.2, configuração de retorno, velocidade, altura e pontos derivados do polígono. O download recebe explicitamente o estado `pre-validacao`: deve ser importado e conferido no DJI Pilot 2. Geração não altera a missão para pronta e não publica nenhum tópico MQTT.

A geração do ZIP é determinística para que o fingerprint MD5, formato exigido pela Cloud API DJI, permaneça igual entre a preparação e o download. O MD5 serve somente para integridade do conteúdo, enquanto o acesso é protegido por URL assinada. Para consumo futuro pela Dock, o serviço monta um descritor com UUID da missão, fingerprint e URL por tempo limitado. O endpoint público não requer sessão, mas valida uma assinatura vinculada à missão, aplica expiração por `DJI_DOCK_WPML_URL_TTL_SECONDS`, não permite cache e somente pode ser anunciado quando `DJI_CLOUD_PUBLIC_URL` usa HTTPS.

Cada `DJIDockMissao` mantém parâmetros operacionais explicitamente revisados: altura de RTH entre 20 e 1500 m, percentual mínimo de bateria, armazenamento mínimo e decisão de interromper a rota na perda de sinal. A confirmação registra administrador e horário. Somente depois dela o serviço consegue montar, sem publicar, os dados de `flighttask_prepare` com missão condicional, janela do planejamento, RTH fixo, retorno como ação de contingência e verificação avançada de segurança.

### Central, liberação e fila DJI

A Central de missões é acessível à administração e coordenação; somente a administração confirma parâmetros e cria prévias de fila. A triagem marca como bloqueio: drone indisponível ou em manutenção, Termo de Coordenação pendente, avaliação de risco exigida ainda não aceita, documento de aeronave vencido, qualificação vencida e parâmetros não confirmados. Meteorologia não consultada/desfavorável, ausência de reserva vinculada e ausência de qualificação cadastrada são alertas, pois podem representar uma etapa ainda em elaboração. A triagem auxilia o operador e não substitui autorizações oficiais.

`DJIDockComando.mensagem_mqtt` guarda a prévia sanitizada de `flighttask_prepare`, enquanto `expira_em` limita sua validade. Nesta fase ela nasce bloqueada e não existe publicador físico. `python manage.py expirar_comandos_dji` cancela registros vencidos.

### Armazenamento de mídias

`SISMOD_MEDIA_STORAGE` seleciona `local`, `s3` ou `minio` por instalação. Local usa `MEDIA_ROOT`; S3 e MinIO usam o backend privado `django-storages`, credenciais externas e bucket sem acesso anônimo. `DJIDockArquivo` registra origem, situação, tamanho, SHA-256, arquivo, horário e eventual falha. O SHA-256 aqui verifica o arquivo armazenado; ele é diferente do MD5 exigido pela DJI para o KMZ. O download autenticado é transmitido pelo SISMOD, evitando expor a URL interna do MinIO.

A galeria aceita upload manual de JPG/JPEG, PNG, TIFF, MP4/MOV, PPK (`obs`, `rtk`, `mrk`, `nav`, `dat`), logs e ZIP até 5 GB. O limite também deve ser aplicado no proxy reverso em produção. O recebimento direto da Dock ainda depende de credenciais temporárias e HTTPS.

### Homologação em contêineres

O `Dockerfile` executa Python 3.12, dependências, arquivos estáticos e Gunicorn. `infra/compose.homologacao.yaml` inclui PostgreSQL, MinIO privado, inicialização do bucket, EMQX e processos separados para web e consumidor. As portas de web e consoles ficam ligadas a `127.0.0.1`; o perfil `dock-real` não deve ser iniciado sem TLS e autenticação do broker. `verificar_implantacao` testa conexão com banco, escrita no armazenamento e informa o estado das travas DJI.

### Cockpit Virtual / DRC

O Cockpit Virtual fica na seção própria **Estações Remotas**, disponível para administradores, coordenadores e pilotos, e nesta versão opera apenas em simulação. Pilotos veem suas próprias missões, mídias e sessões, enquanto os dados globais de auditoria e configuração permanecem restritos. A interface em tela cheia reserva a área principal ao vídeo da aeronave, mantém mapa, saúde do enlace e um segundo monitor para a câmera fixa da Dock no painel lateral e sobrepõe os dados essenciais de voo; as abas secundárias apresentam missão e estado da Dock. O mapa usa a mesma fonte OpenStreetMap validada pela telemetria, aplica política de referência e exibe uma mensagem controlada se o provedor estiver indisponível. `DJIDRCSessao` garante uma sessão ativa por Dock por meio do serviço transacional e de uma restrição no banco, registrando operador, limites, heartbeat, sequência e telemetria simulada. `DJIDRCComando` audita os cinco canais no intervalo DJI de 364 a 1684, com 1024 neutro. Teclado e sliders retornam ao neutro quando liberados; encerramento e watchdog também gravam uma neutralização.

O heartbeat do navegador é enviado a cada segundo. `encerrar_sessoes_drc` encerra sessões que ultrapassem `DJI_DRC_HEARTBEAT_TIMEOUT_SECONDS` ou `DJI_DRC_SESSION_TTL_SECONDS`. O controle real permanece inexistente mesmo que uma variável isolada seja alterada: as três travas `DJI_DRC_ENABLED`, `DJI_DRC_COMMANDS_ENABLED` e `DJI_DOCK_ENABLED` precisam estar ativas, e ainda será necessário implementar o relay DRC autenticado, autoridade de voo/payload, livestream de baixa latência e publicação contínua de `stick_control` a 5–10 Hz.

Os eventos DJI `flighttask_ready` e `flighttask_progress` são correlacionados pelo UUID da missão para registrar disponibilidade, execução, pausa, conclusão, falha, percentual, etapa, waypoint e total de mídias. O evento `file_upload_callback` cria ou atualiza um inventário por `object_key`, com nome, caminho remoto, tipo, indicação de original e metadados de captura saneados. Respostas recebidas em `services_reply` são correlacionadas pelo `tid` com `DJIDockComando`, fechando a auditoria como confirmada ou erro; isso não implica que o SISMOD já publique comandos. Esse inventário não contém o arquivo binário nem credenciais de armazenamento; download e armazenamento somente serão ativados após configurar serviço de objetos privado e credenciais temporárias no ambiente de servidor.

#### Transmissão ao vivo

A fundação de livestream DJI está implementada, mas permanece desligada até a implantação de um servidor de mídia público. O fluxo previsto é **aeronave → DJI Pilot 2 → RTMP/RTMPS → MediaMTX ou SRS → player WebRTC no SISMOD**.

- o piloto conecta o controle e a aeronave pelo portal Open Platforms;
- o SISMOD identifica o drone pelo número de série;
- **Iniciar transmissão** cria uma sessão com chave aleatória e endereço de ingestão temporário;
- o módulo oficial `liveshare` do DJI Pilot 2 configura o RTMP e inicia/encerra o envio;
- estado e métricas de qualidade são devolvidos ao SISMOD;
- a sessão é vinculada ao piloto, drone e, quando houver, à reserva em andamento;
- a dashboard do coordenador mostra somente o endereço HTTPS de reprodução e nunca a URL RTMP de ingestão;
- sessões finalizadas ou com erro deixam de aparecer como ativas.

O modelo `TransmissaoAoVivo` registra identificador, chave de stream, piloto, aeronave, reserva, seriais do equipamento, situação, métricas e horários. A chave não substitui controle de acesso do servidor: em produção, o player deve ficar atrás de HTTPS, autenticação e regras de rede/reverse proxy.

Variáveis adicionais:

- `DJI_LIVESTREAM_ENABLED=false`, chave independente e desligada por padrão;
- `DJI_LIVESTREAM_RTMP_BASE_URL`, destino RTMP/RTMPS aceito pelo servidor de mídia;
- `DJI_LIVESTREAM_PLAYBACK_BASE_URL`, endereço HTTPS do player WebRTC.

A importação manual de Flight Records não depende dessas variáveis e continua disponível mesmo com a livestream desligada.

O menu **Transmissões ao vivo** organiza a operação em quatro abas:

- **Ao vivo:** players autorizados e identificação da sessão;
- **Agendadas:** planejamentos futuros marcados para transmissão;
- **Histórico:** sessões finalizadas ou com erro;
- **Configurações:** diagnóstico disponível somente ao administrador.

No planejamento, o piloto pode marcar **Transmitir esta operação ao vivo**, informar título, público autorizado e intenção de gravação. O agendamento não liga a câmera automaticamente: no DJI Pilot 2 o piloto escolhe a operação e confirma **Iniciar transmissão**. Também existe o caminho avulso **Iniciar transmissão agora**, sem planejamento; essa sessão fica identificada como avulsa e não cria reserva ou voo fictício. Coordenadores somente acompanham, enquanto piloto e administrador podem iniciar conforme o dispositivo e as permissões.

O portal somente habilita o botão de conexão quando todas as configurações estão presentes e válidas. O endereço precisa ser público e HTTPS. O normalizador e o armazenamento de mensagens da Dock estão implementados, mas ainda não existe processo conectado continuamente ao broker MQTT nem recebimento automático de arquivos.

Variáveis necessárias:

- `DJI_CLOUD_ENABLED`, chave geral de ativação (`false` por padrão);
- `DJI_CLOUD_APP_ID`, `DJI_CLOUD_APP_KEY` e `DJI_CLOUD_APP_LICENSE`;
- `DJI_CLOUD_WORKSPACE_ID`, obrigatoriamente um UUID;
- `DJI_CLOUD_PUBLIC_URL` e `DJI_CLOUD_API_HOST`, em HTTPS;
- `DJI_CLOUD_MQTT_HOST`, com protocolo `tcp`, `ssl`, `ws` ou `wss`;
- `DJI_CLOUD_MQTT_USERNAME_PREFIX`;
- nomes da plataforma, workspace e descrição;
- `DJI_DOCK_ENABLED=false`, trava independente para a futura conexão física;
- `DJI_DOCK_SIMULATOR_ENABLED=false`, habilitada somente em homologação local;
- `DJI_DOCK_MQTT_USERNAME` e `DJI_DOCK_MQTT_PASSWORD`, conta exclusiva e sem permissão de publicação em tópicos de comando;
- `DJI_DOCK_MQTT_CLIENT_ID`, identificador único do consumidor;
- `DJI_DOCK_MQTT_TOPIC`, lista separada por vírgulas de tópicos de leitura, incluindo `services_reply` para fechar a auditoria;
- `DJI_DOCK_MQTT_CA_CERT`, caminho opcional para a autoridade certificadora privada;
- `DJI_DOCK_WPML_URL_TTL_SECONDS`, validade da URL assinada usada pela Dock para baixar o KMZ;
- `DJI_DOCK_COMMAND_TTL_SECONDS`, validade das prévias de comandos;
- `SISMOD_MEDIA_STORAGE`, backend `local`, `s3` ou `minio`;
- `SISMOD_STORAGE_BUCKET`, `SISMOD_STORAGE_ACCESS_KEY`, `SISMOD_STORAGE_SECRET_KEY`, `SISMOD_STORAGE_REGION` e `SISMOD_STORAGE_ENDPOINT_URL`, configuração privada do armazenamento;
- `SISMOD_DB_HOST`, `SISMOD_DB_PORT`, `SISMOD_DB_NAME`, `SISMOD_DB_USER` e `SISMOD_DB_PASSWORD`, PostgreSQL opcional; sem host, o desenvolvimento continua em SQLite;
- `DJI_DRC_ENABLED` e `DJI_DRC_COMMANDS_ENABLED`, travas independentes do controle físico, falsas por padrão;
- `DJI_DRC_SIMULATOR_ENABLED`, libera somente o cockpit simulado;
- `DJI_DRC_SESSION_TTL_SECONDS` e `DJI_DRC_HEARTBEAT_TIMEOUT_SECONDS`, limites do watchdog;
- `SISMOD_ALLOWED_HOSTS` e `SISMOD_CSRF_TRUSTED_ORIGINS` para o domínio publicado.

Referências oficiais: [DJI Pilot 2 Access to Cloud](https://developer.dji.com/doc/cloud-api-tutorial/en/feature-set/pilot-feature-set/pilot-access-to-cloud.html), [DJI JSBridge](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/pilot-to-cloud/jsbridge.html) e [DJI Live Stream](https://developer.dji.com/doc/cloud-api-tutorial/en/feature-set/pilot-feature-set/pilot-livestream.html).

### Avaliação de risco

- dados disponíveis são preenchidos pelo planejamento;
- piloto confirma perigos, controles, matriz e declaração;
- não depende de aprovação do administrador;
- administrador e coordenador consultam;
- permite correção rastreável pelo piloto;
- visualização, download e impressão em PDF com papel timbrado persistente.

### Voos e telemetria

- um voo aceita vários logs e voos antigos permanecem selecionáveis;
- logs do mesmo piloto, drone e data são consolidados em uma única operação;
- logs de datas diferentes criam operações e entradas de calendário separadas;
- telemetria sem planejamento prévio entra no calendário como **Regularização pendente**;
- o aviso permanece para piloto, coordenador e administrador até a vinculação do planejamento e a conclusão de checklist e pós-voo;
- o fluxo de regularização preenche automaticamente piloto, drone, data, horários, finalidade e local, exigindo que o usuário confirme e desenhe a área efetivamente sobrevoada;
- suporta CSV normalizado, CSV Autel, Flight Record binário Autel `AUTEL_FR` v3 e Flight Records DJI processados pelo parser;
- exibe rota, `hh:mm:ss`, distância, altitude, velocidade, bateria, satélites e alertas;
- consolida dados por minuto e explica estados normal, atenção e erro;
- alertas georreferenciados aparecem no mapa.
- o piloto pode corrigir seus logs enquanto a operação estiver aberta; depois que o registro pós-voo for concluído, somente o administrador pode excluir telemetria, com recálculo automático do voo e do pós-voo.

Modelos DJI previstos na identificação incluem Matrice 4T/4E, Matrice 300 RTK, Matrice 30T e família Mavic 3. A compatibilidade real depende do formato/firmware e deve ser validada com amostras de cada equipamento.

Na Autel há duas camadas de compatibilidade. O **CSV de registro de voo** exportado pelo Autel Enterprise ou Autel Sky é normalizado, inclusive cabeçalhos `camelCase` e unidades em pés, km/h ou mph. O Flight Record proprietário sem extensão, identificado pela assinatura `AUTEL_FR`, também é aceito na versão 3. Esse leitor foi validado em onze amostras reais de EVO II 640T: nove continham trajetória e duas eram registros curtos de inicialização sem GPS de voo. Por não existir especificação pública do binário, o SISMOD extrai conservadoramente somente horário, latitude, longitude, altitude, velocidade horizontal, serial da aeronave e serial da bateria confirmados nas amostras. Percentual/ciclos da bateria, satélites, sinal e alertas continuam vazios nesse formato até serem comprovados. Arquivos `.LOG`, pacotes de diagnóstico e arquivos de suporte não são tratados como telemetria operacional. Cada outro modelo, aplicativo ou firmware exige validação com amostra real.

Para controladoras Pixhawk, o formato depende do firmware instalado:

- **ArduPilot:** DataFlash `.BIN`, interpretado com `pymavlink`; são normalizados GPS, tempo, altitude, velocidade, bateria, satélites, sinal e mensagens `ERR`;
- **PX4:** `.ULG`, interpretado com `pyulog`; são combinados os tópicos `vehicle_gps_position`, `vehicle_local_position` e `battery_status`, além das mensagens de severidade relevante;
- BIN/ULG podem ter até 200 MB; o processamento continua limitado a 100.000 posições GPS para proteger memória e banco de dados;
- Pixhawk identifica a controladora, não necessariamente o fabricante da aeronave. A associação oficial continua sendo feita ao voo/drone selecionado pelo usuário.

O Wingtra usa ULog e recebe identificação própria no resumo. Além do ULog/PX4 convencional, o leitor normaliza em arquivo temporário a variante Wingtra ULog v2, que acrescenta dois bytes de CRC após cada mensagem; o original nunca é alterado. O tópico `bms_data` é lido por `multi_id`, permitindo registrar separadamente as duas baterias físicas do Wingtra, seus números de série, contadores de ciclos, saúde e posição no conjunto. Cada serial desconhecido permanece como alerta até o cadastro. A validação real foi feita com WingtraRAY 10473: o arquivo principal continha 2.427 posições válidas, cerca de 24min46s, bateria de 100% a 55%, até 34 satélites, altitude relativa máxima aproximada de 129,4 m e duas baterias BMS distintas. O arquivo nomeado pela missão/voo, como `VooRGB Flight 01.ulg`, é a fonte indicada. `sess*_fmu.ulg` contém telemetria técnica redundante da mesma sessão e `sess*_fts.ulg` pode não conter trajetória GPS utilizável; importar os três como se fossem voos diferentes causaria duplicidade.

O suporte senseFly eBee permanece fora do escopo ativo. Os arquivos reais `.BB3` e `_em.bb3` inspecionados são binários proprietários distintos e não possuem decodificador público sustentável confirmado. O SISMOD não aceita esses arquivos para evitar registros incorretos. Uma futura retomada exigirá exportação estruturada oficial do eMotion ou SDK/decodificador homologado.

### Pós-voo

- vinculado à reserva e preenchido pelo próprio usuário;
- concluído só é alterado pelo administrador;
- cria/atualiza voo e conclui reserva/solicitação;
- necessidade de manutenção altera a aeronave, registra histórico e abre inspeção se não houver equivalente aberta.

### Frota e conformidade

- aeronaves, prefixo, status, localização, documentos e histórico;
- baterias, ciclos e saúde;
- componentes com QR Code;
- manutenção e planos de inspeção por dias, voos, horas ou ciclos;
- documentos de piloto, aeronave, bateria ou organização;
- qualificações e recência operacional;
- incidentes, investigação, ações corretivas e alertas.

### Relatórios

- filtros por período, piloto e aeronave;
- totais baseados em telemetria;
- duração padronizada em horas e minutos;
- PDF visualizável e baixável;
- papel timbrado salvo até substituição manual;
- página e tabela adaptadas à orientação/proporção do modelo PDF, sem deformar a arte original.

## 6. Fonte oficial dos indicadores

| Informação | Fonte no SISMOD |
|---|---|
| Reserva/disponibilidade | `Alocacao` e `SolicitacaoVoo` |
| Data e horário efetivos | telemetria importada |
| Horas, duração e distância | logs concluídos |
| Rota e alertas | pontos de telemetria |
| Experiência/recência do piloto | voos com telemetria concluída |
| Inspeção por uso | voos/horas comprovados por telemetria |
| Situação futura | planejamento e calendário |

O horário reservado nunca soma horas de experiência.

## 7. Permissões

| Capacidade | Usuário | Coordenador | Administrador |
|---|:---:|:---:|:---:|
| Editar o próprio perfil | Sim | Sim | Sim |
| Planejar/reservar para si | Sim | Não no modo coordenador | Sim |
| Checklist/pós-voo próprios | Sim | Não no modo coordenador | Sim |
| Importar telemetria própria | Sim | Não no modo coordenador | Sim |
| Ver dados operacionais globais | Não | Sim | Sim |
| Ver equipe, riscos, incidentes e logs globais | Não | Sim, leitura | Sim |
| Gerenciar usuários, frota, documentos e manutenção | Não | Não | Sim |
| Consultar e ativar a licença da instalação | Não | Não | Sim |
| Django Admin | Não | Não | Sim |

A interface oculta ações não permitidas e o servidor valida as rotas diretamente.

## 8. Instalação local

```powershell
git clone <URL-DO-REPOSITORIO>
Set-Location gestao-drones
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py criar_admin_inicial
python manage.py runserver
```

Não é necessário manter o servidor aberto durante alterações. Para testar no navegador ele deve estar executando; reinicie se o recarregamento automático não ocorrer.

## 9. Configuração e dados locais

`.env`:

```dotenv
DJI_FLIGHT_RECORD_APP_KEY=sua_chave_aqui
```

- `.env`: segredo local; nunca versionar;
- `.env.example`: nomes das variáveis, sem segredos;
- `db.sqlite3`: banco local; nunca versionar;
- `media/`: fotos, documentos, logs e modelos; nunca versionar;
- `venv/`: ambiente virtual; nunca versionar.

Git protege o código, mas não substitui backup do banco e de `media/`. Em produção, ambos precisam de backup e restauração próprios.

## 10. Banco e migrations

Após alterar modelos:

```powershell
python manage.py makemigrations core
python manage.py migrate
python manage.py check
```

Migrations ficam em `core/migrations/` e acompanham o código no mesmo commit. Não editar migration já aplicada sem estratégia explícita.

## 11. Testes e Git

```powershell
python manage.py check
python manage.py test core
git diff --check
git status --short
```

Os testes cobrem perfis, permissões, reservas, risco, planejamento, telemetria, baterias, componentes, documentos, inspeções, PDFs e regras operacionais.

## 12. Segurança e produção

A configuração padrão continua local, mas `config/settings.py` já aceita endurecimento por ambiente. Antes de colocar em rede/internet:

1. definir `SISMOD_SECRET_KEY` com valor longo, aleatório e exclusivo;
2. usar `SISMOD_DEBUG=false`;
3. configurar `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS`;
4. usar HTTPS, cookies seguros e cabeçalhos adequados;
5. habilitar validadores de senha;
6. escolher banco e armazenamento apropriados;
7. servir estáticos/mídia fora do `runserver`;
8. usar servidor WSGI/ASGI de produção;
9. executar `python manage.py check --deploy` nas configurações de produção;
10. definir backup, retenção, auditoria e acesso a documentos/logs.

Com `SISMOD_DEBUG=false`, redirecionamento HTTPS, cookies seguros e HSTS (incluindo subdomínios e diretiva de preload) são ativados por padrão. Só use esse modo depois de confirmar HTTPS em todo o domínio. Atrás de proxy HTTPS, defina `SISMOD_BEHIND_HTTPS_PROXY=true`. As variáveis `SISMOD_SECURE_SSL_REDIRECT`, `SISMOD_SESSION_COOKIE_SECURE`, `SISMOD_CSRF_COOKIE_SECURE`, `SISMOD_SECURE_HSTS_SECONDS`, `SISMOD_SECURE_HSTS_INCLUDE_SUBDOMAINS` e `SISMOD_SECURE_HSTS_PRELOAD` permitem ajuste explícito conforme a infraestrutura.

Nunca publicar chaves DJI, CPF, documentos, banco ou mídia no GitHub.

## 13. Limitações conhecidas

O procedimento consolidado de ativação está em [`docs/RECURSOS_DESATIVADOS.md`](RECURSOS_DESATIVADOS.md).

- logs são importados manualmente;
- ingestão automática de logs DJI/Autel ainda não está ativa;
- livestream DJI está implementada no SISMOD, mas depende da implantação e proteção do broker e do servidor de mídia;
- livestream Autel ainda não está integrada;
- token SARPAS não está integrado;
- meteorologia/neblina/camadas aeronáuticas são apoio à decisão;
- tiles OSM públicos têm política de uso e não atendem alto volume;
- SQLite precisa ser reavaliado para implantação multiusuário;
- cada modelo/firmware DJI, Autel, ArduPilot ou PX4 requer log real de teste; na Autel, CSV e `AUTEL_FR` v3 do EVO II 640T estão cobertos nesta etapa.

## 14. Documentação oficial

- Python 3.12: https://docs.python.org/3.12/
- Ambientes virtuais: https://docs.python.org/3.12/tutorial/venv.html
- Django 5.2: https://docs.djangoproject.com/en/5.2/
- Implantação Django: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- Bootstrap: https://getbootstrap.com/docs/5.3/
- Chart.js: https://www.chartjs.org/docs/latest/
- Leaflet: https://leafletjs.com/reference.html
- Leaflet-Geoman: https://geoman.io/docs/leaflet
- OpenStreetMap: https://www.openstreetmap.org/copyright
- Política de tiles OSM: https://operations.osmfoundation.org/policies/tiles/
- Política Nominatim: https://operations.osmfoundation.org/policies/nominatim/
- Open-Meteo: https://open-meteo.com/en/docs
- ReportLab: https://docs.reportlab.com/
- pypdf: https://pypdf.readthedocs.io/
- Pillow: https://pillow.readthedocs.io/
- python-dotenv: https://bbc2.github.io/python-dotenv/
- qrcode: https://github.com/lincolnloop/python-qrcode
- Cryptography — Ed25519: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/
- Parser DJI: https://github.com/olavbolav/dji-flightlog-parser
- DJI Cloud API Live Stream: https://developer.dji.com/doc/cloud-api-tutorial/en/feature-set/pilot-feature-set/pilot-livestream.html
- Autel — segurança e exportação de registros CSV: https://www.autelrobotics.com/news/white-paper/
- Autel — Cloud API: https://developer.autelrobotics.com/cloudApi
- Autel — API de logs de diagnóstico: https://developer.autelrobotics.com/doc/v2.5/android_api_reference/en/10/31
- ArduPilot — estrutura das mensagens de log: https://ardupilot.org/copter/docs/logmessages.html
- ArduPilot — pymavlink: https://github.com/ArduPilot/pymavlink
- PX4 — formato ULog: https://docs.px4.io/main/en/dev_log/ulog_file_format.html
- PX4 — pyulog: https://github.com/PX4/pyulog
- Wingtra — organização dos registros de voo: https://knowledge.wingtra.com/es/organizacion-de-datos-wingtraone
- senseFly — obtenção dos registros BB3/BBZ: https://sensefly.zendesk.com/hc/en-us/articles/360017004300-eBee-X-eBee-TAC-What-to-share-with-technical-support
- MediaMTX: https://mediamtx.org/docs/kickoff/introduction
- AISWEB/DECEA: https://aisweb.decea.mil.br/
- SARPAS/DECEA: https://sarpas.decea.mil.br/
- SISCLATEN: https://sisclaten.defesa.gov.br/sisclaten/
- Autorização de aerolevantamentos: https://www.gov.br/pt-br/servicos/obter-autorizacao-para-realizar-aerolevantamentos

## 15. Licenciamento empresarial anual

O SISMOD adota uma instalação isolada por empresa. `InstalacaoSISMOD` gera um UUID estável que identifica o servidor, e `LicencaSISMOD` preserva o histórico de ativações. A licença é um JSON assinado com Ed25519 contendo empresa, CNPJ, instalação, emissão, validade, tolerância e recursos.

A validação usa somente a chave pública configurada no servidor. A chave privada permanece exclusivamente com o fornecedor. A assinatura é conferida na ativação e novamente durante a leitura do estado, detectando alteração do arquivo ou dos dados persistidos.

Estados operacionais:

- ativa: funcionamento normal;
- expirando: funcionamento normal com aviso a partir de 60 dias;
- tolerância: funcionamento normal por até 15 dias, ou pelo período emitido;
- expirada, ausente, inválida ou sem configuração: consultas e exportações continuam disponíveis, mas requisições de alteração são bloqueadas;
- desativada: modo local de desenvolvimento, controlado por variável de ambiente.

O primeiro administrador é criado por `python manage.py criar_admin_inicial`. Depois disso, o comando recusa uma segunda execução e os usuários passam a ser gerenciados pela interface. O procedimento operacional completo está em [`LICENCIAMENTO_E_IMPLANTACAO.md`](LICENCIAMENTO_E_IMPLANTACAO.md).

## 16. Atualização obrigatória

Toda mudança funcional deve seguir `docs/MANUTENCAO_DOCUMENTACAO.md`. Código, testes e documentação afetada devem estar no mesmo commit.
