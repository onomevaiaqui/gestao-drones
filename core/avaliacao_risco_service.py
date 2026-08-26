from datetime import date


LEGISLACAO_PADRAO = """Código Brasileiro de Aeronáutica — Lei nº 7.565/1986.
RBAC nº 100, Emenda 00 — requisitos gerais para aeronaves não tripuladas de aviação civil.
ICA 100-40/2026 — Aeronaves não tripuladas e o acesso ao espaço aéreo brasileiro.
ICA 100-48 vigente — obtenção de autorizações no SARPAS.
Resolução Anatel nº 715/2019 e atos de homologação aplicáveis ao equipamento.
Portaria GM-MD nº 3.726/2020 e alterações vigentes — procedimentos para aerolevantamento e SisCLATEN.
IS E94-003A — referência para a estrutura desta avaliação de risco operacional.
Confirmar antes da operação as revisões vigentes, NOTAM, AIP/AISWEB e autorizações aplicáveis."""


def _validade_12_meses(data_base):
    try:
        return data_base.replace(year=data_base.year + 1)
    except ValueError:
        return data_base.replace(year=data_base.year + 1, day=28)


def classificar_matriz(probabilidade, severidade):
    celula = f"{int(probabilidade)}{str(severidade).upper()}"
    if celula in {"4A", "5A", "5B"}: return "Extremo"
    if celula in {"3A", "4B", "5C"}: return "Alto"
    if celula in {"1A", "2A", "2B", "3B", "3C", "4C", "4D", "5D", "5E"}: return "Moderado"
    if celula in {"1B", "1C", "2C", "2D", "3D", "3E", "4E"}: return "Baixo"
    return "Muito baixo"


def _situacao(titulo, perigo, mitigacao, prob=3, sev="C", prob_res=1, sev_res="C"):
    return {"titulo": titulo, "perigo": perigo, "probabilidade": prob, "severidade": sev,
            "risco": f"{prob}{sev}", "tolerabilidade": classificar_matriz(prob, sev),
            "medidas": mitigacao, "probabilidade_residual": prob_res, "severidade_residual": sev_res,
            "risco_residual": f"{prob_res}{sev_res}", "tolerabilidade_residual": classificar_matriz(prob_res, sev_res)}


def dados_automaticos_avaliacao(solicitacao):
    planejamento = solicitacao.planejamento
    meteo = planejamento.resumo_meteorologico if planejamento else {}
    aeronautica = meteo.get("aeronautica", {})
    sisclaten = meteo.get("sisclaten", {})
    perigos, mitigacoes, condicoes = [], [], []

    for item in aeronautica.get("itens", []):
        tipo, nome = item.get("tipo", "condicionante"), item.get("nome", "Sem nome")
        if item.get("distancia_km") is not None:
            perigos.append(f"{tipo.title()} {item.get('id') or ''} {nome} a {item['distancia_km']} km da área.")
            mitigacoes.append("Confirmar no SARPAS a necessidade de coordenação com o órgão ATS ou operador do aeródromo antes do voo.")
        elif tipo == "proibida":
            perigos.append(f"A área planejada cruza a área proibida {item.get('id') or ''} {nome}.")
            mitigacoes.append("Não operar dentro da área proibida; redesenhar a área ou obter a autorização oficial aplicável.")
        elif tipo == "restrita":
            perigos.append(f"A área planejada cruza a área restrita {item.get('id') or ''} {nome}.")
            mitigacoes.append("Verificar ativação, limites verticais, NOTAM e condições no AISWEB/SARPAS; coordenar quando exigido.")
        else:
            perigos.append(f"A área planejada cruza a área perigosa {item.get('id') or ''} {nome}.")
            mitigacoes.append("Verificar horários de ativação e atividade perigosa; manter afastamento ou coordenar antes da operação.")

    for hora in meteo.get("horas", []):
        if hora.get("status") != "favoravel":
            for motivo in hora.get("motivos", []):
                texto = f"{hora.get('hora')}: {motivo}"
                if texto not in perigos: perigos.append(texto)
    if meteo:
        condicoes.append(f"Condição geral: {meteo.get('status', 'indisponível')}.")
        if meteo.get("visibilidade_min_m") is not None: condicoes.append(f"Visibilidade mínima prevista: {meteo['visibilidade_min_m']:.0f} m.")
        if meteo.get("rajada_max_kmh") is not None: condicoes.append(f"Rajada máxima prevista: {meteo['rajada_max_kmh']} km/h.")
        if meteo.get("neblina_area_max_percentual"): condicoes.append(f"Possibilidade de neblina em até {meteo['neblina_area_max_percentual']}% da área.")
    if any(h.get("status") != "favoravel" for h in meteo.get("horas", [])):
        mitigacoes.append("Reconfirmar a meteorologia imediatamente antes da decolagem e adiar a operação se os limites do fabricante ou operacionais forem excedidos.")
    if sisclaten.get("status") == "aafa_necessaria":
        perigos.append("A análise do planejamento classificou a AAFA como provavelmente necessária no SISCLATEN.")
        mitigacoes.append("Obter a AAFA no SISCLATEN antes da fase aeroespacial e confirmar a inscrição/categoria da entidade executante.")
    elif sisclaten.get("status") == "confirmar":
        perigos.append("A necessidade de AAFA depende de confirmações ainda pendentes no planejamento.")
        mitigacoes.append("Concluir a triagem de aerolevantamento e confirmar a situação diretamente no SISCLATEN/Ministério da Defesa antes da operação.")
    elif sisclaten.get("status") == "dispensa_aafa":
        mitigacoes.append("Registrar os metadados e cumprir as obrigações do SisCLATEN aplicáveis ao projeto pré-autorizado, mantendo a autorização DECEA separadamente.")
    mitigacoes.extend([
        "Realizar consulta ao SARPAS, AISWEB e NOTAM antes da operação.",
        "Manter VLOS, área de decolagem controlada, observador quando necessário e procedimento de interrupção disponível.",
    ])
    nivel = 4 if aeronautica.get("status") == "desfavoravel" or meteo.get("status") == "desfavoravel" else 3 if aeronautica.get("status") == "atencao" or meteo.get("status") == "atencao" else 2
    drone = getattr(solicitacao, "drone", None)
    planejamento = solicitacao.planejamento
    altura = f", altura máxima planejada de {planejamento.altura_maxima_m} m" if planejamento else ""
    aeronave = f"{drone.nome} — modelo {drone.modelo}" if drone else "Aeronave a confirmar"
    if drone and drone.prefixo: aeronave += f"; prefixo/cadastro {drone.prefixo}"
    if drone and drone.numero_serie: aeronave += f"; nº de série {drone.numero_serie}"
    situacoes = [
        _situacao("Perda de enlace", "Perda do enlace de comando e controle ou degradação do sinal.", "Configurar RTH e altura segura; confirmar ponto de retorno, bateria e procedimento de interrupção; manter VLOS.", 3, "B", 1, "B"),
        _situacao("Tráfego aéreo local", "Conflito com aeronaves tripuladas ou outra aeronave não tripulada.", "Consultar SARPAS, AISWEB e NOTAM; observar o espaço aéreo, ceder passagem e pousar imediatamente se necessário.", 3, "A", 1, "A"),
        _situacao("Pessoas não anuentes", "Sobrevoo ou aproximação de pessoas não anuentes e danos a terceiros.", "Isolar a área, manter distância segura, controlar acessos e interromper o voo se terceiros entrarem na zona operacional.", 3, "A", 1, "B"),
    ]
    if meteo.get("status") in {"atencao", "desfavoravel"}:
        situacoes.append(_situacao("Meteorologia", "Vento, rajadas, chuva, baixa visibilidade ou neblina acima dos limites operacionais.", "Reavaliar a previsão e as condições no local; respeitar limites do fabricante e adiar/cancelar em condição inadequada.", 4, "B", 2, "B"))
    if aeronautica.get("itens"):
        situacoes.append(_situacao("Condicionantes do espaço aéreo", "Proximidade de aeródromo, heliponto ou área condicionada identificada no planejamento.", "Confirmar limites e ativação no AISWEB/SARPAS; obter autorização e coordenação quando aplicável antes da decolagem.", 3, "A", 1, "A"))
    hoje = date.today()
    piloto = getattr(getattr(solicitacao, "piloto", None), "nome", "Piloto a confirmar")
    data_operacao = getattr(solicitacao, "data", hoje)
    hora_inicio = getattr(solicitacao, "hora_inicio", None)
    hora_fim = getattr(solicitacao, "hora_fim", None)
    periodo = f", das {hora_inicio:%H:%M} às {hora_fim:%H:%M}" if hora_inicio and hora_fim else ""
    finalidade = solicitacao.get_finalidade_display().lower() if hasattr(solicitacao, "get_finalidade_display") else "operação planejada"
    return {
        "perigos_identificados":"\n".join(f"• {p}" for p in dict.fromkeys(perigos)) or "• Nenhum perigo adicional identificado automaticamente. Confirmar condições locais.",
        "medidas_mitigadoras":"\n".join(f"• {m}" for m in dict.fromkeys(mitigacoes)),
        "condicoes_meteorologicas":"\n".join(condicoes) or "Previsão não vinculada. Confirmar condições meteorológicas antes do voo.",
        "probabilidade_inicial":nivel, "impacto_inicial":nivel,
        "probabilidade_residual":max(1, nivel-2), "impacto_residual":max(2, nivel-1),
        "area_controlada":False, "pessoas_expostas":False,
        "operador_nome": piloto,
        "operador_documento": getattr(getattr(solicitacao, "piloto", None), "cpf", ""),
        "codigo_sarpas": getattr(getattr(solicitacao, "piloto", None), "codigo_sarpas", ""),
        "aeronave_identificacao": aeronave,
        "cenario_operacional": f"Operação de {finalidade} em {getattr(solicitacao, 'local', '') or getattr(planejamento, 'local', '') or 'local a confirmar'}, em {data_operacao:%d/%m/%Y}{periodo}{altura}.",
        "aspectos_gerais": "\n".join(filter(None, [f"Área planejada: {planejamento.area_hectares} ha." if planejamento and planejamento.area_hectares else "", *condicoes])) or "Confirmar características da área, obstáculos, terceiros, iluminação e condições locais.",
        "legislacao_aplicavel": LEGISLACAO_PADRAO,
        "procedimento_acidente": "Interromper a operação e prestar socorro sem criar novos riscos. Acionar SAMU (192), Bombeiros (193) ou emergência local; preservar registros e comunicar os órgãos competentes conforme a ocorrência.",
        "situacoes_risco": situacoes,
        "responsavel_informacoes": piloto,
        "data_avaliacao": hoje, "validade_ate": _validade_12_meses(hoje),
    }
