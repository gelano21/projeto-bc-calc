"""
igpm_service.py — Serviço de Correção por IGP-M (FGV) em Ciclos de 12 Meses

Regras de negócio:
- Parcelas 1-12: valor original (sem correção IGP-M)
- Parcelas 13-24: valor × fator IGP-M acumulado dos meses do ciclo 1 (mês da parcela 1 ao mês da parcela 12)
- Parcelas 25-36: valor_ciclo2 × fator IGP-M acumulado dos meses do ciclo 2
- O fator acumula em cascata (cada ciclo corrige sobre o valor já corrigido do ciclo anterior)
- Datas do cálculo BCB: dia 01 do mês da 1ª parcela do ciclo → dia 01 do mês da última parcela do ciclo
"""

import datetime
import pandas as pd
import bcb_service


def extrair_mes_ano(date_val):
    """Extrai (mês, ano) de um valor de data, retornando como datetime.date no dia 01."""
    dt_str = bcb_service.parse_date(date_val)
    if not dt_str:
        return None
    try:
        parts = dt_str.split('/')
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        return datetime.date(year, month, 1)
    except Exception:
        return None


def calcular_igpm_ciclico(df, col_data, col_valor, ciclo=12, use_playwright=True):
    """
    Calcula a correção IGP-M em ciclos de N meses (padrão 12).

    Params:
        df: DataFrame com os dados das parcelas (já ordenado por data/parcela)
        col_data: nome da coluna de data de pagamento/vencimento
        col_valor: nome da coluna de valor
        ciclo: número de parcelas por ciclo (padrão 12)
        use_playwright: se True, captura prints reais do BCB

    Returns:
        resultados_por_ciclo: lista de dicts, um por ciclo >= 2, com dados do BCB e print
        valores_corrigidos: lista com o valor corrigido para cada linha do df
    """
    n_total = len(df)
    n_ciclos = (n_total + ciclo - 1) // ciclo

    # Extrair datas e valores base
    datas = []
    valores_base = []
    for i, row in df.iterrows():
        datas.append(row[col_data])
        val = row[col_valor]
        valores_base.append(bcb_service.safe_parse_float(val) if hasattr(bcb_service, 'safe_parse_float') else _safe_float(val))

    # Valor vigente começa como o valor base da primeira parcela válida
    valor_vigente = valores_base[0] if valores_base else 0.0

    # Resultado: valor corrigido por linha
    valores_corrigidos = []
    # Resultados de cada consulta BCB (um por ciclo >= 2)
    resultados_por_ciclo = []

    for c in range(n_ciclos):
        inicio_idx = c * ciclo
        fim_idx = min((c + 1) * ciclo, n_total)

        if c == 0:
            # Primeiro ciclo: sem correção IGP-M
            for i in range(inicio_idx, fim_idx):
                valores_corrigidos.append(valores_base[i])
        else:
            # Ciclo >= 2: calcular IGP-M do ciclo anterior
            ciclo_ant_inicio = (c - 1) * ciclo
            ciclo_ant_fim = min(c * ciclo, n_total) - 1

            # Datas: 01/mês da 1ª parcela do ciclo anterior → 01/mês da última parcela do ciclo anterior
            dt_inicio = extrair_mes_ano(datas[ciclo_ant_inicio])
            dt_fim = extrair_mes_ano(datas[ciclo_ant_fim])

            if dt_inicio and dt_fim:
                data_inicial_bcb = dt_inicio.strftime("%d/%m/%Y")
                data_final_bcb = dt_fim.strftime("%d/%m/%Y")
            else:
                # Fallback: usar as datas diretas das parcelas
                data_inicial_bcb = bcb_service.parse_date(datas[ciclo_ant_inicio])
                data_final_bcb = bcb_service.parse_date(datas[ciclo_ant_fim])

            # Consultar BCB com IGP-M (aba=1), usando o valor vigente do ciclo anterior
            res = bcb_service.processar_calculo_bcb(
                data_inicial=data_inicial_bcb,
                data_final=data_final_bcb,
                valor_input=valor_vigente,
                aba="1",
                use_playwright=use_playwright
            )

            res["ciclo_numero"] = c + 1
            res["parcelas"] = f"{inicio_idx + 1}–{fim_idx}"
            res["valor_antes"] = valor_vigente
            res["data_calculo_inicio"] = data_inicial_bcb
            res["data_calculo_fim"] = data_final_bcb

            if res.get("status") == "Sucesso" and res.get("valor_corrigido_num"):
                valor_vigente = res["valor_corrigido_num"]
                res["valor_depois"] = valor_vigente
            else:
                res["valor_depois"] = valor_vigente

            resultados_por_ciclo.append(res)

            for i in range(inicio_idx, fim_idx):
                valores_corrigidos.append(round(valor_vigente, 2))

    return resultados_por_ciclo, valores_corrigidos


def _safe_float(v):
    """Fallback safe float parser."""
    if pd.isna(v) or v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        s = str(v).replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
        return float(s)
    except Exception:
        return 0.0
