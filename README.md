# Muro de arrimo — verificação (NBR 11682) e dimensionamento (NBR 6118)

Aplicativo Streamlit equivalente à planilha `Verificacao_Muro_Arrimo_NBR11682.xlsx`, com backend em
Python puro. Análise por metro linear de muro de flexão em concreto armado.

## Como rodar

```bash
.venv\Scripts\python -m streamlit run app.py
```

Abre em `http://localhost:8501`. Para montar o ambiente do zero:

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

## Páginas

| Página | O que faz |
|---|---|
| **Verificação NBR 11682** | As 14 seções da aba `Entrada`; tombamento, deslizamento, excentricidade, tensões e capacidade de carga em duas fases; dimensionamento da cortina, base e contrafortes; croqui; memorial PDF; exportação `.xlsx`; projeto `.json`; importação da planilha original |
| **Dimensionamento NBR 6118** | Materiais, cobrimentos e armaduras (seções 10 e 10b); verificações da cortina, base e contrafortes; desenho da seção com cada posição de armadura indicada (bitola e espaçamento) e quadro de ferros |
| **Parâmetros do solo** | Faixas de γ, φ, c e δ por tipo de solo e NSPT (de `Parametros_do_solo_Recomendado.xlsx`), com aplicação direta ao aterro ou à fundação |

### Estudo de solo (página inicial)

Anexe o relatório de sondagem SPT em PDF. O aplicativo lê os boletins (furos, camadas, NSPT por
metro, nível d'água), você informa **em que profundidade o muro começa e termina**, e ele:

- estima γ, φ e c de cada camada pelas tabelas de solo (tipo de solo + NSPT);
- desenha o **esforço lateral** no trecho do muro: ativo de Rankine e repouso por camadas, água,
  e a comparação com o solo homogêneo que a verificação vai usar;
- preenche a verificação (altura, solo arrimado, solo de fundação, água e sobrecarga).

O leitor (`io_/sondagem.py`) foi conferido com os boletins da CLS Sondagens e da JS Sondagens. Ele
depende de o PDF ter texto (PDF escaneado não é lido) e de o boletim seguir o arranjo usual; por
isso as camadas lidas ficam numa tabela editável, e há a opção de montar o perfil à mão. O núcleo
do muro continua com uma única camada de solo arrimado: o perfil por camadas é homogeneizado
(média ponderada ou camada mais desfavorável) e o gráfico mostra a diferença.

Na verificação, a seção **Ferramentas** traz o que a planilha não tem: menor base que atende a
estabilidade, força mínima de travamento exata, estudo paramétrico; e, em **Dimensionamento**,
sugestão de armaduras.

## Estrutura

```
app.py                  navegação
paginas/                inicio.py · verificacao.py · dimensionamento.py · solos.py
core/                   BACKEND — não importa streamlit
  campos.py             tabela das 108 entradas (gerada da planilha: rótulo, unidade, padrão, limites, ajuda)
  enums.py              listas de opção (textos exatos da planilha) + quais são legado GEO5
  models.py             Entrada (pydantic), construída a partir de campos.py
  geometria.py          aba Geometria      empuxo.py        abas Empuxo / Empuxo F2
  forcas.py             abas Forças        verificacoes.py  abas Resumo (FS, tensões, Vesic)
  avisos.py             Resumo!C35         dimensionamento.py + concreto.py   aba Dimensionamento
  fases.py              calcular(entrada) → Resultado; travamento mínimo exato
  solver.py             base mínima, paramétrico, sugestão de armaduras
  planilha.py           resultado → nomes definidos da planilha (usado nos testes)
  solos.py · premissas.py
  perfil.py             sondagem → parâmetros por camada, solo equivalente, esforço lateral
  placa.py              laje com borda livre (elementos finitos) para o muro com contrafortes
ui/                     inputs · painel · graficos · armacao (desenho das armaduras) · estudo_solo · estado
io_/                    projeto (JSON) · excel (importar/exportar) · memorial (PDF) · sondagem (ler PDF)
tools/                  gerar_campos.py · gerar_cenarios.py
tests/                  174 testes
ROTEIRO_IA.md           contexto, decisões e pendências para quem (ou qual IA) for continuar o projeto
```

Os nomes de campos e de resultados são os **nomes definidos da planilha** (`H_muro`, `p_Pah`,
`R_FSd`, `dm_Asnp` …), para rastrear qualquer número até a célula de origem.

## Uso do núcleo sem interface

```python
from core.models import Entrada
from core.fases import calcular

r = calcular(Entrada(H_muro=5.0, b_talao=2.4, phi_at=32))
print(r.fase1.verif.R_FSt, r.fase1.verif.R_FSd, r.atende_estabilidade, r.dim.atende)
```

## Testes

```bash
.venv\Scripts\python -m pytest
```

- `test_paridade_planilha.py` — 75 cenários comparados com a planilha **recalculada no Excel**:
  todos os nomes definidos, as 17 forças das duas fases, as 26 verificações do dimensionamento,
  avisos e vereditos (600 valores por cenário, tolerância 1e-8).
- `test_nucleo.py` — soluções analíticas, invariantes físicos (hypothesis), NBR 6118.
- `test_io.py` — JSON, Excel, PDF, gráficos, ferramentas.
- `test_app.py` — páginas Streamlit (AppTest).

### Quando a planilha mudar

1. `.venv\Scripts\python tools\gerar_campos.py` — atualiza `core/campos.py` se houver entradas novas.
2. Porte as fórmulas novas para o módulo correspondente em `core/`.
3. `.venv\Scripts\python tools\gerar_cenarios.py` — recalcula os cenários no Excel (abre a planilha
   somente leitura e não salva nada; precisa de Excel e `pywin32`).
4. `pytest` — o teste de paridade aponta qualquer nome da planilha sem equivalente no núcleo.

## Onde o aplicativo difere da planilha (deliberado)

- Opções de compatibilidade GEO5 marcadas como **legado** e sinalizadas quando ativas.
- FS infinito e tensão infinita no lugar das sentinelas 999 / 10 000 kPa.
- **Resultante fora da base**: a planilha dimensiona ponta e talão com tensão de solo negativa e
  pode dar "ATENDE"; o aplicativo reprova a base.
- **fck > 40 MPa**: aplica ηc (NBR 6118:2023) e, acima de 50 MPa, os parâmetros do grupo II.
- **Verificações extras**: cortante no talão e espaçamento máximo das barras principais.
- **Resistência frontal na cortina em balanço**: ação favorável, entra com fator 1,0 nos esforços
  de cálculo (a planilha a multiplica por γf).
- **Muro com contrafortes**: cortina e base entre contrafortes como laje com três bordas engastadas
  e uma livre (`core/placa.py`, elementos finitos de placa, conferido contra as soluções clássicas),
  com armadura nas duas direções. Os coeficientes do GEO5 da planilha ficam como opção legada.
- **Blocos de coroamento**: face do bloco alinhada ao tardoz por padrão (a planilha centra o bloco
  nas estacas); o projetista pode escolher "centrado nas estacas" ou informar a posição.
- Três campos existem só no aplicativo (`bl_pos`, `bl_x`, `laje_cf`). Para reproduzir a planilha,
  use `core.planilha.MODO_PLANILHA` — é o que os testes de paridade fazem.
- Comparações de limite com tolerância 1e-9.

## Defeitos encontrados na planilha

- `Resumo!C35` usa `CONCAT`, que não existe no Excel instalado nesta máquina: `C33`, `C35` e `I37`
  (avisos e resultado geral) aparecem como `#NOME?`. Trocar por `CONCATENATE` resolve.
- `TEXT(B_base,"0.00")` no cabeçalho do Resumo mostra "B = 003 m" em Excel pt-BR.
- Listas de validação com vírgula dentro da opção (`0,6·fctd·b·d (GEO5)`, `0,45 (NBR 6118)`,
  `0,259 (GEO5)`) ficam quebradas no menu suspenso.

## Limitações

Uma camada de solo no aterro; sapata de espessura constante; sem dente, sismo ou cargas
concentradas. **Estabilidade global não é verificada.** Não há verificação de fissuração,
ancoragem/emendas de barras nem estribos do contraforte. Os 11 casos GEO5 citados na aba `Notas`
não viraram testes porque a aba traz só os resultados, sem os dados de entrada. Ferramenta de
apoio: a conferência e a responsabilidade técnica são do engenheiro.
