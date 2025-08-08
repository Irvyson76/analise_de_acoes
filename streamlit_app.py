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
        st.write("Estrutura dos dados:")
        st.write(dados.head())
        st.write("Colunas:", dados.columns.tolist())
        
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
        return pd.DataFrame()

def calcular_estatisticas(resumo_historico):
    """Calcula as tabelas de análise de range e reversão."""
    try:
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
            dados_faixa = resumo_historico[
                (resumo_historico['Abertura'] >= min_val) & 
                (resumo_historico['Abertura'] <= max_val)
            ]
            
            if len(dados_faixa) > 10:
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
    except Exception as e:
        st.error(f"Erro ao calcular estatísticas: {str(e)}")
        return {}, {}

def get_faixa_preco(preco):
    """Retorna o nome da faixa de preço para um dado preço."""
    if preco < 3.51: return "Abaixo de R$ 3,50"
    if preco <= 6.00: return "Entre R$ 3,51 e R$ 6,00"
    if preco <= 8.00: return "Entre R$ 6,01 e R$ 8,00"
    if preco <= 10.00: return "Entre R$ 8,01 e R$ 10,00"
    return "Acima de R$ 10,00"

def exibir_painel_periodo(nome_periodo, dados_diarios, resumo_historico, ranges, reversoes):
    """Função genérica para exibir os cards de análise para qualquer período."""
    try:
        st.header(f"Análise {nome_periodo}", divider='rainbow')

        hoje = pd.to_datetime(datetime.now().date())
        periodo_atual = resumo_historico[
            (hoje >= resumo_historico['Data_Inicio']) & 
            (hoje <= resumo_historico['Data_Fim'])
        ]
        
        if periodo_atual.empty:
            st.warning(f"Aguardando o início do próximo período {nome_periodo.lower()}.")
            return

        periodo_atual = periodo_atual.iloc[0]
        abertura_periodo = periodo_atual['Abertura']
        faixa_atual = get_faixa_preco(abertura_periodo)

        col1, col2 = st.columns(2)

        with col1:
            with st.container(border=True):
                st.subheader("🎯 Ranges de Variação")
                st.markdown(f"**Abertura do Período:** R$ {abertura_periodo:.2f}")
                st.markdown(f"**Faixa Histórica:** {faixa_atual}")
                
                if faixa_atual in ranges:
                    st.markdown("**Probabilidades de Fechamento:**")
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

                dados_no_periodo = dados_diarios[
                    (dados_diarios.index >= periodo_atual['Data_Inicio']) & 
                    (dados_diarios.index <= hoje)
                ]
                
                if dados_no_periodo.empty:
                    st.info("Aguardando primeiro dia de negociação do período.")
                    return

                maxima_no_periodo = dados_no_periodo['Maxima'].max()
                minima_no_periodo = dados_no_periodo['Minima'].min()
                
                var_atual_alta = maxima_no_periodo - abertura_periodo
                var_atual_baixa = abertura_periodo - minima_no_periodo

                historico_faixa = resumo_historico[
                    resumo_historico.apply(
                        lambda row: get_faixa_preco(row['Abertura']) == faixa_atual, 
                        axis=1
                    )
                ]
                
                media_var_alta_faixa = historico_faixa['Var_Alta_Rs'].mean()
                media_var_baixa_faixa = historico_faixa['Var_Baixa_Rs'].mean()
                
                dias_restantes = (periodo_atual['Data_Fim'].date() - hoje.date()).days
                
                alerta_disparado = False
                if var_atual_alta >= media_var_alta_faixa:
                    alerta_disparado = True
                    st.success(f"**ALERTA: MÉDIA DE ALTA ATINGIDA!**")
                    st.markdown(f"O ativo atingiu a variação média histórica de alta (R$ {media_var_alta_faixa:.2f}).")
                    st.markdown(f"Faltam **{dias_restantes} dias** para o fim do período.")
                    st.markdown(f"**Probabilidade Média de Recuo da Máxima:** **{reversoes[faixa_atual]['recuo_media']:.1%}**")

                elif var_atual_baixa >= media_var_baixa_faixa:
                    alerta_disparado = True
                    st.error(f"**ALERTA: MÉDIA DE BAIXA ATINGIDA!**")
                    st.markdown(f"O ativo atingiu a variação média histórica de baixa (R$ {media_var_baixa_faixa:.2f}).")
                    st.markdown(f"Faltam **{dias_restantes} dias** para o fim do período.")
                    st.markdown(f"**Probabilidade Média de Recuperação da Mínima:** **{reversoes[faixa_atual]['recup_media']:.1%}**")
                
                if not alerta_disparado:
                    st.info("Nenhum alerta de variação média acionado. O ativo opera dentro dos parâmetros históricos.")

    except Exception as e:
        st.error(f"Erro ao exibir painel do período {nome_periodo}: {str(e)}")

# --- Execução Principal ---
try:
    dados_brutos = carregar_dados("USIM5.SA")
    
    if dados_brutos.empty:
        st.error("Não foi possível carregar os dados do ativo.")
        st.stop()

    # Adicionar a data de hoje
    ultima_linha = dados_brutos.iloc[[-1]]
    ultima_linha.index = [pd.to_datetime(datetime.now().date())]
    dados_com_hoje = pd.concat([dados_brutos, ultima_linha])
    
    # Gerar vencimentos
    vencimentos = gerar_vencimentos(dados_com_hoje.index.min(), dados_com_hoje.index.max())
    
    if not vencimentos:
        st.error("Não foi possível gerar as datas de vencimento.")
        st.stop()
    
    # Processar dados
    dados_processados = processar_dados_com_periodos(dados_com_hoje, vencimentos)
    
    # Cálculos Semanais
    if 'ID_Semana' in dados_processados.columns:
        resumo_semanal = calcular_resumo_periodo(dados_processados, 'ID_Semana')
        if not resumo_semanal.empty:
            ranges_semanais, reversoes_semanais = calcular_estatisticas(resumo_semanal)
            exibir_painel_periodo("Semanal", dados_processados, resumo_semanal, 
                                ranges_semanais, reversoes_semanais)

    # Cálculos Mensais
    if 'ID_Ciclo_Mensal' in dados_processados.columns:
        resumo_mensal = calcular_resumo_periodo(dados_processados, 'ID_Ciclo_Mensal')
        if not resumo_mensal.empty:
            ranges_mensais, reversoes_mensais = calcular_estatisticas(resumo_mensal)
            exibir_painel_periodo("Mensal (Opções)", dados_processados, resumo_mensal, 
                                ranges_mensais, reversoes_mensais)

    # Cálculos Bimestrais
    if 'ID_Ciclo_Bimestral' in dados_processados.columns:
        resumo_bimestral = calcular_resumo_periodo(dados_processados, 'ID_Ciclo_Bimestral')
        if not resumo_bimestral.empty:
            ranges_bimestrais, reversoes_bimestrais = calcular_estatisticas(resumo_bimestral)
            exibir_painel_periodo("Bimestral (Opções)", dados_processados, resumo_bimestral, 
                                ranges_bimestrais, reversoes_bimestrais)

except Exception as e:
    st.error(f"Erro na execução principal: {str(e)}")
    st.info("Por favor, verifique se os dados estão disponíveis e tente novamente.")
