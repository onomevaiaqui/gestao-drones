"""Emissor do fornecedor. A chave privada nunca deve ser copiada para o servidor do cliente."""
import argparse
import base64
import json
import uuid
from datetime import date
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def canonico(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="Emite licença anual assinada do SISMOD")
    parser.add_argument("--private-key", required=True, help="Arquivo PEM da chave privada do fornecedor")
    parser.add_argument("--installation-id", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--cnpj", default="")
    parser.add_argument("--expires", required=True, help="AAAA-MM-DD")
    parser.add_argument("--grace-days", type=int, default=15)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    uuid.UUID(args.installation_id)
    date.fromisoformat(args.expires)
    chave = serialization.load_pem_private_key(Path(args.private_key).read_bytes(), password=None)
    if not isinstance(chave, Ed25519PrivateKey):
        raise SystemExit("A chave deve ser Ed25519.")
    payload = {
        "schema": 1,
        "license_id": str(uuid.uuid4()),
        "installation_id": args.installation_id,
        "company_name": args.company,
        "company_cnpj": args.cnpj,
        "issued_at": date.today().isoformat(),
        "expires_at": args.expires,
        "grace_days": args.grace_days,
        "features": ["core"],
    }
    documento = {"payload": payload, "signature": base64.b64encode(chave.sign(canonico(payload))).decode("ascii")}
    Path(args.output).write_text(json.dumps(documento, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Licença emitida: {args.output}")


if __name__ == "__main__":
    main()
