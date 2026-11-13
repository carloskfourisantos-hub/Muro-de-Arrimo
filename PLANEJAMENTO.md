# Planejamento — Aplicativo de Muro de Arrimo (Streamlit + Python)

Transformação da planilha **`Verificacao_Muro_Arrimo_NBR11682.xlsx`** em aplicativo web, com arquitetura
preparada para receber depois as outras duas planilhas da pasta.

> **Situação em 12/11/2026 — executado.** Este é o plano original (11/11); o estado real do projeto
> está no [README.md](README.md). O que mudou na execução:
> - a planilha ganhou a aba `Dimensionamento` (NBR 6118) depois do plano — foi portada em
>   `core/dimensionamento.py` e `core/concreto.py`;
> - decisões tomadas: opções GEO5 como legado, usuário único (projeto em JSON), croqui em matplotlib,
>   planilha como fonte e NBR 6118 / NBR 11682 prevalecendo em conflito;
> - o modelo de entrada ficou plano (um campo por nome definido), gerado de `core/campos.py`, e não
>   em 9 submodelos; as páginas ficam em `paginas/` com `st.navigation`; o PDF usa reportlab;
> - a validação da camada 1 foi feita com o Excel via COM (75 cenários), não com LibreOffice;
> - a camada 2 (casos GEO5 da aba `Notas`) não foi feita: a aba só traz resultados, sem as entradas;
> - a página "Empuxo de Solos" saiu do escopo porque `Dim. Empuxo de solos.xlsm` foi removido da pasta.

---

## 1. O que a planilha é hoje (levantamento feito)

9 abas, **~230 nomes definidos** (toda célula de entrada e de saída já é nomeada — isso é ouro para o port):

| Aba | Linhas | Papel | Vira o quê no app |
|---|---|---|---|
| `Entrada` | 90 | 9 seções de dados, 54 entradas, 14 listas de validação | `core/models.py` + `ui/inputs.py` |
| `Geometria` | 129 | parâmetros derivados + 6 polígonos (shoelace: área e centroide) + dados do croqui | `core/geometria.py` + `ui/croqui.py` |
| `Empuxo` | 144 | 33 colunas × **100 fatias** de integração numérica (40 tardoz + 40 plano inclinado + 20 sapata) | `core/empuxo.py` (vetorizado) |
| `Forças` | 36 | 17 linhas de forças (Fx, Fz, x, z, Mres, Movr) + detalhe de ancoragem | `core/forcas.py` |
| `Resumo` | 61 | 4 verificações + tensões + Vesic + string de avisos | `core/verificacoes.py`, `core/capacidade.py`, `core/avisos.py` |
| `Empuxo F2`, `Forças F2`, `Resumo F2` | — | **cópias da Fase 2** (muro travado, K0) + força mínima de travamento | mesmo código com `fase=2` |
| `Notas` | 59 | premissas, limitações e **11 casos validados contra o GEO5 5.2026** | docstrings + suíte de testes |

### Fatos estruturais que decidem a arquitetura

1. **A planilha é um DAG puro de células nomeadas.** Não há macro, não há iteração circular, não há
   `VBA` (o `.xlsx` é limpo). Ou seja: dá para portar como **funções puras encadeadas**, sem solver.
2. **As abas "F2" são a mesma planilha duplicada** com `F_fase = 2` (`Forças!I1`). No Python isso não é
   duplicação de código: é **um parâmetro** `fase: 1 | 2`.
3. **O único acoplamento "circular" aparente** é `Empuxo` ler `F_fase` de `Forças`, e `Resumo` ler
   `CC_qult` de si mesma. Na prática a ordem é linear:
   `entrada → geometria → empuxo(fase) → forças(fase) → verificações(fase) → capacidade`.
4. **A integração em 100 fatias é trivial computacionalmente** (~3300 operações). Vetorizada em numpy
   roda em microssegundos → recálculo a cada tecla, sem `st.form`, sem fila de jobs.
5. **Tudo é por metro linear de muro** — não há dimensão longitudinal (contraforte e ancoragem são
   "diluídos" por `t/espaçamento` e `n/v`). Isso simplifica radicalmente o modelo de dados.

---

## 2. Arquitetura

**Regra de ouro: o backend não importa `streamlit`.** O núcleo é uma biblioteca de engenharia testável e
reusável (CLI, API, batch, outro frontend). O Streamlit é só a camada de apresentação.

```
muro_arrimo/
├─ app.py                        # Home: seleção de projeto, descrição, navegação
├─ pages/
│  ├─ 1_🧱_Verificacao_NBR11682.py   # ESTA é a página pedida
│  ├─ 2_📐_Empuxo_de_Solos.py        # futura (Dim. Empuxo de solos.xlsm)
│  └─ 3_🧪_Parametros_do_Solo.py     # futura (Parametros_do_solo_Recomendado.xlsx)
│
├─ core/                         # ← BACKEND PURO (zero streamlit, zero I/O)
│  ├─ enums.py                   # as 14 listas de validação da aba Entrada
│  ├─ models.py                  # Entrada (pydantic) + dataclasses de resultado
│  ├─ constants.py               # FS mínimos NBR 11682, defaults, tolerâncias (1e-9, 1e9)
│  ├─ geometria.py               # derivados, cunha, 6 polígonos (shoelace), croqui
│  ├─ empuxo.py                  # Rankine/Mazindrani, Coulomb, K0, água, subpressão
│  ├─ forcas.py                  # tabela de 17 forças → Hnet, N, Mres, Movr, Hact
│  ├─ ancoragem.py               # Tp, Rt, blocos de coroamento
│  ├─ capacidade.py              # Vesic (Nq, Nc, Nγ, iq, iγ, ic)
│  ├─ verificacoes.py            # FSt, FSd, e/B, σmax/σmin/σef, FScc
│  ├─ avisos.py                  # as 19 checagens de consistência do Resumo!C35
│  ├─ fases.py                   # orquestra Fase 1 + Fase 2 + força mínima de travamento
│  └─ solver.py                  # EXTRA: dimensionamento automático (ver §7)
│
├─ ui/
│  ├─ inputs.py                  # widgets espelhando as seções 1–9 da aba Entrada
│  ├─ croqui.py                  # desenho do muro (plotly)
│  ├─ diagramas.py               # diagrama de empuxo, tensões na base, polígono de forças
│  ├─ resultados.py              # cards de FS, tabela por fase, avisos
│  └─ theme.py                   # formatação pt-BR (vírgula decimal), unidades
│
├─ io_/
│  ├─ projeto.py                 # salvar/carregar projeto (.json versionado)
│  ├─ excel.py                   # importar da planilha / exportar xlsx de resultados
│  └─ memorial.py                # memorial de cálculo em PDF
│
├─ tests/
│  ├─ data/                      # workbooks-cenário com valores recalculados
│  ├─ test_paridade_planilha.py  # célula nomeada a célula nomeada, tol. 1e-9
│  ├─ test_casos_geo5.py         # os 11 casos da aba Notas
│  ├─ test_invariantes.py        # hypothesis: monotonicidades e limites físicos
│  └─ test_regressao_ui.py       # smoke test com streamlit.testing.v1.AppTest
├─ requirements.txt / pyproject.toml
└─ README.md
```

### Stack

| Camada | Escolha | Por quê |
|---|---|---|
| Python | **3.12** em venv | 3.14 está instalado aqui, mas wheels de reportlab/plotly ainda são irregulares |
| Entrada/validação | **pydantic v2** | as 54 entradas têm faixas, unidades e inter-dependências; validação declarativa |
| Numérico | **numpy** | as 100 fatias como arrays; 1 linha substitui 3300 células |
| Tabelas | **pandas** | tabela de forças e de fatias saem prontas para `st.dataframe` |
| Gráficos | **plotly** | croqui com proporção 1:1 travada, hover nos vértices, exportável |
| Frontend | **streamlit** ≥ 1.40 (multipage nativo) | pedido do projeto |
| PDF | **jinja2 + weasyprint** (alt.: reportlab) | memorial em HTML/CSS é muito mais fácil de manter |
| Testes | **pytest + hypothesis** | paridade numérica + invariantes |

### Fluxo de dados

```
ui/inputs.py  →  Entrada (pydantic, frozen, hashable)
                      │
                      ▼  @st.cache_data(hash_funcs={Entrada: hash})
              core.fases.calcular(entrada)
                      │
   ┌──────────────────┴──────────────────┐
   ▼                                     ▼
Fase 1 (ativo, sem travamento)    Fase 2 (K0, travado)   ← só se trav_usar
   │                                     │
   └──────────────┬──────────────────────┘
                  ▼
          ResultadoCompleto  →  ui/resultados.py, ui/croqui.py, io_/memorial.py
```

Uma função pura, um objeto de resultado imutável, cache por hash da entrada. Recálculo total < 5 ms →
UI reativa a cada widget, sem botão "Calcular".

---

## 3. Modelo de dados (mapeamento nome-da-planilha → campo)

`Entrada` é um pydantic model com 9 sub-modelos espelhando as seções da aba. Mapeamento integral
(é o contrato do port — vai no código como comentário de rastreabilidade):

| Seção | Nomes na planilha | Campo Python |
|---|---|---|
| 1. Geometria | `H_muro, h_sap, t_topo, t_base, face_inc, b_ponta, b_talao, D_frente, solo_ponta` | `geometria.*` |
| 2. Contrafortes | `cf_usar, cf_tipo, cf_peso, cf_esp, cf_t, cf_h, cf_Lb, cf_Lt` | `contrafortes.*` |
| 2b. Ancoragem | `anc_usar, anc_x, anc_n1, anc_x2, anc_n2, anc_L, anc_d, anc_esp, anc_a, anc_FS, anc_ds, anc_fy, anc_H` | `ancoragem.*` |
| 2c. Blocos | `bl_usar, bl_B, bl_L, bl_H` | `blocos.*` |
| 2d. Travamento | `trav_usar, trav_z, trav_F, trav_conv, trav_emp` | `travamento.*` |
| 3. Terrapleno | `h_reb, beta_t, q_sc, q_estab` | `terrapleno.*` |
| 4. Aterro | `gam_at, gsat_at, phi_at, c_at, metodo_emp, rk_conv, delta_dv, delta_est, modo_cunha` | `aterro.*` |
| 5. Fundação | `gam_f, gsat_f, phi_f, c_f, k_phi, k_c, ff_tipo, conv_res, sc_vert, bef_desl` | `fundacao.*` |
| 6. Água | `hw_at, hw_fr, gam_w, subp, peso_na` | `agua.*` |
| 7. Material | `gam_c` | `material.gam_c` |
| 8/9. Critérios | `cc_modo, qult_inf, FSt_min, FSd_min, FScc_min, eB_lim` | `criterios.*` |

Os 14 campos de lista viram `StrEnum` em `core/enums.py` — **com os textos exatos da planilha**, porque
há comparações de string embutidas nas fórmulas (`IF(trav_conv="Como GEO5", ...)`). Manter os rótulos
idênticos preserva a rastreabilidade e permite importar/exportar a planilha sem tradução.

Unidades a converter no boundary: `anc_ds` (mm → m), `anc_fy` (MPa → kPa), ângulos (° → rad).

---

## 4. Port módulo por módulo (com as armadilhas já identificadas)

### 4.1 `core/geometria.py`
- Derivados `Geometria!C5:C27`: `h_cort, B_base, x_fb, x_tb, x_ft, x_tt, z_ter, x_bt, z_dv, cv, eps_r, th_c, a_t, u_w, u_t, hit_t, z_P, x_P, z_top_pl, z_na, z_naw, z_cf, z_D`.
- 6 polígonos (cortina, sapata, cunha de solo, parcela abaixo do NA, contraforte, solo sobre a ponta)
  → **uma única função** `poligono(vertices) -> (area, cx, cz)` por shoelace. Substitui ~150 células.
- Armadilhas: `u_w` usa sentinela `1e9` quando o denominador ≤ 1e-9; centroides retornam `(0,0)` quando
  |área| < 1e-9; `cv` e `hit_t` são flags 0/1 usadas em aritmética.
- Saída extra: as polilinhas do croqui (`Geometria!C97:D129`) já existem na planilha → portar direto.

### 4.2 `core/empuxo.py` — o coração
Vetorizar as 100 fatias (`Empuxo!B45:AG144`) em arrays numpy de 100 posições:

```python
z      = np.concatenate([midpoints(zA_top, zA_bot, 40),      # tardoz / dorso virtual
                         midpoints(zA_bot, zB_bot, 40),      # plano inclinado
                         midpoints(h_sap,  0.0,    20)])     # sapata
trecho = np.array(["Tardoz"]*40 + ["Plano inclinado"]*40 + ["Sapata"]*20)
```
Depois, por coluna da planilha: `α` (F), `δ` (G), `x do plano` (H), `σz'` (I), `r=c/σz'` (J),
`K' Mazindrani` (K), `σa Rankine` (L), `Ka Coulomb` Müller-Breslau (M), `Kac` (N), `σa Coulomb` (O),
inclinação (P), `σa adotado` (Q), e as integrais `dPa, dPa,h, dPa,v, dPa,h·z, dPa,v·x` + as colunas
"só solo" (W–AE) usadas para separar as parcelas solo/sobrecarga.

Armadilhas:
- `p_dw = 1e9` significa "sem NA" — manter o sentinela ou trocar por `np.inf` (funciona em `minimum`).
- **Corte de tração**: `max(0, ...)` por fatia, nunca na resultante.
- `rk_conv = "Como GEO5"` muda a fórmula do σa e a forma de somar a sobrecarga (sem `cos β`, fenda no
  diagrama bruto). São dois caminhos distintos, não um fator.
- `sc_vert = "Como GEO5"` usa `p_Pav_s + p_Pav_q` em vez de `p_Pav_c` — duas somas paralelas.
- `p_rep` (Fase 2 em repouso) **curto-circuita** σa para `σz'·K0` com inclinação 0.
- O `δ` varia por trecho: `delta_est` no tardoz e na sapata, `delta_dv` no plano inclinado/dorso virtual.
- Saídas: `p_Pa, p_Pah, p_zPa, p_Pah_s, p_Pah_q, p_Pav*, p_xPav, p_U, p_zU, p_Uf, p_zUf, p_K0f, p_Rff,
  p_zRff, p_u0, p_uB, p_Usub, p_xUsub`.

**Ganho do app sobre a planilha:** o número de fatias passa a ser configurável (100 → 1000) e o
diagrama σa(z) fica disponível como gráfico, não só como 100 linhas invisíveis.

### 4.3 `core/forcas.py`
Tabela de 17 forças (`Forças!B5:I21`) como lista de `Forca(nome, Fx, Fz, x, z, obs)`; os totais saem de
reduções sobre a lista:
- `F_Hnet = Σ Fx`, `F_N = Σ Fz`, `F_Mres = Σ Mres`, `F_Movr = Σ Movr`
- `F_Hact = Σ Fx onde Fx > 0` (o `SUMIF(">0")` — atenção: forças resistentes entram com **Fx negativo**)
- `F_Hres_ext = −Σ(Fx<0) − F_Htrav`
- `Mres`/`Movr` por força dependem de `conv_res` e `trav_conv` (3 convenções de travamento) — manter
  como regra explícita por linha, não como `if` global.

### 4.4 `core/verificacoes.py` + `core/capacidade.py`
- Tombamento `R_FSt = Mres/Movr` (sentinela 999 se `Movr ≤ 0`).
- Deslizamento `R_FSd = (N·tan δb + a·B' + ΣHres + anc_Hm) / H_act`.
- Excentricidade `R_e = B/2 − (Mres−Movr)/N`, limite `eB_lim` (padrão B/6).
- Tensões: linear com três ramos (`|e| ≤ B/6`, triangular, e o **sentinela 10 000 kPa** quando
  `|e| ≥ B/2`, convenção do GEO5) + `σef = N/B'` de Meyerhof.
- Vesic: `Nq, Nc (5,14 se φ=0), Nγ, q0, γ', m, iq, iγ, ic` — com os dois ramos de `φf = 0`.
- Decisão de projeto: no Python os sentinelas (999, 10000) ficam **isolados numa camada de
  apresentação**; o núcleo retorna `None`/`inf` e o veredito OK/NÃO OK vem de comparação explícita.
  Isso evita que 999 vaze para um gráfico ou para um memorial.

### 4.5 `core/fases.py` — e um ganho real sobre a planilha
Fase 1 = ativo sem travamento; Fase 2 = `trav_emp` (K0 ou ativo) com a força. Veredito geral = as duas.

A planilha calcula a **força mínima de travamento** (`Resumo F2!C57:C59`) e avisa em `B61` que o valor
de deslizamento é *estimativa*, porque a força muda a excentricidade e com ela a parcela de adesão.
No app isso vira exato: `scipy.optimize.brentq` sobre `trav_F` para cada FS alvo, recalculando a fase
inteira em cada iteração (5 ms × ~15 iterações = imperceptível). **Esse é o primeiro recurso que o
aplicativo entrega e a planilha não consegue.**

### 4.6 `core/avisos.py`
O `CONCAT` monstruoso de `Resumo!C35` (19 condições) vira uma lista de regras:

```python
REGRAS = [
    Regra("beta_gt_phi", lambda e, g, r: e.terrapleno.beta_t > e.aterro.phi_at,
          "β > φ do aterro: teorias de empuxo inválidas", nivel=ERRO),
    ...
]
```
Com **nível** (erro bloqueante / aviso / informativo), que a planilha não tem: `β > φ` invalida o
cálculo, "contraforte limitado ao talão" é só informativo. Na UI: `st.error` vs `st.warning`.

---

## 5. A página Streamlit `1_🧱_Verificacao_NBR11682.py`

Layout em duas colunas, `wide`:

```
┌─ sidebar ──────────┐┌─ coluna esquerda (entradas) ─┐┌─ coluna direita (resultados) ──┐
│ Projeto / obra     ││ ▸ 1. Geometria do muro       ││  FSt 4,03 ✅   FSd 1,09 ❌      │
│ Salvar / Carregar  ││ ▸ 2. Contrafortes            ││  e/B 0,034 ✅  FScc 6,59 ✅     │
│ Importar planilha  ││ ▸ 2b. Ancoragem na base      ││  ▸▸ NÃO ATENDE                 │
│ Presets de solo    ││ ▸ 2c. Blocos de coroamento   ││ ┌────────────────────────────┐ │
│ Nº de fatias (100) ││ ▸ 2d. Travamento             ││ │  croqui do muro (1:1)      │ │
│ Mostrar memória    ││ ▸ 3. Terrapleno e sobrecarga ││ │  + terreno, NA, plano de   │ │
│ ─────────          ││ ▸ 4. Solo arrimado           ││ │  cálculo, forças, σ base   │ │
│ ⬇ PDF  ⬇ XLSX      ││ ▸ 5. Solo de fundação        ││ └────────────────────────────┘ │
│                    ││ ▸ 6. Água                    ││  Fase 1 | Fase 2 | Limite      │
│                    ││ ▸ 7. Material                ││  ⚠ avisos de consistência      │
│                    ││ ▸ 8/9. Critérios e FS mín.   ││                                │
└────────────────────┘└──────────────────────────────┘└────────────────────────────────┘
```

Abaixo, abas de detalhamento (= as abas da planilha, preservando a auditabilidade):

`📋 Resultados` · `🧮 Forças` · `📈 Empuxo` · `📐 Geometria` · `🏗 Capacidade de carga` · `📖 Premissas`

- **Resultados**: tabela de verificações (valor / limite / situação) + comparativo Fase 1 × Fase 2 +
  força mínima de travamento.
- **Forças**: a tabela de 17 linhas com Fx, Fz, x, z, Mres, Movr e totais (`st.dataframe` com
  destaque de sinal) — é o que o engenheiro confere contra o GEO5.
- **Empuxo**: diagrama σa(z) por trecho + decomposição solo/sobrecarga/água + a tabela de fatias
  (expander, para auditoria) + K's calculados.
- **Geometria**: derivados, áreas e centroides dos 6 polígonos.
- **Capacidade de carga**: os fatores de Vesic passo a passo.
- **Premissas**: a aba `Notas` renderizada em markdown, incluindo limitações e os casos GEO5.

Detalhes de UX que importam num app de engenharia:
- **Croqui que redesenha a cada input** é o maior ganho sobre a planilha: erro de geometria aparece
  visualmente. Proporção travada (`scaleanchor="x"`), cotas anotadas.
- Widgets com `help=` recebendo os textos da coluna E da aba `Entrada` (já são explicações boas e
  revisadas — reaproveitar literalmente).
- Formatação pt-BR com vírgula decimal na exibição (`locale`-free, via função própria).
- Badge de resultado fixo no topo da coluna direita (`st.metric` + cor condicional).
- Nada de `st.form`: recálculo imediato via `@st.cache_data`.
- `st.session_state` guarda a `Entrada` inteira; URL query params opcionais para compartilhar um caso.

---

## 6. Estratégia de validação (o item mais importante do projeto)

Um app de cálculo estrutural sem prova de paridade é um passivo. Três camadas:

**Camada 1 — paridade célula a célula com a planilha.**
A planilha guarda os valores calculados em cache (`data_only=True` já os entrega). Para N cenários:
1. script gera variantes do `.xlsx` alterando as células de entrada;
2. recalcula em lote via `libreoffice --headless --convert-to xlsx` (fallback: pacote `formulas`, ou
   cenários salvos manualmente no Excel uma única vez);
3. `pytest` compara **todos os ~230 nomes definidos** com o resultado Python, tolerância `1e-9` relativa.

Cenários obrigatórios (combinatória das opções que mudam de fórmula, não só de valor):
`Rankine × Coulomb` · `rk_conv Clássica × Como GEO5` · `cunha Vertical × Inclinada` · com/sem talão ·
com/sem ponta · `β = 0 / 15° / φ` · `c = 0 / 5 / 20 kPa` · com/sem NA atrás · com/sem NA na frente ·
subpressão sim/não · `peso_na` Saturado × Submerso · contrafortes atrás/frente/off · ancoragem 1/2 linhas ·
blocos on/off · travamento × 3 convenções × 2 empuxos · `ff_tipo` × `conv_res` · `sc_vert` ·
`bef_desl` · `cc_modo` Calculada × Informada · `φf = 0`. **≈ 60 cenários** cobrem todos os ramos de `IF`.

**Camada 2 — os 11 casos GEO5 da aba `Notas` (B41:B50).**
Já são valores de referência de software comercial, com as opções de equivalência documentadas. Viram
`test_casos_geo5.py` com os números esperados (Mres, Movr, FS, Hres, Hact, e/B, σ, FScc). É a prova de
que o **modelo** está certo, não só o port.

**Camada 3 — invariantes (hypothesis).**
`FSt` decresce com `q_sc`; `Pa` cresce com `γ` e decresce com `φ`; `B' ≤ B`; `σmin ≥ 0`;
integração com 100 e 1000 fatias converge (< 0,5 %); `c = 0 ⇒ diagrama linear ⇒ integração exata`.

Cada caso reprovado vira um teste de regressão permanente. CI: `pytest` em pre-commit/GitHub Actions.

---

## 7. Recursos que só o aplicativo permite (priorizados)

1. **Força mínima de travamento exata** (§4.5) — substitui a estimativa da `Resumo F2`.
2. **Dimensionamento automático** (`core/solver.py`): dado `H`, achar o mínimo `b_talao` / `b_ponta` /
   `h_sap` que atende os 4 FS. No exemplo atual a planilha dá `FSd = 1,09 < 1,5` — o app já responderia
   "talão de 2,45 m resolve" em vez de o usuário ir tentando na mão.
3. **Estudo paramétrico**: varrer uma variável (`q_sc`, `β`, `hw_at`, `b_talao`) e plotar os 4 FS —
   responde "a partir de que nível d'água o muro reprova?".
4. **Memorial de cálculo em PDF** com fórmulas, valores substituídos, croqui e os avisos. É o
   entregável de projeto que a planilha não produz.
5. **Biblioteca de solos** alimentada por `Parametros_do_solo_Recomendado.xlsx` (abas ARGILA, SILTE,
   AREIA, Solos Mistos, Correlações NSPT) → preencher `φ, c, γ` por tipo de solo/NSPT em vez de digitar.
6. **Comparar casos lado a lado** (2–3 alternativas de geometria na mesma tela).
7. Importar/exportar o `.xlsx` original, para conviver com quem ainda usa a planilha.

---

## 8. Cronograma por etapas

| Etapa | Entrega | Depende de |
|---|---|---|
| **E0** Setup | venv 3.12, pyproject, pre-commit, `app.py` vazio rodando, harness de extração de nomes do xlsx | — |
| **E1** Modelos | `enums.py`, `models.py` (54 entradas validadas), `constants.py`, round-trip JSON | E0 |
| **E2** Geometria | `geometria.py` + paridade dos ~25 derivados e 6 polígonos | E1 |
| **E3** Empuxo | `empuxo.py` vetorizado + paridade das 33 colunas × 100 fatias e dos 20 resultados | E2 |
| **E4** Forças e verificações | `forcas.py`, `ancoragem.py`, `capacidade.py`, `verificacoes.py`, `avisos.py` → **Fase 1 completa com paridade** | E3 |
| **E5** Fases | `fases.py`, Fase 2, força mínima exata por `brentq` | E4 |
| **E6** Página Streamlit | entradas, cards de FS, as 6 abas de detalhe, avisos | E5 |
| **E7** Visual | croqui plotly, diagrama de empuxo, tensões na base, polígono de forças | E6 |
| **E8** Validação formal | ~60 cenários de paridade + 11 casos GEO5 + invariantes em CI | E5 |
| **E9** Entregáveis | memorial PDF, export xlsx, salvar/carregar projeto | E6 |
| **E10** Extras | solver de dimensionamento, estudo paramétrico, biblioteca de solos | E8 |
| **E11** Outras páginas | `Empuxo de Solos`, `Parâmetros do Solo` | E10 |

Ordem crítica: **E2→E3→E4 com paridade verificada a cada passo.** Portar tudo e só então testar é a
forma garantida de perder dias caçando uma diferença de 0,3 % no quinto dígito.

---

## 9. Riscos e decisões a tomar

| Risco | Mitigação |
|---|---|
| Recálculo da planilha para gerar os cenários de teste | LibreOffice headless; se indisponível, salvar ~20 cenários manualmente no Excel (uma vez) |
| Divergências numéricas sutis (ordem de operações, `MAX(0,...)` dentro de raiz) | tolerância relativa 1e-9 e comparação **coluna por coluna** das fatias, não só do total |
| Semântica de string das 14 listas | `StrEnum` com os rótulos exatos da planilha; nunca traduzir internamente |
| Python 3.14 nesta máquina | fixar 3.12 no venv (wheels estáveis) |
| Responsabilidade técnica | o app repete as **limitações da aba `Notas`** (uma camada de solo, sem sismo, sem dente, sem estabilidade global) de forma visível no PDF e na UI |
| Escopo estrutural | NBR 6118 (armadura da cortina/sapata/contraforte) **fica fora** desta fase, como na planilha |

### Decisões que preciso confirmar com você

1. **Paridade estrita ou correção?** Onde a planilha segue o GEO5 por compatibilidade (ex.: sentinela
   de 10 000 kPa, `peso_na = Submerso`), mantenho idêntico — ou marco como opção legada?
2. **Multiusuário?** Hoje planejei projeto-em-JSON local (um usuário por sessão). Se vai ser hospedado
   para equipe, entra autenticação + banco (SQLite/Postgres) e isso muda E0 e E9.
3. **Croqui**: plotly (interativo, hover, mas pesado) ou matplotlib (estático, melhor no PDF)?
   Recomendo plotly na tela e matplotlib no memorial.
4. **A planilha continua sendo a fonte da verdade** durante o desenvolvimento (import/export xlsx vale
   a pena), ou o app a substitui de vez?

---

## 10. Primeiro passo concreto

E0 + E1 + E2 em uma tacada: estrutura do projeto, modelo de entrada completo com as 54 variáveis
validadas, módulo de geometria e o primeiro teste de paridade rodando contra os valores já em cache no
`.xlsx`. Isso prova a cadeia inteira (extração → modelo → cálculo → comparação) antes de atacar a
integração do empuxo, que é a parte volumosa.
