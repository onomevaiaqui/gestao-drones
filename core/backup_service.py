"""Backup SQLite + mídia local. Restauração somente em destino novo, nunca em produção."""
import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path, PurePosixPath


def hash_arquivo(caminho):
    digest = hashlib.sha256()
    with Path(caminho).open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def verificar_banco(caminho):
    with closing(sqlite3.connect(Path(caminho).resolve().as_uri() + "?mode=ro", uri=True)) as banco:
        if banco.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise ValueError("Falha de integridade SQLite.")
        if banco.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Vínculos inválidos no banco restaurado.")


def criar_backup(banco, midia, destino):
    banco, midia, destino = Path(banco).resolve(), Path(midia).resolve(), Path(destino).resolve()
    if destino.exists() or destino.is_relative_to(midia):
        raise ValueError("Use um arquivo novo fora da pasta de mídia.")
    if not banco.is_file():
        raise ValueError("Banco SQLite não encontrado.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sismod-backup-") as temporario:
        copia = Path(temporario) / "database.sqlite3"
        with closing(sqlite3.connect(banco.as_uri() + "?mode=ro", uri=True)) as origem, closing(sqlite3.connect(copia)) as alvo:
            origem.backup(alvo)
        verificar_banco(copia)
        arquivos = [("database.sqlite3", copia)]
        for caminho in sorted(midia.rglob("*")) if midia.exists() else []:
            if caminho.is_symlink() or not caminho.resolve().is_relative_to(midia):
                raise ValueError("Links simbólicos não são permitidos no backup.")
            if caminho.is_file():
                arquivos.append(("media/" + caminho.relative_to(midia).as_posix(), caminho))
        manifesto = {"versao": 1, "arquivos": {}}
        criado = False
        try:
            with zipfile.ZipFile(destino, "x", zipfile.ZIP_DEFLATED) as pacote:
                criado = True
                for nome, caminho in arquivos:
                    antes = caminho.stat()
                    digest = hash_arquivo(caminho)
                    pacote.write(caminho, nome)
                    depois = caminho.stat()
                    if (antes.st_size, antes.st_mtime_ns) != (depois.st_size, depois.st_mtime_ns):
                        raise ValueError("Arquivo alterado durante backup. Pare os processos de escrita.")
                    manifesto["arquivos"][nome] = {"sha256": digest, "bytes": antes.st_size}
                pacote.writestr("manifest.json", json.dumps(manifesto))
        except Exception:
            # Somente o arquivo criado exclusivamente por esta chamada.
            if criado:
                destino.unlink(missing_ok=True)
            raise
    return len(arquivos)


def restaurar_backup(pacote, destino, max_bytes=100 * 1024**3):
    destino = Path(destino).resolve()
    if destino.exists():
        raise ValueError("A restauração exige uma pasta que ainda não exista.")
    with zipfile.ZipFile(pacote) as zipado:
        nomes = zipado.namelist()
        if len(nomes) != len(set(nomes)) or zipado.getinfo("manifest.json").file_size > 10 * 1024**2:
            raise ValueError("Manifesto inválido ou arquivos duplicados.")
        manifesto = json.loads(zipado.read("manifest.json"))
        arquivos = manifesto.get("arquivos", {})
        if manifesto.get("versao") != 1 or "database.sqlite3" not in arquivos or set(nomes) != set(arquivos) | {"manifest.json"}:
            raise ValueError("Conteúdo incompatível com o manifesto.")
        if sum(info.file_size for info in zipado.infolist()) > max_bytes:
            raise ValueError("Backup excede limite de restauração.")
        for nome, dados in arquivos.items():
            caminho = PurePosixPath(nome)
            if "\\" in nome or ":" in nome or caminho.is_absolute() or ".." in caminho.parts or (nome != "database.sqlite3" and not nome.startswith("media/")):
                raise ValueError("Caminho inseguro no backup.")
            if zipado.getinfo(nome).file_size != dados["bytes"]:
                raise ValueError("Tamanho divergente do manifesto.")
        # Extrair/verificar em pasta temporária irmã antes de disponibilizar o resultado.
        destino.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="sismod-restore-", dir=destino.parent) as temporario:
            raiz = Path(temporario)
            for nome, dados in arquivos.items():
                alvo = raiz / nome
                alvo.parent.mkdir(parents=True, exist_ok=True)
                with zipado.open(nome) as origem, alvo.open("xb") as saida:
                    shutil.copyfileobj(origem, saida, length=1024 * 1024)
                if hash_arquivo(alvo) != dados["sha256"]:
                    raise ValueError("Hash divergente: backup alterado ou corrompido.")
            verificar_banco(raiz / "database.sqlite3")
            # mkdir exclusivo impede sobrescrever um destino criado durante a validação.
            destino.mkdir()
            for item in raiz.iterdir():
                shutil.move(str(item), str(destino / item.name))
    return len(arquivos)
