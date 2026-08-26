# Documentação técnica do SISMOD

Versão documental: 1.0
Última revisão: 26/08/2026

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
| DJI Flight Record Parsing | Decodificação mediante chave no ambiente. | Importação manual; automação não implementada. |

KML/KMZ pode ser importado no planejamento; o maior polígono encontrado é usado. A área desenhada pode ser exportada em KML.

## 4. Estrutura do projeto

```text
gestao_drones/
├── config/                 configurações, URLs, WSGI e ASGI
├── core/                   domínio e regras do SISMOD
│   ├── models.py           estrutura persistida e propriedades
│   ├── *_forms.py          formulários e validação
│   ├── *_views.py          telas e permissões HTTP
│   ├── *_service.py        regras reutilizáveis e integrações
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
- alteração de senha e edição do próprio perfil, foto, CPF, código SARPAS e documentos;
- administrador pode escolher o modo Administrador, Coordenador ou Usuário no mesmo login;
- coordenador nativo entra diretamente no modo de consulta.

### Dashboard

- métricas somente de voos comprovados por logs;
- mapa e operações previstas do dia;
- situação de pilotos, qualificações, frota, inspeções e documentos;
- avaliações de risco e incidentes pendentes;
- últimos 30 dias comparados aos 30 anteriores;
- gráficos por piloto, aeronave, finalidade e período.

### Planejamento de voo

- desenho de área fechada e cálculo aproximado;
- busca de local e importação/exportação KML/KMZ;
- meteorologia, estimativa de neblina e camadas aeronáuticas;
- raios de atenção e triagem SISCLATEN;
- data, horário, região e finalidade reaproveitados na reserva.

### Reservas, calendário e checklist

- reserva representa disponibilidade prevista, não voo realizado;
- reserva comum é liberada sem aprovação administrativa;
- quando exigida, a avaliação de risco é preenchida e aceita pelo piloto;
- calendário impede conflito da mesma aeronave;
- checklist concluído só pode ser alterado pelo administrador.

### Avaliação de risco

- dados disponíveis são preenchidos pelo planejamento;
- piloto confirma perigos, controles, matriz e declaração;
- não depende de aprovação do administrador;
- administrador e coordenador consultam;
- permite correção rastreável pelo piloto;
- visualização, download e impressão em PDF com papel timbrado persistente.

### Voos e telemetria

- um voo aceita vários logs e voos antigos permanecem selecionáveis;
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
