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
        "Cargas em faixa, em linha e concentrada no terrapleno (só no aplicativo): pressão horizontal pela teoria "
        "da elasticidade (Boussinesq) na forma de Terzaghi (1954) / NAVFAC DM-7.2 — faixa σh = (2q/π)(β − sen β·"
        "cos 2α); linha σh = (4Q/πH)·m²n/(m² + n²)²; ponto σh = 1,77(P/H²)·m²n²/(m² + n²)³·cos²(1,1θ), com m ≥ 0,4. "
        "Padrão 'parede rígida' = dobro da solução elástica (equivale a ν = 0,5); opção sem dobrar para muro que "
        "se desloca. Pressões horizontais, sem atrito, somadas ao empuxo de terra nas duas fases.",
        "Nessas cargas, a estabilidade usa o plano vertical pela extremidade do talão (carga sobre o talão é "
        "tratada como encostada no plano, e o peso dela só estabiliza se a sobrecarga sobre o talão for marcada "
        "como estabilizante); a cortina usa as distâncias ao tardoz; o talão recebe o peso das cargas que estão "
        "sobre ele. A carga concentrada entra pela média num comprimento de muro informado.",
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
        "Deslizamento: FS = (N·tan δb + a·B' + resistências horizontais) / H_act ≥ 1,5, com δb = kφ·φf "
        "(padrão kφ = 3/4) e adesão a = α·cf (campo kc = α).",
        "α da adesão por tipo de solo (nenhuma norma brasileira fixa o valor): areias e siltes sem argila 0 — "
        "coesão aparente, perdida na saturação; solos argilosos mistos e argilas rijas a duras 0,5; argila muito "
        "mole a média 2/3 — faixa de 1/2 a 2/3 de Das; condição não drenada (c = Su): razão adesão/coesão do "
        "NAVFAC DM-7.2 (1,0 até 24 kPa, caindo a 0,32 em 192 kPa). Sem tipo de solo definido: 0,5. A EN 1997-1 "
        "despreza c' na condição drenada: use α = 0 para esse critério.",
        "Solo na frente do muro: resistência em repouso K0·σ' na altura D (padrão), somada à resistência. Empuxo "
        "passivo desprezado. Só vale se esse solo não puder ser escavado nem erodido.",
        "Excentricidade: e = B/2 − (Mres − Movr)/N; limite padrão e ≤ B/6 (base inteiramente comprimida).",
        "Entre o limite e B/4 a base descola em parte (75 % comprimidos em e = B/4). O solo não resiste à tração "
        "e a NBR 6122 (7.6.2) exige ao menos 2/3 da área comprimida; nessa faixa o muro é aceito se ponta e talão "
        "resistirem, à flexão e ao cortante, à distribuição triangular de tensões — o talão descolado fica sem "
        "reação do solo. Acima de B/4 reprova.",
        "Tensões: distribuição linear (triangular se e > B/6) e tensão média de Meyerhof em B' = B − 2|e|.",
        "Capacidade de carga: Vesic, sapata corrida, com B', fatores de inclinação e sem fatores de "
        "profundidade; FS = qult / σef ≥ 3,0.",
        "Qualquer aviso de consistência dos dados leva o resultado a 'NÃO ATENDE', como na planilha.",
        "Ferramentas (base mínima, menor valor): procuram a excentricidade dentro do limite; a faixa até B/4 não "
        "conta como solução.",
    ],
    "Dimensionamento (ABNT NBR 6118)": [
        "Cortina em balanço engastada no topo da sapata, esforços em 21 seções. Caso A = muro livre (empuxo em "
        "repouso por padrão, ou ativo); caso B = muro travado (repouso + força do travamento).",
        "Flexão simples com diagrama retangular; As mín pela Tabela 17.3 (ρmín·b·h); x/d ≤ 0,45; cisalhamento "
        "VRd1 de lajes sem armadura transversal (19.4.1). Esforços característicos × γf.",
        "Ponta e talão em balanço a partir das faces da cortina, com as tensões da verificação de estabilidade "
        "(Fases 1 e 2), subpressão e peso próprio. Estacas sob o talão aumentam os esforços do talão; estacas "
        "sob a ponta não aliviam os da ponta.",
        "Muro com contrafortes: cortina e base entre contrafortes como laje com três bordas engastadas e uma "
        "livre (placa por elementos finitos, momentos nas duas direções) e contraforte como viga em balanço. "
        "Opção legada: coeficientes do GEO5 (M vertical = 0,03·σH·H1·l; M horizontal = σp·l²/12 nos apoios e "
        "σp·l²/20 no vão; V = σp·l/2).",
        "Base (ponta, talão e laje entre contrafortes na frente): pior caso entre (a) as combinações em "
        "equilíbrio — cada grupo de ações (empuxo; pesos, ancoragem e resistências; água) em 1,0 ou γf (NBR 8681), "
        "com a reação do solo do equilíbrio de cada uma — e (b) a combinação local do GEO5: empuxo vertical × γf, "
        "pesos × 1,0 e reação do solo de serviço × 1,0. 'γf × esforços de serviço' (planilha) é uma das (a). Se em "
        "alguma a resultante de cálculo sair da base, reprova.",
        "Opção 'Equilíbrio + todas as locais': troca (b) pelas 8 combinações locais com reação de serviço, pesos e "
        "empuxo vertical em 1,0 ou γf. Não são equilibradas (ex.: pesos × γf contra reação × 1,0) e ficam bem mais "
        "severas no talão. O dimensionamento sempre traz uma nota com os esforços de (a), (b) e (c).",
        "Equilíbrio do nó cortina-sapata (modo 'Máximo' do momento na ponta): a ponta é armada para, no mínimo, o "
        "momento de cálculo da base da cortina menos o momento para o qual o talão é armado. Sem talão, recebe o "
        "momento inteiro da cortina. Não se aplica à base entre contrafortes.",
        "Faces opostas: quando alguma combinação traciona a face inferior do talão ou a superior da ponta, a "
        "armadura dessa face também é verificada.",
        "Critérios a favor da segurança em relação ao GEO5: momento resistente sem a força normal nem a "
        "armadura comprimida; cortante da ponta com γf aplicado a toda a reação do solo.",
    ],
    "Limitações": [
        "Uma única camada de solo no aterro; sapata de espessura constante; sem dente; sem sismo. Cargas "
        "concentradas e em faixa: uma de cada tipo, só no terrapleno, sem efeito nas lajes entre contrafortes; "
        "terreno inclinado e cunha inclinada são tratados como terreno horizontal na altura do plano de cálculo.",
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
    "Padrões diferentes dos da planilha: atrito base-solo δb = 3/4·φ (planilha: 2/3), adesão a = α·c com "
    "α = 0,5 ou conforme o tipo de solo (planilha: 0) e resistência em repouso do solo da frente (planilha: "
    "nenhuma). Um arquivo da planilha importado mantém os valores dela.",
    "Excentricidade entre o limite e B/4: a planilha reprova; o aplicativo aceita se a base, verificada com a "
    "distribuição triangular de tensões (descolamento parcial), tiver armadura e cortante suficientes e a área "
    "comprimida for ≥ 2/3 (NBR 6122 7.6.2).",
    "Cargas em faixa, em linha e concentrada no terrapleno (Boussinesq): não existem na planilha.",
    "Dimensionamento da base: a planilha usa só γf × esforços de serviço; o aplicativo adota o pior caso de "
    "combinações de 1,0 e γf por grupo de ações (NBR 8681) e da combinação local do GEO5 (empuxo vertical × γf, "
    "pesos e reação de serviço × 1,0). Os esforços nunca ficam abaixo dos da planilha.",
    "Momento da ponta com talão (modo 'Máximo'): além das pressões na base, vale o equilíbrio do nó — momento "
    "da cortina menos o do talão. A planilha só leva o momento da cortina à ponta quando não há talão.",
    "Ancoragem na base sob a ponta: a força das estacas não é descontada do momento nem do cortante da ponta "
    "(a planilha desconta). É resistência passiva, mobilizada por inteiro só na ruptura; o GEO5 também não a "
    "desconta. Os esforços da ponta ficam maiores.",
    "Muro com contrafortes: por padrão a cortina e a base entre contrafortes são calculadas como laje com três "
    "bordas engastadas e uma livre (placa por elementos finitos, ν = 0,2), com momentos e armadura nas duas "
    "direções; os coeficientes do GEO5 usados pela planilha ficam como opção legada.",
    "Blocos de coroamento: por padrão a face do bloco fica alinhada ao tardoz (lado da terra) e, com uma só "
    "linha de estacas, a estaca fica no eixo do bloco; a planilha centra o bloco nas estacas (opção mantida).",
    "Comparações de limite usam tolerância de 1e-9 (ex.: espaçamento entre linhas de estacas exatamente "
    "igual a 2,5·d não gera aviso).",
]
