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

Registros de voo Autel podem ser importados manualmente em CSV exportado pelo Autel Enterprise ou Autel Sky. O SISMOD normaliza cabeçalhos e unidades comuns; arquivos `.LOG` de diagnóstico não substituem o CSV de voo. Valide cada modelo e firmware com uma amostra real antes do uso operacional.

Controladoras Pixhawk são aceitas nos formatos nativos dos dois principais firmwares: DataFlash `.BIN` do ArduPilot e `.ULG` do PX4. As dependências `pymavlink` e `pyulog` fazem a leitura binária; a compatibilidade deve ser validada com um log real do firmware e da configuração utilizada.

WingtraOne/WingtraRAY usam registros `.ULG` e são identificados sobre o mesmo leitor técnico do PX4. Para senseFly eBee, o fluxo inicial usa o JSON criado no eMotion pela opção **Create JSON flight log**; os formatos proprietários `.BB3/.BBZ` aguardam validação com amostras reais.

A conexão DJI Open Platforms é configurada por variáveis `DJI_CLOUD_*` descritas no `.env.example`. Ela permanece bloqueada por padrão com `DJI_CLOUD_ENABLED=false`, sem afetar a importação manual de logs. Depois de publicar o SISMOD em HTTPS e concluir a infraestrutura, o administrador poderá ativá-la pela variável de ambiente. As credenciais reais permanecem apenas no `.env` ou no gerenciador de segredos do servidor.

## Validação

```powershell
python manage.py check
python manage.py test core
```

## Documentação

- [Documentação técnica completa](docs/DOCUMENTACAO_TECNICA.md)
- [Política obrigatória de atualização](docs/MANUTENCAO_DOCUMENTACAO.md)
- [Inventário de arquivos legados](docs/ARQUIVOS_LEGADOS.md)
- [Licenciamento anual e implantação por empresa](docs/LICENCIAMENTO_E_IMPLANTACAO.md)

## Situação atual

O projeto usa Python 3.12, Django 5.2 e SQLite para desenvolvimento local. A configuração atual não deve ser usada diretamente em produção; consulte a seção de implantação e segurança da documentação técnica.
