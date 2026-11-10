# Desempenho de participantes do ENEM em provas em Libras e Braile/ledor: uma análise socioeconômica e territorial (2023–2025)

Repositório de código e documentação do artigo desenvolvido na disciplina de mineração de dados educacionais.

**Autores:** Ricardo de Carvalho Nabuco, Tauã Valentim de Albuquerque Martins Frade, Jefte Augusto Gomes Batista

> **Status:** em andamento. Metodologia definida; tratamento dos dados em curso; resultados ainda não disponíveis.

---

## 1. Questão de pesquisa

Como o desempenho dos participantes que realizaram provas em **Libras** ou **Braile/ledor** se diferencia do desempenho dos demais participantes do ENEM entre 2023 e 2025, e como essas diferenças se associam à renda familiar, à localização geográfica e às despesas públicas municipais em educação?

O estudo é **observacional**: os resultados são interpretados como **associações**, sem inferência causal. O recorte não abrange todas as pessoas com deficiência nem todas as formas de atendimento especializado do ENEM.

## 2. Dados

| Base | Fonte | Uso | Local no projeto |
|---|---|---|---|
| Microdados do ENEM 2023, 2024 e 2025 | Inep | Notas, renda familiar (Q006 em 2023; Q007 em 2024 e 2025), município/UF de aplicação, código do caderno | `data/raw/enem/<ano>/` |
| SIOPE — despesas por função/subfunção | FNDE (Dados Abertos SIOPE) | Despesa liquidada em Educação (função) e Educação Especial (subfunção 367), exercícios **2020–2024** | `data/raw/siope/<ano>/` |
| Censo Escolar 2020–2024 | Inep | Matrículas (denominador da despesa por matrícula) | `data/raw/censo/<ano>/` |
| IPCA | IBGE | Correção monetária das despesas | `data/raw/ipca/` |

**Os dados brutos não são versionados** (ver `.gitignore`). Baixe cada base na fonte oficial e coloque na pasta indicada.

### Identificação do grupo de interesse

A prova é identificada pelo **código do caderno (`CO_PROVA_*`)**, não só pela cor: cada caderno tem um código diferente em cada área (CN, CH, LC, MT), conforme os dicionários do Inep. As tabelas completas estão em `src/01_enem_to_parquet.py`.

| Grupo | 2023 | 2024 | 2025 |
|---|---|---|---|
| Libras | Verde – Videoprova Libras | Roxa – Videoprova Libras (inclui ampliada e superampliada) | Roxo – Videoprova Libras |
| Braile/ledor | Laranja – Braile e Laranja – Adaptada Ledor | Laranja – Adaptada Ledor (inclui reaplicação); **não há código de Braile** | Laranja – Adaptada Ledor; **não há código de Braile** |
| Outro atendimento (fora dos dois grupos) | Rosa – Ampliada/Superampliada | Verde – Ampliada/Superampliada (inclui reaplicação) | Laranja – Ampliada/Superampliada, Atendimento Especializado e versões BAM2 |

Atenção: a cor sozinha não identifica a modalidade. Em 2024 e 2025 há cadernos regulares da cor verde, e em 2025 a cor laranja inclui Ampliada, Superampliada e Atendimento Especializado. O grupo é definido por qualquer `CO_PROVA_*` na lista, em qualquer área.

Grupo de interesse: Libras ou Braile/ledor (inicialmente reunidos). Grupo de comparação: participantes regulares (a categoria "outro atendimento" fica de fora).

### Janela das despesas

Média trienal da despesa por matrícula, corrigida pela inflação, nos três anos anteriores a cada edição:

| Edição do ENEM | Anos de despesa |
|---|---|
| 2023 | 2020–2022 |
| 2024 | 2021–2023 |
| 2025 | 2022–2024 |

Cada despesa anual é deflacionada e dividida pelas matrículas do respectivo ano; depois calcula-se a média dos três valores.

## 3. Métodos

1. **Descritiva:** n por grupo, ausentes, média, mediana e quantis por edição e área.
2. **Comparação:** teste t de Welch + tamanho de efeito (d de Cohen) com IC, por área e edição.
3. **Regressão linear (5 modelos, um por nota):** nota ~ grupo + renda familiar (Q006/Q007) + UF + capital/interior + edição; depois, separadamente, indicadores de despesa por matrícula (geral e subfunção 367) e interação grupo × despesa. Erros-padrão robustos agrupados por município.
4. **Diagnósticos:** colinearidade (VIF), observações influentes, cobertura dos dados financeiros.

Decisões já tomadas: registros sem nota válida são excluídos apenas da análise correspondente (nunca tratados como zero); o município de aplicação é usado como aproximação territorial; se não houver indicador por matrícula consistente, a limitação é documentada (sem substituir por despesa total).

## 4. Estrutura do repositório

```
.
├── data/
│   ├── raw/          # dados originais, imutáveis (fora do Git)
│   ├── interim/      # etapas intermediárias em Parquet (fora do Git)
│   └── processed/    # base analítica final (fora do Git)
├── notebooks/        # exploração
├── src/              # scripts reutilizáveis (leitura, limpeza, merge, modelos)
├── reports/          # figuras, tabelas e texto do artigo
├── README.md
├── requirements.txt
└── .gitignore
```

## 5. Como reproduzir

```bash
git clone <url-do-repositorio>
cd <nome-do-repositorio>
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Depois, coloque os dados brutos conforme a seção 2 e execute os scripts de `src/` na ordem:

1. `src/01_enem_to_parquet.py` — lê os CSV do ENEM, seleciona colunas, salva Parquet
2. `src/02_flag_grupos.py` — mapeia códigos de caderno → cor → grupo
3. `src/03_siope_download.py` — baixa o SIOPE por ano/UF
4. `src/04_indicadores_despesa.py` — deflaciona, calcula despesa por matrícula e média trienal
5. `src/05_merge.py` — integra ENEM × SIOPE por município e edição
6. `src/06_analise.py` — descritivas, Welch e regressões

*(Os scripts serão adicionados conforme o desenvolvimento.)*

## 6. Plano de trabalho

- [x] Definição da metodologia
- [ ] Ambiente, estrutura de pastas e repositório
- [ ] Download e conversão dos microdados do ENEM (2023–2025)
- [ ] Mapeamento código do caderno → cor → grupo, validado por edição
- [ ] Estatísticas descritivas e teste de Welch por área e edição
- [ ] Regressão apenas com renda, UF, capital/interior e edição
- [ ] Download do SIOPE (2020–2024) e validação das colunas
- [ ] Matrículas do Censo Escolar e definição dos denominadores
- [ ] Indicadores trienais de despesa por matrícula
- [ ] Integração ENEM × SIOPE e modelos com interação
- [ ] Redação dos resultados e da discussão

## 7. Limitações

Em 2024 e 2025 as bases de participantes e de resultados não podem ser relacionadas (nota do dicionário do Inep), então a renda familiar por participante só está disponível junto às notas em 2023; a categoria Braile/ledor só inclui Braile em 2023. Indicadores financeiros são municipais e não medem recursos por escola ou indivíduo; o município de aplicação da prova pode diferir do de residência/estudo; a categoria Braile/ledor pode reunir recursos distintos; a associação entre despesa e nota pode refletir condições socioeconômicas, necessidades locais e lacunas de cobertura das bases.

## 8. Referências principais

Ver `reports/` (referências do artigo).