import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

# --- Configuração do Painel ---
st.set_page_config(layout="wide", page_title="Análise Dinâmica - USIM5")

st.title("Painel de Análise Dinâmica de Ativos")
st.subheader("Ferramenta de Análise Estatística para USIM5")

@st.cache_data(ttl=900)
def carregar_dados(ticker):
    """Busca os últimos 5 anos de dados históricos para o ativo."""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=5*365)
        dados = yf.download(ticker, start=start_date, end=end_date)
        
        # Renomear colunas corretamente
        dados = dados.rename(columns={
            'Open': 'Abertura',
            'High': 'Maxima',
            'Low': 'Minima',
            'Close': 'Fechamento',
            'Adj Close': 'Fech_Ajust',
            'Volume': 'Volume'
        })
        
        # Garantir que o índice seja chamado de 'Date'
        dados = dados.reset_index()
        dados = dados.rename(columns={'Date': 'Data'})
        dados = dados.set_index('Data')
        
        return dados
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
        dados['ID_Semana'] = dados.index.to_period('W-FRI').astype(str)
        
        vencimentos_ts = [pd.Timestamp(v) for v in vencimentos]

        # Ciclo Mensal
        if len(vencimentos_ts) > 1:
            labels_mensais = [v.strftime('%d/%m/%Y') for v in vencimentos_ts[1:]]
            try:
                dados['ID_Ciclo_Mensal'] = pd.cut(
                    dados.index,
                    bins=vencimentos_ts,
                    labels=labels_mensais,
                    right=False,
                    include_lowest=True
                )
            except:
                dados['ID_Ciclo_Mensal'] = pd.NA

        # Ciclo Bimestral
        bins_bimestrais = vencimentos_ts[::2]
        if len(bins_bimestrais) > 1:
            bim_labels = []
            for i in range(len(bins_bimestrais) - 1):
                venc_idx1 = i * 2
                venc_idx2 = venc_idx1 + 1
                if venc_idx2 < len(vencimentos_ts):
                    mes1 = vencimentos_ts[venc_idx1].strftime("%b")
                    mes2 = vencimentos_ts[venc_idx2].strftime("%b")
                    ano = vencimentos_ts[venc_idx2].year
                    bim_labels.append(f"Bim-{mes1}/{mes2}-{ano}")
            
            try:
                dados['ID_Ciclo_Bimestral'] = pd.cut(
                    dados.index,
                    bins=bins_bimestrais,
                    labels=bim_labels,
                    right=False,
                    include_lowest=True
                )
            except:
                dados['ID_Ciclo_Bimestral'] = pd.NA

        # Debug info
        st.write("Estrutura dos dados processados:")
        st.write(dados.head())
        st.write("Colunas disponíveis:", dados.columns.tolist())
        
        return dados

    except Exception as e:
        st.error(f"Erro ao processar dados: {str(e)}")
        return dados

def calcular_resumo_periodo(dados, id_periodo):
    """Cria a tabela de resumo histórico para um determinado período."""
    try:
        dados_com_data = dados.reset_index()
        if isinstance(dados_com_data[id_periodo].dtype, pd.CategoricalDtype):
            dados_com_data[id_periodo] = dados_com_data[id_periodo].astype(str)

        resumo = dados_com_data.groupby(id_periodo).agg({
            'Abertura': 'first',
            'Maxima': 'max',
            'Minima': 'min',
            'Fechamento': 'last',
            'Data': ['min', 'max']
        })

        # Acertar os nomes das colunas
        resumo.columns = ['Abertura', 'Maxima', 'Minima', 'Fechamento', 'Data_Inicio', 'Data_Fim']
        
        resumo['Var_Alta_Rs'] = resumo['Maxima'] - resumo['Abertura']
        resumo['Var_Baixa_Rs'] = resumo['Abertura'] - resumo['Minima']
        resumo['Recuo_Alta_Rs'] = resumo['Maxima'] - resumo['Fechamento']
        resumo['Recup_Baixa_Rs'] = resumo['Fechamento'] - resumo['Minima']
        resumo['Delta_Rs'] = resumo['Fechamento'] - resumo['Abertura']
        
        return resumo
    except Exception as e:
        st.error(f"Erro ao calcular resumo: {str(e)}")
        st.write("Colunas disponíveis:", dados.columns.tolist())
        return pd.DataFrame()
