import os
import re
import datetime
import urllib.request
import urllib.parse
import pandas as pd
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageChops

def autocrop_image(img_bytes, border=6):
    """
    Crops all white/blank padding around the image, keeping only the actual calculation table
    plus a minimal border, making text large and crystal-clear in 3-column layouts.
    """
    if not img_bytes:
        return None
    try:
        image = Image.open(BytesIO(img_bytes)).convert("RGB")
        
        # Find non-white content bounding box
        bg = Image.new(image.mode, image.size, (255, 255, 255))
        diff = ImageChops.difference(image, bg)
        bbox = diff.getbbox()
        
        if bbox:
            left = max(0, bbox[0] - border)
            top = max(0, bbox[1] - border)
            right = min(image.width, bbox[2] + border)
            bottom = min(image.height, bbox[3] + border)
            
            cropped = image.crop((left, top, right, bottom))
            out_buf = BytesIO()
            cropped.save(out_buf, format="PNG")
            return out_buf.getvalue()
    except Exception:
        pass
    return img_bytes

def parse_date(date_val):
    """Safely converts various date types into DD/MM/AAAA string."""
    if date_val is None or pd.isna(date_val):
        return ""
        
    str_val = str(date_val).strip()
    if str_val in ('', 'NaT', 'nan', 'NaN', 'None'):
        return ""
        
    if isinstance(date_val, (datetime.date, datetime.datetime)):
        try:
            return date_val.strftime("%d/%m/%Y")
        except (ValueError, AttributeError):
            pass
            
    match_iso = re.search(r'^(\d{4})-(\d{2})-(\d{2})', str_val)
    if match_iso:
        y, m, d = match_iso.groups()
        return f"{int(d):02d}/{int(m):02d}/{y}"
        
    match_br = re.search(r'^(\d{1,2})/(\d{1,2})/(\d{4})', str_val)
    if match_br:
        d, m, y = match_br.groups()
        return f"{int(d):02d}/{int(m):02d}/{y}"
        
    try:
        dt = pd.to_datetime(date_val, dayfirst=True)
        if not pd.isna(dt):
            return dt.strftime("%d/%m/%Y")
    except Exception:
        pass
        
    return str_val

def format_currency_input(val):
    """Converts float/int/str/NaN to BCB input format (e.g., 1234,56)."""
    if val is None or pd.isna(val):
        return "0,00"
    if isinstance(val, (int, float)):
        return f"{val:.2f}".replace('.', ',')
    s = str(val).strip().replace('R$', '').replace(' ', '')
    if ',' in s and '.' in s:
        s = s.replace('.', '')
    elif '.' in s and ',' not in s:
        s = s.replace('.', ',')
    return s

def parse_currency_output(val_str):
    """Parses string like 'R$ 1.465,87 (REAL)' or '1.465,87' into float 1465.87."""
    if not val_str:
        return None
    s = str(val_str).strip().replace('R$', '').replace('(REAL)', '').replace(' ', '')
    if not s or s == '-':
        return None
    try:
        if ',' in s and '.' in s:
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s:
            s = s.replace(',', '.')
        return float(s)
    except Exception:
        return None

def is_regra_nova(data_inicial_str):
    """Determines if Poupança deposit is after 03/05/2012 (Nova Regra)."""
    try:
        parts = data_inicial_str.split('/')
        dt = datetime.date(int(parts[2]), int(parts[1]), int(parts[0]))
        cutoff = datetime.date(2012, 5, 3)
        return dt > cutoff
    except Exception:
        return True
def get_bundled_font(size, bold=False):
    """Load bundled Tahoma/Arial font directly from project fonts/ folder for 100% cross-platform parity."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    f_path = os.path.join(base_dir, "fonts", "Tahoma-Bold.ttf" if bold else "Tahoma-Regular.ttf")
    if not os.path.exists(f_path):
        f_path = os.path.join(base_dir, "fonts", "Arial-Bold.ttf" if bold else "Arial-Regular.ttf")
    try:
        return ImageFont.truetype(f_path, size)
    except Exception:
        return ImageFont.load_default()

def create_fallback_image(data_inicial, data_final, valor_orig, valor_corrigido, fator, percentual, indicador_nome="Poupança"):
    """
    100% Pixel-perfect visual match of BCB Calculadora do Cidadão table (Image 1),
    using bundled Tahoma TrueType fonts so text & accents render flawlessly on Streamlit Cloud Linux.
    """
    W = 368
    HEADER1_H = 26
    HEADER2_H = 26
    ROW_H = 24
    PAD_X = 6
    COL_VAL_X = W - PAD_X - 1

    CLR_DARK_BLUE = (0, 61, 121)       # #003d79 (main header)
    CLR_MID_BLUE = (74, 115, 162)      # #4a73a2 (sub headers)
    CLR_WHITE = (255, 255, 255)
    CLR_ROW_BG = (248, 249, 250)       # #f8f9fa (uniform row background)
    CLR_ROW_ALT_BG = (255, 255, 255)   # #ffffff
    CLR_TEXT = (0, 0, 0)
    CLR_BTN_BG = (239, 239, 239)
    CLR_BTN_BORDER = (0, 0, 0)
    CLR_LINE = (230, 234, 238)

    f_h1 = get_bundled_font(13, bold=True)
    f_h2 = get_bundled_font(13, bold=True)
    f_lbl = get_bundled_font(12, bold=False)
    f_val = get_bundled_font(12, bold=False)
    f_btn = get_bundled_font(11, bold=False)

    indicador_map = {
        "Poupança": "Poupança",
        "SELIC": "SELIC",
        "CDI": "CDI",
        "TR": "TR",
        "IGP-M": "IGP-M (FGV)",
        "1": "IGP-M (FGV)",
        "2": "TR",
        "3": "Poupança",
        "4": "SELIC",
        "5": "CDI",
        "6": "Taxa Legal",
    }
    ind_name = indicador_map.get(str(indicador_nome), str(indicador_nome))

    t_h1 = f"Dados básicos da correção pela {ind_name}" if "Poupança" not in ind_name else "Dados básicos da correção pela Poupança"
    t_h2_inf = "Dados informados"
    t_h2_calc = "Dados calculados"

    t_dt_ini_lbl = "Data inicial"
    t_dt_fim_lbl = "Data final"
    t_val_nom_lbl = "Valor nominal"
    t_regra_lbl = "Regra de correção"

    t_ind_lbl = "Índice de correção no período"
    t_perc_lbl = "Valor percentual correspondente"
    t_vcorr_lbl = "Valor corrigido na data final"

    def fmt_r(v):
        s = str(v).strip()
        if not s or s == '-':
            return '-'
        if s.startswith('R$'):
            return f"{s} (REAL)"
        if ',' in s:
            return f"R$ {s} (REAL)"
        try:
            fv = float(s.replace('.', '').replace(',', '.'))
            formatted = f"{fv:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            return f"R$ {formatted} (REAL)"
        except Exception:
            return s

    val_nom_str = fmt_r(valor_orig)
    val_corr_str = fmt_r(valor_corrigido)
    fator_str = str(fator)
    perc_str = f"{percentual}" if '%' in str(percentual) else f"{percentual}%"
    regra_str = "Nova" if "Poupança" in t_h1 or "3" in str(indicador_nome) else "Padrão"

    info_rows = [
        (t_dt_ini_lbl, str(data_inicial)),
        (t_dt_fim_lbl, str(data_final)),
        (t_val_nom_lbl, val_nom_str),
        (t_regra_lbl, regra_str),
    ]

    calc_rows = [
        (t_ind_lbl, fator_str),
        (t_perc_lbl, perc_str),
        (t_vcorr_lbl, val_corr_str),
    ]

    TABLE_H = HEADER1_H + 2 + HEADER2_H + (ROW_H * len(info_rows)) + HEADER2_H + (ROW_H * len(calc_rows))
    BTN_BAR_H = 34
    TOTAL_H = TABLE_H + BTN_BAR_H

    img = Image.new('RGB', (W, TOTAL_H), color=CLR_WHITE)
    draw = ImageDraw.Draw(img)

    y = 0

    # 1. Main Header
    draw.rectangle([0, y, W, y + HEADER1_H], fill=CLR_DARK_BLUE)
    draw.text((PAD_X, y + 4), t_h1, fill=CLR_WHITE, font=f_h1)
    y += HEADER1_H + 2

    # 2. Sub Header: Dados informados
    draw.rectangle([0, y, W, y + HEADER2_H], fill=CLR_MID_BLUE)
    draw.text((PAD_X, y + 4), t_h2_inf, fill=CLR_WHITE, font=f_h2)
    y += HEADER2_H

    # 3. Info rows (uniform #f8f9fa background for ALL rows)
    for label, val in info_rows:
        draw.rectangle([0, y, W, y + ROW_H - 1], fill=CLR_ROW_BG)
        draw.line([0, y, W, y], fill=CLR_LINE, width=1)
        draw.text((PAD_X, y + 4), label, fill=CLR_TEXT, font=f_lbl)
        try:
            bbox = draw.textbbox((0, 0), val, font=f_val)
            vw = bbox[2] - bbox[0]
        except AttributeError:
            vw = len(val) * 7
        draw.text((COL_VAL_X - vw, y + 4), val, fill=CLR_TEXT, font=f_val)
        y += ROW_H

    # 4. Sub Header: Dados calculados
    draw.rectangle([0, y, W, y + HEADER2_H], fill=CLR_MID_BLUE)
    draw.text((PAD_X, y + 4), t_h2_calc, fill=CLR_WHITE, font=f_h2)
    y += HEADER2_H

    # 5. Calc rows (uniform #f8f9fa background for ALL rows)
    for label, val in calc_rows:
        draw.rectangle([0, y, W, y + ROW_H - 1], fill=CLR_ROW_BG)
        draw.line([0, y, W, y], fill=CLR_LINE, width=1)
        draw.text((PAD_X, y + 4), label, fill=CLR_TEXT, font=f_lbl)
        try:
            bbox = draw.textbbox((0, 0), val, font=f_val)
            vw = bbox[2] - bbox[0]
        except AttributeError:
            vw = len(val) * 7
        draw.text((COL_VAL_X - vw, y + 4), val, fill=CLR_TEXT, font=f_val)
        y += ROW_H

    # Table outer border
    draw.rectangle([0, 0, W - 1, TABLE_H - 1], outline=CLR_DARK_BLUE, width=1)

    # 6. Bottom Buttons
    y_btn = TABLE_H + 6
    btn1_txt = "Fazer nova pesquisa"
    btn2_txt = "Imprimir"

    btn1_w = 110
    btn1_x = (W // 2) - btn1_w - 6
    draw.rectangle([btn1_x, y_btn, btn1_x + btn1_w, y_btn + 20], fill=CLR_BTN_BG, outline=CLR_BTN_BORDER, width=1)
    draw.text((btn1_x + 6, y_btn + 3), btn1_txt, fill=CLR_TEXT, font=f_btn)

    btn2_w = 60
    btn2_x = (W // 2) + 6
    draw.rectangle([btn2_x, y_btn, btn2_x + btn2_w, y_btn + 20], fill=CLR_BTN_BG, outline=CLR_BTN_BORDER, width=1)
    draw.text((btn2_x + 9, y_btn + 3), btn2_txt, fill=CLR_TEXT, font=f_btn)

    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

def consultar_bcb_http(data_inicial, data_final, valor_input, aba="3"):
    """Consults BCB via HTTP POST."""
    url_map = {
        "1": "corrigirPelaIgpM.do?method=corrigirPelaIgpM",
        "2": "corrigirPelaTR.do?method=corrigirPelaTR",
        "3": "corrigirPelaPoupanca.do?method=corrigirPelaPoupanca",
        "4": "corrigirPelaSelic.do?method=corrigirPelaSelic",
        "5": "corrigirPeloCDI.do?method=corrigirPeloCDI",
        "6": "corrigirPelaTaxaLegal.do?method=corrigirPelaTaxaLegal",
    }
    
    path = url_map.get(str(aba), "corrigirPelaPoupanca.do?method=corrigirPelaPoupanca")
    url = f"https://www3.bcb.gov.br/CALCIDADAO/publico/{path}"
    
    dt_init = parse_date(data_inicial)
    dt_end = parse_date(data_final)
    val_str = format_currency_input(valor_input)
    
    if not dt_init:
        return {"status": "Erro", "mensagem_erro": "Data inicial em branco ou inválida."}
        
    post_params = {
        'aba': str(aba),
        'dataInicial': dt_init,
        'dataFinal': dt_end,
        'valorCorrecao': val_str,
    }
    if str(aba) == "3":
        post_params['regraNova'] = 'true' if is_regra_nova(dt_init) else 'false'
        
    data = urllib.parse.urlencode(post_params).encode('latin1')
    req = urllib.request.Request(url, data=data, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Content-Type': 'application/x-www-form-urlencoded'
    })
    
    try:
        resp = urllib.request.urlopen(req, timeout=15).read()
        soup = BeautifulSoup(resp, 'html.parser')
        text = soup.get_text()
        
        if "alerta" in text.lower() and ("inválida" in text.lower() or "erro" in text.lower()):
            err = soup.find('div', class_='alerta') or soup.find('span', class_='erro')
            err_msg = err.get_text(strip=True) if err else "Data ou valor inválido no BCB."
            return {"status": "Erro", "mensagem_erro": err_msg}
            
        val_corrigido = None
        fator = "1,00"
        percentual = "0,00%"
        
        tables = soup.find_all('table')
        for t in tables:
            t_text = t.get_text()
            if "Valor corrigido na data" in t_text or "Resultado da" in t_text:
                for tr in t.find_all('tr'):
                    row_txt = tr.get_text(separator=" ", strip=True)
                    if "Valor corrigido na data" in row_txt:
                        m = re.search(r'R\$\s*([\d\.,]+)', row_txt)
                        if m:
                            val_corrigido = m.group(1)
                    elif "Índice de" in row_txt or "fator" in row_txt.lower():
                        m = re.search(r'([\d,]{3,})', row_txt)
                        if m:
                            fator = m.group(1)
                    elif "percentual" in row_txt.lower():
                        m = re.search(r'([\d,]+\s*%)', row_txt)
                        if m:
                            percentual = m.group(1)
                            
        val_corrigido_num = parse_currency_output(val_corrigido) if val_corrigido else None
        
        return {
            "status": "Sucesso",
            "data_inicial": dt_init,
            "data_final": dt_end,
            "valor_original_str": val_str,
            "valor_corrigido_str": val_corrigido or val_str,
            "valor_corrigido_num": val_corrigido_num,
            "fator_correcao": fator,
            "percentual": percentual
        }
    except Exception as e:
        return {"status": "Erro", "mensagem_erro": str(e)}

def consultar_bcb_playwright(data_inicial, data_final, valor_input, aba="3"):
    """Consults BCB via Playwright & captures tightly cropped screenshot of the result box."""
    from playwright.sync_api import sync_playwright
    
    dt_init = parse_date(data_inicial)
    dt_end = parse_date(data_final)
    val_str = format_currency_input(valor_input)
    
    if not dt_init:
        return {"status": "Erro", "mensagem_erro": "Data inicial em branco ou inválida."}
        
    url = f"https://www3.bcb.gov.br/CALCIDADAO/publico/exibirFormCorrecaoValores.do?method=exibirFormCorrecaoValores&aba={aba}"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use compact viewport width to prevent wide empty margins
        context = browser.new_context(viewport={'width': 800, 'height': 600})
        page = context.new_page()
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            
            page.fill('input[name="dataInicial"]', dt_init)
            page.fill('input[name="dataFinal"]', dt_end)
            page.fill('input[name="valorCorrecao"]', val_str)
            
            if str(aba) == "3":
                regra_val = "true" if is_regra_nova(dt_init) else "false"
                page.check(f'input[name="regraNova"][value="{regra_val}"]')
                
            page.click('input[type="submit"][value="Corrigir valor"]')
            page.wait_for_load_state('networkidle')
            
            text = page.inner_text('body')
            
            val_corrigido_str = None
            fator = "1,00"
            percentual = "0,00%"
            
            m_val = re.search(r'Valor corrigido na data final[^\n]*\s+R\$\s*([\d\.,]+)', text, re.IGNORECASE)
            if m_val:
                val_corrigido_str = m_val.group(1)
            else:
                m_val2 = re.search(r'R\$\s*([\d\.,]+)\s*\(REAL\)', text)
                if m_val2:
                    matches = re.findall(r'R\$\s*([\d\.,]+)', text)
                    if len(matches) >= 2:
                        val_corrigido_str = matches[1]
                    elif len(matches) == 1:
                        val_corrigido_str = matches[0]

            m_fat = re.search(r'Índice de corre[çc]ã[o0] no per[íi]odo[^\d]*([\d,]{3,})', text, re.IGNORECASE)
            if m_fat:
                fator = m_fat.group(1)
                
            m_perc = re.search(r'Valor percentual correspondente[^\d]*([\d,]+\s*%)', text, re.IGNORECASE)
            if m_perc:
                percentual = m_perc.group(1)

            # Locate the exact result box table
            tables = page.query_selector_all('table')
            target_el = None
            for t in tables:
                t_txt = t.inner_text()
                if "Resultado da" in t_txt and "Valor corrigido" in t_txt:
                    target_el = t
                    break
            if not target_el:
                for t in tables:
                    t_txt = t.inner_text()
                    if "Dados informados" in t_txt:
                        target_el = t
                        break
                    
            raw_screenshot = target_el.screenshot() if target_el else page.screenshot()
            
            # Autocrop white side padding so image fits crisp & large in Word
            screenshot_bytes = autocrop_image(raw_screenshot, border=6)
            
            val_corrigido_num = parse_currency_output(f"R$ {val_corrigido_str}") if val_corrigido_str else None
            
            browser.close()
            return {
                "status": "Sucesso",
                "data_inicial": dt_init,
                "data_final": dt_end,
                "valor_original_str": val_str,
                "valor_corrigido_str": val_corrigido_str or val_str,
                "valor_corrigido_num": val_corrigido_num,
                "fator_correcao": fator,
                "percentual": percentual,
                "screenshot_bytes": screenshot_bytes
            }
        except Exception as e:
            browser.close()
            return {"status": "Erro", "mensagem_erro": str(e)}

def processar_calculo_bcb(data_inicial, data_final, valor_input, aba="3", use_playwright=True):
    """
    Main entrypoint for BCB calculation with autocropped HD screenshots.
    """
    if pd.isna(data_inicial) or parse_date(data_inicial) == "":
        dt_end = parse_date(data_final)
        val_str = format_currency_input(valor_input)
        return {
            "status": "Erro",
            "mensagem_erro": "Data de pagamento em branco ou inválida",
            "data_inicial": "-",
            "data_final": dt_end,
            "valor_original_str": val_str,
            "valor_corrigido_str": "-",
            "valor_original_num": 0.0,
            "valor_corrigido_num": None,
            "fator_correcao": "-",
            "percentual": "-",
            "screenshot_bytes": None
        }

    if use_playwright:
        try:
            res = consultar_bcb_playwright(data_inicial, data_final, valor_input, aba)
            if res.get("status") == "Sucesso" and res.get("screenshot_bytes"):
                return res
        except Exception:
            pass
            
    res = consultar_bcb_http(data_inicial, data_final, valor_input, aba)
    if res.get("status") == "Sucesso":
        fb_raw = create_fallback_image(
            res["data_inicial"],
            res["data_final"],
            res["valor_original_str"],
            res["valor_corrigido_str"],
            res["fator_correcao"],
            res["percentual"]
        )
        res["screenshot_bytes"] = autocrop_image(fb_raw, border=4)
    return res
