
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


# =========================================================
# CONFIGURAÇÃO
# =========================================================

ROOT = Path(__file__).resolve().parent

CAMINHO_DADOS = (
    ROOT
    / "data"
    / "processed"
    / "indicadores_financeiros_2021_2023.csv"
)

st.set_page_config(
    page_title="Análise Financeira — CVM",
    page_icon="📊",
    layout="wide",
)


# =========================================================
# CARREGAMENTO DOS DADOS
# =========================================================

@st.cache_data(ttl=3600)
def carregar_dados():
    if not CAMINHO_DADOS.exists():
        raise FileNotFoundError(
            "Arquivo de indicadores não encontrado. "
            "Execute primeiro o script 09_calcular_indicadores.py."
        )

    df = pd.read_csv(
        CAMINHO_DADOS,
        sep=";",
        encoding="utf-8-sig",
    )

    colunas_numericas = [
        "ANO",
        "receita_liquida",
        "lucro_liquido",
        "patrimonio_liquido",
        "roe_pct",
        "margem_bruta_pct",
        "margem_ebit_pct",
        "margem_liquida_pct",
        "liquidez_corrente",
        "divida_liquida",
        "divida_bruta",
    ]

    for coluna in colunas_numericas:
        if coluna in df.columns:
            df[coluna] = pd.to_numeric(
                df[coluna],
                errors="coerce",
            )

    df["ANO"] = df["ANO"].astype(int)
    df["TICKER"] = df["TICKER"].astype(str)

    df["SETOR_ANALISE"] = (
        df["SETOR_ANALISE"].fillna("Não classificado")
    )

    return df


try:
    dados = carregar_dados()

except Exception as erro:
    st.error(f"Não foi possível carregar os dados: {erro}")
    st.stop()


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================


def formatar_reais_bilhoes(valor):
    if pd.isna(valor):
        return "—"

    valor_bilhoes = valor / 1_000_000_000

    if abs(valor_bilhoes) >= 1000:
        texto = f"R$ {valor_bilhoes / 1000:,.2f} tri"
    else:
        texto = f"R$ {valor_bilhoes:,.2f} bi"

    return texto.replace(",", "X").replace(".", ",").replace("X", ".")



def formatar_percentual(valor):
    if pd.isna(valor):
        return "—"

    return f"{valor:.2f}%".replace(".", ",")


def formatar_variacao_percentual(atual, anterior):
    if pd.isna(atual) or pd.isna(anterior) or anterior == 0:
        return None

    variacao = ((atual / anterior) - 1) * 100
    return f"{variacao:+.2f}%".replace(".", ",")


def formatar_variacao_reais(atual, anterior):
    if pd.isna(atual) or pd.isna(anterior):
        return None

    diferenca = atual - anterior

    sinal = "+" if diferenca >= 0 else "-"

    return f"{sinal}{formatar_reais_bilhoes(abs(diferenca))}"


# =========================================================
# CABEÇALHO
# =========================================================

st.title("📊 Análise Fundamentalista — Empresas da B3")

st.markdown(
    """
    **Análise das demonstrações financeiras de 2021 a 2023**

    Dados extraídos das Demonstrações Financeiras Padronizadas
    (DFP) disponibilizadas pela Comissão de Valores Mobiliários (CVM).
    """
)

st.divider()


# =========================================================
# FILTROS
# =========================================================

with st.sidebar:
    st.header("Filtros")

    if st.button("Limpar filtros", width="stretch"):
        for chave in ["f_anos", "f_tickers", "f_setores"]:
            st.session_state.pop(chave, None)

        st.rerun()

    anos_disponiveis = sorted(dados["ANO"].unique().tolist())
    tickers_disponiveis = sorted(dados["TICKER"].unique().tolist())
    setores_disponiveis = sorted(
        dados["SETOR_ANALISE"].dropna().unique().tolist()
    )

    anos_selecionados = st.multiselect(
        "Exercício",
        options=anos_disponiveis,
        default=anos_disponiveis,
        key="f_anos",
    )

    tickers_selecionados = st.multiselect(
        "Empresas",
        options=tickers_disponiveis,
        default=tickers_disponiveis,
        key="f_tickers",
    )

    setores_selecionados = st.multiselect(
        "Setores",
        options=setores_disponiveis,
        default=setores_disponiveis,
        key="f_setores",
    )

    st.divider()

    st.caption("Fonte: CVM — Demonstrações Financeiras Padronizadas.")


if (
    not anos_selecionados
    or not tickers_selecionados
    or not setores_selecionados
):
    st.warning("Selecione pelo menos um ano, uma empresa e um setor.")
    st.stop()


# Filtra empresas e setores, mantendo todos os anos
# disponíveis para calcular as variações anuais.
dados_empresas = dados[
    dados["TICKER"].isin(tickers_selecionados)
    & dados["SETOR_ANALISE"].isin(setores_selecionados)
].copy()

dados_filtrados = dados_empresas[
    dados_empresas["ANO"].isin(anos_selecionados)
].copy()

if dados_filtrados.empty:
    st.warning("Não existem dados para os filtros selecionados.")
    st.stop()

ano_atual = max(anos_selecionados)

dados_atuais = dados_filtrados[
    dados_filtrados["ANO"] == ano_atual
].copy()

dados_anteriores = dados_empresas[
    dados_empresas["ANO"] == ano_atual - 1
].copy()


# =========================================================
# INDICADORES — KPIs
# =========================================================

receita_atual = dados_atuais["receita_liquida"].sum()

receita_anterior = dados_anteriores["receita_liquida"].sum()

lucro_atual = dados_atuais["lucro_liquido"].sum()

lucro_anterior = dados_anteriores["lucro_liquido"].sum()

roe_medio = dados_atuais["roe_pct"].mean()

liquidez_media = dados_atuais.loc[
    dados_atuais["TICKER"] != "ITUB4",
    "liquidez_corrente",
].mean()

delta_receita = formatar_variacao_percentual(
    receita_atual,
    receita_anterior,
)

delta_lucro = formatar_variacao_reais(
    lucro_atual,
    lucro_anterior,
)

st.subheader(f"Indicadores gerais — {ano_atual}")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Receita líquida total",
    formatar_reais_bilhoes(receita_atual),
    delta=delta_receita,
    help="Variação percentual em relação ao exercício anterior.",
)

col2.metric(
    "Lucro líquido agregado",
    formatar_reais_bilhoes(lucro_atual),
    delta=delta_lucro,
    help="Variação absoluta em reais em relação ao exercício anterior.",
)

col3.metric(
    "ROE médio",
    formatar_percentual(roe_medio),
    help="Média simples do ROE das empresas selecionadas.",
)

col4.metric(
    "Liquidez corrente média",
    (
        f"{liquidez_media:.2f}x".replace(".", ",")
        if pd.notna(liquidez_media)
        else "—"
    ),
    help="Média das empresas não financeiras. Itaú não incluído.",
)

st.caption(
    "Os totais representam a soma das empresas selecionadas, "
    "não demonstrações consolidadas de um único grupo econômico."
)

st.divider()


# =========================================================
# ABAS
# =========================================================

aba_visao, aba_rentabilidade, aba_endividamento, aba_dados = st.tabs(
    [
        "Visão geral",
        "Rentabilidade",
        "Liquidez e endividamento",
        "Dados detalhados",
    ]
)


# =========================================================
# ABA 1 — VISÃO GERAL
# =========================================================

with aba_visao:
    st.subheader("Evolução da receita líquida por empresa")

    receita = dados_filtrados.dropna(
        subset=["receita_liquida"]
    ).copy()

    receita["receita_bi"] = (
        receita["receita_liquida"] / 1_000_000_000
    )
    receita["ano_grafico"] = receita["ANO"].astype(str)

    if not receita.empty:
        fig_receita = px.bar(
            receita,
            x="TICKER",
            y="receita_bi",
            color="ano_grafico",
            barmode="group",
            title="Receita líquida — 2021 a 2023",
            labels={
                "TICKER": "Empresa",
                "receita_bi": "Receita (R$ bilhões)",
                "ano_grafico": "Exercício",
            },
            category_orders={
    "ano_grafico": [
        str(ano) for ano in sorted(anos_selecionados)
    ]
},
            hover_data={
                "receita_liquida": ":,.0f",
                "receita_bi": ":.2f",
            },
        )

        fig_receita.update_layout(
            xaxis_title="Empresa",
            yaxis_title="Receita líquida (R$ bilhões)",
            legend_title="Ano",
        )

        st.plotly_chart(
            fig_receita,
            width="stretch",
        )

    st.divider()

    st.subheader(
        f"Participação da receita por setor — {ano_atual}"
    )

    receita_setor = (
        dados_atuais
        .dropna(subset=["receita_liquida"])
        .groupby("SETOR_ANALISE", as_index=False)
        ["receita_liquida"]
        .sum()
    )

    if not receita_setor.empty:
        fig_setor = px.pie(
            receita_setor,
            names="SETOR_ANALISE",
            values="receita_liquida",
            hole=0.55,
            title="Distribuição da receita líquida por setor",
        )

        fig_setor.update_traces(
            textposition="inside",
            textinfo="percent+label",
        )

        st.plotly_chart(
            fig_setor,
            width="stretch",
        )


# =========================================================
# ABA 2 — RENTABILIDADE
# =========================================================

with aba_rentabilidade:
    st.subheader("Margem líquida versus ROE")

    rentabilidade = dados_atuais.dropna(
        subset=["margem_liquida_pct", "roe_pct", "receita_liquida"]
    ).copy()

    rentabilidade["receita_bi"] = (
        rentabilidade["receita_liquida"] / 1_000_000_000
    )

    if not rentabilidade.empty:
        fig_scatter = px.scatter(
            rentabilidade,
            x="margem_liquida_pct",
            y="roe_pct",
            size="receita_bi",
            color="SETOR_ANALISE",
            hover_name="TICKER",
            title=f"Margem líquida x ROE — {ano_atual}",
            labels={
                "margem_liquida_pct": "Margem líquida (%)",
                "roe_pct": "ROE (%)",
                "SETOR_ANALISE": "Setor",
                "receita_bi": "Receita (R$ bilhões)",
            },
            size_max=45,
        )

        media_margem = rentabilidade["margem_liquida_pct"].mean()
        media_roe = rentabilidade["roe_pct"].mean()

        fig_scatter.add_hline(
            y=media_roe,
            line_dash="dash",
            annotation_text="ROE médio",
        )

        fig_scatter.add_vline(
            x=media_margem,
            line_dash="dash",
            annotation_text="Margem média",
        )

        st.plotly_chart(
            fig_scatter,
            width="stretch",
        )

    st.divider()

    st.subheader("Distribuição da margem EBIT por setor")

    margem_ebit = dados_filtrados.dropna(
        subset=["margem_ebit_pct"]
    ).copy()

    if not margem_ebit.empty:
        fig_box = px.box(
            margem_ebit,
            x="SETOR_ANALISE",
            y="margem_ebit_pct",
            color="SETOR_ANALISE",
            points="all",
            hover_data=["TICKER", "ANO"],
            title="Margem EBIT por setor e exercício",
            labels={
                "SETOR_ANALISE": "Setor",
                "margem_ebit_pct": "Margem EBIT (%)",
            },
        )

        fig_box.update_layout(
            showlegend=False,
            xaxis_title="Setor",
            yaxis_title="Margem EBIT (%)",
        )

        st.plotly_chart(
            fig_box,
            width="stretch",
        )

    st.info(
        "O Itaú está incluído na análise de ROE e margem líquida, "
        "mas não na comparação de margem EBIT, devido às diferenças "
        "na estrutura de demonstração de resultados de instituições financeiras."
    )


# =========================================================
# ABA 3 — LIQUIDEZ E ENDIVIDAMENTO
# =========================================================

with aba_endividamento:
    st.subheader("Dívida líquida versus liquidez corrente")

    endividamento = dados_atuais.dropna(
        subset=["divida_liquida", "liquidez_corrente"]
    ).copy()

    endividamento = endividamento[
        endividamento["TICKER"] != "ITUB4"
    ]

    endividamento["divida_liquida_bi"] = (
        endividamento["divida_liquida"] / 1_000_000_000
    )

    endividamento["receita_bi"] = (
        endividamento["receita_liquida"] / 1_000_000_000
    )

    if not endividamento.empty:
        fig_divida = px.scatter(
            endividamento,
            x="divida_liquida_bi",
            y="liquidez_corrente",
            size="receita_bi",
            color="SETOR_ANALISE",
            hover_name="TICKER",
            title=f"Dívida líquida x Liquidez corrente — {ano_atual}",
            labels={
                "divida_liquida_bi": "Dívida líquida (R$ bilhões)",
                "liquidez_corrente": "Liquidez corrente (x)",
                "SETOR_ANALISE": "Setor",
                "receita_bi": "Receita (R$ bilhões)",
            },
            size_max=45,
        )

        fig_divida.add_hline(
            y=1.5,
            line_dash="dash",
            annotation_text="Referência: 1,5x",
        )

        fig_divida.add_vline(
            x=0,
            line_dash="dash",
            annotation_text="Dívida líquida zero",
        )

        st.plotly_chart(
            fig_divida,
            width="stretch",
        )

    st.caption(
        "Dívida líquida negativa indica que o caixa e equivalentes "
        "superam a dívida bruta considerada no cálculo."
    )

    st.info(
        "O Itaú foi excluído da comparação de liquidez e dívida "
        "por possuir estrutura contábil própria de instituição financeira."
    )


# =========================================================
# ABA 4 — DADOS DETALHADOS
# =========================================================

with aba_dados:
    st.subheader("Tabela de indicadores financeiros")

    colunas_exibicao = [
        "TICKER",
        "SETOR_ANALISE",
        "ANO",
        "receita_liquida",
        "lucro_liquido",
        "roe_pct",
        "margem_bruta_pct",
        "margem_ebit_pct",
        "margem_liquida_pct",
        "liquidez_corrente",
        "divida_bruta",
        "divida_liquida",
        "OBSERVACAO",
    ]

    colunas_disponiveis = [
        coluna
        for coluna in colunas_exibicao
        if coluna in dados_filtrados.columns
    ]

    tabela = dados_filtrados[colunas_disponiveis].copy()

    st.dataframe(
        tabela,
        width="stretch",
        hide_index=True,
    )

    csv = dados_filtrados.to_csv(
        index=False,
        sep=";",
    ).encode("utf-8-sig")

    st.download_button(
        label="⬇️ Baixar dados filtrados em CSV",
        data=csv,
        file_name="indicadores_financeiros_filtrados.csv",
        mime="text/csv",
        width="stretch",
    )


# =========================================================
# RODAPÉ — METODOLOGIA
# =========================================================

st.divider()

with st.expander("Notas metodológicas e limitações"):
    st.markdown(
        """
        - **Fonte:** Demonstrações Financeiras Padronizadas (DFP) da CVM.
        - **Período:** exercícios de 2021, 2022 e 2023.
        - **Escopo:** 12 companhias selecionadas para o estudo.
        - **ROE de 2021:** utiliza o patrimônio líquido final do exercício
          como aproximação, pois a base analisada começa em 2021 e não
          inclui o saldo de encerramento de 2020.
        - **Instituições financeiras:** o Itaú permanece nas análises
          de receita, lucro líquido, ROE e margem líquida. Foi excluído
          das comparações de margem EBIT, liquidez corrente e dívida líquida.
        - **Liquidez:** a linha de referência de 1,5x é um parâmetro
          de análise, não uma regra universal de solvência.
        - **Dívida líquida:** calculada pela dívida bruta considerada
          no estudo menos caixa e equivalentes de caixa.
        - **Valores:** os valores monetários foram convertidos para reais.
        - **Comparabilidade:** as diferenças entre setores e modelos de
          negócio devem ser consideradas na interpretação dos indicadores.
        """
    )

st.caption(
    "Projeto acadêmico de Visualização de Dados e Business Intelligence."
)
