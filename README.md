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
python manage.py createsuperuser
python manage.py runserver
```

Acesse `http://127.0.0.1:8000/`.

Para ler logs binários DJI, preencha `DJI_FLIGHT_RECORD_APP_KEY` no arquivo `.env`. Nunca envie esse arquivo ao GitHub.

## Validação

```powershell
python manage.py check
python manage.py test core
```

## Documentação

- [Documentação técnica completa](docs/DOCUMENTACAO_TECNICA.md)
- [Política obrigatória de atualização](docs/MANUTENCAO_DOCUMENTACAO.md)
- [Inventário de arquivos legados](docs/ARQUIVOS_LEGADOS.md)

## Situação atual

O projeto usa Python 3.12, Django 5.2 e SQLite para desenvolvimento local. A configuração atual não deve ser usada diretamente em produção; consulte a seção de implantação e segurança da documentação técnica.
