import re
import unicodedata


def _normalizar(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def modelo_operacional(drone, modelo_detectado=""):
    return _normalizar(" ".join(filter(None, [
        getattr(drone, "nome", ""), getattr(drone, "modelo", ""), modelo_detectado,
    ])))


def componente_exige_cadastro(drone, detectado, modelo_detectado=""):
    """Retorna se o item detectado é destacável e deve integrar o patrimônio."""
    origem = str(detectado.get("origem") or "").lower()
    tipo = str(detectado.get("tipo") or "").lower()
    modelo = modelo_operacional(drone, modelo_detectado)

    # O controle aparece no Flight Record, mas não é um payload instalado na aeronave.
    if origem == "remotecontroller" or tipo == "controle":
        return False, "Controle remoto não é payload da aeronave."

    # Um serial RTK informado pelo Flight Record representa módulo/acessório rastreável.
    if origem == "rtk" or "rtk" in _normalizar(detectado.get("nome")):
        return True, "Módulo RTK destacável identificado."

    camera_ou_gimbal = tipo in {"camera", "gimbal"} or origem in {
        "camera", "rightcamera", "leftcamera", "gimbal",
    }
    # M300/M350 são plataformas de payload intercambiável (Zenmuse e equivalentes).
    if camera_ou_gimbal and any(marca in modelo for marca in (
        "matrice 300", "m300", "matrice 350", "m350",
    )):
        return True, "Payload de câmera/gimbal intercambiável identificado."

    camera_integrada = any(marca in modelo for marca in (
        "mavic 3", "mini 3", "mini 4", "matrice 4", "m4t", "m4e",
        "matrice 30", "m30t", "m30",
    ))
    if camera_ou_gimbal and camera_integrada:
        return False, "Câmera/gimbal integrado de fábrica; cadastro separado desnecessário."

    # Em modelo não reconhecido, preserva o aviso para não ocultar equipamento real.
    return True, "Componente destacável ou compatibilidade ainda não classificada."
