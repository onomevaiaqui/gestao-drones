import io
import zipfile
from xml.etree import ElementTree


def extrair_poligono_kml(arquivo):
    nome = (arquivo.name or "").lower()
    bruto = arquivo.read()
    if len(bruto) > 10 * 1024 * 1024:
        raise ValueError("O arquivo deve possuir no máximo 10 MB.")
    if nome.endswith(".kmz"):
        try:
            with zipfile.ZipFile(io.BytesIO(bruto)) as pacote:
                candidatos = [i for i in pacote.infolist() if i.filename.lower().endswith(".kml")]
                if not candidatos:
                    raise ValueError("O KMZ não contém um arquivo KML.")
                escolhido = next((i for i in candidatos if i.filename.lower().endswith("doc.kml")), candidatos[0])
                if escolhido.file_size > 20 * 1024 * 1024:
                    raise ValueError("O conteúdo do KMZ é muito grande.")
                bruto = pacote.read(escolhido)
        except zipfile.BadZipFile as erro:
            raise ValueError("O arquivo KMZ é inválido.") from erro
    elif not nome.endswith(".kml"):
        raise ValueError("Envie um arquivo com extensão .kml ou .kmz.")
    try:
        raiz = ElementTree.fromstring(bruto)
    except ElementTree.ParseError as erro:
        raise ValueError("O conteúdo KML é inválido.") from erro
    poligonos = []
    for poligono in (e for e in raiz.iter() if e.tag.split("}")[-1] == "Polygon"):
        coordenadas = next((e for e in poligono.iter() if e.tag.split("}")[-1] == "coordinates" and e.text), None)
        if coordenadas is not None:
            pontos = []
            for item in coordenadas.text.strip().replace("\n", " ").split():
                partes = item.split(",")
                if len(partes) >= 2:
                    try: pontos.append([float(partes[0]), float(partes[1])])
                    except ValueError: pass
            if len(pontos) >= 3:
                if pontos[0] != pontos[-1]: pontos.append(pontos[0])
                poligonos.append(pontos)
    if not poligonos:
        raise ValueError("Nenhum polígono foi encontrado no KML/KMZ.")
    maior = max(poligonos, key=len)
    return {"type":"Polygon", "coordinates":[maior]}
