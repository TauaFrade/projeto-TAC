# ENEM 2023–2025 — Acessibilidade e Gasto Público em Educação

## Sobre o projeto

Este projeto analisa a relação entre o desempenho de participantes do ENEM 2023–2025 em provas adaptadas em Libras ou Braile/ledor e indicadores territoriais de gasto público em educação nas esferas municipal e estadual.

O modelo é observacional. Os resultados devem ser interpretados como associações, não como efeitos causais.

A renda familiar não integra a modelagem final revisada.

## Fonte dos dados

### 1. ENEM

Baixar os microdados oficiais do INEP em:

- `data/raw/enem/2023/`
- `data/raw/enem/2024/`
- `data/raw/enem/2025/`

Arquivos esperados:

- 2023: um arquivo CSV cujo nome contenha `MICRODADOS`;
- 2024 e 2025: um CSV contendo `PARTICIPANTES` e outro contendo `RESULTADOS`.

A etapa atual usa principalmente os dados de resultados dos três anos.

### 2. FINBRA municipal

Baixar/exportar o Anexo I-E — Despesas por Função para Municípios em:

- `data/raw/finbra/2020/finbra_municipios.csv`
- `data/raw/finbra/2021/finbra_municipios.csv`
- `data/raw/finbra/2022/finbra_municipios.csv`
- `data/raw/finbra/2023/finbra_municipios.csv`
- `data/raw/finbra/2024/finbra_municipios.csv`

Campos necessários:

- `Instituição`
- `Cod.IBGE`
- `UF`
- `População`
- `Coluna`
- `Conta`
- `Identificador da Conta`
- `Valor`

O recorte principal usa `Despesas Liquidadas` e as subfunções 12.361, 12.362, 12.365, 12.367 e 12.368.

### 3. FINBRA estadual

Baixar/exportar o Anexo I-E — Despesas por Função para Estados/DF em:

- `data/raw/finbra/2020/finbra_estados.csv`
- `data/raw/finbra/2021/finbra_estados.csv`
- `data/raw/finbra/2022/finbra_estados.csv`
- `data/raw/finbra/2023/finbra_estados.csv`
- `data/raw/finbra/2024/finbra_estados.csv`

A chave estadual usa `Cod.IBGE` como código de UF de dois dígitos ou `UF` como sigla.

### 4. Censo Escolar

Colocar os microdados em:

- `data/raw/censo_escolar/2020/`
- `data/raw/censo_escolar/2021/`
- `data/raw/censo_escolar/2022/`
- `data/raw/censo_escolar/2023/`
- `data/raw/censo_escolar/2024/`

Arquivos CSV principais:

- `microdados_ed_basica_2020.CSV`
- `microdados_ed_basica_2021.csv`
- `microdados_ed_basica_2022.csv`
- `microdados_ed_basica_2023.csv`
- `microdados_ed_basica_2024.csv`

O arquivo de 2022 pode estar em subpasta extraída.

Variáveis utilizadas:

- `NU_ANO_CENSO`
- `CO_UF`
- `CO_MUNICIPIO`
- `TP_DEPENDENCIA`
- `TP_SITUACAO_FUNCIONAMENTO`
- `QT_MAT_BAS`
- `QT_MAT_FUND`
- `QT_MAT_MED`
- `QT_MAT_INF`
- `QT_MAT_ESP`

O dicionário XLSX não é necessário para a execução dos scripts atuais, mas pode ser mantido em `data/raw/censo_escolar/<ano>/` para documentação.

### 5. IPCA

Colocar os JSON oficiais em:

- `data/raw/IPCA/IPCA_indice_geral.json`
- `data/raw/IPCA/IPCA_numero_indice.json`

Os scripts utilizam `IPCA_numero_indice.json` para deflação.

## Estrutura de pastas

```text
projeto-TAC/
├── data/
│   ├── raw/
│   │   ├── enem/
│   │   │   ├── 2023/
│   │   │   ├── 2024/
│   │   │   └── 2025/
│   │   ├── finbra/
│   │   │   ├── 2020/
│   │   │   │   ├── finbra_municipios.csv
│   │   │   │   └── finbra_estados.csv
│   │   │   ├── 2021/
│   │   │   ├── 2022/
│   │   │   ├── 2023/
│   │   │   └── 2024/
│   │   ├── censo_escolar/
│   │   │   ├── 2020/
│   │   │   ├── 2021/
│   │   │   ├── 2022/
│   │   │   ├── 2023/
│   │   │   └── 2024/
│   │   └── IPCA/
│   ├── interim/
│   └── processed/
├── reports/
├── src/
├── requirements.txt
├── METODOLOGIA_ANALISE.md
├── PLANO_DE_ACAO_ANALITICA.md
└── README.md
```

## Ambiente no Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Execução completa

Executar na raiz do projeto, na ordem indicada:

```powershell
python .\src\01_enem_to_parquet.py
python .\src\02_build_base_preliminar.py
python .\src\03_fase2_descritivas.py
python .\src\04_fase3_welch_efeito.py
python .\src\05_fase4_territorial.py
python .\src\06_fase5_mapas_uf.py
python .\src\07_fase5_mapas_malha_ibge.py
python .\src\08_auditoria_cobertura_finbra_censo_ipca.py
python .\src\09_indicador_gasto_trienal.py
python .\src\10_merge_enem_gasto_trienal.py
python .\src\12_auditoria_finbra_estadual.py
python .\src\13_indicador_gasto_estadual_trienal.py
python .\src\16_indicador_gasto_municipal_especial_trienal.py
python .\src\14_merge_enem_gastos_municipal_estadual.py
python .\src\11_modelos_enem_gasto_trienal.py
python .\src\15_modelos_integrados_municipal_estadual.py
python .\src\17_revisao_modelos_integrados.py
python .\src\18_robustez_modelos_integrados.py
python .\src\19_resultados_finais.py
```

Observação: o script `18_robustez_modelos_integrados.py` pode ser pesado e demorará conforme CPU e memória. O script principal integrado é `15_modelos_integrados_municipal_estadual.py`.

## Fluxo dos dados

```text
microdados ENEM
+ FINBRA municipal
+ FINBRA estadual
+ Censo Escolar
+ IPCA
        ↓
conversão e auditoria
        ↓
gasto real por matrícula
        ↓
média trienal municipal/estadual
        ↓
integração por município/UF de aplicação
        ↓
base final + modelos + revisão
```

## Principais scripts

### ENEM e análise preliminar

- `01_enem_to_parquet.py`: leitura e conversão dos microdados.
- `02_build_base_preliminar.py`: consolidação de 2023–2025.
- `03_fase2_descritivas.py`: contagens e estatísticas descritivas.
- `04_fase3_welch_efeito.py`: Welch e Hedges g.
- `05_fase4_territorial.py`: territorial e capital/interior.
- `06_fase5_mapas_uf.py`: cartogramas offline.
- `07_fase5_mapas_malha_ibge.py`: malhas oficiais IBGE.

### Cobertura e indicadores

- `08_auditoria_cobertura_finbra_censo_ipca.py`: auditoria municipal.
- `09_indicador_gasto_trienal.py`: indicador municipal geral.
- `10_merge_enem_gasto_trienal.py`: integração municipal ao ENEM.
- `12_auditoria_finbra_estadual.py`: auditoria estadual.
- `13_indicador_gasto_estadual_trienal.py`: indicadores estaduais gerais/especiais.
- `16_indicador_gasto_municipal_especial_trienal.py`: indicador municipal de Educação Especial.
- `14_merge_enem_gastos_municipal_estadual.py`: integração final municipal/estadual.

### Modelos e revisão

- `11_modelos_enem_gasto_trienal.py`: modelo municipal preliminar.
- `15_modelos_integrados_municipal_estadual.py`: modelos finais integrados.
- `17_revisao_modelos_integrados.py`: consolidação dos resultados.
- `18_robustez_modelos_integrados.py`: robustez por ano e modalidade.

## Principais saídas

- `data/processed/enem_2023_2025_com_gastos_municipal_estadual.parquet`
- `data/processed/modelos_integrados_municipal_estadual.csv`
- `data/processed/modelos_integrados_municipal_estadual_diagnosticos.csv`
- `data/processed/revisao_modelos_*`
- `data/processed/robustez_modelos_integrados.csv`
- `data/processed/robustez_modelos_resumo.csv`

## Limitações

- `municipio de prova` é aproximação territorial.
- gasto agregado não representa recurso individual recebido pela pessoa participante.
- Libras, Braile e ledor podem reunir modalidades de recursos diferentes entre anos.
- os modelos são associativos e não causais.
- Em 2024 e 2025 os microdados não permitem ligar individualmente participantes e resultados.
- renda familiar não está incluída na modelagem revisada.

## Documentação complementar

- `METODOLOGIA_ANALISE.md`: metodologia estatística e conceitual completa.
- `PLANO_DE_ACAO_ANALITICA.md`: plano operacional e decisões.

Os pacotes relevantes incluem `pandas`, `pyarrow`, `numpy`, `scipy`, `statsmodels`, `matplotlib` e dependências de notebook.
