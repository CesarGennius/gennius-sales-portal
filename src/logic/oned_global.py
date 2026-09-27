import time
from playwright.sync_api import sync_playwright

def obtener_metricas_oned_1d():
    """
    Extrae las métricas Tokenized Volume y Transaction Volume de ONED
    haciendo clic explícito en la pestaña '1d' de cada tarjeta.
    """
    url = "https://oned.global/#/"
    max_intentos = 3
    user_agent_real = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

    for intento in range(1, max_intentos + 1):
        print(f"🕵️‍♂️ [ONED] Intento {intento} de {max_intentos}...")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--single-process",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--no-first-run",
                        "--no-zygote"
                    ]
                )
                
                context = browser.new_context(
                    user_agent=user_agent_real,
                    viewport={"width": 1280, "height": 720},
                    locale="en-US"
                )
                
                page = context.new_page()

                # Navegar y esperar a que Angular renderice los componentes bs-card
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_selector("app-bs-card", timeout=15000)
                page.wait_for_timeout(2000)

                # 🟢 JavaScript a clickea iti "1d" ken mangala ti aria-label
                script_JS = """
                async () => {
                  let tokenized = 0;
                  let transaction = 0;
                  
                  const cards = Array.from(document.querySelectorAll('app-bs-card'));
                  
                  for (let card of cards) {
                    const h3 = card.querySelector('h3.bs-card__label');
                    if (!h3) continue;
                    
                    const titulo = h3.innerText.trim();
                    if (titulo === 'Tokenized Volume' || titulo === 'Transaction Volume') {
                      // Búsqueda y clic en el botón '1d'
                      const btn1d = Array.from(card.querySelectorAll('button.bs-card__range'))
                                        .find(b => b.innerText.trim().toLowerCase() === '1d');
                      if (btn1d) {
                        btn1d.click();
                      }
                    }
                  }

                  // Espera breve para la actualización de datos en el DOM
                  await new Promise(r => setTimeout(r, 1000));

                  cards.forEach(card => {
                    const h3 = card.querySelector('h3.bs-card__label');
                    const strong = card.querySelector('strong.bs-card__value');
                    
                    if (h3 && strong) {
                      const titulo = h3.innerText.trim();
                      const valAria = strong.getAttribute('aria-label') || strong.innerText;
                      const num = parseInt(valAria.replace(/[^0-9]/g, ''), 10);
                      
                      if (titulo === 'Tokenized Volume' && !isNaN(num)) {
                        tokenized = num;
                      }
                      if (titulo === 'Transaction Volume' && !isNaN(num)) {
                        transaction = num;
                      }
                    }
                  });
                  
                  return { tokenized, transaction };
                }
                """

                datos = page.evaluate(script_JS)
                tokenized_val = datos.get("tokenized", 0)
                transaction_val = datos.get("transaction", 0)

                browser.close()

                if tokenized_val > 0 or transaction_val > 0:
                    print(f"✅ [ONED 1d] Éxito en intento {intento}: Tokenized={tokenized_val}, Transaction={transaction_val}")
                    return {"tokenized": tokenized_val, "transaction": transaction_val}
                else:
                    print(f"  ⚠️ Intento {intento}: La SPA de Angular no había completado el renderizado.")

        except Exception as e:
            print(f"⚠️ Intento {intento} fallido: {e}")

        if intento < max_intentos:
            time.sleep(2)

    print("❌ [ONED] Se agotaron los intentos. Retornando ceros de contingencia.")
    return {"tokenized": 0, "transaction": 0}