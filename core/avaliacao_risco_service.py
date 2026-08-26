def dados_automaticos_avaliacao(solicitacao):
    planejamento = solicitacao.planejamento
    meteo = planejamento.resumo_meteorologico if planejamento else {}
    aeronautica = meteo.get("aeronautica", {})
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
    mitigacoes.extend([
        "Realizar consulta ao SARPAS, AISWEB e NOTAM antes da operação.",
        "Manter VLOS, área de decolagem controlada, observador quando necessário e procedimento de interrupção disponível.",
    ])
    nivel = 4 if aeronautica.get("status") == "desfavoravel" or meteo.get("status") == "desfavoravel" else 3 if aeronautica.get("status") == "atencao" or meteo.get("status") == "atencao" else 2
    return {
        "perigos_identificados":"\n".join(f"• {p}" for p in dict.fromkeys(perigos)) or "• Nenhum perigo adicional identificado automaticamente. Confirmar condições locais.",
        "medidas_mitigadoras":"\n".join(f"• {m}" for m in dict.fromkeys(mitigacoes)),
        "condicoes_meteorologicas":"\n".join(condicoes) or "Previsão não vinculada. Confirmar condições meteorológicas antes do voo.",
        "probabilidade_inicial":nivel, "impacto_inicial":nivel,
        "probabilidade_residual":max(1, nivel-2), "impacto_residual":max(2, nivel-1),
        "area_controlada":False, "pessoas_expostas":False,
    }
