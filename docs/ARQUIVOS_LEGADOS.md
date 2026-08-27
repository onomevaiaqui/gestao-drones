# Inventário de arquivos legados

Estes arquivos foram mantidos para preservar o histórico das aplicações manuais anteriores. Eles não fazem parte do fluxo normal de execução e não devem receber novas regras do SISMOD:

- `ADICIONAR_AO_CSS.txt`;
- `ADICIONAR_AO_SETTINGS.txt`;
- `core/AJUSTES_VIEWS.txt`;
- `core/AJUSTES_URLS.txt`;
- `core/AJUSTES_FORMS.txt`;
- `core/ADICIONAR_EM_VIEWS.txt`;
- `core/migrations/0003_alocacao_manutencao.py.py`.

A migration válida é `core/migrations/0003_alocacao_manutencao.py`. O arquivo com extensão `.py.py` não é carregado pelo Django.

Nenhum desses arquivos deve ser apagado automaticamente. Depois de conferir o histórico no Git, eles podem ser removidos em uma alteração separada e explicitamente aprovada.
