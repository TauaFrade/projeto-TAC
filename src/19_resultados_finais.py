"""Gera os resultados finais documentais a partir dos CSVs já validados.

Este script NÃO executa nem ajusta modelos.
Ele apenas consolida tabelas e redige resumos prontos para revisão acadêmica.

Entradas:
- data/processed/modelos_integrados_municipal_estadual.csv
- data/processed/modelos_integrados_municipal_estadual_diagnosticos.csv
- data/processed/revisao_modelos_resumo_por_area.csv
- data/processed/revisao_modelos_resumo_por_termo.csv
- data/processed/revisao_modelos_leitura_academica.csv
- data/processed/enem_gastos_cobertura_combinada_ano.csv

Saídas:
- data/processed/resultados_finais_coeficientes_tabelados.csv
- data/processed/resultados_finais_resumo.csv
- reports/RESULTADOS_FINAIS.md
- reports/QUADRO_RESUMO_RESULTADOS.md
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path("data/processed")
REPORT_DIR = Path("reports")

MODELS = DATA_DIR / "modelos_integrados_municipal_estadual.csv"
DIAG = DATA_DIR / "modelos_integrados_municipal_estadual_diagnosticos.csv"
TERM_REVIEW = DATA_DIR / "revisao_modelos_resumo_por_termo.csv"
AREA_REVIEW = DATA_DIR / "revisao_modelos_resumo_por_area.csv"
ACADEMIC_REVIEW = DATA_DIR / "revisao_modelos_leitura_academica.csv"
COVERAGE = DATA_DIR / "enem_gastos_cobertura_combinada_ano.csv"

OUT_TABLE = DATA_DIR / "resultados_finais_coeficientes_tabelados.csv"
OUT_SUMMARY = DATA_DIR / "resultados_finais_resumo.csv"
OUT_RESULTS_MD = REPORT_DIR / "RESULTADOS_FINAIS.md"
OUT_QUADRO_MD = REPORT_DIR / "QUADRO_RESUMO_RESULTADOS.md"

TERM_LABELS = {
    "GRUPO_ACESSIVEL": "Participante identificado com prova acessível",
    "GASTO_MUNICIPAL_Z": "Gasto municipal geral",
    "GASTO_MUNICIPAL_ESPECIAL_Z": "Gasto municipal em Educação Especial",
    "GASTO_ESTADUAL_Z": "Gasto estadual geral",
    "GASTO_ESTADUAL_ESPECIAL_Z": "Gasto estadual em Educação Especial",
    "GRUPO_ACESSIVEL:GASTO_MUNICIPAL_Z": "Acessível × gasto municipal geral",
    "GRUPO_ACESSIVEL:GASTO_MUNICIPAL_ESPECIAL_Z": "Acessível × gasto municipal em Educação Especial",
    "GRUPO_ACESSIVEL:GASTO_ESTADUAL_Z": "Acessível × gasto estadual geral",
    "GRUPO_ACESSIVEL:GASTO_ESTADUAL_ESPECIAL_Z": "Acessível × gasto estadual em Educação Especial",
}


def format_coef(row: pd.Series) -> str:
    coef = float(row["COEFICIENTE"])
    ic_inf = float(row["IC95_INF"])
    ic_sup = float(row["IC95_SUP"])
    p = str(row["P_VALOR_FMT"])
    return f"{coef:.3f} (IC95% {ic_inf:.3f}; {ic_sup:.3f}; p={p})"


def format_significance(flag: bool) -> str:
    return "Sim" if bool(flag) else "Não"


def require_input(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Entrada necessária não encontrada: {path}. "
            "Execute os scripts anteriores antes de gerar os resultados finais."
        )
    return pd.read_csv(path)


def build_tabled_coefficients(models: pd.DataFrame) -> pd.DataFrame:
    table = models.copy()
    table["INDICADOR"] = table["TERMO"].map(TERM_LABELS).fillna(table["TERMO"])
    table["RESULTADO"] = table.apply(format_coef, axis=1)
    table["SIGNIFICANTE_5PCT"] = table["SIGNIFICANTE_5PCT"].map(format_significance)

    return table[[
        "AREA", "AREA_NOME", "INDICADOR", "COEFICIENTE",
        "ERRO_PADRAO_CLUSTER", "P_VALOR", "P_VALOR_FMT",
        "IC95_INF", "IC95_SUP", "SIGNIFICANTE_5PCT", "RESULTADO",
    ]].sort_values(["AREA", "INDICADOR"])


def build_summary(models: pd.DataFrame, diagnostics: pd.DataFrame) -> pd.DataFrame:
    merge = diagnostics[[
        "AREA", "AREA_NOME", "N", "N_ACESSIVEL", "N_REGULAR",
        "N_MUNICIPIOS", "R_QUADRADO", "R_QUADRADO_AJUSTADO", "STATUS",
    ]].copy()

    sig_counts = (
        models.groupby(["AREA", "AREA_NOME"], as_index=False)
        .agg(
            N_COEFICIENTES=("TERMO", "count"),
            N_SIGNIFICANTES=("SIGNIFICANTE_5PCT", "sum"),
        )
    )

    interaction_rows = []
    for area in models["AREA"].drop_duplicates():
        sub = models[(models["AREA"] == area) & models["TERMO"].str.startswith("GRUPO_ACESSIVEL:")]
        interaction_rows.append({
            "AREA": area,
            "N_INTERACOES_SIGNIFICANTES": int(sub["SIGNIFICANTE_5PCT"].sum()),
        })

    interactions = pd.DataFrame(interaction_rows)
    summary = merge.merge(sig_counts, on=["AREA", "AREA_NOME"], how="left")
    summary = summary.merge(interactions, on="AREA", how="left")
    return summary.sort_values("AREA")


def build_area_text(academic: pd.DataFrame) -> str:
    lines = ["## Resultado por área", ""]

    for _, r in academic.iterrows():
        lines.extend([
            f"### {r['AREA_NOME']}",
            "",
            f"- Efeito principal do grupo acessível: {r['EFEITO_GRUPO']}.",
            f"- Termos estatisticamente significativos: {r['TERMOS_SIGNIFICANTES']}.",
            f"- Interações significativas: {int(r['N_INTERACOES_SIGNIFICANTES'])}.",
            f"- Interpretação: {r['LEITURA']}",
            "",
        ])

    return "\n".join(lines)


def build_coverage_text(coverage: pd.DataFrame) -> str:
    lines = ["## Cobertura dos indicadores", ""]
    for _, r in coverage.iterrows():
        lines.append(
            f"- ENEM {int(r['ANO'])}: **{float(r['PCT_COMBINADO']):.3f}%** com indicador municipal-estadual combinado; "
            f"**{float(r['PCT_TRIENIO_COMBINADO']):.3f}%** com triênio combinado completo."
        )
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    models = require_input(MODELS)
    diagnostics = require_input(DIAG)
    academic = require_input(ACADEMIC_REVIEW)
    coverage = require_input(COVERAGE)

    table = build_tabled_coefficients(models)
    summary = build_summary(models, diagnostics)

    table.to_csv(OUT_TABLE, index=False, encoding="utf-8-sig")
    summary.to_csv(OUT_SUMMARY, index=False, encoding="utf-8-sig")

    areas_text = build_area_text(academic)
    coverage_text = build_coverage_text(coverage)

    def coefficient_cell(area: str, term: str) -> str:
        row = models[(models["AREA"] == area) & (models["TERMO"] == term)]
        if row.empty:
            return "não estimado"
        r = row.iloc[0]
        if not bool(r["SIGNIFICANTE_5PCT"]):
            return "não significativo"
        stars = "***" if float(r["P_VALOR"]) < 0.001 else "*"
        return f"{float(r['COEFICIENTE']):+.3f}{stars}"

    group_area_names = {
        "NU_NOTA_CN": "Ciências da Natureza",
        "NU_NOTA_CH": "Ciências Humanas",
        "NU_NOTA_LC": "Linguagens",
        "NU_NOTA_MT": "Matemática",
        "NU_NOTA_REDACAO": "Redação",
    }

    quadro_rows = [
        "# Quadro resumido dos resultados",
        "",
        "| Área | Grupo acessível | Gasto municipal | Gasto municipal Especial | Gasto estadual | Gasto estadual Especial | Interações relevantes |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]

    for area, area_name in group_area_names.items():
        sig_interactions = models[
            (models["AREA"] == area)
            & models["TERMO"].str.startswith("GRUPO_ACESSIVEL:")
            & (models["SIGNIFICANTE_5PCT"] == True)
        ]["TERMO"].tolist()

        interaction_text = "nenhuma"
        if sig_interactions:
            labels = {
                "GRUPO_ACESSIVEL:GASTO_MUNICIPAL_Z": "municipal",
                "GRUPO_ACESSIVEL:GASTO_MUNICIPAL_ESPECIAL_Z": "municipal Especial",
                "GRUPO_ACESSIVEL:GASTO_ESTADUAL_Z": "estadual",
                "GRUPO_ACESSIVEL:GASTO_ESTADUAL_ESPECIAL_Z": "estadual Especial",
            }
            interaction_text = "; ".join(labels.get(t, t) for t in sig_interactions)

        quadro_rows.append(
            f"| {area_name} | "
            f"{coefficient_cell(area, 'GRUPO_ACESSIVEL')} | "
            f"{coefficient_cell(area, 'GASTO_MUNICIPAL_Z')} | "
            f"{coefficient_cell(area, 'GASTO_MUNICIPAL_ESPECIAL_Z')} | "
            f"{coefficient_cell(area, 'GASTO_ESTADUAL_Z')} | "
            f"{coefficient_cell(area, 'GASTO_ESTADUAL_ESPECIAL_Z')} | "
            f"{interaction_text} |"
        )

    results_md = "\n".join([
        "# Resultados finais — ENEM e gasto público municipal/estadual",
        "",
        "## Delimitação",
        "",
        "Os coeficientes abaixo são associações observacionais. Não representam efeitos causais de gasto público sobre notas.",
        "Os gastos são agregados por município ou UF de aplicação da prova e não medem recursos recebidos diretamente por participantes ou escolas.",
        "",
        coverage_text,
        "",
        areas_text,
        "## Síntese",
        "",
        "- O efeito principal do grupo acessível foi negativo nas cinco áreas.",
        "- O gasto municipal apresentou associação principal significativa em Matemática.",
        "- O gasto estadual apresentou associação principal em Ciências da Natureza.",
        "- O gasto estadual em Educação Especial apresentou associação significativa em Linguagens, Matemática e Redação.",
        "- O gasto municipal em Educação Especial não apresentou associação principal significativa neste modelo.",
        "- Interações com o grupo acessível foram significativas principalmente em Matemática.",
        "",
        "## Limitações",
        "",
        "- Município de aplicação da prova usado como aproximação territorial.",
        "- Ausência de vinculação individual do participante à escola estudada.",
        "- Categoria Braile/ledor pode reunir recursos diferentes entre edições.",
        "- Indicadores financeiros agregados podem refletir endogeneidade e fatores não observados.",
        "- Renda familiar não foi incluída na modelagem revisada.",
    ])

    quad_ro = "\n".join(quadro_rows)

    OUT_RESULTS_MD.write_text(results_md, encoding="utf-8")
    OUT_QUADRO_MD.write_text(quad_ro, encoding="utf-8")

    print("Resultados finais documentais preparados.")
    print(f"- {OUT_TABLE}")
    print(f"- {OUT_SUMMARY}")
    print(f"- {OUT_RESULTS_MD}")
    print(f"- {OUT_QUADRO_MD}")


if __name__ == "__main__":
    main()
