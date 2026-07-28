import streamlit as st
import pandas as pd
import datetime
import os
import importlib
import io

import bcb_service
import word_service
import excel_service
import igpm_service

# Ensure modules are dynamically reloaded if modified
importlib.reload(bcb_service)
importlib.reload(word_service)
importlib.reload(excel_service)
importlib.reload(igpm_service)

st.set_page_config(
    page_title="Atualizador Monetário BCB | Word & Excel",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# DESIGN SYSTEM & CUSTOM CSS (UX Polish)
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Headers */
    .main-header {
        background: linear-gradient(135deg, #0f2b48 0%, #1e4976 100%);
        padding: 28px 32px;
        border-radius: 14px;
        color: white;
        margin-bottom: 25px;
        box-shadow: 0 10px 25px -5px rgba(15, 43, 72, 0.25);
    }
    .main-header h1 {
        color: #ffffff !important;
        margin: 0;
        font-size: 28px;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    .main-header p {
        color: #bcd2e8;
        margin-top: 8px;
        margin-bottom: 0;
        font-size: 15px;
        line-height: 1.5;
    }
    
    .igpm-header {
        background: linear-gradient(135deg, #134e2a 0%, #257d47 100%);
        padding: 28px 32px;
        border-radius: 14px;
        color: white;
        margin-bottom: 25px;
        box-shadow: 0 10px 25px -5px rgba(19, 78, 42, 0.25);
    }
    .igpm-header h1 {
        color: #ffffff !important;
        margin: 0;
        font-size: 28px;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    .igpm-header p {
        color: #b7e4c7;
        margin-top: 8px;
        margin-bottom: 0;
        font-size: 15px;
        line-height: 1.5;
    }

    /* Cards & Containers */
    .ux-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    
    /* Empty state wizard card */
    .wizard-card {
        background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
        border: 2px dashed #cbd5e1;
        border-radius: 16px;
        padding: 40px 30px;
        text-align: center;
        margin: 20px 0;
    }
    .wizard-icon {
        font-size: 48px;
        margin-bottom: 12px;
    }
    .wizard-title {
        font-size: 22px;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 8px;
    }
    .wizard-subtitle {
        font-size: 14px;
        color: #64748b;
        max-width: 580px;
        margin: 0 auto 28px auto;
    }
    
    /* Column sample pills */
    .sample-pill {
        display: inline-block;
        background-color: #f1f5f9;
        border: 1px solid #cbd5e1;
        color: #334155;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 500;
        margin-right: 6px;
        margin-top: 4px;
    }
    .sample-box {
        background: #f8fafc;
        border-left: 3px solid #0284c7;
        padding: 8px 12px;
        border-radius: 0 8px 8px 0;
        margin-top: 6px;
        margin-bottom: 12px;
        font-size: 13px;
        color: #475569;
    }

    /* KPI Metrics Styling */
    div[data-testid="stMetricValue"] {
        font-size: 24px !important;
        font-weight: 700 !important;
    }
    
    /* Footer */
    .app-footer {
        text-align: center;
        padding: 24px 0 12px 0;
        color: #94a3b8;
        font-size: 13px;
        border-top: 1px solid #e2e8f0;
        margin-top: 40px;
    }
</style>
""", unsafe_allow_html=True)

def safe_parse_float(v):
    if pd.isna(v) or v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        s = str(v).replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
        return float(s)
    except Exception:
        return 0.0

def format_currency_br(val):
    if val is None or pd.isna(val):
        return "R$ 0,00"
    return f"R$ {val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def get_column_samples(df, col_name, n=3):
    """Returns a formatted string of sample values from a dataframe column."""
    if not col_name or col_name not in df.columns:
        return ""
    non_nulls = df[col_name].dropna().tolist()
    samples = [str(x).strip() for x in non_nulls[:n] if str(x).strip() != ""]
    if not samples:
        return "Nenhum valor encontrado"
    return " • ".join(samples)


# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("### 🛠️ Modo de Operação")
    modo = st.radio(
        "Selecione a funcionalidade:",
        ["🏦 Correção Monetária (Poupança/SELIC/CDI)", "📈 Atualizar IGP-M (Ciclos de 12 Meses)"],
        index=0,
        help="Escolha entre a atualização individual por data ou o cálculo cíclico de IGP-M a cada 12 parcelas."
    )

    st.markdown("---")

    if modo.startswith("🏦"):
        with st.expander("⚙️ Configurações do Cálculo", expanded=True):
            data_final_def = datetime.date.today()
            data_final_input = st.date_input(
                "Data Final da Correção",
                value=data_final_def,
                format="DD/MM/YYYY",
                help="Selecione a data de referência final para atualização de todos os lançamentos."
            )
            data_final_str = data_final_input.strftime("%d/%m/%Y")

            aba_opcoes = {
                "Poupança (aba 3 - Padrão)": "3",
                "SELIC (aba 4)": "4",
                "CDI (aba 5)": "5",
                "TR - Taxa Referencial (aba 2)": "2",
                "Taxa Legal (aba 6)": "6",
                "IGP-M / Índices de Preços (aba 1)": "1"
            }
            aba_selecionada = st.selectbox(
                "Indicador do Banco Central",
                options=list(aba_opcoes.keys()),
                help="Selecione qual tabela oficial do BCB será consultada."
            )
            aba_codigo = aba_opcoes[aba_selecionada]

    else:
        with st.expander("⚙️ Configurações do IGP-M", expanded=True):
            ciclo_meses = 12
            st.info(f"🔄 Ciclo fixo de **{ciclo_meses} meses** por atualização.")

    st.markdown("---")
    with st.expander("📁 Arquivos de Exemplo", expanded=False):
        st.write("Baixe a planilha modelo para testar o sistema imediatamente:")
        if os.path.exists("exemplo_pagamentos.xlsx"):
            with open("exemplo_pagamentos.xlsx", "rb") as f:
                st.download_button(
                    "📊 Baixar Excel Exemplo",
                    data=f.read(),
                    file_name="exemplo_pagamentos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )


# ==========================================
# MODO 1: CORREÇÃO MONETÁRIA
# ==========================================
if modo.startswith("🏦"):
    st.markdown("""
    <div class="main-header">
        <h1>🏦 Atualizador Monetário BCB (Calculadora do Cidadão)</h1>
        <p>Atualize tabelas de pagamentos pela Caderneta de Poupança, SELIC, CDI ou TR. Gera automaticamente comprovantes com o layout oficial do Banco Central e relatório completo em Word e Excel.</p>
    </div>
    """, unsafe_allow_html=True)

    col_up1, col_up2 = st.columns(2)
    with col_up1:
        st.markdown("##### 1. Enviar Planilha de Pagamentos (Excel)")
        uploaded_excel = st.file_uploader(
            "Selecione a planilha (.xlsx ou .xls)",
            type=["xlsx", "xls"],
            key="excel_correcao",
            help="Planilha contendo ao menos uma coluna com datas de pagamento e uma com valores em R$."
        )
    with col_up2:
        st.markdown("##### 2. Enviar Modelo Word (.docx) - Opcional")
        uploaded_word = st.file_uploader(
            "Selecione seu modelo de documento Word",
            type=["docx"],
            key="word_correcao",
            help="Opcional. Se enviado, o relatório com os prints será anexado ao final do seu modelo."
        )

    if uploaded_excel:
        try:
            excel_bytes = uploaded_excel.read()
            df_raw, map_sugest = excel_service.carregar_excel(excel_bytes)

            st.session_state["df_correcao"] = df_raw
            st.session_state["excel_bytes_correcao"] = excel_bytes

            st.markdown("---")
            st.subheader("📌 Mapeamento Inteligente de Colunas")
            st.caption("Verifique se as colunas identificadas correspondem aos dados da sua planilha. Veja a amostra abaixo de cada seletor.")

            cols = list(df_raw.columns)
            col_m1, col_m2, col_m3 = st.columns(3)
            idx_data = cols.index(map_sugest["col_data"]) if map_sugest["col_data"] in cols else 0
            idx_val = cols.index(map_sugest["col_valor"]) if map_sugest["col_valor"] in cols else min(1, len(cols)-1)

            with col_m1:
                selected_col_data = st.selectbox(
                    "📅 Coluna da Data de Pagamento",
                    options=cols,
                    index=idx_data,
                    key="cd1",
                    help="Coluna com as datas de cada pagamento ou vencimento."
                )
                sample_dt = get_column_samples(df_raw, selected_col_data)
                st.markdown(f'<div class="sample-box"><b>🔍 Amostra:</b> {sample_dt}</div>', unsafe_allow_html=True)

            with col_m2:
                selected_col_valor = st.selectbox(
                    "💰 Coluna do Valor Original (R$)",
                    options=cols,
                    index=idx_val,
                    key="cv1",
                    help="Coluna com os valores monetários a serem corrigidos."
                )
                sample_val = get_column_samples(df_raw, selected_col_valor)
                st.markdown(f'<div class="sample-box"><b>🔍 Amostra:</b> {sample_val}</div>', unsafe_allow_html=True)

            with col_m3:
                options_desc = ["(Nenhum / Usar número da linha)"] + cols
                selected_col_desc = st.selectbox(
                    "🏷️ Coluna de Descrição (Opcional)",
                    options=options_desc,
                    key="desc1",
                    help="Coluna para identificar a parcela (ex: 'Fornecedor A', 'Parcela #1')."
                )
                if selected_col_desc != "(Nenhum / Usar número da linha)":
                    sample_desc = get_column_samples(df_raw, selected_col_desc)
                    st.markdown(f'<div class="sample-box"><b>🔍 Amostra:</b> {sample_desc}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="sample-box"><i>Será usado: Lançamento #1, #2...</i></div>', unsafe_allow_html=True)

            st.write("#### 👁️ Pré-visualização da Planilha Enviada:")
            st.dataframe(df_raw.head(8).astype(str), use_container_width=True)
            tot_linhas = len(df_raw)
            st.info(f"📋 **{tot_linhas} linha(s)** prontas para atualização monetária até **{data_final_str}**.")
            st.markdown("---")

            if st.button("🚀 Iniciar Atualização Monetária e Gerar Documentos", type="primary", use_container_width=True):
                importlib.reload(word_service)
                importlib.reload(bcb_service)
                importlib.reload(excel_service)

                progress_bar = st.progress(0)
                status_text = st.empty()
                resultados = []

                for i, row in df_raw.iterrows():
                    dt_in = row[selected_col_data]
                    val_orig = row[selected_col_valor]
                    desc_text = row[selected_col_desc] if selected_col_desc != "(Nenhum / Usar número da linha)" else f"Lançamento #{i+1}"
                    pct = int(((i + 1) / tot_linhas) * 100)
                    status_text.markdown(f"⏳ Processando item **{i+1}/{tot_linhas}** ({pct}%): `{desc_text}`...")

                    try:
                        res = bcb_service.processar_calculo_bcb(
                            data_inicial=dt_in, data_final=data_final_str,
                            valor_input=val_orig, aba=aba_codigo, use_playwright=False
                        )
                    except Exception as err_item:
                        res = {"status": "Erro", "mensagem_erro": str(err_item), "data_inicial": "-",
                               "data_final": data_final_str, "valor_original_str": str(val_orig),
                               "valor_corrigido_str": "-", "fator_correcao": "-", "percentual": "-",
                               "screenshot_bytes": None}

                    res["descricao"] = str(desc_text) if not pd.isna(desc_text) else f"Lançamento #{i+1}"
                    res["valor_original_num"] = safe_parse_float(val_orig)
                    resultados.append(res)
                    progress_bar.progress((i + 1) / tot_linhas)

                status_text.success("🎉 Atualização concluída com sucesso!")
                st.balloons()

                # Calculate KPI Totals
                total_orig = sum(r.get("valor_original_num", 0.0) for r in resultados)
                total_corr = sum(
                    r.get("valor_corrigido_num")
                    if (r.get("valor_corrigido_num") is not None)
                    else safe_parse_float(r.get("valor_corrigido_str"))
                    for r in resultados
                )
                diferenca = total_corr - total_orig
                pct_aumento = ((total_corr / total_orig) - 1) * 100 if total_orig > 0 else 0.0

                # KPI Metrics Cards
                st.markdown("### 📊 Resumo Executivo dos Resultados")
                kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                kpi1.metric("Parcelas Processadas", f"{tot_linhas}")
                kpi2.metric("Valor Original Total", format_currency_br(total_orig))
                kpi3.metric("Valor Corrigido Total", format_currency_br(total_corr), delta=f"+{pct_aumento:.2f}%")
                kpi4.metric("Diferença da Correção", format_currency_br(diferenca), delta=f"R$ {diferenca:,.2f}")

                st.markdown("---")

                # Generate files
                modelo_bytes = uploaded_word.read() if uploaded_word else None
                word_bytes = word_service.gerar_relatorio_word(resultados, df_original=df_raw, modelo_bytes=modelo_bytes)
                excel_out_bytes = excel_service.gerar_excel_atualizado(
                    df_raw, resultados, selected_col_data, selected_col_valor,
                    col_desc=selected_col_desc if selected_col_desc != "(Nenhum / Usar número da linha)" else None
                )

                st.markdown("### 📥 Baixar Relatórios Gerados")
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.download_button(
                        "📄 Baixar Relatório Word com Comprovantes (.docx)",
                        data=word_bytes,
                        file_name=f"Relatorio_BCB_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
                with col_d2:
                    st.download_button(
                        "📊 Baixar Planilha Excel Atualizada (.xlsx)",
                        data=excel_out_bytes,
                        file_name=f"Pagamentos_BCB_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

                st.markdown("---")
                st.subheader("🖼️ Comprovantes Oficiais do Banco Central")
                grid_cols = st.columns(3)
                for idx, r in enumerate(resultados):
                    with grid_cols[idx % 3]:
                        st.caption(f"Item #{idx+1}: {r.get('descricao')}")
                        if r.get("screenshot_bytes"):
                            st.image(r["screenshot_bytes"], use_column_width=True)

        except Exception as e:
            st.error(f"Erro ao ler ou processar o arquivo: {str(e)}")
    else:
        # Empty State Wizard Guide
        st.markdown("""
        <div class="wizard-card">
            <div class="wizard-icon">📊</div>
            <div class="wizard-title">Envie sua planilha Excel para iniciar</div>
            <div class="wizard-subtitle">
                O sistema fará a leitura automática das parcelas, consultará a Calculadora do Cidadão do Banco Central e gerará um relatório completo em Word e Excel com comprovantes.
            </div>
            <div style="display: flex; justify-content: center; gap: 24px; text-align: left; max-width: 680px; margin: 0 auto;">
                <div><b>1. Upload</b><br><span style="font-size:13px; color:#64748b;">Envie o arquivo .xlsx ou .xls no campo acima</span></div>
                <div><b>2. Mapeamento</b><br><span style="font-size:13px; color:#64748b;">Confirme as colunas de data e valor</span></div>
                <div><b>3. Processamento</b><br><span style="font-size:13px; color:#64748b;">Cálculo oficial via Banco Central</span></div>
                <div><b>4. Relatório</b><br><span style="font-size:13px; color:#64748b;">Download de Word com prints e Excel</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ==========================================
# MODO 2: ATUALIZAR IGP-M
# ==========================================
elif modo.startswith("📈"):
    st.markdown("""
    <div class="igpm-header">
        <h1>📈 Atualização por IGP-M (FGV) — Ciclos de 12 Meses</h1>
        <p>Cálculo de reajuste anual por ciclos de 12 parcelas. As primeiras 12 parcelas mantêm o valor original. A partir da 13ª parcela, aplica-se o IGP-M acumulado dos 12 meses anteriores de forma em cascata.</p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("1. Selecionar Planilha de Origem")

    has_session_df = "df_correcao" in st.session_state and st.session_state["df_correcao"] is not None

    if has_session_df:
        fonte = st.radio(
            "De onde vem a planilha das parcelas?",
            ["📋 Usar planilha recém-corrigida (da sessão atual)", "📁 Fazer upload de uma nova planilha"],
            index=0, key="fonte_igpm"
        )
    else:
        fonte = "📁 Fazer upload de uma nova planilha"

    df_igpm = None
    if fonte.startswith("📋") and has_session_df:
        df_igpm = st.session_state["df_correcao"]
        st.success(f"✅ Usando planilha com {len(df_igpm)} parcelas da sessão atual.")
    else:
        uploaded_igpm = st.file_uploader(
            "Selecione o arquivo Excel (.xlsx ou .xls)",
            type=["xlsx", "xls"],
            key="excel_igpm",
            help="Planilha com a lista completa de parcelas numeradas/ordenadas."
        )
        if uploaded_igpm:
            igpm_bytes = uploaded_igpm.read()
            df_igpm, _ = excel_service.carregar_excel(igpm_bytes)

    if df_igpm is not None:
        st.markdown("---")
        st.subheader("📌 Mapeamento de Colunas para IGP-M")

        cols = list(df_igpm.columns)

        auto_data = None
        auto_valor = None
        for c in cols:
            cl = str(c).lower()
            if not auto_data and any(k in cl for k in ['data', 'dt', 'vencimento', 'pagamento']):
                auto_data = c
            if not auto_valor and any(k in cl for k in ['valor', 'val', 'quantia', 'preco', 'preço', 'montante']):
                auto_valor = c

        idx_data = cols.index(auto_data) if auto_data in cols else 0
        idx_val = cols.index(auto_valor) if auto_valor in cols else min(1, len(cols)-1)

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            igpm_col_data = st.selectbox(
                "📅 Coluna da Data de Vencimento/Pagamento",
                options=cols,
                index=idx_data,
                key="igpm_cd",
                help="Coluna com as datas das parcelas para delimitar os períodos de 12 meses."
            )
            sample_dt_igpm = get_column_samples(df_igpm, igpm_col_data)
            st.markdown(f'<div class="sample-box"><b>🔍 Amostra:</b> {sample_dt_igpm}</div>', unsafe_allow_html=True)

        with col_m2:
            igpm_col_valor = st.selectbox(
                "💰 Coluna do Valor da Parcela (R$)",
                options=cols,
                index=idx_val,
                key="igpm_cv",
                help="Coluna com o valor base inicial das parcelas."
            )
            sample_val_igpm = get_column_samples(df_igpm, igpm_col_valor)
            st.markdown(f'<div class="sample-box"><b>🔍 Amostra:</b> {sample_val_igpm}</div>', unsafe_allow_html=True)

        st.write("#### 👁️ Pré-visualização da Planilha:")
        st.dataframe(df_igpm.head(12).astype(str), use_container_width=True)

        n_parcelas = len(df_igpm)
        n_ciclos = (n_parcelas + 11) // 12
        st.info(f"📌 Total: **{n_parcelas} parcela(s)** → **{n_ciclos} ciclo(s) de 12 meses**. "
                f"{'O 1º ciclo (parcelas 1-12) mantém o valor base.' if n_ciclos >= 1 else ''} "
                f"{'Serão feitas ' + str(n_ciclos - 1) + ' consulta(s) ao BCB.' if n_ciclos > 1 else ''}")

        st.markdown("---")

        if st.button("📈 Calcular Reajuste IGP-M e Gerar Relatório", type="primary", use_container_width=True):
            importlib.reload(igpm_service)
            importlib.reload(bcb_service)
            importlib.reload(word_service)

            progress_text = st.empty()
            progress_bar = st.progress(0)

            progress_text.markdown("⏳ Processando reajustes anuais de IGP-M no Banco Central...")

            resultados_ciclo, valores_corrigidos = igpm_service.calcular_igpm_ciclico(
                df=df_igpm,
                col_data=igpm_col_data,
                col_valor=igpm_col_valor,
                ciclo=12,
                use_playwright=False
            )

            progress_bar.progress(100)
            progress_text.success(f"🎉 {len(resultados_ciclo)} ciclo(s) de IGP-M processados com sucesso!")
            st.balloons()

            # Prepare word results
            word_resultados = []
            for rc in resultados_ciclo:
                rc["descricao"] = f"Ciclo {rc.get('ciclo_numero', '?')} — Parcelas {rc.get('parcelas', '?')}"
                rc["valor_original_num"] = rc.get("valor_antes", 0)
                word_resultados.append(rc)

            # DataFrame with corrected column
            df_resultado = df_igpm.copy()
            df_resultado["Correção IGP-M (R$)"] = valores_corrigidos

            # KPI Calculations
            val_base_1 = valores_corrigidos[0] if valores_corrigidos else 0.0
            val_final_ult = valores_corrigidos[-1] if valores_corrigidos else 0.0
            soma_original = sum(safe_parse_float(v) for v in df_igpm[igpm_col_valor])
            soma_corrigida = sum(valores_corrigidos)
            dif_igpm = soma_corrigida - soma_original

            st.markdown("### 📊 Resumo do Reajuste por IGP-M")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Total de Parcelas", f"{n_parcelas}")
            k2.metric("Valor Inicial (Ciclo 1)", format_currency_br(val_base_1))
            k3.metric("Valor Final (Último Ciclo)", format_currency_br(val_final_ult))
            k4.metric("Aumento Acumulado", format_currency_br(dif_igpm), delta=f"R$ {dif_igpm:,.2f}")

            st.markdown("---")

            # Word generation
            word_bytes = word_service.gerar_relatorio_word(
                word_resultados,
                df_original=df_resultado,
                titulo="Relatório de Correção por IGP-M (FGV) — Ciclos de 12 Meses"
            )

            # Excel generation
            excel_buf = io.BytesIO()
            with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
                df_resultado.to_excel(writer, index=False, sheet_name='Parcelas com IGP-M')
            excel_out = excel_buf.getvalue()

            st.markdown("### 📥 Baixar Relatórios do IGP-M")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.download_button(
                    "📄 Relatório Word com Comprovantes (.docx)",
                    data=word_bytes,
                    file_name=f"Relatorio_IGPM_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
            with col_d2:
                st.download_button(
                    "📊 Planilha Excel com IGP-M (.xlsx)",
                    data=excel_out,
                    file_name=f"Parcelas_IGPM_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

            st.markdown("---")
            st.subheader("📊 Detalhes dos Ciclos de Reajuste")

            for rc in resultados_ciclo:
                ciclo_n = rc.get("ciclo_numero", "?")
                parcelas = rc.get("parcelas", "?")
                val_antes = rc.get("valor_antes", 0)
                val_depois = rc.get("valor_depois", 0)
                fator = rc.get("fator_correcao", "-")
                perc = rc.get("percentual", "-")
                dt_ini = rc.get("data_calculo_inicio", "-")
                dt_fim = rc.get("data_calculo_fim", "-")

                with st.expander(f"🔄 Ciclo {ciclo_n} — Parcelas {parcelas}", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Valor Anterior", format_currency_br(val_antes))
                    c2.metric("Fator IGP-M Acumulado", str(fator))
                    c3.metric("Novo Valor Reajustado", format_currency_br(val_depois))
                    st.caption(f"📅 Período BCB: {dt_ini} → {dt_fim} | Percentual: {perc}")

                    if rc.get("screenshot_bytes"):
                        st.image(rc["screenshot_bytes"], use_column_width=True, caption=f"Comprovante BCB — IGP-M Ciclo {ciclo_n}")

    else:
        st.markdown("""
        <div class="wizard-card">
            <div class="wizard-icon">📈</div>
            <div class="wizard-title">Cálculo de IGP-M por Ciclos de 12 Meses</div>
            <div class="wizard-subtitle">
                Selecione a planilha da sessão ou faça upload de um arquivo contendo a listagem das parcelas para calcular os reajustes anuais acumulados.
            </div>
        </div>
        """, unsafe_allow_html=True)

# Footer
st.markdown("""
<div class="app-footer">
    🏦 <b>Atualizador Monetário BCB</b> | Integrado à Calculadora do Cidadão do Banco Central do Brasil<br>
    Formatos exportados: Microsoft Word (.docx) & Microsoft Excel (.xlsx)<br>
    <span style="font-size:11px; color:#64748b;">Versão 1.2 (Fontes Tahoma Embarcadas)</span>
</div>
""", unsafe_allow_html=True)
