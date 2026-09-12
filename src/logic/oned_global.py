import time
import re
from playwright.sync_api import sync_playwright

def obtener_metricas_oned_1d():
    """
    Navega a la plataforma ONED usando el evento rápido 'load'.
    Soporta reintentos ante caídas de DNS corporativos.
    """
    url = "https://oned.global/#/"
    max_intentos = 3
    
    for intento in range(1, max_intentos + 1):
        print(f"🕵️‍♂️ [ONED] Intento {intento} de {max_intentos}...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-gl-drawing-for-tests"])
            context = browser.new_context()
            page = context.new_page()
            
            try:
                # 🌐 Cambiado de 'networkidle' a 'load' para evitar congelamientos por DNS empresarial
                page.goto(url, wait_until="load", timeout=25000) 
                
                page.wait_for_selector("article", timeout=15000)
                page.locator("article").first.scroll_into_view_if_needed()
                
                btn_1d_tokenized = page.locator("article:has(h3:has-text('Tokenized Volume'))").locator("button:has-text('1d')")
                btn_1d_transaction = page.locator("article:has(h3:has-text('Transaction Volume'))").locator("button:has-text('1d')")
                
                btn_1d_tokenized.click()
                btn_1d_transaction.click()
                
                page.wait_for_timeout(5000)
                
                contenedor_tok = page.locator("article:has(h3:has-text('Tokenized Volume'))").locator("strong.bs-card__value")
                contenedor_tx = page.locator("article:has(h3:has-text('Transaction Volume'))").locator("strong.bs-card__value")
                
                val_tok_raw = contenedor_tok.get_attribute("aria-label")
                val_tx_raw = contenedor_tx.get_attribute("aria-label")
                
                if not val_tok_raw or not val_tx_raw:
                    raise ValueError("Etiquetas aria-label no listas.")
                
                tokenized_val = int(re.sub(r'[^0-9]', '', val_tok_raw)) if any(c.isdigit() for c in val_tok_raw) else 0
                transaction_val = int(re.sub(r'[^0-9]', '', val_tx_raw)) if any(c.isdigit() for c in val_tx_raw) else 0
                
                if tokenized_val > 0 or transaction_val > 0:
                    print(f"✅ [ONED] Éxito en el intento {intento}.")
                    context.close(); browser.close()
                    return {"tokenized": tokenized_val, "transaction": transaction_val}
                else:
                    raise ValueError("Valores en cero.")
                    
            except Exception as e:
                print(f"⚠️ Intento {intento} fallido: {e}")
                context.close(); browser.close()
                if intento < max_intentos:
                    time.sleep(3)
                    
    print("❌ [ONED] Se agotaron los intentos. Retornando ceros de contingencia.")
    return {"tokenized": 0, "transaction": 0}