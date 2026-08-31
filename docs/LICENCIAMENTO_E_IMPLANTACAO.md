# Licenciamento anual e implantação por empresa

## Modelo adotado

Cada cliente recebe uma instalação própria do SISMOD em seu servidor e uma licença anual vinculada ao código daquela instalação. O administrador inicial cria os demais usuários. Nenhuma chave privada de assinatura é entregue ao cliente.

## Instalação inicial

1. Instale as dependências e configure o `.env` sem segredos no Git.
2. Execute `python manage.py migrate`.
3. Execute `python manage.py criar_admin_inicial` e informe usuário, e-mail, nome e senha no terminal protegido.
4. Entre como administrador e abra **Administração > Licença**.
5. Copie o código da instalação e envie ao responsável comercial pela emissão.
6. Receba o arquivo `.sismod-license` e ative-o na mesma tela.

O arquivo de licença pode ser guardado no cofre documental da empresa para auditoria, mas não deve ser colocado no repositório Git. O SISMOD conserva no banco os dados assinados e o histórico de ativações.

Para provisionamento não interativo, o comando aceita `--noinput` e lê temporariamente `SISMOD_INITIAL_ADMIN_USERNAME`, `SISMOD_INITIAL_ADMIN_EMAIL`, `SISMOD_INITIAL_ADMIN_NAME` e `SISMOD_INITIAL_ADMIN_PASSWORD`. Remova essas variáveis imediatamente depois da criação.

## Configuração comercial

O servidor recebe somente:

```dotenv
SISMOD_LICENSE_ENFORCEMENT=true
SISMOD_LICENSE_PUBLIC_KEY=CHAVE_PUBLICA_ED25519_EM_BASE64
```

Reinicie o serviço após mudar o ambiente. Em desenvolvimento, mantenha a fiscalização desligada para não bloquear os testes locais.

Depois de ativar a fiscalização sem uma licença válida, somente login, consulta, exportação e a própria renovação permanecem liberados para alteração. Faça a primeira ativação em uma janela controlada e mantenha o arquivo emitido disponível.

## Emissão pelo fornecedor

Em uma máquina protegida e separada, gere o par uma única vez:

```powershell
python tools/licenciamento/gerar_chaves.py --private-output C:\segredos\sismod-ed25519.pem
```

Guarde a chave privada em cofre criptográfico, com backup protegido e acesso restrito. Copie apenas a chave pública impressa para a configuração das instalações.

Emita uma licença:

```powershell
python tools/licenciamento/emitir_licenca.py --private-key C:\segredos\sismod-ed25519.pem --installation-id UUID_DO_CLIENTE --company "Empresa Cliente" --cnpj "00.000.000/0001-00" --expires 2027-08-31 --output cliente-2027.sismod-license
```

Nunca envie a chave privada, o diretório de segredos ou variáveis reais ao GitHub.

Os scripts de emissão pertencem ao fornecedor. Nas cópias entregues ao cliente eles podem ser removidos do pacote final, pois não participam da execução do SISMOD.

## Renovação e vencimento

O sistema avisa a partir de 60 dias antes do vencimento. Após a data final, aplica a tolerância contida na licença, com padrão de 15 dias. Depois disso:

- consultas, históricos, visualizações e exportações continuam disponíveis;
- os dados existentes não são apagados nem ocultados;
- novos registros, edições e exclusões são bloqueados;
- login e ativação de uma licença renovada continuam disponíveis.

O administrador envia o novo arquivo na tela de licença. A licença anterior fica no histórico e deixa de ser a ativa.

## Limite de proteção

A assinatura impede falsificação comum e detecta adulteração dos dados. Como o cliente controla o próprio servidor e, numa distribuição em código-fonte, pode modificar o programa, nenhuma licença exclusivamente offline é inviolável contra um administrador malicioso. Para proteção comercial mais forte, distribua uma imagem assinada/empacotada, restrinja alterações no servidor e considere validação periódica em um serviço do fornecedor, respeitando disponibilidade e privacidade.

## Backup

Inclua banco, mídia e configuração segura no backup empresarial. O código da instalação reside no banco; restaurar somente arquivos sem o banco gera outro código e exigirá nova emissão.
