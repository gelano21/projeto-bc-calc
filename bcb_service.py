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
def get_best_font(size, bold=False):
    """Robust cross-platform font loader for Windows, Mac, and Linux/Streamlit Cloud."""
    font_names = [
        "arialbd.ttf" if bold else "arial.ttf",
        "calibri.ttf" if not bold else "calibrib.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()

def create_fallback_image(data_inicial, data_final, valor_orig, valor_corrigido, fator, percentual, indicador_nome="Poupança"):
    """
    Generates a high-legibility 500x317 px result image matching BCB style with crisp text,
    proper font sizing, clear alignment, and perfect accent rendering across all OS platforms.
    """
    W = 500
    HEADER_H = 34
    ROW_H = 30
    PAD_LEFT = 12
    PAD_RIGHT = 12
    COL_VALUE_X = W - PAD_RIGHT

    CLR_DARK_BLUE = (0, 51, 102)        # #003366 — BCB header
    CLR_MID_BLUE = (51, 102, 153)       # #336699 — BCB sub-header
    CLR_WHITE = (255, 255, 255)
    CLR_ROW_BG1 = (242, 246, 250)       # Light row bg
    CLR_ROW_BG2 = (255, 255, 255)
    CLR_TEXT_DARK = (20, 20, 20)
    CLR_BORDER = (220, 230, 240)

    font_header = get_best_font(15, bold=True)
    font_section = get_best_font(14, bold=True)
    font_label = get_best_font(13, bold=False)
    font_value = get_best_font(13, bold=False)
    font_value_bold = get_best_font(14, bold=True)

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
    header_title = f"Dados básicos da correção pela {ind_name}"

    def fmt_val(v):
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

    info_rows = [
        ("Data inicial", str(data_inicial)),
        ("Data final", str(data_final)),
        ("Valor nominal", fmt_val(valor_orig)),
        ("Regra de correção", "Nova" if "Poupança" in ind_name else "Padrão"),
    ]

    calc_rows = [
        ("Índice de correção no período", str(fator)),
        ("Valor percentual correspondente", f"{percentual}" if '%' in str(percentual) else f"{percentual}%"),
        ("Valor corrigido na data final", fmt_val(valor_corrigido)),
    ]

    H = HEADER_H + 2 + HEADER_H + 1 + (ROW_H * len(info_rows)) + HEADER_H + (ROW_H * len(calc_rows)) + 2

    img = Image.new('RGB', (W, H), color=CLR_WHITE)
    draw = ImageDraw.Draw(img)

    y = 0

    # 1. Main Header
    draw.rectangle([0, y, W, y + HEADER_H], fill=CLR_DARK_BLUE)
    draw.text((PAD_LEFT, y + 7), header_title, fill=CLR_WHITE, font=font_header)
    y += HEADER_H + 2

    # 2. Sub Header: Dados informados
    draw.rectangle([0, y, W, y + HEADER_H], fill=CLR_MID_BLUE)
    draw.text((PAD_LEFT, y + 7), "Dados informados", fill=CLR_WHITE, font=font_section)
    y += HEADER_H + 1

    # 3. Info rows
    for i, (label, value) in enumerate(info_rows):
        bg = CLR_ROW_BG1 if i % 2 == 0 else CLR_ROW_BG2
        draw.rectangle([0, y, W, y + ROW_H - 1], fill=bg)
        draw.line([0, y, W, y], fill=CLR_BORDER, width=1)
        draw.text((PAD_LEFT, y + 6), label, fill=CLR_TEXT_DARK, font=font_label)
        try:
            val_bbox = draw.textbbox((0, 0), value, font=font_value)
            val_w = val_bbox[2] - val_bbox[0]
        except AttributeError:
            val_w = len(value) * 8
        draw.text((COL_VALUE_X - val_w, y + 6), value, fill=CLR_TEXT_DARK, font=font_value)
        y += ROW_H

    # 4. Sub Header: Dados calculados
    draw.rectangle([0, y, W, y + HEADER_H], fill=CLR_MID_BLUE)
    draw.text((PAD_LEFT, y + 7), "Dados calculados", fill=CLR_WHITE, font=font_section)
    y += HEADER_H

    # 5. Calc rows
    for i, (label, value) in enumerate(calc_rows):
        bg = CLR_ROW_BG1 if i % 2 == 0 else CLR_ROW_BG2
        draw.rectangle([0, y, W, y + ROW_H - 1], fill=bg)
        draw.line([0, y, W, y], fill=CLR_BORDER, width=1)
        draw.text((PAD_LEFT, y + 6), label, fill=CLR_TEXT_DARK, font=font_label)
        use_font = font_value_bold if i == len(calc_rows) - 1 else font_value
        try:
            val_bbox = draw.textbbox((0, 0), value, font=use_font)
            val_w = val_bbox[2] - val_bbox[0]
        except AttributeError:
            val_w = len(value) * 8
        draw.text((COL_VALUE_X - val_w, y + 6), value, fill=CLR_TEXT_DARK, font=use_font)
        y += ROW_H

    # Border
    draw.rectangle([0, 0, W - 1, H - 1], outline=CLR_DARK_BLUE, width=1)

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
