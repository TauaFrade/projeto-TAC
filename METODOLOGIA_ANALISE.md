# Metodologia da análise — Desempenho no ENEM e gasto público em educação

## 1. Objetivo didático

Este projeto investiga se as notas do ENEM estão associadas ao gasto público em educação em contextos municipais e estaduais. O foco é comparar participantes identificados por provas adaptadas em Libras ou Braile/ledor com participantes de provas regulares, nas áreas de Ciências da Natureza, Ciências Humanas, Linguagens, Matemática e Redação.

A análise não afirma que gastar mais causou maior ou menor desempenho. Os indicadores financeiros são contextuais: representam o gasto agregado no território onde ocorreu a prova e não medem diretamente quanto foi destinado ao participante, à sua escola ou à sua necessidade específica.

## 2. Pergunta central

O desempenho dos participantes com provas acessíveis difere do desempenho dos participantes regulares, e essa diferença varia conforme:

1. o gasto municipal em educação;
2. o gasto municipal destinado à Educação Especial;
3. o gasto estadual em educação;
4. o gasto estadual destinado à Educação Especial;
5. ano do exame, UF e localização em capital ou interior.

## 3. Recortes e grupos

- **Grupo Libras:** participantes classificados pelo código dos cadernos de Libras, não pela cor da prova.
- **Grupo Braile/ledor:** participantes identificados por Braile ou Adaptada Ledor, conforme a edição.
- **Grupo regular:** participantes sem caderno especial selecionado.
- **Fora do recorte:** categorias de outro atendimento ficam fora da comparação principal.
- Libras e Braile/ledor são reunidos no modelo principal. Análises separadas são tratadas como robustez.

A classificação considera `CO_PROVA_*` em todas as áreas disponíveis, pois códigos e cores variam entre 2023, 2024 e 2025.

## 4. Dados utilizados

### ENEM 2023–2025

Microdados utilizados para:

- notas válidas por área;
- município e UF de aplicação;
- presença das provas em cada área;
- classificação dos participantes por tipo de caderno;
- identificação de capital/interior.

Notas ausentes não são convertidas em zero: cada área usa apenas registros com nota válida.

A renda familiar foi excluída da modelagem final porque não pode ser vinculada corretamente às notas de 2024 e 2025.

### FINBRA municipal e estadual

A despesa principal é **Despesas Liquidadas** em cinco subfunções:

- `12.361` — Ensino Fundamental;
- `12.362` — Ensino Médio;
- `12.365` — Educação Infantil;
- `12.367` — Educação Especial;
- `12.368` — Educação Básica.

`12.122` — Administração Geral fica fora do indicador principal.

A despesa geral é construída pela soma das subfunções disponíveis. A subfunção `12.367` também é mantida como indicador separado.

Não é somada a conta agregada `12 - Educação` às subfunções, para evitar dupla contagem.

### Censo Escolar

O Censo fornece o denominador das matrículas públicas:

- município: dependência municipal (`TP_DEPENDENCIA = 3`);
- Estado: dependência estadual (`TP_DEPENDENCIA = 2`);
- escolas públicas em situação ativa (`TP_SITUACAO_FUNCIONAMENTO = 1`).

Variáveis principais: `QT_MAT_BAS`, `QT_MAT_FUND`, `QT_MAT_MED`, `QT_MAT_INF` e `QT_MAT_ESP`.

### IPCA

O número-índice médio mensal do IPCA é usado para levar gastos anuais a uma base monetária comum, com ano-base de 2024 nos scripts atuais.

## 5. Construção dos indicadores

### Janela trienal

Para cada edição do ENEM:

- ENEM 2023: despesas de 2020–2022;
- ENEM 2024: despesas de 2021–2023;
- ENEM 2025: despesas de 2022–2024.

Para cada ano:

$$Gasto_{real,município,ano}
= \frac{Despesa\ liquidada\ real}{Matrículas\ públicas\ municipais}$$

Depois é calculada a média dos três anos:

$$Gasto_{trienal} = \frac{Gasto_{ano_1}+Gasto_{ano_2}+Gasto_{ano_3}}{3}$$

O mesmo procedimento é aplicado aos indicadores estaduais, com agregação por UF.

A Educação Especial municipal é calculada com gasto municipal em `12.367` dividido por `QT_MAT_ESP` municipal. A Educação Especial estadual usa gasto estadual em `12.367` dividido por `QT_MAT_ESP` estadual.

## 6. Integração territorial

- ENEM × municipal: ano do exame + código IBGE do município de prova.
- ENEM × estadual: ano do exame + UF de prova.
- O município de prova é uma aproximação: pode diferir do município de residência ou estudo.
- Municípios e Estados permanecem em indicadores separados e não são somados automaticamente no modelo principal.

## 7. Estatística aplicada

### Descritiva preliminar

A etapa descritiva usa:

- contagem de participantes;
- distribuição por grupo e ano;
- média, mediana e quantis das notas;
- cobertura por município e UF;
- comparação de notas por capital/interior.

### Welch e tamanho de efeito

Nas análises preliminares, as médias dos grupos acessível e regular são comparadas pelo teste t de Welch, que não exige variâncias iguais. O tamanho de efeito usado é Hedges g.

Essa etapa descreve diferenças; não controla UF, ano ou outras características.

### Modelos lineares integrados

O modelo principal utiliza regressão linear OLS para cada nota:

$$Nota_i = \beta_0 + \beta_1 Acessivel_i + \beta_2 GastoMunicipal_i + \beta_3 GastoEspecialMunicipal_i + \beta_4 GastoEstadual_i + \beta_5 GastoEspecialEstadual_i + \beta_6(Acessivel_i \times GastoMunicipal_i) + \beta_7(Acessivel_i \times GastoEspecialMunicipal_i) + \beta_8(Acessivel_i \times GastoEstadual_i) + \beta_9(Acessivel_i \times GastoEspecialEstadual_i) + Ano_i + UF_i + CapitalInterior_i + \epsilon_i$$

Os quatro gastos são padronizados em desvios-padrão antes da modelagem. Assim, coeficientes representam associação aproximada com um desvio-padrão a mais no indicador, mantendo comparabilidade entre unidades monetárias e esferas.

Controles:

- ano do ENEM;
- UF;
- capital/interior;
- grupo acessível.

### Erros-padrão clusterizados

Os participantes dentro do mesmo município compartilham indicadores financeiros territoriais. Por isso, os erros-padrão são clusterizados pelo município de prova no modelo principal.

Como os indicadores estaduais variam por UF, os scripts também preservam UF como controle. Caso a análise estadual isolada seja feita em robustez, o modelo pode exigir cluster por UF.

### Interpretação

O termo principal de gasto representa associação entre gasto e nota no grupo regular ou no contraste definido pela interação.

O termo `grupo acessível × gasto` indica se a associação com gasto é diferente para participantes identificados com provas acessíveis.

O sinal, o intervalo de confiança e o p-valor devem ser lidos juntos. Significância estatística não implica importância prática ou causalidade.

## 8. Validação e robustez

Os scripts prévios e as etapas implementadas permitem:

- comparar gasto em nível absoluto e em log;
- comparar triênio completo e cobertura parcial;
- repetir modelos por 2023, 2024 e 2025;
- comparar Libras e Braile/ledor separadamente;
- comparar gasto municipal e estadual em especificações separadas;
- verificar outliers e cobertura;
- verificar rank da matriz e evitar coeficientes de modelos singulares;
- verificar cobertura por ano e por grupo.

Uma especificação com matriz singular não é apresentada como resultado final.

## 9. Limitações

- Os dados financeiros são agregados por território, não por participante ou escola.
- Município de aplicação não corresponde necessariamente a residência ou estudo.
- `Braile/ledor` reúne diferentes recursos em algumas edições.
- Em 2024 e 2025 não há vínculo individual entre participantes e resultados após a separação das bases.
- A ausência de renda é uma limitação, não uma substituição por proxy.
- O gasto estadual pode representar responsabilidade de ensino médio de modo diferente do gasto municipal.
- Endogenidade, seleção e fatores não observados podem produzir associação sem causalidade.

## 10. Scripts em `src/`

| Script | Objetivo em alto nível |
|---|---|
| `01_enem_to_parquet.py` | Ler ENEM, selecionar colunas e converter dados anualizados para Parquet, classificando os grupos pelos códigos dos cadernos. |
| `02_build_base_preliminar.py` | Consolidar os três anos ENEM e criar recortes `acessivel`, `regular` e `fora_recorte`. |
| `03_fase2_descritivas.py` | Gerar contagens, estatísticas das notas e lacunas acessível x regular. |
| `04_fase3_welch_efeito.py` | Aplicar Welch e Hedges g nas comparações preliminares. |
| `05_fase4_territorial.py` | Analisar diferença entre capital/interior e participação por UF. |
| `06_fase5_mapas_uf.py` | Gerar tabelas cartográficas offline e mapas por UF. |
| `07_fase5_mapas_malha_ibge.py` | Gerar mapas oficiais usando malhas geográficas do IBGE. |
| `08_auditoria_cobertura_finbra_censo_ipca.py` | Auditar município-ano entre FINBRA, Censo e IPCA. |
| `09_indicador_gasto_trienal.py` | Calcular gasto municipal real por matrícula e média trienal. |
| `10_merge_enem_gasto_trienal.py` | Integrar gasto municipal trienal à base ENEM por ano e município de prova. |
| `11_modelos_enem_gasto_trienal.py` | Ajustar modelos municipais preliminares nas cinco áreas. |
| `12_auditoria_finbra_estadual.py` | Auditar FINBRA estadual por UF e ano. |
| `13_indicador_gasto_estadual_trienal.py` | Calcular gasto estadual geral e de Educação Especial por matrícula e médio trienal. |
| `14_merge_enem_gastos_municipal_estadual.py` | Integrar gasto municipal e estadual à base ENEM. |
| `15_modelos_integrados_municipal_estadual.py` | Ajustar os modelos finais integrados nas cinco áreas. |
| `16_indicador_gasto_municipal_especial_trienal.py` | Separar o indicador municipal de Educação Especial. |
| `17_revisao_modelos_integrados.py` | Consolidar coeficientes, significância e leitura acadêmica. |
| `18_robustez_modelos_integrados.py` | Executar robustez por esfera, ano e modalidade. |
| `19_resultados_finais.py` | Consolidar os modelos já validados em tabelas e textos finais, sem ajustar modelos novamente. |

## 11. Fluxo objetivo

```text
ENEM + FINBRA municipal + FINBRA estadual + Censo + IPCA
            ↓
Auditoria e tratamento
            ↓
Gasto real por matrícula
            ↓
Média trienal por município/UF
            ↓
Integração territorial ao ENEM
            ↓
Comparações descritivas e inferenciais
            ↓
Revisão e robustez
            ↓
Resultados associativos e limitações
```

## 12. Síntese para redação

O estudo não usa renda familiar na versão revisada. A contribuição principal é integrar desempenho adaptado x regular com gasto público municipal e estadual em educação geral e Educação Especial, mantendo município e Estado como esferas separadas e interpretando tudo como associação observacional.
