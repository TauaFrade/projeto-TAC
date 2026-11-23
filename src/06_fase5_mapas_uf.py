"""Fase 5: tabelas por UF (com sigla) e mapas em PNG para slides.

Este script gera:
1) Tabelas
- data/processed/fase5_participacao_uf_sigla.csv
- data/processed/fase5_gap_uf_5areas_sigla.csv
- data/processed/fase5_gap_uf_5areas_sigla_pooled.csv

2) Mapas (cartograma por UF, offline)
- reports/figures/fase5_participacao_uf_2023.png
- reports/figures/fase5_participacao_uf_2024.png
- reports/figures/fase5_participacao_uf_2025.png
- reports/figures/fase5_gap_uf_pooled_NU_NOTA_CN.png
- reports/figures/fase5_gap_uf_pooled_NU_NOTA_CH.png
- reports/figures/fase5_gap_uf_pooled_NU_NOTA_LC.png
- reports/figures/fase5_gap_uf_pooled_NU_NOTA_MT.png
- reports/figures/fase5_gap_uf_pooled_NU_NOTA_REDACAO.png

Uso:
  python src/06_fase5_mapas_uf.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import pandas as pd

BASE_PATH = Path("data/processed/enem_2023_2025_preliminar.parquet")
OUT_DATA = Path("data/processed")
OUT_FIG = Path("reports/figures")

NOTAS = ["NU_NOTA_CN", "NU_NOTA_CH", "NU_NOTA_LC", "NU_NOTA_MT", "NU_NOTA_REDACAO"]

UF_NUM_TO_SIGLA = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL", 28: "SE", 29: "BA",
    31: "MG", 32: "ES", 33: "RJ", 35: "SP",
    41: "PR", 42: "SC", 43: "RS",
    50: "MS", 51: "MT", 52: "GO", 53: "DF",
}

# Coordenadas simples de cartograma por UF (aproximacao visual para slides, offline).
UF_TILE = {
    "RR": (4, 0), "AP": (7, 1), "AM": (4, 1), "PA": (6, 2),
    "AC": (1, 3), "RO": (2, 3), "TO": (6, 4),
    "MA": (7, 3), "PI": (8, 3), "CE": (9, 3), "RN": (11, 2),
    "PB": (11, 3), "PE": (10, 4), "AL": (10, 5), "SE": (10, 6), "BA": (9, 6),
    "MT": (4, 5), "MS": (4, 8), "GO": (6, 6), "DF": (6, 7),
    "MG": (8, 8), "ES": (9, 8), "RJ": (9, 9), "SP": (7, 9),
    "PR": (6, 10), "SC": (6, 11), "RS": (5, 12),
}


def preparar_base() -> pd.DataFrame:
    if not BASE_PATH.exists():
        raise FileNotFoundError(
            f"Base preliminar nao encontrada em {BASE_PATH}. Rode antes: src/02_build_base_preliminar.py"
        )

    df = pd.read_parquet(BASE_PATH)
    df = df[df["GRUPO_RECORTE"].isin(["acessivel", "regular"])].copy()

    df["UF_SIGLA"] = df["UF_PROVA"].map(UF_NUM_TO_SIGLA)
    df = df[df["UF_SIGLA"].notna()].copy()
    return df


def tabela_participacao(df: pd.DataFrame) -> pd.DataFrame:
    tab = (
        df.groupby(["ANO", "UF_PROVA", "UF_SIGLA", "GRUPO_RECORTE"], dropna=False)
        .size()
        .unstack("GRUPO_RECORTE", fill_value=0)
        .reset_index()
    )

    if "acessivel" not in tab.columns:
        tab["acessivel"] = 0
    if "regular" not in tab.columns:
        tab["regular"] = 0

    tab = tab.rename(columns={"acessivel": "N_ACESSIVEL", "regular": "N_REGULAR"})
    tab["N_TOTAL_RECORTE"] = tab["N_ACESSIVEL"] + tab["N_REGULAR"]
    tab["TAXA_ACESSIVEL_PCT"] = (100 * tab["N_ACESSIVEL"] / tab["N_TOTAL_RECORTE"]).round(4)

    return tab.sort_values(["ANO", "TAXA_ACESSIVEL_PCT"], ascending=[True, False]).reset_index(drop=True)


def tabela_gap_por_uf(df: pd.DataFrame) -> pd.DataFrame:
    long = df.melt(
        id_vars=["ANO", "UF_PROVA", "UF_SIGLA", "GRUPO_RECORTE"],
        value_vars=NOTAS,
        var_name="AREA",
        value_name="NOTA",
    ).dropna(subset=["NOTA"])

    medias = (
        long.groupby(["ANO", "UF_PROVA", "UF_SIGLA", "AREA", "GRUPO_RECORTE"], dropna=False)["NOTA"]
        .mean()
        .unstack("GRUPO_RECORTE")
        .reset_index()
        .rename(columns={"acessivel": "MEDIA_ACESSIVEL", "regular": "MEDIA_REGULAR"})
    )

    cont = (
        long.groupby(["ANO", "UF_PROVA", "UF_SIGLA", "AREA", "GRUPO_RECORTE"], dropna=False)
        .size()
        .unstack("GRUPO_RECORTE")
        .reset_index()
        .rename(columns={"acessivel": "N_ACESSIVEL", "regular": "N_REGULAR"})
    )

    out = medias.merge(cont, on=["ANO", "UF_PROVA", "UF_SIGLA", "AREA"], how="left")
    out["GAP_ACESSIVEL_MENOS_REGULAR"] = out["MEDIA_ACESSIVEL"] - out["MEDIA_REGULAR"]

    for c in ["MEDIA_ACESSIVEL", "MEDIA_REGULAR", "GAP_ACESSIVEL_MENOS_REGULAR"]:
        out[c] = out[c].round(3)

    return out.sort_values(["ANO", "AREA", "UF_SIGLA"]).reset_index(drop=True)


def tabela_gap_pooled(gap_por_ano: pd.DataFrame) -> pd.DataFrame:
    # Pool 2023-2025 por UF e area usando media ponderada pelo N valido de cada grupo.
    g = gap_por_ano.copy()

    g["SUM_ACC"] = g["MEDIA_ACESSIVEL"] * g["N_ACESSIVEL"]
    g["SUM_REG"] = g["MEDIA_REGULAR"] * g["N_REGULAR"]

    pooled = (
        g.groupby(["UF_PROVA", "UF_SIGLA", "AREA"], dropna=False)
        .agg(
            N_ACESSIVEL=("N_ACESSIVEL", "sum"),
            N_REGULAR=("N_REGULAR", "sum"),
            SUM_ACC=("SUM_ACC", "sum"),
            SUM_REG=("SUM_REG", "sum"),
        )
        .reset_index()
    )

    pooled["MEDIA_ACESSIVEL"] = pooled["SUM_ACC"] / pooled["N_ACESSIVEL"]
    pooled["MEDIA_REGULAR"] = pooled["SUM_REG"] / pooled["N_REGULAR"]
    pooled["GAP_ACESSIVEL_MENOS_REGULAR"] = pooled["MEDIA_ACESSIVEL"] - pooled["MEDIA_REGULAR"]

    for c in ["MEDIA_ACESSIVEL", "MEDIA_REGULAR", "GAP_ACESSIVEL_MENOS_REGULAR"]:
        pooled[c] = pooled[c].round(3)

    return pooled[[
        "UF_PROVA", "UF_SIGLA", "AREA", "N_ACESSIVEL", "N_REGULAR",
        "MEDIA_ACESSIVEL", "MEDIA_REGULAR", "GAP_ACESSIVEL_MENOS_REGULAR",
    ]].sort_values(["AREA", "UF_SIGLA"]).reset_index(drop=True)


def draw_tile_map(
    df: pd.DataFrame,
    value_col: str,
    title: str,
    output_path: Path,
    cmap: str = "YlGnBu",
    vmin: float | None = None,
    vmax: float | None = None,
    value_fmt: str = "{:.3f}",
) -> None:
    d = {row.UF_SIGLA: getattr(row, value_col) for row in df.itertuples(index=False)}
    vals = [v for v in d.values() if pd.notna(v)]

    if not vals:
        return

    lo = min(vals) if vmin is None else vmin
    hi = max(vals) if vmax is None else vmax
    if lo == hi:
        hi = lo + 1e-9

    norm = Normalize(vmin=lo, vmax=hi)
    cmap_obj = plt.get_cmap(cmap)

    fig, ax = plt.subplots(figsize=(11, 8))
    ax.set_title(title, fontsize=14, weight="bold", pad=12)

    # desenha tiles
    for uf, (x, y) in UF_TILE.items():
        val = d.get(uf)
        if pd.isna(val) if uf in d else True:
            color = "#f2f2f2"
            txt = "NA"
        else:
            color = cmap_obj(norm(val))
            txt = value_fmt.format(val)

        rect = plt.Rectangle((x, -y), 1, 1, facecolor=color, edgecolor="white", linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x + 0.5, -y + 0.62, uf, ha="center", va="center", fontsize=9, weight="bold")
        ax.text(x + 0.5, -y + 0.30, txt, ha="center", va="center", fontsize=7)

    ax.set_xlim(0.5, 12.8)
    ax.set_ylim(-13.2, 0.8)
    ax.set_aspect("equal")
    ax.axis("off")

    sm = ScalarMappable(norm=norm, cmap=cmap_obj)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.028, pad=0.02)
    cbar.ax.tick_params(labelsize=8)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def gerar_mapas_participacao(tab_part: pd.DataFrame) -> None:
    for ano in sorted(tab_part["ANO"].unique()):
        sub = tab_part[tab_part["ANO"] == ano][["UF_SIGLA", "TAXA_ACESSIVEL_PCT"]].copy()
        draw_tile_map(
            sub,
            value_col="TAXA_ACESSIVEL_PCT",
            title=f"Taxa de participacao em provas acessiveis por UF ({ano})",
            output_path=OUT_FIG / f"fase5_participacao_uf_{ano}.png",
            cmap="YlGnBu",
            value_fmt="{:.3f}%",
        )


def gerar_mapas_gap_pooled(tab_gap_pool: pd.DataFrame) -> None:
    for area in NOTAS:
        sub = tab_gap_pool[tab_gap_pool["AREA"] == area][["UF_SIGLA", "GAP_ACESSIVEL_MENOS_REGULAR"]].copy()
        draw_tile_map(
            sub,
            value_col="GAP_ACESSIVEL_MENOS_REGULAR",
            title=f"Gap acessivel - regular por UF (pooled 2023-2025) | {area}",
            output_path=OUT_FIG / f"fase5_gap_uf_pooled_{area}.png",
            cmap="RdYlBu",
            value_fmt="{:.1f}",
        )


def main() -> None:
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    OUT_FIG.mkdir(parents=True, exist_ok=True)

    df = preparar_base()
    tab_part = tabela_participacao(df)
    tab_gap = tabela_gap_por_uf(df)
    tab_gap_pool = tabela_gap_pooled(tab_gap)

    p1 = OUT_DATA / "fase5_participacao_uf_sigla.csv"
    p2 = OUT_DATA / "fase5_gap_uf_5areas_sigla.csv"
    p3 = OUT_DATA / "fase5_gap_uf_5areas_sigla_pooled.csv"

    tab_part.to_csv(p1, index=False, encoding="utf-8-sig")
    tab_gap.to_csv(p2, index=False, encoding="utf-8-sig")
    tab_gap_pool.to_csv(p3, index=False, encoding="utf-8-sig")

    gerar_mapas_participacao(tab_part)
    gerar_mapas_gap_pooled(tab_gap_pool)

    print("Tabelas geradas:")
    print(f"- {p1}")
    print(f"- {p2}")
    print(f"- {p3}")
    print("\nMapas gerados em reports/figures:")
    for ano in sorted(tab_part["ANO"].unique()):
        print(f"- {OUT_FIG / f'fase5_participacao_uf_{ano}.png'}")
    for area in NOTAS:
        print(f"- {OUT_FIG / f'fase5_gap_uf_pooled_{area}.png'}")


if __name__ == "__main__":
    main()
