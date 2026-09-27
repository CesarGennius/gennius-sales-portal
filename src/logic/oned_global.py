import time
import re
from playwright.sync_api import sync_playwright

def obtener_metricas_oned_1d():
    """
    Navega a la plataforma ONED evadiendo bloqueos de Headless/Cloudflare
    y extrayendo los indicadores Tokenized y Transaction Volume.
    """
    url = "https://oned.global/#/"
    max_intentos = 3
    user_agent_real = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

    for intento in range(1, max_intentos + 1):
        print(f"🕵️‍♂️ [ONED] Intento {intento} de {max_intentos}...")

        with sync_playwright() as p:
            # 🟢 Argumentos para evadir la detección antibot en IPs de servidores (Render)
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-gl-drawing-for-tests",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-first-run",
                    "--no-zygote"
                ]
            )
            
            context = browser.new_context(
                user_agent=user_agent_real,
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
                locale="en-US",
                timezone_id="America/Bogota"
            )
            
            page = context.new_page()

            try:
                # 🟢 Navegación con timeout permisivo
                page.goto(url, wait_until="domcontentloaded", timeout=35000)

                # 🟢 Espera flexible por el contenido principal o tarjetas (Soporta múltiples selectores)
                try:
                    page.wait_for_selector("article, .bs-card, h3", timeout=15000)
                except Exception:
                    print("  ⚠️ [ONED] Selector primario no hallado de inmediato, esperando renderizado de SPA...")

                page.wait_for_timeout(3000)

                # Intentar interactuar con los botones de '1d' si existen
                try:
                    btn_1d_tok = page.locator("article:has(h3:has-text('Tokenized Volume')), div:has(h3:has-text('Tokenized Volume'))").locator("button:has-text('1d')")
                    btn_1d_tx = page.locator("article:has(h3:has-text('Transaction Volume')), div:has(h3:has-text('Transaction Volume'))").locator("button:has-text('1d')")
                    
                    if btn_1d_tok.count() > 0:
                        btn_1d_tok.first.click(timeout=3000)
                    if btn_1d_tx.count() > 0:
                        btn_1d_tx.first.click(timeout=3000)
                    
                    page.wait_for_timeout(2000)
                except Exception as e_btn:
                    print(f"  ⚠️ [ONED] Aviso al hacer clic en botones 1d: {e_btn}")

                # 🟢 Búsqueda por clases de valor o aria-label
                contenedor_tok = page.locator("h3:has-text('Tokenized Volume') ~ *, article:has(h3:has-text('Tokenized Volume')) .bs-card__value, strong.bs-card__value").first
                contenedor_tx = page.locator("h3:has-text('Transaction Volume') ~ *, article:has(h3:has-text('Transaction Volume')) .bs-card__value, strong.bs-card__value").last

                val_tok_raw = (contenedor_tok.get_attribute("aria-label") or contenedor_tok.inner_text() or "").strip()
                val_tx_raw = (contenedor_tx.get_attribute("aria-label") or contenedor_tx.inner_text() or "").strip()

                tokenized_val = int(re.sub(r'[^0-9]', '', val_tok_raw)) if any(c.isdigit() for c in val_tok_raw) else 0
                transaction_val = int(re.sub(r'[^0-9]', '', val_tx_raw)) if any(c.isdigit() for c in val_tx_raw) else 0

                if tokenized_val > 0 or transaction_val > 0:
                    print(f"✅ [ONED] Éxito en intento {intento}: Tokenized={tokenized_val}, Transaction={transaction_val}")
                    context.close(); browser.close()
                    return {"tokenized": tokenized_val, "transaction": transaction_val}
                else:
                    raise ValueError(f"Valores extraídos en cero (raw_tok='{val_tok_raw}', raw_tx='{val_tx_raw}')")

            except Exception as e:
                print(f"⚠️ Intento {intento} fallido: {e}")
                context.close(); browser.close()
                if intento < max_intentos:
                    time.sleep(3)

    print("❌ [ONED] Se agotaron los intentos. Retornando ceros de contingencia.")
    return {"tokenized": 0, "transaction": 0}