# Política de manutenção da documentação

Esta política é obrigatória para todas as próximas alterações do SISMOD.

## Regra para cada envio ao GitHub

Antes de criar um commit, verificar se a mudança afeta:

- comportamento de tela ou fluxo;
- permissões dos perfis;
- modelo, campo, migration ou regra de negócio;
- dependência ou biblioteca de interface;
- variável de ambiente ou integração externa;
- instalação, execução, testes ou implantação;
- relatório, PDF, arquivo importado ou exportado;
- fonte de dados, cálculo ou indicador.

Se afetar, atualizar no mesmo commit:

1. `README.md`, quando mudar instalação ou primeiros passos;
2. `docs/DOCUMENTACAO_TECNICA.md`, quando mudar arquitetura, módulos, regras, integrações ou operação;
3. `requirements.txt`, quando mudar dependências Python;
4. `.env.example`, quando mudar variáveis de ambiente.

A mensagem final de cada atualização deve informar se a documentação foi alterada ou se não precisava de alteração.

## Lista de conferência antes do commit

- [ ] O comportamento implementado está descrito?
- [ ] A matriz de permissões continua correta?
- [ ] Novos campos e fontes de dados foram explicados?
- [ ] Dependências e variáveis de ambiente estão atualizadas?
- [ ] `manage.py check` e `manage.py test core` passaram?
- [ ] Nenhum segredo, `.env`, banco, mídia ou backup entrou no commit?
- [ ] Os links oficiais continuam válidos?

Última revisão: 26/08/2026.
