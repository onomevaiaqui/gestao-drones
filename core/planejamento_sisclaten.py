from .geo_utils import distancia_km


def classificar_sisclaten(planejamento):
    if not planejamento.gera_dados_aerolevantamento:
        return {"status":"nao_aplicavel", "titulo":"SISCLATEN não aplicável pela declaração atual",
                "motivos":["O usuário declarou que a operação não produzirá dados caracterizados como aerolevantamento."],
                "raio_maximo_km":None, "aviso":"Se a missão gerar ortomosaico, mapa, modelo, nuvem de pontos, dado espectral, LiDAR ou geofísico, edite o planejamento e refaça a análise."}
    coords = (planejamento.area_geojson or {}).get("coordinates", [[]])[0]
    lat0, lon0 = float(planejamento.centro_latitude), float(planejamento.centro_longitude)
    raio_max = max((distancia_km(lat0, lon0, float(lat), float(lon)) for lon, lat in coords), default=0)
    area_ha = float(planejamento.area_hectares or 0)
    motivos, pendencias, impeditivos = [], [], []
    if area_ha > 1500 or raio_max > 2.2:
        impeditivos.append(f"Área/abrangência acima do limite de pré-autorização: {area_ha:.2f} ha e raio máximo aproximado de {raio_max:.2f} km.")
    else:
        motivos.append(f"Área dentro da triagem do art. 38: {area_ha:.2f} ha e raio máximo aproximado de {raio_max:.2f} km.")
    if planejamento.tipo_aerolevantamento == "geofisico": impeditivos.append("Aerolevantamento geofísico não se enquadra na dispensa de AAFA.")
    elif not planejamento.tipo_aerolevantamento: pendencias.append("Confirme o tipo de aerolevantamento.")
    if planejamento.dentro_condicionantes_ica == "nao": impeditivos.append("A operação foi declarada fora das condicionantes da ICA 100-40.")
    elif planejamento.dentro_condicionantes_ica == "nao_sei": pendencias.append("Confirme o atendimento integral às condicionantes da ICA 100-40.")
    if planejamento.interseca_area_sensivel_defesa == "sim": impeditivos.append("Foi declarada interseção com área ou instalação sensível à Defesa.")
    elif planejamento.interseca_area_sensivel_defesa == "nao_sei": pendencias.append("Consulte o SisCLATEN/Ministério da Defesa sobre áreas ou instalações sensíveis.")
    if planejamento.projeto_contiguo_12_meses == "sim": impeditivos.append("Há projeto contíguo em período inferior a 12 meses, impedindo usar a dispensa para fracionamento da área.")
    elif planejamento.projeto_contiguo_12_meses == "nao_sei": pendencias.append("Confirme se houve projeto contíguo nos últimos 12 meses.")
    if planejamento.atividade_agroflorestal:
        if planejamento.exclusivo_proprietario_rural == "nao": impeditivos.append("A operação agroflorestal não atenderá exclusivamente ao proprietário do imóvel rural.")
        elif planejamento.exclusivo_proprietario_rural == "nao_sei": pendencias.append("Confirme o beneficiário exclusivo da operação agroflorestal.")
    if impeditivos:
        status, titulo = "aafa_necessaria", "AAFA provavelmente necessária no SISCLATEN"
    elif pendencias:
        status, titulo = "confirmar", "Necessidade de AAFA depende de confirmação"
    else:
        status, titulo = "dispensa_aafa", "Projeto pré-autorizado, com dispensa do processo de AAFA"
    return {"status":status, "titulo":titulo, "motivos":motivos+impeditivos+pendencias,
            "raio_maximo_km":round(raio_max,2),
            "aviso":"Triagem referente à AAFA. Não substitui a inscrição da entidade, o registro de metadados no SisCLATEN, a consulta de áreas sensíveis nem a autorização de acesso ao espaço aéreo pelo DECEA."}
