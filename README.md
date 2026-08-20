# Gestão de Drones - Base inicial

Projeto Django com:
- Login
- Dashboard
- Cadastro de pilotos
- Cadastro de drones
- Registro de voos
- Gráfico de uso por piloto
- Gráfico de uso por drone
- Banco SQLite para testes locais

## Instalação rápida

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Acesse:
http://127.0.0.1:8000/
