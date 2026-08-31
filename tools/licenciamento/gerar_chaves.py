"""Uso único pelo fornecedor; mantenha o arquivo privado fora do Git e dos clientes."""
import argparse
import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


parser = argparse.ArgumentParser()
parser.add_argument("--private-output", required=True)
args = parser.parse_args()
chave = Ed25519PrivateKey.generate()
Path(args.private_output).write_bytes(chave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
publica = chave.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
print("SISMOD_LICENSE_PUBLIC_KEY=" + base64.b64encode(publica).decode("ascii"))
