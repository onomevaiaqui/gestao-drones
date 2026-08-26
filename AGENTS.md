# Instruções permanentes do repositório SISMOD

## Documentação obrigatória

Antes de todo commit ou push, avaliar o impacto da alteração conforme `docs/MANUTENCAO_DOCUMENTACAO.md`.

Quando a mudança afetar comportamento, permissões, arquitetura, modelos, dependências, integrações, configuração, instalação, testes, relatórios ou fontes de indicadores, atualizar a documentação correspondente no mesmo commit.

Manter sempre coerentes:

- `README.md` para instalação e início rápido;
- `docs/DOCUMENTACAO_TECNICA.md` para módulos, arquitetura, regras e operação;
- `requirements.txt` para dependências Python;
- `.env.example` para nomes de variáveis de ambiente, nunca com segredos.

Antes do push, executar `python manage.py check`, `python manage.py test core` e `git diff --check`. Não incluir `.env`, banco, mídia, backups ou credenciais.
