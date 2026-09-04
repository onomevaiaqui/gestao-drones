# Backup e restauração do SISMOD

Git preserva código; não preserva banco, documentos, logs de voo ou segredos. Os comandos abaixo são manuais. Definir com a empresa periodicidade, retenção, responsável, criptografia e uma cópia fora do servidor. Não enviar backups ao GitHub.

## SQLite e mídia local (ambiente atual)

1. Parar Django, importadores e demais processos que alterem banco ou mídia. Manter o terminal de manutenção disponível. O parâmetro de confirmação não para os processos por conta própria.
2. Executar a partir do projeto, usando um caminho novo num volume de backup protegido:

```powershell
python manage.py backup_local D:\BackupSISMOD\sismod-20260904.sismod-backup.zip --confirmar-manutencao
```

O comando cria uma cópia consistente SQLite, inclui os arquivos da pasta media e um manifesto SHA-256. Recusa sobrescrever um pacote existente ou salvá-lo dentro de media. Links simbólicos são recusados. A manutenção é necessária para consistência conjunta entre banco e mídia.

3. Testar restauração em uma pasta que não exista, sem substituir a aplicação:

```powershell
python manage.py restaurar_backup_local D:\BackupSISMOD\sismod-20260904.sismod-backup.zip D:\TesteRestauracao\sismod-20260904
```

O comando confere manifesto, hashes, caminhos, tamanho máximo (100 GiB), integridade SQLite e vínculos. Arquivos são conferidos numa área temporária antes de disponibilizar a cópia. O banco em uso não é alterado. Em erro de movimentação/disco, o destino pode ficar incompleto; não usá-lo sem nova restauração validada em outro destino.

4. Para teste funcional, usar uma cópia separada do código na mesma versão do backup, apontar para o banco restaurado e a pasta media restaurada, fornecer segredos pelo cofre e manter todas as integrações externas desligadas. Conferir login, documentos, reservas e telemetria.
5. Substituir uma instalação real somente em uma manutenção aprovada, após conferir a restauração e preservar a versão anterior para retorno.

**Proteção:** o ZIP não é criptografado e inclui dados pessoais e hashes de senhas. Guardar em destino com criptografia e ACL; o manifesto detecta corrupção, não prova autoria. O pacote não contém `.env` nem chaves privadas: guardá-los separadamente em cofre, incluindo chaves MFA históricas necessárias à restauração.

O teste automatizado cria banco e documento sintéticos, gera backup, restaura e compara o conteúdo. Também testa recusa de sobrescrita, corrupção e caminhos maliciosos. Não foi gerado backup completo dos dados reais sem uma janela de manutenção.

## PostgreSQL e S3/MinIO (servidor futuro)

Procedimento a homologar no servidor, não executado nesta máquina:

1. Pausar web e workers de escrita, registrar a versão do código e das migrations.
2. Usar `pg_dump --format=custom` com usuário de backup e credenciais fornecidas por cofre/arquivo protegido, não na linha de comando. Usar cliente compatível com a versão PostgreSQL instalada.
3. Preservar o bucket privado por snapshot/versionamento ou cópia autenticada, com manifesto e mesmo ponto de manutenção do banco. Não usar `sync --delete` contra o bucket em uso.
4. Criar um banco de teste vazio e bucket separado; restaurar com `pg_restore --exit-on-error --no-owner --dbname=<banco-de-teste>`. Nunca usar o nome do banco em produção para ensaio.
5. Restaurar objetos no bucket de teste e validar contagens, hashes e acesso privado. Não publicar objetos anonimamente.
6. Subir uma instância isolada na versão registrada, com os segredos necessários e integrações DJI/MQTT/livestream desativadas. Executar check, testes de navegação e validação de documentos/telemetria.
7. Registrar duração, resultado e perdas toleradas (RTO/RPO). Só aprovar produção após um ensaio completo e documentado.

Referências: [PostgreSQL backup](https://www.postgresql.org/docs/current/backup-dump.html), [Django storage](https://docs.djangoproject.com/en/5.2/ref/files/storage/).
