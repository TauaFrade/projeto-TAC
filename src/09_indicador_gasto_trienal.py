"""Calcula indicador anual e trienal de gasto real por matricula (municipio).

Premissas desta etapa:
- Usa a auditoria de cobertura ja calculada.
- Usa somente municipios-ano com PRONTO_INDICADOR_BASE = True.
- Numerador: FINBRA_VALOR_TOTAL_ALVO (despesas liquidadas nas subfuncoes alvo).
- Denominador: CENSO_MAT_ALVO_SUM.
- Deflacao: IPCA numero-indice medio anual, para ano-base escolhido.

Saidas:
- data/processed/indicador_gasto_municipio_ano_real.csv
- data/processed/indicador_gasto_trienal_enem_municipio.csv
- data/processed/indicador_gasto_trienal_enem_resumo.csv

Uso:
  python src/09_indicador_gasto_trienal.py
  python src/09_indicador_gasto_trienal.py --ano-base-ipca 2024
  python src/09_indicador_gasto_trienal.py --anos-enem 2023 2024 2025
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

AUDITORIA_PATH = Path("data/processed/auditoria_cobertura_municipio_ano.csv")
IPCA_PATH = Path("data/raw/IPCA/IPCA_numero_indice.json")
OUT_DIR = Path("data/processed")

OUT_ANUAL = OUT_DIR / "indicador_gasto_municipio_ano_real.csv"
OUT_TRIENAL = OUT_DIR / "indicador_gasto_trienal_enem_municipio.csv"
OUT_RESUMO = OUT_DIR / "indicador_gasto_trienal_enem_resumo.csv"


def load_ipca_media_anual() -> pd.DataFrame:
    if not IPCA_PATH.exists():
        raise FileNotFoundError(f"Arquivo IPCA nao encontrado: {IPCA_PATH}")

    raw = json.loads(IPCA_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or len(raw) < 2:
        raise ValueError("Formato inesperado no JSON do IPCA (esperado: lista com cabecalho + linhas)")

    rows = []
    for rec in raw[1:]:
        mes_code = str(rec.get("D3C", ""))
        val = rec.get("V", None)
        if len(mes_code) < 6 or not mes_code[:6].isdigit():
            continue
        try:
            indice = float(str(val).replace(",", "."))
        except ValueError:
            continue
        rows.append({"ANO": int(mes_code[:4]), "MES": int(mes_code[4:6]), "IPCA_INDICE": indice})

    ipca = pd.DataFrame(rows)
    if ipca.empty:
        raise ValueError("Nao foi possivel extrair series mensais validas do IPCA")

    anual = (
        ipca.groupby("ANO", as_index=False)
        .agg(IPCA_MEDIA_ANUAL=("IPCA_INDICE", "mean"), N_MESES=("MES", "nunique"))
        .sort_values("ANO")
    )

    anual = anual[anual["N_MESES"] >= 12].copy()
    if anual.empty:
        raise ValueError("Nao ha anos com 12 meses completos no IPCA")

    return anual


def build_indicador_anual(ano_base_ipca: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not AUDITORIA_PATH.exists():
        raise FileNotFoundError(
            f"Arquivo de auditoria nao encontrado: {AUDITORIA_PATH}. Rode antes o script 08."
        )

    audit = pd.read_csv(AUDITORIA_PATH)
    ipca = load_ipca_media_anual()

    base_row = ipca[ipca["ANO"] == ano_base_ipca]
    if base_row.empty:
        anos_disp = ", ".join(map(str, ipca["ANO"].tolist()))
        raise ValueError(f"Ano-base {ano_base_ipca} nao disponivel no IPCA. Anos disponiveis: {anos_disp}")

    ipca_base = float(base_row.iloc[0]["IPCA_MEDIA_ANUAL"])

    # Apenas municipios-ano aptos no criterio indicador_base.
    df = audit.loc[audit["PRONTO_INDICADOR_BASE"] == True].copy()  # noqa: E712

    df = df.merge(ipca[["ANO", "IPCA_MEDIA_ANUAL"]], on="ANO", how="left")
    if df["IPCA_MEDIA_ANUAL"].isna().any():
        raise ValueError("Existem anos aptos sem IPCA medio anual apos merge")

    df["FATOR_DEFLATOR_ANO_BASE"] = ipca_base / df["IPCA_MEDIA_ANUAL"]
    df["DESPESA_REAL_ALVO_ANO_BASE"] = df["FINBRA_VALOR_TOTAL_ALVO"] * df["FATOR_DEFLATOR_ANO_BASE"]
    df["GASTO_REAL_POR_MATRICULA"] = df["DESPESA_REAL_ALVO_ANO_BASE"] / df["CENSO_MAT_ALVO_SUM"]

    df["DESPESA_REAL_ALVO_ANO_BASE"] = df["DESPESA_REAL_ALVO_ANO_BASE"].round(2)
    df["GASTO_REAL_POR_MATRICULA"] = df["GASTO_REAL_POR_MATRICULA"].round(6)
    df["ANO_BASE_IPCA"] = ano_base_ipca

    keep_cols = [
        "ANO",
        "CO_MUNICIPIO",
        "ANO_BASE_IPCA",
        "IPCA_MEDIA_ANUAL",
        "FATOR_DEFLATOR_ANO_BASE",
        "FINBRA_N_SUBFUNCOES_PRESENTES",
        "FINBRA_VALOR_TOTAL_ALVO",
        "DESPESA_REAL_ALVO_ANO_BASE",
        "CENSO_MAT_ALVO_SUM",
        "GASTO_REAL_POR_MATRICULA",
        "PRONTO_INDICADOR_BASE",
    ]
    out = df[keep_cols].sort_values(["ANO", "CO_MUNICIPIO"]).reset_index(drop=True)
    return out, ipca


def build_trienio_municipio(anual: pd.DataFrame, anos_enem: list[int]) -> pd.DataFrame:
    frames = []
    for ano_enem in anos_enem:
        janela = [ano_enem - 3, ano_enem - 2, ano_enem - 1]
        sub = anual[anual["ANO"].isin(janela)].copy()

        agg = (
            sub.groupby("CO_MUNICIPIO", as_index=False)
            .agg(
                N_ANOS_DISPONIVEIS=("ANO", "nunique"),
                GASTO_REAL_POR_MATRICULA_TRIENIO=("GASTO_REAL_POR_MATRICULA", "mean"),
                DESPESA_REAL_ALVO_TRIENIO_MEDIA=("DESPESA_REAL_ALVO_ANO_BASE", "mean"),
                CENSO_MAT_ALVO_TRIENIO_MEDIA=("CENSO_MAT_ALVO_SUM", "mean"),
            )
            .copy()
        )

        agg["ANO_ENEM"] = ano_enem
        agg["TRIENIO_INICIO"] = janela[0]
        agg["TRIENIO_FIM"] = janela[-1]
        agg["TRIENIO_COMPLETO"] = agg["N_ANOS_DISPONIVEIS"] == 3

        agg["GASTO_REAL_POR_MATRICULA_TRIENIO"] = agg["GASTO_REAL_POR_MATRICULA_TRIENIO"].round(6)
        agg["DESPESA_REAL_ALVO_TRIENIO_MEDIA"] = agg["DESPESA_REAL_ALVO_TRIENIO_MEDIA"].round(2)
        agg["CENSO_MAT_ALVO_TRIENIO_MEDIA"] = agg["CENSO_MAT_ALVO_TRIENIO_MEDIA"].round(2)

        frames.append(agg)

    trienio = pd.concat(frames, ignore_index=True)
    return trienio.sort_values(["ANO_ENEM", "CO_MUNICIPIO"]).reset_index(drop=True)


def build_resumo_trienio(trienio: pd.DataFrame) -> pd.DataFrame:
    resumo = (
        trienio.groupby("ANO_ENEM", as_index=False)
        .agg(
            MUNICIPIOS_COM_ALGUM_DADO=("CO_MUNICIPIO", "nunique"),
            MUNICIPIOS_TRIENIO_COMPLETO=("TRIENIO_COMPLETO", "sum"),
            GASTO_TRIENIO_MEDIANA=("GASTO_REAL_POR_MATRICULA_TRIENIO", "median"),
            GASTO_TRIENIO_MEDIA=("GASTO_REAL_POR_MATRICULA_TRIENIO", "mean"),
            GASTO_TRIENIO_P25=("GASTO_REAL_POR_MATRICULA_TRIENIO", lambda s: s.quantile(0.25)),
            GASTO_TRIENIO_P75=("GASTO_REAL_POR_MATRICULA_TRIENIO", lambda s: s.quantile(0.75)),
        )
        .copy()
    )

    resumo["PCT_TRIENIO_COMPLETO"] = (
        100 * resumo["MUNICIPIOS_TRIENIO_COMPLETO"] / resumo["MUNICIPIOS_COM_ALGUM_DADO"]
    ).round(2)

    for c in ["GASTO_TRIENIO_MEDIANA", "GASTO_TRIENIO_MEDIA", "GASTO_TRIENIO_P25", "GASTO_TRIENIO_P75"]:
        resumo[c] = resumo[c].round(6)

    return resumo


def main(ano_base_ipca: int, anos_enem: list[int]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    anual, _ = build_indicador_anual(ano_base_ipca=ano_base_ipca)
    trienio = build_trienio_municipio(anual=anual, anos_enem=anos_enem)
    resumo = build_resumo_trienio(trienio=trienio)

    anual.to_csv(OUT_ANUAL, index=False, encoding="utf-8-sig")
    trienio.to_csv(OUT_TRIENAL, index=False, encoding="utf-8-sig")
    resumo.to_csv(OUT_RESUMO, index=False, encoding="utf-8-sig")

    print("Indicadores gerados com sucesso:")
    print(f"- {OUT_ANUAL}")
    print(f"- {OUT_TRIENAL}")
    print(f"- {OUT_RESUMO}")
    print("\nResumo por ano ENEM:")
    print(resumo.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ano-base-ipca", type=int, default=2024)
    parser.add_argument("--anos-enem", nargs="+", type=int, default=[2023, 2024, 2025])
    args = parser.parse_args()
    main(ano_base_ipca=args.ano_base_ipca, anos_enem=args.anos_enem)
