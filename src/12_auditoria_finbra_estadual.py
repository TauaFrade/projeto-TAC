"""Auditoria da série estadual FINBRA 2020–2024.

Entradas:
- data/raw/finbra/<ano>/finbra_estados.csv

Saídas:
- data/processed/auditoria_finbra_estadual_municipio_ano.csv
- data/processed/auditoria_finbra_estadual_resumo_ano.csv
- data/processed/auditoria_finbra_estadual_faltantes.csv

Uso:
  python src/12_auditoria_finbra_estadual.py
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

FINBRA_DIR = Path("data/raw/finbra")
OUT_DIR = Path("data/processed")
OUT_UF_ANO = OUT_DIR / "auditoria_finbra_estadual_municipio_ano.csv"
OUT_RESUMO = OUT_DIR / "auditoria_finbra_estadual_resumo_ano.csv"
OUT_FALTANTES = OUT_DIR / "auditoria_finbra_estadual_faltantes.csv"

SUBFUNCOES_ALVO = {"12.361", "12.362", "12.365", "12.367", "12.368"}

UF_CODES = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
    28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR",
    42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF",
}


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    s = unicodedata.normalize("NFKD", str(value).strip())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()


def parse_br_number(value: object) -> float:
    if value is None:
        return np.nan
    s = str(value).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return np.nan


def extract_subfuncao(conta: object) -> str | None:
    match = re.match(r"^\s*(\d{2}\.\d{3})\b", str(conta or ""))
    return match.group(1) if match else None


def detect_encoding(path: Path) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            pd.read_csv(path, sep=";", encoding=enc, skiprows=3, nrows=2)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def audit_year(ano: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = FINBRA_DIR / str(ano) / "finbra_estados.csv"
    if not path.exists():
        raise FileNotFoundError(f"Arquivo estadual nao encontrado: {path}")

    enc = detect_encoding(path)
    df = pd.read_csv(
        path,
        sep=";",
        encoding=enc,
        skiprows=3,
        dtype={
            "Instituição": "string",
            "Cod.IBGE": "string",
            "UF": "string",
            "População": "string",
            "Coluna": "string",
            "Conta": "string",
            "Identificador da Conta": "string",
            "Valor": "string",
        },
        low_memory=False,
    )

    df["COD_UF"] = pd.to_numeric(df["Cod.IBGE"], errors="coerce").astype("Int64")
    df["UF_SIGLA"] = df["UF"].str.strip().str.upper()
    df["UF_VALIDO"] = df["COD_UF"].isin(UF_CODES.keys())
    df["UF_SIGLA_EXPECTADA"] = df["COD_UF"].map(UF_CODES)
    df["UF_SIGLA_OK"] = df["UF_SIGLA"] == df["UF_SIGLA_EXPECTADA"]

    df["COLUNA_NORM"] = df["Coluna"].map(normalize_text)
    df["SUBFUNCAO"] = df["Conta"].map(extract_subfuncao)
    df["VALOR_NUM"] = df["Valor"].map(parse_br_number)

    liquidadas = df[df["COLUNA_NORM"] == "despesas liquidadas"].copy()
    liquidadas = liquidadas[liquidadas["SUBFUNCAO"].isin(SUBFUNCOES_ALVO)].copy()

    agg = (
        liquidadas.groupby(["COD_UF", "UF_SIGLA"], as_index=False, dropna=False)
        .agg(
            FINBRA_EST_N_SUBFUNCOES_PRESENTES=("SUBFUNCAO", "nunique"),
            FINBRA_EST_VALOR_TOTAL_ALVO=("VALOR_NUM", "sum"),
        )
    )

    agg["ANO"] = ano
    agg["FINBRA_EST_HAS_ALL_5"] = agg["FINBRA_EST_N_SUBFUNCOES_PRESENTES"] == 5
    agg["FINBRA_EST_VALOR_TOTAL_POSITIVO"] = agg["FINBRA_EST_VALOR_TOTAL_ALVO"] > 0

    resumo = {
        "ANO": ano,
        "REGISTROS_TOTAL": len(df),
        "UFS_COM_DADO_BRUTO": df["UF_SIGLA"].nunique(dropna=True),
        "UFS_COM_SUBFUNCOES_ALVO": agg["UF_SIGLA"].nunique(dropna=True),
        "UFS_COM_ALL_5": int(agg["FINBRA_EST_HAS_ALL_5"].sum()),
        "UFS_SIGLA_CODIGO_CONSISTENTES": int(df["UF_SIGLA_OK"].sum()),
        "VALORES_NULOS_TOTAL": int(df["Valor"].isna().sum()),
        "VALORES_INVALIDOS_LIQUIDADAS_ALVO": int(liquidadas["VALOR_NUM"].isna().sum()),
        "IDENTIFICADOR_UNICOS": int(df["Identificador da Conta"].nunique(dropna=True)),
        "COLUNAS_UNICAS": int(df["Coluna"].nunique(dropna=True)),
        "CONTAS_UNICAS": int(df["Conta"].nunique(dropna=True)),
    }

    faltantes = pd.DataFrame({"UF_SIGLA": list(UF_CODES.values())})
    faltantes["ANO"] = ano
    faltantes = faltantes.merge(
        agg[["UF_SIGLA", "FINBRA_EST_N_SUBFUNCOES_PRESENTES", "FINBRA_EST_HAS_ALL_5", "FINBRA_EST_VALOR_TOTAL_POSITIVO"]],
        on="UF_SIGLA",
        how="left",
    )
    faltantes["FINBRA_EST_N_SUBFUNCOES_PRESENTES"] = faltantes["FINBRA_EST_N_SUBFUNCOES_PRESENTES"].fillna(0)
    faltantes["FINBRA_EST_HAS_ALL_5"] = faltantes["FINBRA_EST_HAS_ALL_5"].fillna(False)
    faltantes["FINBRA_EST_VALOR_TOTAL_POSITIVO"] = faltantes["FINBRA_EST_VALOR_TOTAL_POSITIVO"].fillna(False)

    faltantes["MOTIVO_FALTA"] = np.select(
        [
            faltantes["FINBRA_EST_N_SUBFUNCOES_PRESENTES"] == 0,
            ~faltantes["FINBRA_EST_HAS_ALL_5"],
            ~faltantes["FINBRA_EST_VALOR_TOTAL_POSITIVO"],
        ],
        [
            "sem_subfuncoes_alvo",
            "subfuncoes_incompletas",
            "valor_total_nao_positivo",
        ],
        default="ok",
    )

    faltantes = faltantes[faltantes["MOTIVO_FALTA"] != "ok"].copy()
    return pd.DataFrame([resumo]), faltantes.assign(
        UF_CODIGO=lambda x: x["UF_SIGLA"].map({v: k for k, v in UF_CODES.items()}),
    )


def main(anos: list[int]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    uf_frames = []
    resumo_frames = []
    faltante_frames = []

    for ano in anos:
        resumo, faltantes = audit_year(ano)
        resumo_frames.append(resumo)

        path = FINBRA_DIR / str(ano) / "finbra_estados.csv"
        enc = detect_encoding(path)
        df = pd.read_csv(
            path,
            sep=";",
            encoding=enc,
            skiprows=3,
            dtype={"Cod.IBGE": "string", "UF": "string", "Coluna": "string", "Conta": "string", "Valor": "string"},
            low_memory=False,
        )
        df["COLUNA_NORM"] = df["Coluna"].map(normalize_text)
        df["SUBFUNCAO"] = df["Conta"].map(extract_subfuncao)
        df["VALOR_NUM"] = df["Valor"].map(parse_br_number)
        liquidadas = df[
            (df["COLUNA_NORM"] == "despesas liquidadas")
            & df["SUBFUNCAO"].isin(SUBFUNCOES_ALVO)
        ].copy()
        liquidadas["COD_UF"] = pd.to_numeric(liquidadas["Cod.IBGE"], errors="coerce").astype("Int64")
        liquidadas["UF_SIGLA"] = liquidadas["UF"].str.strip().str.upper()

        uf_agg = (
            liquidadas.groupby(["COD_UF", "UF_SIGLA"], as_index=False)
            .agg(
                FINBRA_EST_N_SUBFUNCOES_PRESENTES=("SUBFUNCAO", "nunique"),
                FINBRA_EST_VALOR_TOTAL_ALVO=("VALOR_NUM", "sum"),
            )
        )
        uf_agg["ANO"] = ano
        uf_agg["FINBRA_EST_HAS_ALL_5"] = uf_agg["FINBRA_EST_N_SUBFUNCOES_PRESENTES"] == 5
        uf_agg["FINBRA_EST_VALOR_TOTAL_POSITIVO"] = uf_agg["FINBRA_EST_VALOR_TOTAL_ALVO"] > 0
        uf_frames.append(uf_agg)
        faltante_frames.append(faltantes)

    uf_panel = pd.concat(uf_frames, ignore_index=True)
    resumo_panel = pd.concat(resumo_frames, ignore_index=True)
    faltantes_panel = pd.concat(faltante_frames, ignore_index=True)

    uf_panel.to_csv(OUT_UF_ANO, index=False, encoding="utf-8-sig")
    resumo_panel.to_csv(OUT_RESUMO, index=False, encoding="utf-8-sig")
    faltantes_panel.to_csv(OUT_FALTANTES, index=False, encoding="utf-8-sig")

    print("Auditoria estadual concluida.")
    print(f"- {OUT_UF_ANO}")
    print(f"- {OUT_RESUMO}")
    print(f"- {OUT_FALTANTES}")
    print("\nResumo por ano:")
    print(resumo_panel.to_string(index=False))


if __name__ == "__main__":
    main([2020, 2021, 2022, 2023, 2024])
