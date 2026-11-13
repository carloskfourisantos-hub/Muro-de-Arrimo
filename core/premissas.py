"""Premissas, limitações e diferenças em relação à planilha (texto para a UI e o memorial).

Conteúdo da aba ``Notas`` da planilha, organizado por tema.
"""

PREMISSAS: dict[str, list[str]] = {
    "Modelo": [
        "Muro tratado como corpo rígido, por metro linear. Momentos em torno da aresta inferior da ponta.",
        "Plano de cálculo do empuxo — cunha 'Inclinada' (padrão): plano de ruptura de Rankine, "
        "θ = 45° − φ/2 − (ε − β)/2 com a vertical (sen ε = sen β / sen φ), da extremidade do talão até encontrar "
        "o tardoz; acima disso o empuxo atua no tardoz real (δ estrutura-solo). Só o triângulo de solo abaixo do "
        "plano conta como peso sobre o talão.",
        "Cunha 'Vertical': dorso virtual vertical pela extremidade do talão; todo o solo sobre o talão conta "
        "como peso.",
        "Na altura da sapata o empuxo atua num plano vertical em x = B com δ estrutura-solo. Sem talão, atua no "
        "tardoz real em toda a altura.",
        "Contrafortes não alteram o empuxo e, por padrão, não entram no peso (a favor da segurança).",
    ],
    "Empuxo": [
        "Rankine: formulação de Mazindrani-Ganjali (1997) — Rankine com coesão e terreno inclinado: "
        "σa = σz'·K'·cos β, paralelo ao terreno.",
        "Coulomb por trecho: Ka(α, δ, β) de Müller-Breslau; σa = Ka·σz' − 2c·Kac, com "
        "Kac = cos φ·cos β·cos²α / (1 + sen(φ + δ − α − β)); empuxo inclinado de α + δ com a horizontal.",
        "Corte de tração: σa < 0 é zerado. A sobrecarga q soma-se a σz' em toda a altura.",
        "Integração numérica por fatias (ponto médio): exata para diagramas lineares.",
        "Fase 2 (muro travado): empuxo em repouso K0 = (1 − sen φ)(1 + sen β) (Jaky; EN 1997-1 9.5.2), "
        "horizontal e sem coesão, mais a força do travamento.",
    ],
    "Água": [
        "Empuxo de terra com tensões efetivas (γ' = γsat − γw abaixo do NA) + empuxo hidrostático separado.",
        "Peso do solo sobre o talão com γsat abaixo do NA; subpressão linear entre γw·hw,frente (ponta) e "
        "γw·hw,atrás (talão).",
    ],
    "Verificações de estabilidade (ABNT NBR 11682)": [
        "Tombamento: FS = Mres / Movr ≥ 2,0.",
        "Deslizamento: FS = (N·tan δb + a·B' + resistências horizontais) / H_act ≥ 1,5, com δb = kφ·φf e "
        "a = kc·cf. Empuxo passivo na frente desprezado.",
        "Excentricidade: e = B/2 − (Mres − Movr)/N; limite padrão e ≤ B/6 (base inteiramente comprimida).",
        "Tensões: distribuição linear (triangular se e > B/6) e tensão média de Meyerhof em B' = B − 2|e|.",
        "Capacidade de carga: Vesic, sapata corrida, com B', fatores de inclinação e sem fatores de "
        "profundidade; FS = qult / σef ≥ 3,0.",
        "Qualquer aviso de consistência dos dados leva o resultado a 'NÃO ATENDE', como na planilha.",
    ],
    "Dimensionamento (ABNT NBR 6118)": [
        "Cortina em balanço engastada no topo da sapata, esforços em 21 seções. Caso A = muro livre (empuxo em "
        "repouso por padrão, ou ativo); caso B = muro travado (repouso + força do travamento).",
        "Flexão simples com diagrama retangular; As mín pela Tabela 17.3 (ρmín·b·h); x/d ≤ 0,45; cisalhamento "
        "VRd1 de lajes sem armadura transversal (19.4.1). Esforços característicos × γf.",
        "Ponta e talão em balanço a partir das faces da cortina, com as tensões da verificação de estabilidade "
        "(Fases 1 e 2), subpressão, peso próprio e estacas.",
        "Muro com contrafortes: cortina e base entre contrafortes como laje com três bordas engastadas e uma "
        "livre (placa por elementos finitos, momentos nas duas direções) e contraforte como viga em balanço. "
        "Opção legada: coeficientes do GEO5 (M vertical = 0,03·σH·H1·l; M horizontal = σp·l²/12 nos apoios e "
        "σp·l²/20 no vão; V = σp·l/2).",
        "Critérios a favor da segurança em relação ao GEO5: momento resistente sem a força normal nem a "
        "armadura comprimida; cortante da ponta com γf aplicado a toda a reação do solo.",
    ],
    "Limitações": [
        "Uma única camada de solo no aterro; sapata de espessura constante; sem dente; sem sismo; sem cargas "
        "concentradas.",
        "Estabilidade global (FS ≥ 1,5 pela NBR 11682) NÃO é verificada: use um programa de estabilidade de "
        "taludes.",
        "Cunha inclinada que atinge o terreno antes do tardoz (talão longo) e cunha inclinada com Rankine: "
        "implementadas, mas não validadas contra o GEO5. NA na frente e subpressão linear idem.",
        "Blocos de coroamento: sem empuxo passivo no bloco, efeito de grupo ou parcela de compressão absorvida "
        "pelas estacas. Tração nas estacas e ligação bloco-sapata devem ser dimensionadas à parte.",
        "Não são verificados: fissuração (ELS-W), ancoragem e emendas das barras, armadura transversal do "
        "contraforte, juntas e drenagem.",
    ],
}

DIFERENCAS_DA_PLANILHA: list[str] = [
    "Opções de compatibilidade com o GEO5 continuam disponíveis, mas marcadas como LEGADO e sinalizadas no "
    "resultado quando ativas.",
    "FS infinito e tensão infinita são mostrados como '∞' / 'fora da base' em vez das sentinelas 999 e "
    "10 000 kPa da planilha (convenção do GEO5).",
    "Resultante fora da base (|e| ≥ B/2): a planilha segue dimensionando ponta e talão com tensões de solo "
    "negativas e pode indicar 'ATENDE'; o aplicativo reprova o dimensionamento da base.",
    "fck > 40 MPa: o aplicativo aplica ηc (NBR 6118:2023, 17.2.2) e, acima de 50 MPa, λ, αc, fctm, ρmín e "
    "x/d ≤ 0,35 do grupo II; a planilha usa 0,85·fcd·0,8x e ρmín = 0,208 % para qualquer fck.",
    "Verificações adicionais (NBR 6118): cortante no talão (19.4.1) e espaçamento máximo das barras "
    "principais (20.1). A planilha só verifica o cortante na ponta.",
    "Força mínima de travamento: além da estimativa da planilha (excentricidade fixa), o aplicativo calcula o "
    "valor exato recalculando a Fase 2.",
    "Resistência do solo da frente no dimensionamento da cortina em balanço: é ação favorável e entra com "
    "fator 1,0 (NBR 8681); a planilha a multiplica por γf. Os esforços de cálculo ficam um pouco maiores.",
    "Muro com contrafortes: por padrão a cortina e a base entre contrafortes são calculadas como laje com três "
    "bordas engastadas e uma livre (placa por elementos finitos, ν = 0,2), com momentos e armadura nas duas "
    "direções; os coeficientes do GEO5 usados pela planilha ficam como opção legada.",
    "Blocos de coroamento: por padrão a face do bloco fica alinhada ao tardoz (lado da terra) e, com uma só "
    "linha de estacas, a estaca fica no eixo do bloco; a planilha centra o bloco nas estacas (opção mantida).",
    "Comparações de limite usam tolerância de 1e-9 (ex.: espaçamento entre linhas de estacas exatamente "
    "igual a 2,5·d não gera aviso).",
]
