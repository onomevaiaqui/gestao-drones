#!/usr/bin/env python
"""Insere o botão Pós-voo ao lado do Checklist no calendário atual."""
from __future__ import annotations

import datetime as dt
import shutil
import subprocess
import sys
from pathlib import Path

CHECKLIST = '<a href="{% url \'checklist_pre_voo\' a.pk %}" class="icon-btn">Checklist</a>'
POS_VOO = '<a href="{% url \'registro_pos_voo\' alocacao_id=a.pk %}" class="icon-btn">Pós-voo</a>'


def main():
    root = Path.cwd().resolve()
    manage = root / "manage.py"
    template = root / "templates" / "calendario" / "calendario.html"

    if not manage.exists():
        raise SystemExit("Execute este patch na pasta que contém manage.py.")
    if not template.exists():
        raise SystemExit(f"Template não encontrado: {template}")

    texto = template.read_text(encoding="utf-8")
    if POS_VOO in texto:
        print("O botão Pós-voo já está instalado.")
    else:
        if CHECKLIST not in texto:
            raise SystemExit("Não encontrei o botão Checklist esperado; nenhum arquivo foi alterado.")

        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = root / "backups" / f"antes_botao_pos_voo_{stamp}" / template.relative_to(root)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template, backup)

        novo = texto.replace(CHECKLIST, CHECKLIST + "\n" + POS_VOO, 1)
        template.write_text(novo, encoding="utf-8", newline="\n")
        print("Botão Pós-voo inserido ao lado do Checklist.")

        try:
            subprocess.run([sys.executable, "manage.py", "check"], cwd=root, check=True)
        except Exception:
            shutil.copy2(backup, template)
            print("Falha na validação. O template original foi restaurado.")
            raise

        print(f"Backup em: {backup.parent.parent.parent}")

    print("Correção concluída e validada com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
