"""Roda os modelos do GEO5 na planilha revisada (Rev. 01) e compara com os memoriais do GEO5.

    .venv/bin/python tools/geo5_na_planilha.py

Para cada memorial (dados em tests/test_geo5.py): preenche a Entrada da revisão, recalcula no
LibreOffice, grava a planilha preenchida em ``exemplos/`` (para abrir no Excel) e imprime a
comparação com os valores do GEO5.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import openpyxl

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from core.campos import CAMPOS  # noqa: E402
from core.models import Entrada  # noqa: E402
from tests import test_geo5 as g  # noqa: E402

REVISAO = RAIZ / "Verificacao_Muro_Arrimo_NBR11682_Rev01.xlsx"
EXEMPLOS = RAIZ / "exemplos"
RECALC = next(Path("/root/.claude/skills").rglob("xlsx/scripts/recalc.py"), None) if Path("/root/.claude/skills").exists() else None

# (rótulo, nome na planilha, fator para a unidade do GEO5, valor do GEO5)
ESTAB = [
    ("Empuxo ativo horizontal (kN/m)", "p_Pah_s", 1), ("Sobrecarga horizontal (kN/m)", "p_Pah_q", 1),
    ("Componentes verticais do empuxo (kN/m)", "p_Pav", 1), ("N (kN/m)", "F_N", 1),
    ("Mres (kN·m/m)", "F_Mres", 1), ("Movr (kN·m/m)", "F_Movr", 1), ("FS tombamento", "R_FSt", 1),
    ("Hres (kN/m)", "R_Hres", 1), ("Hact (kN/m)", "R_Hact", 1), ("FS deslizamento", "R_FSd", 1),
    ("e/B", "R_eB", 1), ("Tensão na base (kPa)", "R_sef", 1), ("FS capacidade de carga", "R_FScc", 1),
]
HASTE = [("Haste: MSd (kN·m/m)", "dm_MSdp", 1), ("Haste: VEd (kN/m)", "dm_VSd", 1),
         ("Haste: As necessária (mm²/m)", "dm_Asnp", 100), ("Haste: As adotada (mm²/m)", "dm_Ast", 100),
         ("Haste: VRd (kN/m)", "dm_VRd", 1), ("Haste: MRd (kN·m/m)", "dm_MRdp", 1)]
PONTA = [("Avanço: MSd (kN·m/m)", "dm_MSd_pt", 1), ("Avanço: VEd (kN/m)", "dm_VSd_pt", 1),
         ("Avanço: As necessária (mm²/m)", "dm_As_pt", 100), ("Avanço: MRd (kN·m/m)", "dm_MRd_pt", 1),
         ("Avanço: VRd (kN/m)", "dm_VRd_pt", 1)]

MODELOS = {
    "sem_talao": dict(
        titulo="Muro sem talão (memorial de 13/11/2026)",
        dados={**g.MURO, **g.CRITERIOS_GEO5},
        geo5=[17.43, 8.04, 4.81, 40.95, 49.08, 24.22, 2.03, 29.71, 23.67, 1.26, 0.143, 33.72, 2.97,
              94.33, 83.33, 1552.2, 1674.8, 124.42, 101.75, 94.33, 23.00, 1106.0, 112.41, 162.82],
        itens=ESTAB + HASTE + PONTA),
    "ancoragem": dict(
        titulo="Muro com ancoragem na base (memorial de 16/11/2026)",
        dados={**g.MURO_ANC, **g.CRITERIOS_ANC},
        geo5=[10.35, 6.37, 3.27, 52.51, 25.57, 12.71, 2.01, 32.77, 14.92, 2.20, 0.194, 107.14, 0.93,
              58.15, 60.40, 906.7, 1022.2, 108.57, 64.36, 58.15, 46.01, 906.7, 58.93, 108.57],
        itens=ESTAB + HASTE + PONTA),
    "contrafortes": dict(
        titulo="Muro com contrafortes na frente (memorial de 16/11/2026)",
        dados={**g.MURO_CF, **g.CRITERIOS_CF},
        geo5=[16.71, 7.88, 4.66, 75.75, 45.56, 22.97, 1.98, 46.72, 22.80, 2.05, 0.202, 127.03, 1.18,
              49.80, 10.07, 2.52, 34.68, 20.81, 30.83, 178.40, 156.78, 607.62, 254.59,
              269.24, 90.87, 54.52, 242.31, 869.0],
        itens=ESTAB + [
            ("Cortina: σH de cálculo na base (kPa)", "cs_sH", 1), ("Cortina: M vertical tardoz (kN·m/m)", "cs_Mvt", 1),
            ("Cortina: M vertical frente (kN·m/m)", "cs_Mvf", 1), ("Cortina: M horizontal apoios (kN·m em 3,00 m)", "cs_Mht", 3),
            ("Cortina: M horizontal vão (kN·m em 3,00 m)", "cs_Mhf", 3), ("Cortina: cortante (kN/m)", "cs_V", 1),
            ("Contraforte: MSd (kN·m)", "cf_MSd", 1), ("Contraforte: VSd (kN)", "cf_VSd", 1),
            ("Contraforte: MRd (kN·m)", "cf_MRd", 1), ("Contraforte: VRd (kN)", "cf_VRd", 1),
            ("Base: tensão de cálculo (kPa)", "bd_s", 1), ("Base: M inferior (kN·m em 0,80 m)", "bd_M12", 0.8),
            ("Base: M superior (kN·m em 0,80 m)", "bd_M20", 0.8), ("Base: cortante (kN em 0,80 m)", "bd_V", 0.8),
            ("Base: As superior necessária (mm² em 0,80 m)", "bd_Ass", 80)]),
    "talao_C25": dict(
        titulo="Muro com talão e cunha inclinada, C25 (memorial de 16/11/2026)",
        dados={**g.MURO_TALAO, "fck_c": 25, "ar_bs_phi": 10, **g.CRITERIOS_TALAO, "ponta_mod": "Máximo"},
        geo5=[24.25, 8.60, 32.76 + 9.03, 139.11, 158.48, 31.83, 4.98, 89.42, 31.05, 2.88, 0.021, 76.40, 1.96,
              94.35, 83.49, 869.6, 1341.1, 201.22, 141.28, 67.68, 59.05, 614.8, 141.57, 201.22,
              26.68, 21.26, 58.65],
        itens=ESTAB + HASTE + PONTA + [("Dente (talão): MSd (kN·m/m)", "dm_MSd_tl", 1),
                                       ("Dente (talão): VEd (kN/m)", "dm_VSd_tl", 1),
                                       ("Dente (talão): MRd (kN·m/m)", "dm_MRd_tl", 1)]),
}
RESULTADOS = [("Estabilidade (Resumo)", "Resumo", "I37"), ("Dimensionamento (linha 47)", "Dimensionamento", "O47")]


def rodar(nome: str, destino: Path | None = None) -> dict:
    """Preenche, recalcula e devolve {nome definido: valor} da planilha revisada."""
    if RECALC is None:
        raise RuntimeError("LibreOffice/recalc.py não encontrado")
    m = MODELOS[nome]
    wb = openpyxl.load_workbook(REVISAO)
    refs = {n: dn.attr_text for n, dn in wb.defined_names.items()}
    for campo, val in Entrada(**m["dados"]).para_planilha(so_app=True).items():
        if campo in refs and campo in {c.nome for c in CAMPOS}:
            aba, cel = refs[campo].split("!")
            wb[aba.strip("'")][cel.replace("$", "")] = val
    destino = destino or EXEMPLOS / f"Rev01_GEO5_{nome}.xlsx"
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)
    info = json.loads(subprocess.run([sys.executable, str(RECALC), str(destino), "180"],
                                     capture_output=True, text=True).stdout)
    if info.get("total_errors"):
        raise RuntimeError(f"{nome}: {info['total_errors']} erros de fórmula")
    v = openpyxl.load_workbook(destino, data_only=True)
    out = {}
    for n, ref in refs.items():
        if "!" in ref and ":" not in ref:
            aba, cel = ref.split("!")
            out[n] = v[aba.strip("'")][cel.replace("$", "")].value
    for rot, aba, cel in RESULTADOS:
        out[rot] = v[aba][cel].value
    return out


def main() -> None:
    for nome, m in MODELOS.items():
        r = rodar(nome)
        print(f"\n=== {m['titulo']}  →  exemplos/Rev01_GEO5_{nome}.xlsx")
        print(f"{'Grandeza':52s} {'GEO5':>10s} {'Planilha':>10s} {'Dif.':>8s}")
        for (rot, n, k), geo in zip(m["itens"], m["geo5"]):
            val = r[n] * k
            dif = (val - geo) / geo * 100 if geo else 0.0
            print(f"{rot:52s} {geo:10.2f} {val:10.2f} {dif:+7.1f}%")
        for rot, *_ in RESULTADOS:
            print(f"{rot:52s} {r[rot]}")


if __name__ == "__main__":
    main()
