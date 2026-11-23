"""Fase 3: comparacao acessivel vs regular com Welch e tamanho de efeito.

Entradas:
- data/processed/enem_2023_2025_preliminar.parquet

Saidas:
- data/processed/fase3_welch_efeito_por_ano_area.csv
- data/processed/fase3_resumo_significancia.csv

Uso:
  python src/04_fase3_welch_efeito.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

BASE_PATH = Path("data/processed/enem_2023_2025_preliminar.parquet")
OUT_DIR = Path("data/processed")
NOTAS = ["NU_NOTA_CN", "NU_NOTA_CH", "NU_NOTA_LC", "NU_NOTA_MT", "NU_NOTA_REDACAO"]


def hedges_g(x: np.ndarray, y: np.ndarray) -> float:
    n1 = x.size
    n2 = y.size
    if n1 < 2 or n2 < 2:
        return np.nan

    s1 = np.std(x, ddof=1)
    s2 = np.std(y, ddof=1)
    sp_num = (n1 - 1) * (s1 ** 2) + (n2 - 1) * (s2 ** 2)
    sp_den = (n1 + n2 - 2)
    if sp_den <= 0:
        return np.nan
    sp = np.sqrt(sp_num / sp_den)
    if sp == 0:
        return np.nan

    d = (np.mean(x) - np.mean(y)) / sp
    j = 1 - (3 / (4 * (n1 + n2) - 9))
    return float(j * d)


def magnitude_label(abs_eff: float) -> str:
    if np.isnan(abs_eff):
        return "indefinido"
    if abs_eff < 0.2:
        return "desprezivel"
    if abs_eff < 0.5:
        return "pequeno"
    if abs_eff < 0.8:
        return "medio"
    return "grande"


def analisar(df: pd.DataFrame) -> pd.DataFrame:
    resultados: list[dict] = []

    for ano in sorted(df["ANO"].dropna().unique()):
        sub_ano = df[df["ANO"] == ano]

        for area in NOTAS:
            sub = sub_ano[sub_ano["GRUPO_RECORTE"].isin(["acessivel", "regular"])].copy()
            sub = sub[["GRUPO_RECORTE", area]].dropna()

            acc = sub.loc[sub["GRUPO_RECORTE"] == "acessivel", area].to_numpy(dtype=float)
            reg = sub.loc[sub["GRUPO_RECORTE"] == "regular", area].to_numpy(dtype=float)

            if acc.size < 2 or reg.size < 2:
                continue

            t = stats.ttest_ind(acc, reg, equal_var=False, nan_policy="omit")
            g = hedges_g(acc, reg)
            gap = float(np.mean(acc) - np.mean(reg))

            resultados.append(
                {
                    "ANO": int(ano),
                    "AREA": area,
                    "N_ACESSIVEL": int(acc.size),
                    "N_REGULAR": int(reg.size),
                    "MEDIA_ACESSIVEL": round(float(np.mean(acc)), 3),
                    "MEDIA_REGULAR": round(float(np.mean(reg)), 3),
                    "GAP_ACESSIVEL_MENOS_REGULAR": round(gap, 3),
                    "T_WELCH": round(float(t.statistic), 6),
                    "P_VALOR": float(t.pvalue),
                    "HEDGES_G": round(g, 6),
                    "MAGNITUDE": magnitude_label(abs(g)),
                    "SIGNIFICANTE_5PCT": bool(t.pvalue < 0.05),
                }
            )

    out = pd.DataFrame(resultados)
    out = out.sort_values(["ANO", "AREA"]).reset_index(drop=True)

    # Formata p-valor para leitura no slide sem perder versao numerica.
    out["P_VALOR_FMT"] = out["P_VALOR"].map(
        lambda p: "<1e-300" if p < 1e-300 else f"{p:.3e}"
    )

    return out


def resumo_significancia(tab: pd.DataFrame) -> pd.DataFrame:
    resumo = (
        tab.groupby("ANO", dropna=False)
        .agg(
            TESTES=("AREA", "count"),
            TESTES_SIGNIFICANTES_5PCT=("SIGNIFICANTE_5PCT", "sum"),
            MEDIA_ABS_HEDGES_G=("HEDGES_G", lambda s: float(np.mean(np.abs(s)))),
            MAIOR_GAP_ABS=("GAP_ACESSIVEL_MENOS_REGULAR", lambda s: float(np.max(np.abs(s)))),
        )
        .reset_index()
    )
    resumo["MEDIA_ABS_HEDGES_G"] = resumo["MEDIA_ABS_HEDGES_G"].round(3)
    resumo["MAIOR_GAP_ABS"] = resumo["MAIOR_GAP_ABS"].round(3)
    return resumo


def main() -> None:
    if not BASE_PATH.exists():
        raise FileNotFoundError(
            f"Base preliminar nao encontrada em {BASE_PATH}. Rode antes: src/02_build_base_preliminar.py"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(BASE_PATH)

    tabela = analisar(df)
    resumo = resumo_significancia(tabela)

    p1 = OUT_DIR / "fase3_welch_efeito_por_ano_area.csv"
    p2 = OUT_DIR / "fase3_resumo_significancia.csv"

    tabela.to_csv(p1, index=False, encoding="utf-8-sig")
    resumo.to_csv(p2, index=False, encoding="utf-8-sig")

    print("Arquivos gerados:")
    print(f"- {p1}")
    print(f"- {p2}")

    print("\nResumo por ano:")
    print(resumo.to_string(index=False))

    print("\nTabela completa (Welch + efeito):")
    cols_show = [
        "ANO",
        "AREA",
        "N_ACESSIVEL",
        "N_REGULAR",
        "GAP_ACESSIVEL_MENOS_REGULAR",
        "P_VALOR_FMT",
        "HEDGES_G",
        "MAGNITUDE",
        "SIGNIFICANTE_5PCT",
    ]
    print(tabela[cols_show].to_string(index=False))


if __name__ == "__main__":
    main()
