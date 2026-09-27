import time
import re
from playwright.sync_api import sync_playwright

def obtener_metricas_oned_1d():
    """
    Extrae con precisión las tarjetas 'Tokenized Volume' y 'Transaction Volume' 
    en su filtro diario '1d'.
    """
    url = "https://oned.global/#/"
    max_intentos = 3
    user_agent_real = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

    for intento in range(1, max_intentos + 1):
        print(f"🕵️‍♂️ [ONED] Intento {intento} de {max_intentos}...")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-gl-drawing-for-tests",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage"
                ]
            )
            
            context = browser.new_context(
                user_agent=user_agent_real,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/Bogota"
            )
            
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=35000)
                page.wait_for_selector("h3:has-text('Tokenized Volume')", timeout=20000)

                # 🟢 1. Localizar los contenedores específicos por título H3 exacto
                card_tok = page.locator("div, article").filter(has=page.locator("h3:has-text('Tokenized Volume')")).first
                card_tx = page.locator("div, article").filter(has=page.locator("h3:has-text('Transaction Volume')")).first

                # 🟢 2. Hacer clic en los botones '1d' dentro de CADA tarjeta específica
                try:
                    btn_1d_tok = card_tok.locator("button:has-text('1d')")
                    if btn_1d_tok.count() > 0:
                        btn_1d_tok.click(timeout=3000)

                    btn_1d_tx = card_tx.locator("button:has-text('1d')")
                    if btn_1d_tx.count() > 0:
                        btn_1d_tx.click(timeout=3000)

                    page.wait_for_timeout(2000)
                except Exception as e_btn:
                    print(f"  ⚠️ [ONED] Aviso interactuando con botones 1d: {e_btn}")

                # 🟢 3. Extraer el valor interno estricto del elemento que contiene la cifra
                val_tok_raw = card_tok.locator(".bs-card__value, strong, span").first.inner_text() or ""
                val_tx_raw = card_tx.locator(".bs-card__value, strong, span").first.inner_text() or ""

                tokenized_val = int(re.sub(r'[^0-9]', '', val_tok_raw)) if any(c.isdigit() for c in val_tok_raw) else 0
                transaction_val = int(re.sub(r'[^0-9]', '', val_tx_raw)) if any(c.isdigit() for c in val_tx_raw) else 0

                if tokenized_val > 0 or transaction_val > 0:
                    print(f"✅ [ONED] Éxito en intento {intento}: Tokenized={tokenized_val}, Transaction={transaction_val}")
                    context.close(); browser.close()
                    return {"tokenized": tokenized_val, "transaction": transaction_val}
                else:
                    raise ValueError(f"Valores en cero (tok_raw='{val_tok_raw}', tx_raw='{val_tx_raw}')")

            except Exception as e:
                print(f"⚠️ Intento {intento} fallido: {e}")
                context.close(); browser.close()
                if intento < max_intentos:
                    time.sleep(3)

    print("❌ [ONED] Se agotaron los intentos. Retornando ceros de contingencia.")
    return {"tokenized": 0, "transaction": 0}