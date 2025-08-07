# Para executar este código online (usando o Streamlit Community Cloud),
# você precisaria de um ficheiro chamado requirements.txt com o seguinte conteúdo:
# streamlit
# pandas
# yfinance
# numpy

import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

# --- Configuração do Painel ---
st.set_page_config(layout="wide", page_title="Análise Semanal - USIM5")

st.title("Painel de Análise Dinâmica de Ativos")
st.subheader("Ferramenta de Análise Estatística Semanal para USIM5")

# --- 1. LÓGICA DE DADOS E CÁLCULOS ---

@st.cache_data(ttl=900) # Atualiza os dados a cada 15 minutos
def carregar_dados(ticker):
    """Busca os últimos 5 anos de dados históricos para o ativo."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5*365)
    dados = yf.download(ticker, start=start_date, end=end_date)
    # Renomeia as colunas para português para facilitar a leitura
    dados.rename(columns={
        "Open": "Abertura", "High": "Maxima", "Low": "Minima",
        "Close": "Fechamento", "Adj Close": "Fech_Ajust", "Volume": "Volume"
    }, inplace=True)
    return dados

def processar_dados_semanais(dados):
    """Adiciona a coluna de identificação de semana aos dados diários."""
    dados['ID_Semana'] = dados.index.to_period('W-FRI').astype(str)
    return dados

def calcular_resumo_semanal(dados):
    """Cria a tabela de resumo histórico semanal."""
    resumo = dados.groupby('ID_Semana').agg(
        Abertura=('Abertura', 'first'),
        Maxima=('Maxima', 'max'),
        Minima=('Minima', 'min'),
        Fechamento=('Fechamento', 'last'),
        Data_Inicio=(dados.index.name or 'Date', 'min'),
        Data_Fim=(dados.index.name or 'Date', 'max')
    )
    resumo['Var_Alta_Rs'] = resumo['Maxima'] - resumo['Abertura']
    resumo['Var_Baixa_Rs'] = resumo['Abertura'] - resumo['Minima']
    resumo['Recuo_Alta_Rs'] = resumo['Maxima'] - resumo['Fechamento']
    resumo['Recup_Baixa_Rs'] = resumo['Fechamento'] - resumo['Minima']
    resumo['Delta_Rs'] = resumo['Fechamento'] - resumo['Abertura']
    return resumo

def calcular_estatisticas(resumo_historico):
    """Calcula as tabelas de análise de range e reversão."""
    faixas = {
        "Abaixo de R$ 3,50": (0, 3.50),
        "Entre R$ 3,51 e R$ 6,00": (3.51, 6.00),
        "Entre R$ 6,01 e R$ 8,00": (6.01, 8.00),
        "Entre R$ 8,01 e R$ 10,00": (8.01, 10.00),
        "Acima de R$ 10,00": (10.01, 999)
    }
    
    ranges = {}
    reversoes = {}

    for nome_faixa, (min_val, max_val) in faixas.items():
        dados_faixa = resumo_historico[(resumo_historico['Abertura'] >= min_val) & (resumo_historico['Abertura'] <= max_val)]
        
        if len(dados_faixa) > 10: # Mínimo de 10 períodos para estatística
            deltas = dados_faixa['Delta_Rs']
            ranges[nome_faixa] = {
                60: np.max([np.abs(deltas.quantile(0.20)), np.abs(deltas.quantile(0.80))]),
                70: np.max([np.abs(deltas.quantile(0.15)), np.abs(deltas.quantile(0.85))]),
                75: np.max([np.abs(deltas.quantile(0.125)), np.abs(deltas.quantile(0.875))]),
                80: np.max([np.abs(deltas.quantile(0.10)), np.abs(deltas.quantile(0.90))])
            }
            
            reversoes[nome_faixa] = {
                'recuo_20': len(dados_faixa[dados_faixa['Recuo_Alta_Rs'] > 0.2 * dados_faixa['Var_Alta_Rs']]) / len(dados_faixa),
                'recuo_30': len(dados_faixa[dados_faixa['Recuo_Alta_Rs'] > 0.3 * dados_faixa['Var_Alta_Rs']]) / len(dados_faixa),
                'recuo_40': len(dados_faixa[dados_faixa['Recuo_Alta_Rs'] > 0.4 * dados_faixa['Var_Alta_Rs']]) / len(dados_faixa),
                'recuo_50': len(dados_faixa[dados_faixa['Recuo_Alta_Rs'] > 0.5 * dados_faixa['Var_Alta_Rs']]) / len(dados_faixa),
                'recup_20': len(dados_faixa[dados_faixa['Recup_Baixa_Rs'] > 0.2 * dados_faixa['Var_Baixa_Rs']]) / len(dados_faixa),
                'recup_30': len(dados_faixa[dados_faixa['Recup_Baixa_Rs'] > 0.3 * dados_faixa['Var_Baixa_Rs']]) / len(dados_faixa),
                'recup_40': len(dados_faixa[dados_faixa['Recup_Baixa_Rs'] > 0.4 * dados_faixa['Var_Baixa_Rs']]) / len(dados_faixa),
                'recup_50': len(dados_faixa[dados_faixa['Recup_Baixa_Rs'] > 0.5 * dados_faixa['Var_Baixa_Rs']]) / len(dados_faixa),
            }
            reversoes[nome_faixa]['recuo_media'] = np.mean(list(reversoes[nome_faixa].values())[:4])
            reversoes[nome_faixa]['recup_media'] = np.mean(list(reversoes[nome_faixa].values())[4:8])

    return ranges, reversoes

def get_faixa_preco(preco):
    """Retorna o nome da faixa de preço para um dado preço."""
    if preco < 3.51: return "Abaixo de R$ 3,50"
    if preco <= 6.00: return "Entre R$ 3,51 e R$ 6,00"
    if preco <= 8.00: return "Entre R$ 6,01 e R$ 8,00"
    if preco <= 10.00: return "Entre R$ 8,01 e R$ 10,00"
    return "Acima de R$ 10,00"


# --- 2. INTERFACE DO PAINEL (STREAMLIT) ---

def exibir_painel_semanal(dados_diarios, resumo_historico, ranges, reversoes):
    """Função para exibir os cards de análise semanal."""
    st.header(f"Análise Semanal", divider='rainbow')

    hoje = pd.to_datetime(datetime.now().date())
    periodo_atual = resumo_historico[(hoje >= resumo_historico['Data_Inicio']) & (hoje <= resumo_historico['Data_Fim'])]
    
    if periodo_atual.empty:
        st.warning(f"Aguardando o início da próxima semana.")
        return

    periodo_atual = periodo_atual.iloc[0]
    abertura_periodo = periodo_atual['Abertura']
    faixa_atual = get_faixa_preco(abertura_periodo)

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.subheader("🎯 Ranges de Variação")
            st.markdown(f"**Abertura da Semana:** R$ {abertura_periodo:.2f}")
            st.markdown(f"**Faixa Histórica:** {faixa_atual}")
            
            if faixa_atual in ranges:
                st.markdown("**Probabilidades de Fechamento na Sexta-feira:**")
                for prob, var in ranges[faixa_atual].items():
                    st.text(f"  - {prob}% de chance de fechar entre R$ {abertura_periodo - var:.2f} e R$ {abertura_periodo + var:.2f}")
            else:
                st.info("Não há dados históricos suficientes para esta faixa de preço.")

    with col2:
        with st.container(border=True):
            st.subheader("🚨 Alertas de Variação")
            
            if faixa_atual not in reversoes:
                 st.info("Não há dados históricos suficientes para esta faixa de preço.")
                 return

            dados_no_periodo = dados_diarios[(dados_diarios.index >= periodo_atual['Data_Inicio']) & (dados_diarios.index <= hoje)]
            if dados_no_periodo.empty:
                st.info("Aguardando primeiro dia de negociação da semana.")
                return

            maxima_no_periodo = dados_no_periodo['Maxima'].max()
            minima_no_periodo = dados_no_periodo['Minima'].min()
            
            var_atual_alta = maxima_no_periodo - abertura_periodo
            var_atual_baixa = abertura_periodo - minima_no_periodo

            historico_faixa = resumo_historico[resumo_historico.apply(lambda row: get_faixa_preco(row['Abertura']) == faixa_atual, axis=1)]
            media_var_alta_faixa = historico_faixa['Var_Alta_Rs'].mean()
            media_var_baixa_faixa = historico_faixa['Var_Baixa_Rs'].mean()
            
            dias_restantes = (periodo_atual['Data_Fim'].date() - hoje.date()).days
            
            alerta_disparado = False
            if var_atual_alta >= media_var_alta_faixa:
                alerta_disparado = True
                st.success(f"**ALERTA: MÉDIA DE ALTA ATINGIDA!**")
                st.markdown(f"O ativo atingiu a variação média histórica de alta (R$ {media_var_alta_faixa:.2f}).")
                st.markdown(f"Faltam **{dias_restantes} dias** para o fim da semana.")
                st.markdown(f"**Probabilidade Média de Recuo da Máxima:** **{reversoes[faixa_atual]['recuo_media']:.1%}**")

            elif var_atual_baixa >= media_var_baixa_faixa:
                alerta_disparado = True
                st.error(f"**ALERTA: MÉDIA DE BAIXA ATINGIDA!**")
                st.markdown(f"O ativo atingiu a variação média histórica de baixa (R$ {media_var_baixa_faixa:.2f}).")
                st.markdown(f"Faltam **{dias_restantes} dias** para o fim da semana.")
                st.markdown(f"**Probabilidade Média de Recuperação da Mínima:** **{reversoes[faixa_atual]['recup_media']:.1%}**")
            
            if not alerta_disparado:
                st.info("Nenhum alerta de variação média acionado. O ativo opera dentro dos parâmetros históricos.")


# --- Execução Principal ---
try:
    dados_brutos = carregar_dados("USIM5.SA")
    
    if not dados_brutos.empty:
        # Adiciona a data de hoje com os últimos dados para garantir que o período atual seja encontrado
        ultima_linha = dados_brutos.iloc[[-1]]
        ultima_linha.index = [pd.to_datetime(datetime.now().date())]
        dados_com_hoje = pd.concat([dados_brutos, ultima_linha])
        
        dados_processados = processar_dados_semanais(dados_com_hoje)

        # Cálculos Semanais
        resumo_semanal = calcular_resumo_semanal(dados_processados)
        ranges_semanais, reversoes_semanais = calcular_estatisticas(resumo_semanal)
        exibir_painel_semanal(dados_processados, resumo_semanal, ranges_semanais, reversoes_semanais)

    else:
        st.error("Não foi possível carregar os dados do ativo. A API pode estar temporariamente indisponível.")

except Exception as e:
    st.error(f"Ocorreu um erro ao executar a análise: {e}")
    st.info("Pode ser um problema temporário com a obtenção dos dados. Por favor, tente recarregar a página em alguns minutos.")

