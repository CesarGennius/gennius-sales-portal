import time
import re
import requests

def obtener_metricas_oned_1d():
    """
    Extrae Tokenized Volume (1d) y Transaction Volume (1d) directamente
    mediante HTTP Request ligero, sin consumir la RAM del servidor con Chromium.
    """
    url = "https://oned.global/#/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }

    max_intentos = 3

    for intento in range(1, max_intentos + 1):
        print(f"🕵️‍♂️ [ONED - HTTP] Intento {intento} de {max_intentos}...")
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                html = resp.text
                
                # Búsqueda de valores numéricos en las tarjetas de Tokenized Volume y Transaction Volume
                # Buscar números formateados cerca de las palabras clave
                tok_match = re.search(r'Tokenized\s+Volume.*?class="[^"]*bs-card__value[^"]*"[^>]*>([\d,.]+)', html, re.DOTALL | re.IGNORECASE)
                tx_match = re.search(r'Transaction\s+Volume.*?class="[^"]*bs-card__value[^"]*"[^>]*>([\d,.]+)', html, re.DOTALL | re.IGNORECASE)
                
                tok_val = 0
                tx_val = 0

                if tok_match:
                    raw_str = tok_match.group(1)
                    tok_val = int(re.sub(r'[^\d]', '', raw_str)) if re.sub(r'[^\d]', '', raw_str) else 0

                if tx_match:
                    raw_str = tx_match.group(1)
                    tx_val = int(re.sub(r'[^\d]', '', raw_str)) if re.sub(r'[^\d]', '', raw_str) else 0

                # Fallback por regex si la clase cambia
                if tok_val == 0:
                    tok_m2 = re.search(r'Tokenized\s+Volume[^\d]+([\d,]{4,15})', html, re.IGNORECASE)
                    if tok_m2:
                        tok_val = int(re.sub(r'[^\d]', '', tok_m2.group(1)))

                if tx_val == 0:
                    tx_m2 = re.search(r'Transaction\s+Volume[^\d]+([\d,]{4,15})', html, re.IGNORECASE)
                    if tx_m2:
                        tx_val = int(re.sub(r'[^\d]', '', tx_m2.group(1)))

                if tok_val > 0 or tx_val > 0:
                    print(f"✅ [ONED - HTTP] Éxito: Tokenized={tok_val}, Transaction={tx_val}")
                    return {"tokenized": tok_val, "transaction": tx_val}

        except Exception as e:
            print(f"⚠️ [ONED - HTTP] Intento {intento} fallido: {e}")
            time.sleep(1)

    # Si la SPA requiere renderizado obligatoriamente, intentamos un Playwright ultraliviano con descarte rápido
    print("⚠️ Reintentando con motor secundario ultraliviano...")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--single-process", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(3000)

            val_tok = page.evaluate("""() => {
                const el = Array.from(document.querySelectorAll('div, article')).find(e => e.innerText.includes('Tokenized Volume'));
                if (!el) return 0;
                const strong = el.querySelector('strong, .bs-card__value');
                return strong ? parseInt((strong.getAttribute('aria-label') || strong.innerText).replace(/[^0-9]/g, ''), 10) : 0;
            }""")

            val_tx = page.evaluate("""() => {
                const el = Array.from(document.querySelectorAll('div, article')).find(e => e.innerText.includes('Transaction Volume'));
                if (!el) return 0;
                const strong = el.querySelector('strong, .bs-card__value');
                return strong ? parseInt((strong.getAttribute('aria-label') || strong.innerText).replace(/[^0-9]/g, ''), 10) : 0;
            }""")

            browser.close()
            return {"tokenized": val_tok or 0, "transaction": val_tx or 0}
    except Exception as e_pw:
        print(f"❌ [ONED] Falló fallback secundario: {e_pw}")

    return {"tokenized": 0, "transaction": 0}