GESTÃO DE DRONES - ATUALIZAÇÃO V2

IMPORTANTE
Esta atualização foi feita para preservar o banco db.sqlite3 atual.
NÃO apague o db.sqlite3.

COMO INSTALAR

1. Pare o servidor:
CTRL + C

2. Faça uma cópia de segurança da pasta atual do projeto.

3. Extraia este ZIP.

4. Copie para o seu projeto:
- pasta core
- pasta templates
- pasta static

Destino:
C:\Users\Alex\Documents\gestao_drones

Substitua os arquivos quando solicitado.

5. Com o ambiente virtual ativo:
python manage.py makemigrations
python manage.py migrate

Se o Django informar que já existe uma migration 0002 diferente, NÃO continue.
Nesse caso envie a mensagem para o ChatGPT para ajustarmos a numeração.

6. Inicie:
python manage.py runserver

7. Acesse:
http://127.0.0.1:8000/

NOVIDADES
- Novo menu lateral
- Dashboard profissional
- Filtro por período
- Gráficos por piloto, drone, finalidade e tempo
- Tela de voos com filtros
- Novo formulário de voo
- Editar drones
- Calendário de alocação
- Bloqueio de conflito de horário por drone
- Relatórios
- Manutenções
- Interface responsiva

PERMISSÕES
Administrador:
- acesso total

Usuário:
- dashboard
- voos
- registrar voo
- calendário em modo consulta
