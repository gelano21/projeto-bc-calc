---
title: Atualizador Monetario BCB
emoji: 🏦
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: 1.35.0
app_file: app.py
pinned: false
---

# 🏦 Atualizador Monetário BCB (Word & Excel)

Sistema web para atualização monetária de tabelas de pagamento utilizando a **Calculadora do Cidadão do Banco Central do Brasil (BCB)**.

---

## 🌟 Funcionalidades

1. **🏦 Correção Monetária Individual**:
   - Leitura de planilhas Excel (`.xlsx` e `.xls`).
   - Mapeamento inteligente e interativo de colunas com pré-visualização de amostras.
   - Atualização por **Poupança**, **SELIC**, **CDI**, **TR** ou **Taxa Legal**.
   - Geração de comprovantes visuais oficiais do Banco Central para cada lançamento.

2. **📈 Reajuste por IGP-M (FGV) em Ciclos de 12 Meses**:
   - Atualização automática em ciclos anuais (parcelas 1-12 mantêm valor base; 13-24 recebem o IGP-M dos 12 meses anteriores de forma acumulada em cascata).
   - Consulta direta ao BCB para cada período anual.

3. **📄 Exportação de Documentos**:
   - **Word (.docx)**: Grade de comprovantes visuais + tabela comparativa com valores originais e corrigidos. Aceita modelo personalizado `.docx`.
   - **Excel (.xlsx)**: Planilha atualizada pronta para uso.

---

## 🚀 Como Executar Localmente

1. Clone o repositório:
```bash
git clone <seu-repositorio>
cd "Projeto BC Calc"
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Execute o Streamlit:
```bash
streamlit run app.py
```

---

## 🌐 Deploy no Streamlit Community Cloud

1. Suba este código para um repositório no seu **GitHub**.
2. Acesse [share.streamlit.io](https://share.streamlit.io).
3. Conecte sua conta do GitHub e escolha este repositório.
4. Defina o arquivo principal como `app.py`.
5. Clique em **Deploy**!
