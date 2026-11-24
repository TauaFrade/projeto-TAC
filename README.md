# Desempenho no ENEM de participantes de provas acessíveis

Este repositório contém os dados processados, scripts e documentação usados no artigo sobre o desempenho de participantes do ENEM em provas de Libras e Braille/ledor, comparados a participantes das provas regulares. A análise utiliza as edições de 2023, 2024 e 2025 e integra gastos públicos municipais e estaduais, Censo Escolar e IPCA.

O estudo é observacional. Os resultados representam associações e não efeitos causais.

## Objetivo

Comparar o desempenho dos grupos acessível e regular nas cinco áreas do ENEM e verificar se a diferença entre eles se associa aos gastos públicos em educação geral e em Educação Especial nas esferas municipal e estadual.

## Estrutura do projeto

```text
projeto-TAC/
├── data/
│   ├── raw/       # dados brutos; vários são mantidos compactados
│   ├── interim/   # arquivos intermediários gerados pelo pipeline
│   └── processed/ # bases finais, tabelas e diagnósticos
├── reports/       # mapas, tabelas, gráficos e relatórios em Markdown
├── src/           # scripts numerados do pipeline
├── template-latex/# estilo e arquivos do template SBC
├── introducao_trabalhos_relacionados.tex
├── requirements.txt
└── README.md
```

Os dados principais ficam em:

```text
data/raw/enem/<ano>/
data/raw/finbra/<ano>/
data/raw/censo_escolar/<ano>/
data/raw/IPCA/
```

## Dados brutos compactados

Os dados brutos não devem ser modificados. Quando estiverem disponíveis como arquivos ZIP, extraia o conteúdo na própria pasta do ano correspondente.

Exemplos:

```text
data/raw/enem/2023/microdados_enem_2023.zip
data/raw/enem/2024/microdados_enem_2024.zip
data/raw/enem/2025/microdados_enem_2025.zip
data/raw/censo_escolar/2020/microdados_censo_escolar_2020.zip
data/raw/censo_escolar/2021/microdados_censo_escolar_2021.zip
data/raw/censo_escolar/2022/microdados_censo_escolar_2022.zip
data/raw/censo_escolar/2023/microdados_censo_escolar_2023.zip
data/raw/censo_escolar/2024/microdados_censo_escolar_2024.zip
```

No Windows, os arquivos podem ser extraídos pelo Explorador de Arquivos. Também é possível usar PowerShell:

```powershell
Expand-Archive -Path .\data\raw\enem\2023\microdados_enem_2023.zip -DestinationPath .\data\raw\enem\2023 -Force
Expand-Archive -Path .\data\raw\enem\2024\microdados_enem_2024.zip -DestinationPath .\data\raw\enem\2024 -Force
Expand-Archive -Path .\data\raw\enem\2025\microdados_enem_2025.zip -DestinationPath .\data\raw\enem\2025 -Force
```

Repita a extração para os ZIP do Censo Escolar e para os arquivos FINBRA compactados. O resultado deve conter os CSV utilizados pelos scripts.

## Arquivos esperados

### ENEM

No diretório de cada ano:

- 2023: `MICRODADOS_ENEM_2023.csv`;
- 2024: `PARTICIPANTES_2024.csv` e `RESULTADOS_2024.csv`;
- 2025: `PARTICIPANTES_2025.csv` e `RESULTADOS_2025.csv`.

A identificação acessível é feita pelos códigos dos cadernos de prova, não pela cor.

### FINBRA

Em `data/raw/finbra/<ano>/` devem existir:

- `finbra_municipios.csv`;
- `finbra_estados.csv`.

Os scripts utilizam a coluna `Despesas Liquidadas` e as subfunções 12.361, 12.362, 12.365, 12.367 e 12.368.

### Censo Escolar

Em `data/raw/censo_escolar/<ano>/` devem existir os arquivos CSV:

- `microdados_ed_basica_2020.CSV`;
- `microdados_ed_basica_2021.csv`;
- `microdados_ed_basica_2022.csv`;
- `microdados_ed_basica_2023.csv`;
- `microdados_ed_basica_2024.csv`.

### IPCA

Em `data/raw/IPCA/`:

- `IPCA_indice_geral.json`;
- `IPCA_numero_indice.json`.

A deflação utiliza `IPCA_numero_indice.json`, com ano-base 2024.

## Configuração do ambiente

Requisitos: Python 3.10 ou superior no Windows.

```powershell
cd C:\caminho\projeto-TAC
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

O projeto utiliza principalmente pandas, pyarrow, numpy, scipy, statsmodels, matplotlib e os pacotes auxiliares listados em `requirements.txt`.

## Replicação da análise

Execute os comandos a partir da pasta raiz do projeto:

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

O script `18_robustez_modelos_integrados.py` é opcional para o fluxo principal e pode exigir mais tempo e memória.

## Principais scripts

- `01` a `07`: conversão dos microdados, base preliminar, estatísticas, testes e mapas territoriais.
- `08` a `10`: auditoria municipal, gasto real por matrícula e integração municipal ao ENEM.
- `12` a `14`: auditoria estadual, gasto estadual trienal e integração municipal-estadual.
- `16`: indicador municipal separado de Educação Especial.
- `11` e `15`: modelos municipal preliminar e modelos integrados finais.
- `17`: revisão dos coeficientes e resultados integrados.
- `18`: análises de robustez.
- `19`: consolidação dos resultados finais.

## Principais saídas

- `data/processed/enem_2023_2025.parquet`: base consolidada preliminar;
- `data/processed/enem_2023_2025_com_gastos_municipal_estadual.parquet`: base integrada;
- `data/processed/modelos_integrados_municipal_estadual.csv`;
- `data/processed/modelos_integrados_municipal_estadual_diagnosticos.csv`;
- `data/processed/revisao_modelos_*.csv`;
- `data/processed/resultados_finais_*.csv`;
- `reports/RESULTADOS_FINAIS.md`;
- `reports/QUADRO_RESUMO_RESULTADOS.md`.

Os nomes exatos podem variar conforme arquivos já gerados pelo pipeline.

## Fluxo resumido

```text
Microdados ENEM
+ FINBRA municipal
+ FINBRA estadual
+ Censo Escolar
+ IPCA
        ↓
Conversão e auditoria
        ↓
Gasto real por matrícula
        ↓
Média trienal municipal e estadual
        ↓
Integração ao município/UF de aplicação
        ↓
Estatísticas, modelos e relatórios
```

## Limitações principais

- O município de aplicação é uma aproximação do território de residência ou estudo.
- Gastos agregados não representam recursos efetivamente destinados a uma pessoa ou escola.
- A classificação Libras/Braille-ledor identifica a modalidade aplicada e não o diagnóstico individual.
- A renda familiar não integra a modelagem revisada.
- Em 2024 e 2025 não é possível ligar individualmente participantes e resultados.
- Os modelos são associativos e não causais.

## Documentação complementar

- `METODOLOGIA_ANALISE.md`: detalhes da metodologia;
- `PLANO_DE_ACAO_ANALITICA.md`: planejamento e decisões operacionais;
- `introducao_trabalhos_relacionados.tex`: versão em LaTeX do artigo;
- `reports/RESULTADOS_FINAIS.md`: consolidação dos resultados finais.