# Planejamento — aplicativo de muro de arrimo em alvenaria estrutural

Documento para entregar a uma sessão de IA que vai desenvolver o aplicativo. Foi escrito a partir da
experiência de um projeto irmão já pronto: o aplicativo de **muro de arrimo de flexão em concreto
armado**, portado de uma planilha Excel (repositório `carloskfourisantos-hub/Muro-de-Arrimo`, branch
`main-8nxdfu`). O novo aplicativo deve seguir a mesma arquitetura, reaproveitar o que for de mecânica
dos solos e de interface, e trocar só o que é específico da alvenaria.

---

## 0. Instruções para a IA que vai executar este plano

1. **Leia este documento inteiro antes de escrever código.** Depois leia, no repositório de base,
   `ROTEIRO_IA.md` e `README.md`: eles trazem decisões, convenções e armadilhas que valem aqui também.
   Para ter acesso ao repositório de base, peça para anexá-lo à sessão
   (`carloskfourisantos-hub/Muro-de-Arrimo`, branch `main-8nxdfu`).
2. **Responda sempre em português do Brasil.** O usuário é engenheiro estrutural e quer resultados
   conferíveis: todo número precisa ser rastreável a uma célula da planilha ou a um item de norma.
3. **Trabalhe por etapas, na ordem da seção 5.** Cada etapa tem um critério de pronto. Não comece a
   seguinte com testes vermelhos.
4. **Pergunte só o que é decisão do projetista** (seção 3). O resto, decida com o padrão recomendado e
   registre. Quando a planilha e a norma divergirem, **a norma prevalece** — mas avise e registre o desvio.
5. **Nunca invente valores de norma.** Coeficientes, tabelas de resistência (ftk, fvk), limites e
   fatores devem vir da planilha ou do texto da norma. Se não tiver o texto, diga que não tem e peça.
6. **Relate o resultado como ele é**: o que passou, o que falhou, o que não foi verificado.
7. **Mantenha um `ROTEIRO_IA.md` no novo repositório**, no mesmo formato do de base, atualizado a cada
   decisão. É ele que permite continuar o trabalho em outra sessão.

---

## 1. O que é o aplicativo

Aplicativo **Streamlit + núcleo em Python puro** que substitui a planilha de muro de arrimo em
alvenaria estrutural do usuário:

- **Estabilidade externa** (ABNT NBR 11682): tombamento, deslizamento, excentricidade, tensões na base e
  capacidade de carga, por metro linear.
- **Dimensionamento da alvenaria** (ABNT NBR 16868-1): flexão, cisalhamento e compressão da parede
  (armada ou não armada, conforme a planilha), grauteamento, armaduras e detalhamento.
- **Dimensionamento da fundação**: se a base for sapata de concreto armado, ABNT NBR 6118 (reaproveitar
  do projeto de base); fundação conforme ABNT NBR 6122.
- Ações e combinações: ABNT NBR 8681.

> Confirme as edições vigentes das normas antes de citá-las (a NBR 16868-1 de 2020 unificou as antigas
> NBR 15961-1, de blocos de concreto, e NBR 15812-1, de blocos cerâmicos; blocos pela NBR 6136 e pela
> NBR 15270). Não cite item ou tabela de memória.

---

## 2. O que reaproveitar do projeto de base

A mecânica dos solos é a mesma de um muro de concreto; o que muda é o material da parede e o seu
dimensionamento. Copie e adapte, não reescreva.

| Do projeto de base | Uso no novo aplicativo |
|---|---|
| `core/empuxo.py` | Empuxo ativo/repouso (Rankine/Mazindrani, Coulomb), água, integração por fatias. Reaproveitar quase inteiro |
| `core/forcas.py`, `core/verificacoes.py` | Tabela de forças e verificações da NBR 11682 (Vesic, Meyerhof). Adaptar os pesos (alvenaria grauteada e não grauteada) |
| `core/boussinesq.py` | Cargas em faixa, linha e ponto no terrapleno |
| `core/solos.py`, `core/perfil.py`, `io_/sondagem.py`, `ui/estudo_solo.py` | Parâmetros por NSPT, α da adesão, leitura de boletim de sondagem em PDF, gráfico de esforço lateral |
| `core/concreto.py` e a parte de base de `core/dimensionamento.py` | Sapata de concreto armado (NBR 6118), combinações da base e equilíbrio do nó |
| `core/models.py`, `core/enums.py`, `tools/gerar_campos.py` | Padrão de entrada gerada da planilha (pydantic congelado, enums com o texto exato da planilha) |
| `core/planilha.py`, `tests/paridade.py`, `tools/gerar_cenarios.py` | Teste de paridade célula a célula com a planilha |
| `tools/revisar_planilha.py`, `tools/conferir_revisao.py` | Revisão da planilha por script e conferência no LibreOffice |
| `io_/projeto.py`, `io_/excel.py`, `io_/memorial.py` | Projeto em JSON, importação/exportação Excel, memorial em PDF |
| `ui/`, `paginas/`, `app.py` | Navegação, formulário gerado dos campos, painel, croqui em matplotlib |
| `desktop/`, `android/`, `.github/workflows/android.yml` | Versões desktop (pywebview + PyInstaller) e Android (Pyodide + Capacitor) |

O que é **novo**: geometria da parede de alvenaria (blocos, espessura, furos grauteados, eventuais
pilares/contrafortes de alvenaria), peso próprio por tipo de preenchimento e todo o dimensionamento da
NBR 16868-1 (`core/alvenaria.py`).

---

## 3. Decisões para confirmar com o projetista no início

Faça estas perguntas uma vez, com a recomendação em primeiro lugar. No projeto de base, todas foram
respondidas como indicado em "Recomendado".

| Decisão | Recomendado (como no projeto de base) |
|---|---|
| Fonte da verdade | A planilha; em conflito ou erro, prevalecem as normas. Desvios registrados e testados |
| Usuários | Um só; projeto salvo em arquivo JSON, sem banco nem login |
| Gráficos | matplotlib (croqui, diagramas, desenho das armaduras) |
| Opções de compatibilidade com programa comercial (ex.: GEO5) | Mantidas como "legado", sinalizadas quando ativas |
| Dimensionamento | Página própria, com desenho da seção (blocos, graute, barras, bitola e espaçamento) |
| Padrões de deslizamento | δb = 3/4·φ; adesão a = α·c com α por tipo de solo; solo da frente em repouso |
| Excentricidade | Limite B/6; entre B/6 e B/4 aceita só com a base verificada; acima de B/4 reprova |
| Combinações da base | Pior caso entre as combinações em equilíbrio (1,0 / γf por grupo) e a local do GEO5 |
| Versões | Web (Streamlit), desktop e Android, nessa ordem |

Perguntas específicas da alvenaria (não há resposta no projeto de base — pergunte):

1. Blocos de concreto, cerâmicos ou os dois? Quais famílias e espessuras?
2. Parede **armada** (furos grauteados com barras), **não armada** ou as duas opções?
3. A base é sapata de concreto armado? A parede é engastada nela por esperas no graute?
4. Há pilares/contrafortes de alvenaria ou de concreto ao longo do muro?
5. Há memoriais de um programa de referência (ex.: GEO5 "Muro de alvenaria") para validar?

---

## 4. Arquitetura e convenções (iguais ao projeto de base)

```
app.py            navegação (st.navigation)
paginas/          inicio · verificacao · dimensionamento · solos
core/             campos.py (GERADO) · enums · models · geometria · empuxo · forcas · verificacoes
                  avisos · alvenaria (NOVO) · concreto · fundacao · fases · solver · planilha
                  boussinesq · solos · perfil · premissas
ui/               estado · inputs · painel · graficos · armacao · estudo_solo · formato
io_/              projeto (JSON) · excel · memorial (PDF) · sondagem
tools/            gerar_campos · gerar_cenarios · revisar_planilha · conferir_revisao
tests/            paridade com a planilha + núcleo + interface + E/S; tests/data/cenarios.json
desktop/  android/
```

Regras que não se negociam:

- **`core/` não importa `streamlit`** (nem matplotlib ou pandas). É uma biblioteca testável sozinha e é
  o que roda no Android via Pyodide: use só Python puro, numpy e pydantic. Sem scipy.
- **Nomes de campos e resultados = nomes definidos da planilha.** Não renomeie: é o que permite rastrear
  cada número até a célula. Se a planilha não tiver nomes definidos, crie-os (com o projetista) antes de
  portar.
- `core/campos.py` é **gerado** por `tools/gerar_campos.py` a partir da aba de entrada. Não edite à mão.
  Campos que só existem no aplicativo ficam numa tabela `SO_APP` do gerador, com `celula == ""`.
- `Entrada` é pydantic v2 congelado; para variar um dado use `entrada.com(campo=valor)`.
- Enums `str` com **o texto exato da planilha**; `OPCOES_LEGADAS` marca as de compatibilidade.
- Sentinelas da planilha (999, 10 000) viram `math.inf` no núcleo; `core/planilha.py` reconverte.
- Desvios deliberados em relação à planilha vão para **três lugares**: `core/premissas.py`
  (`DIFERENCAS_DA_PLANILHA`), o README e uma exceção nomeada no teste de paridade.
- Comparações de limite com tolerância (1e-9): use funções tolerantes, como em `core/avisos.py`.
- Estado no Streamlit: `st.session_state["dados"]` é a fonte da verdade; widgets `w_<campo>`.

---

## 5. Etapas de desenvolvimento

Cada etapa termina com testes verdes, commit e atualização do `ROTEIRO_IA.md`.

### Etapa 1 — Inventário da planilha (sem código de produto)

- Leia a planilha com `openpyxl` em duas passadas (fórmulas e valores). Liste abas, nomes definidos,
  células de entrada (cor/preenchimento), validações de lista, formatações condicionais e gráficos.
- **Confira se o LibreOffice reproduz o Excel**: grave uma cópia com openpyxl, recalcule no LibreOffice e
  compare todas as células com os valores gravados pelo Excel. No projeto de base deu 11.171 de 11.171
  iguais. Se bater, o LibreOffice serve para gerar e conferir cenários sem Windows.
- Procure defeitos da planilha (no projeto de base: `CONCAT` inexistente no Excel 2016, `TEXT(x;"0.00")`
  errado em Excel pt-BR, listas de validação com vírgula dentro da opção). Liste-os para o projetista.
- Escreva `PLANEJAMENTO.md` do novo projeto: mapa aba → módulo do núcleo, fórmulas por grupo e dúvidas.

**Pronto quando:** inventário entregue, dúvidas da seção 3 respondidas e decisões registradas.

### Etapa 2 — Estrutura do projeto e entradas

- Crie o repositório com a árvore da seção 4, `requirements.txt` (streamlit, numpy, pandas, matplotlib,
  pydantic, openpyxl, reportlab, pymupdf, pytest, hypothesis) e `pyproject.toml`.
- Adapte `tools/gerar_campos.py` à aba de entrada da nova planilha e gere `core/campos.py`.
- `core/enums.py`, `core/models.py` (validação de limites e coerência).

**Pronto quando:** `Entrada()` reproduz os padrões da planilha e o teste de importação da planilha passa.

### Etapa 3 — Porte do núcleo de estabilidade

- Geometria da parede de alvenaria e da base (polígonos, áreas, centroides).
- Empuxo, forças, verificações e avisos: copie do projeto de base e adapte só o que a planilha fizer
  diferente. Peso da parede conforme o preenchimento (grauteada/vazada) que a planilha usar.
- Fases (sem/com travamento) se a planilha tiver.

**Pronto quando:** os valores de estabilidade do exemplo da planilha batem com tolerância 1e-8.

### Etapa 4 — Dimensionamento da alvenaria (NBR 16868-1) e da base

- `core/alvenaria.py`: resistências de cálculo a partir de fpk/fk e γm; flexão (armada: momento resistente,
  linha neutra, armaduras mínima e máxima, espaçamento das barras, graute; não armada: tração na flexão);
  cisalhamento; compressão/flexo-compressão; ligação parede–sapata (esperas, ancoragem e emenda no
  graute). Tudo exatamente como a planilha faz; onde a planilha não fizer, proponha ao projetista.
- Sapata de concreto armado: reaproveite a parte de base de `core/dimensionamento.py` (ponta, talão,
  combinações da base, equilíbrio do nó, faixa até B/4).
- Verificações em lista de `Check` (nome, solicitante, resistente, situação), como no projeto de base.

**Pronto quando:** o dimensionamento do exemplo da planilha bate com tolerância 1e-8.

### Etapa 5 — Paridade célula a célula

- `tests/cenarios.py`: 50 a 80 cenários que cubram **todos os ramos de `IF`** da planilha (cada opção de
  lista e os dois estados de cada Sim/Não), como no projeto de base.
- Gere `tests/data/cenarios.json` no Excel (COM, Windows do usuário) ou, se a etapa 1 confirmou a
  equivalência, no LibreOffice. Compare todos os nomes definidos e as verificações, tolerância 1e-8.
- **Nunca alargue a tolerância para passar um teste**: ou é erro de porte, ou é desvio deliberado que
  precisa de decisão do projetista e de exceção nomeada.

**Pronto quando:** todos os cenários passam, sem exceções que não estejam registradas.

### Etapa 6 — Interface Streamlit

- Páginas: Início (estudo de solo e sondagem), Verificação, Dimensionamento, Parâmetros do solo.
- Formulário gerado de `campos.py` (seções, ajuda, validação, opções legadas sinalizadas).
- Painel: vereditos, cartões de FS, croqui do muro (blocos e graute), tabelas de forças e empuxo,
  verificações, notas e premissas.
- Página de dimensionamento com **desenho da seção de alvenaria**: blocos, furos grauteados, barras
  verticais e horizontais com bitola e espaçamento, esperas na sapata e armaduras da base.
- Teste com `streamlit.testing.v1.AppTest` e confira as páginas de verdade no navegador.

**Pronto quando:** todas as páginas abrem sem erro e os testes de interface passam.

### Etapa 7 — Entrada e saída

- Projeto em JSON versionado; importação da planilha original; exportação dos resultados em `.xlsx`.
- Memorial de cálculo em PDF (reportlab): dados, croqui, forças, verificações, dimensionamento e premissas.
- Leitura de boletim de sondagem SPT em PDF (reaproveitar).

### Etapa 8 — Validação externa

- Se houver memoriais de programa comercial, transforme cada um em teste (como `tests/test_geo5.py`):
  dados de entrada completos + valores do memorial, com tolerância de arredondamento.
- Para cada diferença: explique a causa (critério × erro). Critério diferente vira opção ou desvio
  registrado; erro de modelo é corrigido. Diga sempre de que lado da segurança fica cada diferença.

### Etapa 9 — Melhorias propostas (só com aprovação)

O projeto de base acrescentou, a pedido do projetista, itens que provavelmente valem aqui também.
**Proponha; não implemente sem aprovação.**

- Combinações de ações da base pela NBR 8681 (cada grupo em 1,0 ou γf) e nota com os três conjuntos.
- Resistência do solo da frente como ação favorável (fator 1,0) no dimensionamento da parede.
- Ancoragem sob a ponta sem aliviar momento e cortante.
- Faixa de excentricidade B/6–B/4 com verificação da base com descolamento (NBR 6122, área comprimida ≥ 2/3).
- Cargas em faixa, linha e ponto (Boussinesq/Terzaghi), parede rígida ×2.
- Ferramentas: base mínima e sugestão de armaduras.

### Etapa 10 — Revisão da planilha

- `tools/revisar_planilha.py`: gera a revisão da planilha a partir da original com as alterações do
  aplicativo (a original fica intacta como referência da paridade).
- `tools/conferir_revisao.py`: recalcula a revisão no LibreOffice e compara com o núcleo em todos os
  cenários. Entregue a revisão com valores calculados e com a lista de alterações numa aba Notas.

### Etapa 11 — Desktop e Android

- Desktop: copie `desktop/` (lançador que sobe o Streamlit em 127.0.0.1 numa janela pywebview, receita
  do PyInstaller, `.bat` de dois cliques). O `.exe` só pode ser gerado no Windows.
- Android: copie `android/` (ponte JSON `ponte.py`, interface para celular, Pyodide num Web Worker,
  service worker para uso sem internet, Capacitor) e o workflow do GitHub Actions que gera o APK e o
  testa num emulador.

---

## 6. Armadilhas já encontradas no projeto de base

- **PowerShell 5.1** no Windows do usuário: não há `&&`; `python -c` com aspas quebra — escreva o script
  em arquivo. Ativar o venv pode exigir `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- Arquivos em **UTF-8 sem BOM**.
- `openpyxl`: `data_only=True` perde as fórmulas se salvar; fórmulas novas ficam sem valor até
  recalcular; regravar perde parte da formatação de gráficos (restaure o XML original do gráfico);
  inserir linhas não atualiza referências nem nomes (acrescente no fim da aba).
- Excel: use funções da era 2007 (`SUMPRODUCT`, `INDEX`, `IF`); `CONCATENATE` no lugar de `CONCAT`;
  `FIXED` no lugar de `TEXT(x;"0.00")`; listas de validação em intervalo de aba oculta.
- Ponto flutuante em limites (1,4 − 0,4 < 1,0): tolerância.
- Lambdas criadas em laço: fixe a variável com argumento padrão.
- matplotlib: `bold`, não `semibold`.
- AppTest: confira as chaves dos widgets; nos testes de cobertura, pule campos só do aplicativo.
- Android/Capacitor: a WebView não baixa arquivo gerado — use os plugins Filesystem e Share. O Pyodide
  deve rodar num Web Worker do tipo módulo.

---

## 7. Fluxo para cada pedido novo (copie para o `ROTEIRO_IA.md`)

1. Identifique se o pedido toca núcleo (`core/`), interface (`ui/`, `paginas/`) ou E/S (`io_/`).
2. Se envolver a planilha, releia as células com `openpyxl` antes de escrever código.
3. Rode `pytest` antes de começar.
4. Mude o núcleo primeiro, com teste; depois a interface.
5. Se o resultado passar a diferir da planilha: erro de porte (corrija) ou desvio deliberado (registre
   nos três lugares). Em conflito, prevalece a norma.
6. Abra o aplicativo e confira a página alterada.
7. Rode a suíte inteira e informe o resultado como ele é.
8. Atualize README e `ROTEIRO_IA.md`.
