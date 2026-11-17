# Roteiro e contexto para continuar o projeto (leitura obrigatória para a IA)

Este arquivo resume a conversa que construiu o aplicativo, as decisões do projetista e o que falta.
Leia-o inteiro antes de mexer em qualquer coisa. O estado técnico detalhado está no
[README.md](README.md); o plano original, em [PLANEJAMENTO.md](PLANEJAMENTO.md) (histórico — não é
mais a referência).

Situação em 16/11/2026: aplicativo completo e funcionando, **211 testes passando**.

---

## 1. O projeto em uma frase

Aplicativo **Streamlit + backend em Python puro** que substitui a planilha
`Verificacao_Muro_Arrimo_NBR11682.xlsx`: verificação de estabilidade de muro de arrimo de flexão em
concreto armado (ABNT NBR 11682) e dimensionamento estrutural (ABNT NBR 6118), por metro linear.

## 2. Com quem você está trabalhando

- Engenheiro estrutural, único usuário do aplicativo. **Responda sempre em português do Brasil.**
- Quer resultado conferível: todo número deve ser rastreável à planilha ou à norma.
- Usa o GEO5 como programa de comparação e envia memoriais para confronto.
- Edita a planilha entre sessões: **releia a planilha antes de assumir que nada mudou**.

## 3. Decisões já tomadas — não reabrir

| Data | Decisão |
|---|---|
| 12/11/2026 | Opções de compatibilidade com o GEO5 ficam no aplicativo, marcadas como **legado** e sinalizadas quando ativas |
| 12/11/2026 | **Um único usuário**: projeto salvo em arquivo JSON, sem banco de dados nem autenticação |
| 12/11/2026 | Croqui e gráficos em **matplotlib** (não plotly) |
| 12/11/2026 | A planilha é a fonte; **em conflito ou erro prevalecem a NBR 6118 e a NBR 11682** |
| 13/11/2026 | Blocos de coroamento: face do bloco **alinhada ao tardoz** (lado da terra) por padrão, com opção de mudar |
| 13/11/2026 | Muro com contrafortes: cortina e base como **laje com três bordas engastadas e uma livre**, armada nas duas direções; o método do GEO5 virou opção legada |
| 13/11/2026 | Dimensionamento em **página própria**, com desenho da seção e indicação de bitola e espaçamento de cada armadura |
| 13/11/2026 | Resistência do solo da frente é ação favorável: entra com fator **1,0** no dimensionamento da cortina (a planilha multiplica por γf) |
| 16/11/2026 | Ancoragem (estacas) sob a ponta **não é descontada** do momento nem do cortante da ponta (a planilha desconta; o GEO5 não) |
| 16/11/2026 | Padrões: **δb = 3/4·φ**, **adesão a = α·c** com α por tipo de solo, **solo da frente em repouso** |
| 16/11/2026 | Excentricidade: limite continua B/6; **entre B/6 e B/4 aceita se a base resistir** à distribuição triangular (descolamento); acima de B/4 reprova |
| 16/11/2026 | **Cargas em faixa, em linha e concentrada** (Boussinesq/Terzaghi), parede rígida ×2 por padrão; carga pontual pela média num comprimento de muro |
| 16/11/2026 | Base dimensionada pela **envoltória** de γf × serviço com a combinação de **ações favoráveis em 1,0** (critério do GEO5) |
| 16/11/2026 | Base pelo **pior caso de todas as combinações de 1,0 e γf** por grupo de ações, incluindo reação de serviço sem majorar (pedido expresso; governa o talão) |
| 16/11/2026 | **Equilíbrio do nó**: no modo "Máximo" a ponta recebe no mínimo o momento da cortina menos o do talão |
| 17/11/2026 | Combinações locais: **padrão = critério do GEO5** (empuxo vertical × γf; pesos e reação × 1,0); "todas as locais" virou opção (`comb_base`); nota sempre mostra equilíbrio, GEO5 e todas |
| 17/11/2026 | **Versão desktop** = o mesmo aplicativo numa janela própria (`desktop/`: lançador com pywebview + receita do PyInstaller); não reescrever a interface em outra tecnologia |
| 17/11/2026 | **Versão Android** = interface própria para celular + o mesmo `core/` rodando no aparelho com Pyodide (`android/`); APK pelo GitHub Actions. Nada de reescrever fórmulas em outra linguagem |

Regra derivada: todo novo desvio em relação à planilha tem de ser (a) registrado em
`core/premissas.py` (`DIFERENCAS_DA_PLANILHA`), (b) descrito no README e (c) coberto por teste.

## 4. O que foi pedido e entregue, em ordem

1. **Planejamento** do software → `PLANEJAMENTO.md`.
2. **Execução do plano** com as quatro decisões de 12/11: porte completo da planilha para `core/`,
   interface Streamlit, memorial em PDF, importação/exportação `.xlsx`, projeto em `.json`, testes
   de paridade célula a célula.
3. **Acabamento**: verificação visual das páginas e README.
4. **Estudo de solo na página inicial**: anexar relatório de sondagem SPT em PDF, ler furos, camadas,
   NSPT e nível d'água, escolher **a profundidade em que o muro começa e termina**, preencher a
   verificação e gerar o **gráfico de esforço lateral**.
5. **Três ajustes**: posição do bloco de coroamento; laje com borda livre no muro com
   contrafortes; página separada de dimensionamento com o desenho das armaduras.
6. **Comparação com o GEO5** (mesmo muro, resultados diferentes, principalmente no deslizamento):
   análise das causas e procura de erros no modelo — ver a seção 8.
7. **Correção do item 1 da análise**: resistência frontal sem majoração na cortina em balanço.
8. **Incidente**: outra conversa sobrescreveu `.claude/launch.json`. Nada do software foi afetado;
   a configuração de preview foi restaurada.
9. **Mudança para a nuvem** e este roteiro.

## 5. Arquitetura

Regra de ouro: **`core/` não importa `streamlit`**. É uma biblioteca de engenharia testável sozinha.

```
app.py            navegação (st.navigation): Início · Verificação · Dimensionamento · Parâmetros do solo
paginas/          inicio.py · verificacao.py · dimensionamento.py · solos.py
core/             campos.py (GERADO) · enums.py · models.py · geometria.py · empuxo.py · forcas.py
                  verificacoes.py · avisos.py · concreto.py · dimensionamento.py · fases.py
                  solver.py · planilha.py · placa.py · perfil.py · solos.py · premissas.py
ui/               estado.py · inputs.py · painel.py · graficos.py · armacao.py · estudo_solo.py · formato.py
io_/              projeto.py (JSON) · excel.py · memorial.py (PDF) · sondagem.py (leitura do PDF de SPT)
tools/            gerar_campos.py · gerar_cenarios.py
android/          ponte.py (núcleo ↔ JSON) · src/ (interface para celular) · montar.py · LEIAME.md
desktop/          muro_desktop.py (lançador) · muro_desktop.spec (PyInstaller) · gerar_executavel.bat ·
                  Abrir Muro de Arrimo.bat · requirements-desktop.txt
tests/            10 arquivos, 211 testes; tests/data/cenarios.json é a referência do Excel
```

Cadeia de cálculo (funções puras, sem iteração):

```
Entrada → geometria → empuxo(fase) → forças(fase) → verificações(fase) → dimensionamento
          core.fases.calcular(entrada) devolve Resultado(entrada, geo, fase1, fase2, trav, dim)
```

Convenções que você precisa respeitar:

- **Nomes de campos e resultados = nomes definidos da planilha** (`H_muro`, `p_Pah`, `R_FSd`,
  `dm_Asnp`…). Não renomeie: é o que permite rastrear cada número até a célula.
- `core/campos.py` é **gerado** por `tools/gerar_campos.py` a partir da planilha. Não edite à mão.
  São 121 campos: 108 da planilha e 13 só do aplicativo (`bl_pos`, `bl_x`, `laje_cf`, `comb_base` e os nove `sc_*` das cargas concentradas), reconhecíveis
  por `Campo.celula == ""`.
- `Entrada` é um modelo pydantic v2 congelado, montado com `create_model` a partir de `campos.py`.
  Para variar um dado use `entrada.com(campo=valor)`.
- As listas de opção são enums `str` com **o texto exato da planilha** (`core/enums.py`).
  `OPCOES_LEGADAS` marca as do GEO5.
- Fase 1 (muro livre) e Fase 2 (muro travado, K0) são o mesmo código com o parâmetro `fase`.
- Empuxo por integração numérica em 100 fatias (40 tardoz + 40 plano inclinado + 20 sapata), como
  na planilha.
- As sentinelas da planilha (999 e 10 000 kPa) são `math.inf` no núcleo; `core/planilha.py` as
  reconverte para comparar.
- `core.planilha.MODO_PLANILHA` devolve o aplicativo ao comportamento da planilha nos campos só do
  aplicativo. É o que os testes de paridade usam.
- Estado no Streamlit: `st.session_state["dados"]` é a fonte da verdade; os widgets têm chave
  `w_<campo>`; para aplicar mudanças por código grave em `_pendente` e chame `st.rerun()`
  (`ui/estado.py`).
- API atual do Streamlit: `width="stretch"`, `st.segmented_control`, `st.data_editor`.
- Laje com borda livre: `core/placa.py`, elemento finito de placa retangular de 12 graus de
  liberdade (Kirchhoff), ν = 0,2, conferido contra soluções clássicas em `tests/test_placa.py`.
- Paleta dos gráficos: azul `#2a78d6`, laranja `#eb6834`, verde-água `#1baf7a`.

## 6. Como rodar e testar

Windows (computador do projetista):

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

```bash
.venv\Scripts\python -m streamlit run app.py
```

```bash
.venv\Scripts\python -m pytest
```

Linux (nuvem): os mesmos comandos, trocando `.venv\Scripts\python` por `.venv/bin/python`. O
aplicativo abre em `http://localhost:8501`.

**Limites do ambiente Linux/nuvem:**

- Não há Excel. `tools/gerar_cenarios.py` (recalcula os 75 cenários no Excel por COM) **só roda no
  Windows do projetista**. Os testes de paridade continuam funcionando porque leem
  `tests/data/cenarios.json`.
- Consequência: **se a planilha mudar, a referência não pode ser regerada na nuvem.** Peça ao
  projetista para rodar o gerador no Windows e enviar o novo `cenarios.json`.
- `pywin32` já está restrito ao Windows no `requirements.txt`.

## 7. Onde o aplicativo difere da planilha (deliberado)

Lista completa e atualizada em `core/premissas.py` e no README. Resumo:

- resultante fora da base: o aplicativo reprova o dimensionamento da base (a planilha segue
  calculando com tensão de solo negativa);
- fck > 40 MPa: ηc e, acima de 50 MPa, parâmetros do grupo II;
- verificações extras: cortante no talão e espaçamento máximo das barras;
- resistência frontal com fator 1,0 na cortina;
- ancoragem sob a ponta não alivia os esforços da ponta;
- padrões de `k_phi` (0,75), `k_c` (0,5) e `ff_tipo` (em repouso) — vêm de `PADRAO_APP` em
  `tools/gerar_campos.py`; `core.planilha.PADROES_PLANILHA` devolve os da planilha;
- cargas em faixa/linha/ponto: `core/boussinesq.py`; entram como linhas extras **depois** das 17 forças da
  planilha (só quando ativas) e somadas às pressões da cortina;
- faixa de excentricidade até B/4 (`Verificacoes.exc_faixa`, checks “Base com descolamento”, valores `ex_*`);
- laje com borda livre no muro com contrafortes;
- bloco de coroamento alinhado ao tardoz;
- FS e tensão infinitos no lugar das sentinelas; comparações com tolerância 1e-9.

Nos testes de paridade (`tests/test_paridade_planilha.py`) essas diferenças aparecem como exceções
nomeadas (`_BASE`, `_FRONTAL`, `_ANCORAGEM`, `_FAVORAVEIS`). **Não alargue a tolerância (1e-8) para fazer um teste passar**:
ou é erro de porte, ou é um desvio novo que precisa ser decidido com o projetista.

Defeitos da própria planilha (já comunicados): `Resumo!C35` usa `CONCAT`, inexistente no Excel do
projetista (`#NOME?`); `TEXT(B_base,"0.00")` mostra "B = 003 m" em Excel pt-BR; listas de validação
com vírgula dentro da opção ficam quebradas.

## 8. Comparação com o GEO5 — o que já se sabe

Caso de referência em `tests/test_geo5.py`: muro sem talão, cortina 0,20 × 3,00 m, sapata
1,70 × 0,25 m, argila φ = 30°, c = 5 kPa, γ = 20 kN/m³, q = 10 kPa.

**O deslizamento 0,58 (aplicativo) × 1,26 (GEO5) vem só de critérios, não de erro no modelo:**

| Critério alterado, acumulado | FS deslizamento |
|---|---|
| Padrão do aplicativo (δb = 2/3·φ, sem adesão, sem resistência frontal) | 0,58 |
| δb = φ (`k_phi = 1`) | 0,92 |
| + adesão c·B' (`k_c = 1`) | 1,15 |
| + resistência frontal em repouso, descontada da ação | 1,24 |
| + componente vertical da sobrecarga como no GEO5 | 1,26 |

Com os critérios do GEO5 selecionados, o aplicativo reproduz N, Mres, Movr, Hres, Hact, e/B e σ.

Segundo caso de referência (16/11/2026, no mesmo arquivo): muro com ancoragem na base, cortina
0,20 × 2,50 m, sapata 0,80 × 0,20 m, C20. Estabilidade e armaduras reproduzidas. Cortante da ponta:
GEO5 46,01 (γf só no empuxo, excentricidade recalculada, sem descontar a ancoragem) × aplicativo
70,75 (γf em toda a reação de serviço). MRd da haste com x/d = 0,28: GEO5 64,36 × aplicativo 64,67
(+0,5 %, único ponto em que o aplicativo fica acima); na ponta, com x/d < 0,259, os dois coincidem.

Terceiro caso (16/11/2026, mesmo arquivo): muro com contrafortes na frente e ancoragem. Estabilidade
reproduzida. Atenção: o "espaçamento l" do GEO5 é o **vão livre**; o `cf_esp` do aplicativo é entre
eixos (l + espessura). Cortina: mesmas fórmulas, aplicativo ~4 % acima (o GEO5 não majora a sobrecarga).
Contraforte: aplicativo 40 % acima (o GEO5 usa coeficiente 1,0). As mín do GEO5 = 0,15 %·b·d (aplicativo:
b·h). **Base entre contrafortes: aplicativo 17 % ABAIXO do GEO5** (224 × 269 kPa) — o GEO5 majora só o
empuxo, com pesos e ancoragem em 1,0; o aplicativo multiplica tudo por γf e a excentricidade fica menor.
**Corrigido em 16/11/2026**: a base usa a envoltória com a combinação de ações favoráveis em 1,0
(`comb_fav` em `core/dimensionamento.py`, valores `dm_*_fav` e `bd_s_fav`), que reproduz os 269 kPa e
os cortantes de ponta do GEO5 (23,0 e 46,0 kN/m nos dois primeiros casos).

Quarto caso (16/11/2026): muro com talão e cunha inclinada (primeira validação desse modelo contra o
GEO5), rodado em C20 e em C25. Estabilidade, haste e cortante da ponta reproduzidos. Momento do avanço:
67,68 no GEO5 × 30,9 no aplicativo (pressões na base). **Confirmado** com a página do dente: o GEO5 usa
o equilíbrio do nó, avanço = haste − dente = 94,35 − 26,68. O dente do GEO5 (26,68 kN·m/m e 21,26 kN/m)
usa empuxo × 1,4, pesos × 1,0 e a reação do solo de serviço × 1,0, e soma o momento do empuxo
horizontal; o cortante foi reproduzido, o momento só com a seção 0,10 m dentro da haste (regra não
identificada). **Ajustado em 16/11/2026**: equilíbrio do nó na ponta (78,6 neste muro, contra 67,68) e
talão pelo pior caso das combinações (15,9 kN·m/m e 28,2 kN/m). O momento do empuxo horizontal do "dente"
do GEO5 NÃO foi copiado: tem sentido contrário ao das cargas verticais e é levado pela haste. Em 17/11/2026 o padrão das
combinações locais passou a ser o do GEO5, que reproduz o cortante do dente (21,3 × 21,26 kN/m); com
"todas as locais" o exemplo padrão reprova no talão (8,65 × 8,18 cm²/m).

Diferenças que permanecem, com o aplicativo a favor da segurança salvo indicação:

- momento resistente da cortina: 100,5 × 101,75 kN·m/m. Hipótese **não confirmada**: o GEO5 soma a
  força normal ou a armadura comprimida;
- cortante resistente: o padrão do aplicativo é VRd1 da NBR 6118; o GEO5 usa 0,6·fctd·b·d (legado);
- cortante de cálculo na ponta: 45,1 × 23,0 kN/m. O GEO5 majora só o empuxo e ignora o solo sobre a
  ponta; o aplicativo aplica γf a toda a reação do solo.

## 9. Pendências conhecidas (nenhuma foi pedida ainda)

Proponha antes de fazer; a decisão é do projetista.

1. A opção legada "0,259 (GEO5)" para o limite x/d não reproduz o GEO5 (aplicativo x/d = 0,37).
2. (Resolvida em 16/11/2026) Cortante da ponta: a combinação de ações favoráveis em 1,0 reproduz o GEO5; o aplicativo adota a envoltória com γf × serviço.
3. A água na cortina em balanço é majorada por `gf_f`, e não por `gw_f`. Só importa se os dois
   forem diferentes; no padrão são iguais.
4. Os 11 casos GEO5 citados na aba `Notas` não viraram testes: a aba traz só resultados, sem os
   dados de entrada. Se o projetista fornecer as entradas, viram testes como `test_geo5.py`.
5. O envio do PDF de sondagem pelo navegador não foi testado de ponta a ponta. O leitor foi
   conferido com boletins de duas empresas de sondagem, direto pelos arquivos.
6. Limitações do modelo: uma camada de solo no aterro (o perfil da sondagem é homogeneizado),
   sapata de espessura constante, sem dente nem sismo; cargas concentradas sem efeito nas lajes entre contrafortes; **estabilidade global não
   é verificada**; sem fissuração, ancoragem e emendas, nem estribos do contraforte.
7. `Parametros_do_solo_Recomendado.xlsx` alimenta `core/solos.py`; se mudar, atualizar as tabelas.

## 10. Roteiro para atender um pedido novo

1. Leia o pedido e identifique se ele toca **cálculo** (`core/`), **interface** (`ui/`, `paginas/`)
   ou **entrada/saída** (`io_/`).
2. Se envolver a planilha, releia as células envolvidas com `openpyxl` (fórmulas e valores) antes
   de escrever código.
3. Rode `pytest` antes de começar, para confirmar os 211 testes verdes.
4. Faça a mudança no núcleo primeiro, com teste; só depois a interface.
5. Se o resultado passar a diferir da planilha, pare e classifique: erro de porte (corrija) ou
   desvio deliberado (registre em `premissas.py`, no README e como exceção nomeada na paridade).
   Em conflito entre planilha e norma, **prevalece a norma**.
6. Se a planilha ganhou entradas: `tools/gerar_campos.py` → portar as fórmulas →
   `tools/gerar_cenarios.py` (só no Windows) → `pytest`.
7. Confira a interface de verdade: abra o aplicativo e olhe a página alterada, além do
   `tests/test_app.py` (AppTest).
8. Rode a suíte inteira e informe o resultado como ele é, incluindo o que não foi verificado.
9. Atualize o README (e este roteiro, se mudar uma decisão ou pendência).

## 11. Armadilhas já encontradas

- **PowerShell 5.1** no Windows do projetista: não há `&&`; `python -c` com aspas quebra — escreva
  o script num arquivo temporário e execute.
- Arquivos do projeto são **UTF-8 sem BOM**; não regrave com `Set-Content` sem `-Encoding utf8`.
- Gerador de cenários: abre a planilha somente leitura, nunca salva, e troca `CONCAT` por
  `CONCATENATE` em memória.
- Comparações de limite com ponto flutuante (ex.: 1,4 − 0,4 < 1,0): use as funções tolerantes de
  `core/avisos.py`.
- Lambdas criadas em laço (tabela de forças): fixe a variável com argumento padrão.
- Leitor de sondagem: os boletins trazem cabeçalho e legenda na coluna de descrição, texto
  sobreposto duplicado e pares de golpes quebrados em duas linhas; as linhas de SPT são
  reconhecidas pela aritmética N1 = g1 + g2 e N2 = g2 + g3. PDF escaneado não é lido.
- AppTest: verifique as chaves dos widgets; nos testes de cobertura, pule campos com
  `celula == ""`.
- matplotlib: use `bold`, não `semibold`.
- A pasta `site/` e a configuração `site-ohara` em `.claude/launch.json` pertencem a **outro
  projeto** do mesmo usuário e não fazem parte deste repositório. Não mexa nelas.
