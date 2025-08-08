import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

# --- Configuração do Painel ---
st.set_page_config(layout="wide", page_title="Análise Dinâmica - USIM5")
st.title("Painel de Análise Dinâmica de Ativos")
st.subheader("Ferramenta de Análise Estatística para USIM5")

# --- 1. LÓGICA DE DADOS E CÁLCULOS ---

@st.cache_data(ttl=900)
def carregar_dados(ticker):
    """Busca os últimos 5 anos de dados históricos para o ativo."""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=5*365)
        dados = yf.download(ticker, start=start_date, end=end_date)
        dados = dados.rename(columns={
            "Open": "Abertura", "High": "Maxima", "Low": "Minima",
            "Close": "Fechamento", "Adj Close": "Fech_Ajust", "Volume": "Volume"
        })
        return dados.reset_index()  # Resetar o índice para trabalhar com a coluna Date
    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")
        return pd.DataFrame()

@st.cache_data
def gerar_vencimentos(_start_date, _end_date):
    """Gera a lista de vencimentos (3ª sexta-feira) para o período."""
    try:
        vencimentos = set()
        start_date = pd.to_datetime(_start_date).replace(day=1)
        end_date = pd.to_datetime(_end_date).replace(day=1)
        
        current_date = start_date - pd.DateOffset(months=1)
        while current_date <= end_date + pd.DateOffset(months=2):
            year, month = current_date.year, current_date.month
            first_day = datetime(year, month, 1)
            first_friday = first_day + timedelta(days=(4 - first_day.weekday() + 7) % 7)
            third_friday = first_friday + timedelta(weeks=2)
            vencimentos.add(pd.to_datetime(third_friday))
            current_date += pd.DateOffset(months=1)
            
        return sorted(list(vencimentos))
    except Exception as e:
        st.error(f"Erro ao gerar vencimentos: {str(e)}")
        return []

def processar_dados_com_periodos(dados, vencimentos):
    """Adiciona colunas de identificação de período aos dados diários."""
    try:
        dados = dados.copy()
        dados['ID_Semana'] = dados['Date'].dt.to_period('W-FRI').astype(str)
        
        vencimentos_ts = [pd.Timestamp(v) for v in vencimentos]

        # Ciclo Mensal
        dados['ID_Ciclo_Mensal'] = pd.NA
        if len(vencimentos_ts) > 1:
            labels_mensais = [v.strftime('%d/%m/%Y') for v in vencimentos_ts[1:]]
            try:
                dados['ID_Ciclo_Mensal'] = pd.cut(
                    dados['Date'],
                    bins=vencimentos_ts,
                    labels=labels_mensais,
                    right=False,
                    include_lowest=True
                )
            except Exception as e:
                st.error(f"Erro no ciclo mensal: {str(e)}")

        # Ciclo Bimestral
        dados['ID_Ciclo_Bimestral'] = pd.NA
        bins_bimestrais = vencimentos_ts[::2]
        if len(bins_bimestrais) > 1:
            bim_labels = []
            for i in range(len(bins_bimestrais) - 1):
                if (i*2+1) < len(vencimentos_ts):
                    mes1 = vencimentos_ts[i*2].strftime("%b")
                    mes2 = vencimentos_ts[i*2+1].strftime("%b")
                    ano = vencimentos_ts[i*2+1].year
                    bim_labels.append(f"Bim-{mes1}/{mes2}-{ano}")
            
            try:
                dados['ID_Ciclo_Bimestral'] = pd.cut(
                    dados['Date'],
                    bins=bins_bimestrais,
                    labels=bim_labels,
                    right=False,
                    include_lowest=True
                )
            except Exception as e:
                st.error(f"Erro no ciclo bimestral: {str(e)}")

        # Filtrar dados válidos
        cols = ['ID_Ciclo_Mensal', 'ID_Ciclo_Bimestral']
        valid_cols = [col for col in cols if col in dados.columns]
        if valid_cols:
            dados = dados.dropna(subset=valid_cols)
            
        return dados.set_index('Date')
    
    except Exception as e:
        st.error(f"Erro ao processar dados: {str(e)}")
        return dados

# ... (mantenha as outras funções igual com exceção da execução principal)

# --- Execução Principal ---
try:
    dados_brutos = carregar_dados("USIM5.SA")
    
    if not dados_brutos.empty:
        dados_com_hoje = dados_brutos.copy()
        if pd.to_datetime(datetime.now().date()) not in dados_com_hoje['Date'].values:
            nova_linha = dados_brutos.iloc[[-1]].copy()
            nova_linha['Date'] = pd.to_datetime(datetime.now().date())
            dados_com_hoje = pd.concat([dados_brutos, nova_linha])
        
        vencimentos = gerar_vencimentos(dados_com_hoje['Date'].min(), dados_com_hoje['Date'].max())
        dados_processados = processar_dados_com_periodos(dados_com_hoje, vencimentos)

        # Verificar colunas existentes antes de processar
        if 'ID_Semana' in dados_processados.columns:
            resumo_semanal = calcular_resumo_periodo(dados_processados, 'ID_Semana')
            # Restante do processamento...

        if 'ID_Ciclo_Mensal' in dados_processados.columns:
            resumo_mensal = calcular_resumo_periodo(dados_processados, 'ID_Ciclo_Mensal')
            # Restante do processamento...

        if 'ID_Ciclo_Bimestral' in dados_processados.columns:
            resumo_bimestral = calcular_resumo_periodo(dados_processados, 'ID_Ciclo_Bimestral')
            # Restante do processamento...

    else:
        st.error("Não foi possível carregar os dados do ativo.")

except Exception as e:
    st.error(f"Ocorreu um erro ao executar a análise: {str(e)}")
