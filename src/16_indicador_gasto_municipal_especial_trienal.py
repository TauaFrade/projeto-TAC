"""Indicador municipal trienal específico de Educação Especial.

Numerador: despesa liquidada FINBRA subfunção 12.367.
Denominador: matrículas QT_MAT_ESP da rede pública municipal no Censo Escolar.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

FINBRA_DIR = Path("data/raw/finbra")
CENSO_DIR = Path("data/raw/censo_escolar")
IPCA_PATH = Path("data/raw/IPCA/IPCA_numero_indice.json")
OUT_ANUAL = Path("data/processed/indicador_gasto_municipal_especial_municipio_ano_real.csv")
OUT_TRIENAL = Path("data/processed/indicador_gasto_municipal_especial_trienal_enem_municipio.csv")


def normalize_text(value: object) -> str:
    s = unicodedata.normalize("NFKD", str(value or "").strip())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()


def parse_br(value: object) -> float:
    if value is None:
        return np.nan
    s = str(value).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return np.nan


def extract_subfuncao(conta: object) -> str | None:
    m = re.match(r"^\s*(\d{2}\.\d{3})\b", str(conta or ""))
    return m.group(1) if m else None


def find_censo_csv(year_dir: Path) -> Path:
    csvs = sorted(set([p.resolve() for p in year_dir.rglob("*.csv")]))
    csvs += sorted(set([p.resolve() for p in year_dir.rglob("*.CSV")]))
    csvs = sorted(set(csvs))
    matches = [p for p in csvs if "microdados_ed_basica" in p.name.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(csvs) == 1:
        return csvs[0]
    raise RuntimeError(f"Arquivo Censo ambiguo em {year_dir}: {csvs}")


def detect_encoding(path: Path) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            pd.read_csv(path, sep=";", encoding=enc, nrows=2)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def ipca_media() -> pd.DataFrame:
    raw = json.loads(IPCA_PATH.read_text(encoding="utf-8"))
    rows = []
    for r in raw[1:]:
        code = str(r.get("D3C", ""))
        if len(code) >= 6 and code[:6].isdigit():
            try:
                rows.append({"ANO": int(code[:4]), "MES": int(code[4:6]), "IPCA": float(str(r.get("V")).replace(",", "."))})
            except (TypeError, ValueError):
                continue
    ipca = pd.DataFrame(rows)
    out = ipca.groupby("ANO", as_index=False).agg(IPCA_MEDIA=("IPCA", "mean"), N_MESES=("MES", "nunique"))
    return out[out["N_MESES"] >= 12].copy()


def load_finbra(ano: int) -> pd.DataFrame:
    path = FINBRA_DIR / str(ano) / "finbra_municipios.csv"
    if not path.exists():
        raise FileNotFoundError(f"FINBRA municipal nao encontrado: {path}")
    enc = detect_encoding(path)
    df = pd.read_csv(path, sep=";", encoding=enc, skiprows=3,
                     dtype={"Cod.IBGE": "string", "Coluna": "string", "Conta": "string", "Valor": "string"},
                     low_memory=False)
    df["COD_MUN"] = pd.to_numeric(df["Cod.IBGE"], errors="coerce").astype("Int64")
    df["COLUNA"] = df["Coluna"].map(normalize_text)
    df["SUBFUNCAO"] = df["Conta"].map(extract_subfuncao)
    df["VALOR"] = df["Valor"].map(parse_br)
    sub = df[(df["COLUNA"] == "despesas liquidadas") & (df["SUBFUNCAO"] == "12.367")]
    return sub.groupby("COD_MUN", as_index=False).agg(DESPESA_ESPECIAL=("VALOR", "sum"))


def load_censo(ano: int) -> pd.DataFrame:
    path = find_censo_csv(CENSO_DIR / str(ano))
    enc = detect_encoding(path)
    df = pd.read_csv(path, sep=";", encoding=enc,
                     usecols=["NU_ANO_CENSO", "CO_MUNICIPIO", "TP_DEPENDENCIA", "TP_SITUACAO_FUNCIONAMENTO", "QT_MAT_ESP"],
                     dtype={"NU_ANO_CENSO": "Int64", "CO_MUNICIPIO": "string", "TP_DEPENDENCIA": "Int64", "TP_SITUACAO_FUNCIONAMENTO": "Int64", "QT_MAT_ESP": "float64"},
                     low_memory=False)
    df["COD_MUN"] = pd.to_numeric(df["CO_MUNICIPIO"], errors="coerce").astype("Int64")
    df = df[(df["NU_ANO_CENSO"] == ano) & (df["TP_DEPENDENCIA"] == 3) & (df["TP_SITUACAO_FUNCIONAMENTO"] == 1)].copy()
    df["QT_MAT_ESP"] = df["QT_MAT_ESP"].fillna(0)
    return df.groupby("COD_MUN", as_index=False).agg(MAT_ESP=("QT_MAT_ESP", "sum"))


def main(ano_base: int = 2024) -> None:
    ipca = ipca_media()
    base = ipca[ipca["ANO"] == ano_base]
    if base.empty:
        raise ValueError("Ano-base IPCA indisponivel")
    ipca_base = float(base.iloc[0]["IPCA_MEDIA"])

    frames = []
    for ano in [2020, 2021, 2022, 2023, 2024]:
        fin = load_finbra(ano)
        cen = load_censo(ano)
        panel = fin.merge(cen, on="COD_MUN", how="outer")
        panel["ANO"] = ano
        frames.append(panel)

    annual = pd.concat(frames, ignore_index=True)
    annual = annual.merge(ipca[["ANO", "IPCA_MEDIA"]], on="ANO", how="left")
    annual["ANO_BASE_IPCA"] = ano_base
    annual["FATOR_DEFLATOR"] = ipca_base / annual["IPCA_MEDIA"]
    annual["DESPESA_ESPECIAL_REAL"] = annual["DESPESA_ESPECIAL"] * annual["FATOR_DEFLATOR"]
    annual["GASTO_MUNICIPAL_ESPECIAL_POR_MATRICULA_ESP"] = annual["DESPESA_ESPECIAL_REAL"] / annual["MAT_ESP"]
    annual["VALIDO"] = annual["GASTO_MUNICIPAL_ESPECIAL_POR_MATRICULA_ESP"].notna() & np.isfinite(annual["GASTO_MUNICIPAL_ESPECIAL_POR_MATRICULA_ESP"]) & (annual["MAT_ESP"] > 0)

    annual = annual.sort_values(["ANO", "COD_MUN"])
    annual.to_csv(OUT_ANUAL, index=False, encoding="utf-8-sig")

    trienios = []
    for ano_enem in [2023, 2024, 2025]:
        janela = [ano_enem - 3, ano_enem - 2, ano_enem - 1]
        sub = annual[annual["ANO"].isin(janela) & annual["VALIDO"]].copy()
        agg = sub.groupby("COD_MUN", as_index=False).agg(
            N_ANOS_ESPECIAL=("ANO", "nunique"),
            GASTO_MUNICIPAL_ESPECIAL_POR_MATRICULA_TRIENIO=("GASTO_MUNICIPAL_ESPECIAL_POR_MATRICULA_ESP", "mean"),
        )
        agg["ANO_ENEM"] = ano_enem
        agg["TRIENIO_COMPLETO_ESPECIAL"] = agg["N_ANOS_ESPECIAL"] == 3
        trienios.append(agg)

    trienal = pd.concat(trienios, ignore_index=True).sort_values(["ANO_ENEM", "COD_MUN"])
    trienal.to_csv(OUT_TRIENAL, index=False, encoding="utf-8-sig")

    print(f"- {OUT_ANUAL}")
    print(f"- {OUT_TRIENAL}")


if __name__ == "__main__":
    main()
