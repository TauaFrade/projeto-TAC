"""Revisao sistematica dos modelos integrados municipal-estaduais.

Entradas:
- data/processed/modelos_integrados_municipal_estadual.csv
- data/processed/modelos_integrados_municipal_estadual_diagnosticos.csv
- data/processed/enem_gastos_cobertura_combinada_ano.csv

Saidas:
- data/processed/revisao_modelos_resumo_por_termo.csv
- data/processed/revisao_modelos_resumo_por_area.csv
- data/processed/revisao_modelos_leitura_academica.csv
- data/processed/revisao_modelos_registro.txt
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT_DIR = Path("data/processed")
MODELS_PATH = OUT_DIR / "modelos_integrados_municipal_estadual.csv"
DIAG_PATH = OUT_DIR / "modelos_integrados_municipal_estadual_diagnosticos.csv"
COV_PATH = OUT_DIR / "enem_gastos_cobertura_combinada_ano.csv"

OUT_TERM = OUT_DIR / "revisao_modelos_resumo_por_termo.csv"
OUT_AREA = OUT_DIR / "revisao_modelos_resumo_por_area.csv"
OUT_TEXT = OUT_DIR / "revisao_modelos_leitura_academica.csv"
OUT_LOG = OUT_DIR / "revisao_modelos_registro.txt"


def term_family(term: str) -> str:
    if term == "GRUPO_ACESSIVEL":
        return "efeito_principal_grupo"
    if term.startswith("GRUPO_ACESSIVEL:"):
        return "interacao_grupo_gasto"
    if term.startswith("GASTO_"):
        return "efeito_principal_gasto"
    return "outro"


def effect_direction(coef: float) -> str:
    if coef > 0:
        return "positivo"
    if coef < 0:
        return "negativo"
    return "nulo"


def main() -> None:
    if not MODELS_PATH.exists():
        raise FileNotFoundError(f"Arquivo de modelos nao encontrado: {MODELS_PATH}")
    if not DIAG_PATH.exists():
        raise FileNotFoundError(f"Arquivo de diagnosticos nao encontrado: {DIAG_PATH}")

    coef = pd.read_csv(MODELS_PATH)
    diag = pd.read_csv(DIAG_PATH)

    coef["FAMILIA"] = coef["TERMO"].map(term_family)
    coef["DIRECAO"] = coef["COEFICIENTE"].map(effect_direction)

    term_summary = (
        coef.groupby(["FAMILIA", "TERMO"], as_index=False)
        .agg(
            N_AREAS=("AREA", "nunique"),
            AREAS_COM_EFEITO_POSITIVO=("DIRECAO", lambda s: int((s == "positivo").sum()) if False else int((coef.loc[s.index, "SIGNIFICANTE_5PCT"] & (coef.loc[s.index, "COEFICIENTE"] > 0)).sum())),
            AREAS_COM_EFEITO_NEGATIVO=("DIRECAO", lambda s: int((s == "negativo").sum()) if False else int((coef.loc[s.index, "SIGNIFICANTE_5PCT"] & (coef.loc[s.index, "COEFICIENTE"] < 0)).sum())),
            N_SIGNIFICANTES=("SIGNIFICANTE_5PCT", "sum"),
            MEDIA_COEFICIENTE=("COEFICIENTE", "mean"),
            MEDIANA_COEFICIENTE=("COEFICIENTE", "median"),
        )
    )

    term_summary["MEDIA_COEFICIENTE"] = term_summary["MEDIA_COEFICIENTE"].round(6)
    term_summary["MEDIANA_COEFICIENTE"] = term_summary["MEDIANA_COEFICIENTE"].round(6)

    area_summary = (
        coef.groupby(["AREA", "AREA_NOME"], as_index=False)
        .agg(
            N_TERMO=("TERMO", "nunique"),
            N_SIGNIFICANTES=("SIGNIFICANTE_5PCT", "sum"),
            N_INTERACOES_SIGNIFICANTES=("TERMO", lambda s: int((coef.loc[s.index, "SIGNIFICANTE_5PCT"] & coef.loc[s.index, "FAMILIA"].eq("interacao_grupo_gasto")).sum())),
        )
    )

    # Confirmacao da cobertura e qualidade da amostra para o registro academico.
    coverage = pd.read_csv(COV_PATH) if COV_PATH.exists() else pd.DataFrame()

    academic_rows = []
    for _, row in area_summary.iterrows():
        sub = coef[coef["AREA"] == row["AREA"]].copy()
        sig = sub[sub["SIGNIFICANTE_5PCT"]].copy()

        principal_group = sub[sub["TERMO"] == "GRUPO_ACESSIVEL"]
        if principal_group.empty:
            group_text = "grupo acessivel nao estimado"
        else:
            r = principal_group.iloc[0]
            group_text = (
                f"grupo acessivel associado a {r['COEFICIENTE']:.3f} pontos "
                f"na nota ({r['P_VALOR_FMT']})"
            )

        sig_text = "; ".join(
            f"{r['TERMO']}={r['COEFICIENTE']:.3f} ({r['P_VALOR_FMT']})"
            for _, r in sig.iterrows()
        )
        if not sig_text:
            sig_text = "nenhum termo adicional significativo a 5%"

        academic_rows.append({
            "AREA": row["AREA"],
            "AREA_NOME": row["AREA_NOME"],
            "N_TERMO": row["N_TERMO"],
            "N_SIGNIFICANTES": row["N_SIGNIFICANTES"],
            "N_INTERACOES_SIGNIFICANTES": row["N_INTERACOES_SIGNIFICANTES"],
            "EFEITO_GRUPO": group_text,
            "TERMOS_SIGNIFICANTES": sig_text,
            "LEITURA": "Requer interpretacao associativa; nao implica causalidade.",
        })

    academic = pd.DataFrame(academic_rows)

    term_summary.to_csv(OUT_TERM, index=False, encoding="utf-8-sig")
    area_summary.to_csv(OUT_AREA, index=False, encoding="utf-8-sig")
    academic.to_csv(OUT_TEXT, index=False, encoding="utf-8-sig")

    lines = [
        "REVISAO SISTEMATICA DOS MODELOS INTEGRADOS",
        "",
        "Base estatistica:",
        "- cinco modelos lineares, uma nota por modelo",
        "- grupo acessivel comparado ao grupo regular",
        "- gastos municipais e estaduais separados",
        "- Educação Especial separada em indicador municipal e estadual",
        "- controles: ano, UF e capital/interior",
        "- erros-padrao robustos clusterizados por municipio de prova",
        "",
        "Advertencia central:",
        "- toda associacao deve ser interpretada como observacional",
        "- gasto agregado nao mede recursos recebidos diretamente pelo participante",
        "- o municipio de prova e uma aproximacao territorial",
        "",
        "Resumo por area:",
    ]

    for _, r in academic.iterrows():
        lines.append(f"- {r['AREA_NOME']}: {r['EFEITO_GRUPO']}; {r['TERMOS_SIGNIFICANTES']}")

    if not coverage.empty:
        lines += ["", "Cobertura combinada municipal-estadual:"]
        for _, r in coverage.iterrows():
            lines.append(
                f"- ENEM {int(r['ANO'])}: {r['PCT_COMBINADO']:.3f}% com indicador municipal-estadual combinado; "
                f"{r['PCT_TRIENIO_COMBINADO']:.3f}% com trienio combinado completo"
            )

    OUT_LOG.write_text("\n".join(lines), encoding="utf-8")

    print("Revisao concluida.")
    print(f"- {OUT_TERM}")
    print(f"- {OUT_AREA}")
    print(f"- {OUT_TEXT}")
    print(f"- {OUT_LOG}")
    print("\nRegistro academico:")
    print(OUT_LOG.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
