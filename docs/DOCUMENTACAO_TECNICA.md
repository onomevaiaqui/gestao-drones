# Documentação técnica do SISMOD

Versão documental: 1.2
Última revisão: 27/08/2026

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
| `reportlab` | Gera PDFs de relatórios e avaliações de risco. |
| `pypdf` | Lê, combina e aplica papel timbrado aos PDFs. |
| `qrcode[pil]` | Gera QR Codes de componentes. |
| `Pillow` | Suporte a imagens, fotos e QR Code. |

Pacotes como `asgiref`, `sqlparse`, `httpx`, `pydantic` e bibliotecas criptográficas são dependências transitivas instaladas pelos pacotes diretos. Não devem ser removidos manualmente do ambiente virtual.

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

O portal somente habilita o botão de conexão quando todas as configurações estão presentes e válidas. O endereço precisa ser público e HTTPS. A integração ainda não recebe tópicos MQTT nem arquivos automaticamente; isso será habilitado depois da instalação e configuração do broker.

Variáveis necessárias:

- `DJI_CLOUD_ENABLED`, chave geral de ativação (`false` por padrão);
- `DJI_CLOUD_APP_ID`, `DJI_CLOUD_APP_KEY` e `DJI_CLOUD_APP_LICENSE`;
- `DJI_CLOUD_WORKSPACE_ID`, obrigatoriamente um UUID;
- `DJI_CLOUD_PUBLIC_URL` e `DJI_CLOUD_API_HOST`, em HTTPS;
- `DJI_CLOUD_MQTT_HOST`, com protocolo `tcp`, `ssl`, `ws` ou `wss`;
- `DJI_CLOUD_MQTT_USERNAME_PREFIX`;
- nomes da plataforma, workspace e descrição;
- `SISMOD_ALLOWED_HOSTS` e `SISMOD_CSRF_TRUSTED_ORIGINS` para o domínio publicado.

Referências oficiais: [DJI Pilot 2 Access to Cloud](https://developer.dji.com/doc/cloud-api-tutorial/en/feature-set/pilot-feature-set/pilot-access-to-cloud.html) e [DJI JSBridge](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/pilot-to-cloud/jsbridge.html).

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
- suporta CSV normalizado e Flight Records DJI processados pelo parser;
- exibe rota, `hh:mm:ss`, distância, altitude, velocidade, bateria, satélites e alertas;
- consolida dados por minuto e explica estados normal, atenção e erro;
- alertas georreferenciados aparecem no mapa.

Modelos DJI previstos na identificação incluem Matrice 4T/4E, Matrice 300 RTK, Matrice 30T e família Mavic 3. A compatibilidade real depende do formato/firmware e deve ser validada com amostras de cada equipamento.

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
python manage.py createsuperuser
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

A configuração atual é local: `DEBUG=True`, chave fixa, SQLite, hosts locais e `runserver`. Antes de colocar em rede/internet:

1. mover `SECRET_KEY`, `DEBUG` e hosts para variáveis de ambiente;
2. usar `DEBUG=False`;
3. configurar `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS`;
4. usar HTTPS, cookies seguros e cabeçalhos adequados;
5. habilitar validadores de senha;
6. escolher banco e armazenamento apropriados;
7. servir estáticos/mídia fora do `runserver`;
8. usar servidor WSGI/ASGI de produção;
9. executar `python manage.py check --deploy` nas configurações de produção;
10. definir backup, retenção, auditoria e acesso a documentos/logs.

Nunca publicar chaves DJI, CPF, documentos, banco ou mídia no GitHub.

## 13. Limitações conhecidas

- logs são importados manualmente;
- integração automática DJI/Autel não existe ainda;
- token SARPAS não está integrado;
- meteorologia/neblina/camadas aeronáuticas são apoio à decisão;
- tiles OSM públicos têm política de uso e não atendem alto volume;
- SQLite precisa ser reavaliado para implantação multiusuário;
- cada modelo/firmware DJI requer log real de teste.

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
- Parser DJI: https://github.com/olavbolav/dji-flightlog-parser
- AISWEB/DECEA: https://aisweb.decea.mil.br/
- SARPAS/DECEA: https://sarpas.decea.mil.br/
- SISCLATEN: https://sisclaten.defesa.gov.br/sisclaten/
- Autorização de aerolevantamentos: https://www.gov.br/pt-br/servicos/obter-autorizacao-para-realizar-aerolevantamentos

## 15. Atualização obrigatória

Toda mudança funcional deve seguir `docs/MANUTENCAO_DOCUMENTACAO.md`. Código, testes e documentação afetada devem estar no mesmo commit.
