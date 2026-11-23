"""Fase 4: resultados territoriais preliminares.

Entradas:
- data/processed/enem_2023_2025_preliminar.parquet

Saidas:
- data/processed/fase4_gap_capital_vs_interior.csv
- data/processed/fase4_participacao_uf_acessivel.csv
- data/processed/fase4_ranking_uf_acessivel_top_bottom.csv

Uso:
  python src/05_fase4_territorial.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE_PATH = Path("data/processed/enem_2023_2025_preliminar.parquet")
OUT_DIR = Path("data/processed")
NOTAS = ["NU_NOTA_CN", "NU_NOTA_CH", "NU_NOTA_LC", "NU_NOTA_MT", "NU_NOTA_REDACAO"]


def tabela_capital_interior(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["GRUPO_RECORTE"].isin(["acessivel", "regular"])].copy()
    sub = sub[sub["CAPITAL_PROVA"].notna()].copy()

    long = sub.melt(
        id_vars=["ANO", "CAPITAL_PROVA", "GRUPO_RECORTE"],
        value_vars=NOTAS,
        var_name="AREA",
        value_name="NOTA",
    ).dropna(subset=["NOTA"])

    agg = (
        long.groupby(["ANO", "AREA", "CAPITAL_PROVA", "GRUPO_RECORTE"], dropna=False)["NOTA"]
        .agg(N="count", MEDIA="mean")
        .reset_index()
    )

    # Pivot para ter media por grupo e poder calcular gaps.
    piv = (
        agg.pivot_table(
            index=["ANO", "AREA", "CAPITAL_PROVA"],
            columns="GRUPO_RECORTE",
            values="MEDIA",
            aggfunc="first",
        )
        .reset_index()
        .rename(columns={"acessivel": "MEDIA_ACESSIVEL", "regular": "MEDIA_REGULAR"})
    )

    piv_n = (
        agg.pivot_table(
            index=["ANO", "AREA", "CAPITAL_PROVA"],
            columns="GRUPO_RECORTE",
            values="N",
            aggfunc="first",
        )
        .reset_index()
        .rename(columns={"acessivel": "N_ACESSIVEL", "regular": "N_REGULAR"})
    )

    out = piv.merge(piv_n, on=["ANO", "AREA", "CAPITAL_PROVA"], how="left")
    out["GAP_ACESSIVEL_MENOS_REGULAR"] = out["MEDIA_ACESSIVEL"] - out["MEDIA_REGULAR"]

    out["LOCAL"] = out["CAPITAL_PROVA"].map({True: "capital", False: "interior"})
    out = out.drop(columns=["CAPITAL_PROVA"])

    for c in ["MEDIA_ACESSIVEL", "MEDIA_REGULAR", "GAP_ACESSIVEL_MENOS_REGULAR"]:
        out[c] = out[c].round(3)

    out = out.sort_values(["ANO", "AREA", "LOCAL"]).reset_index(drop=True)
    return out


def tabela_participacao_uf(df: pd.DataFrame) -> pd.DataFrame:
    # Taxa de acessivel no recorte principal: acessivel / (acessivel + regular).
    sub = df[df["GRUPO_RECORTE"].isin(["acessivel", "regular"])].copy()

    tab = (
        sub.groupby(["ANO", "UF_PROVA", "GRUPO_RECORTE"], dropna=False)
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
    tab["TAXA_ACESSIVEL_PCT"] = np.where(
        tab["N_TOTAL_RECORTE"] > 0,
        100 * tab["N_ACESSIVEL"] / tab["N_TOTAL_RECORTE"],
        np.nan,
    )
    tab["TAXA_ACESSIVEL_PCT"] = tab["TAXA_ACESSIVEL_PCT"].round(4)

    tab = tab.sort_values(["ANO", "TAXA_ACESSIVEL_PCT"], ascending=[True, False]).reset_index(drop=True)
    return tab


def ranking_top_bottom_uf(tab_uf: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    frames = []
    for ano in sorted(tab_uf["ANO"].dropna().unique()):
        sub = tab_uf[tab_uf["ANO"] == ano].copy()
        top = sub.nlargest(top_n, "TAXA_ACESSIVEL_PCT").copy()
        top["POSICAO"] = "top"
        bot = sub.nsmallest(top_n, "TAXA_ACESSIVEL_PCT").copy()
        bot["POSICAO"] = "bottom"
        frames.append(pd.concat([top, bot], ignore_index=True))

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["ANO", "POSICAO", "TAXA_ACESSIVEL_PCT"], ascending=[True, True, False])
    return out[[
        "ANO",
        "POSICAO",
        "UF_PROVA",
        "N_ACESSIVEL",
        "N_REGULAR",
        "N_TOTAL_RECORTE",
        "TAXA_ACESSIVEL_PCT",
    ]]


def main() -> None:
    if not BASE_PATH.exists():
        raise FileNotFoundError(
            f"Base preliminar nao encontrada em {BASE_PATH}. Rode antes: src/02_build_base_preliminar.py"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(BASE_PATH)

    t_cap = tabela_capital_interior(df)
    t_uf = tabela_participacao_uf(df)
    t_rank = ranking_top_bottom_uf(t_uf, top_n=5)

    p1 = OUT_DIR / "fase4_gap_capital_vs_interior.csv"
    p2 = OUT_DIR / "fase4_participacao_uf_acessivel.csv"
    p3 = OUT_DIR / "fase4_ranking_uf_acessivel_top_bottom.csv"

    t_cap.to_csv(p1, index=False, encoding="utf-8-sig")
    t_uf.to_csv(p2, index=False, encoding="utf-8-sig")
    t_rank.to_csv(p3, index=False, encoding="utf-8-sig")

    print("Arquivos gerados:")
    print(f"- {p1}")
    print(f"- {p2}")
    print(f"- {p3}")

    print("\nResumo: gap acessivel - regular por local (media entre areas por ano)")
    resumo_local = (
        t_cap.groupby(["ANO", "LOCAL"], dropna=False)["GAP_ACESSIVEL_MENOS_REGULAR"]
        .mean()
        .reset_index()
        .rename(columns={"GAP_ACESSIVEL_MENOS_REGULAR": "GAP_MEDIO"})
    )
    resumo_local["GAP_MEDIO"] = resumo_local["GAP_MEDIO"].round(3)
    print(resumo_local.to_string(index=False))

    print("\nTop 3 UFs por taxa de acessivel em cada ano")
    top3 = (
        t_uf.sort_values(["ANO", "TAXA_ACESSIVEL_PCT"], ascending=[True, False])
        .groupby("ANO", as_index=False)
        .head(3)
    )
    print(top3[["ANO", "UF_PROVA", "TAXA_ACESSIVEL_PCT", "N_ACESSIVEL", "N_TOTAL_RECORTE"]].to_string(index=False))


if __name__ == "__main__":
    main()
