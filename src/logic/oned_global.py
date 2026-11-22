import gc
import time
import platform
import threading
from playwright.sync_api import sync_playwright

_CACHE_ONED = {"data": None, "timestamp": 0}
TTL_SEGUNDOS = 900
_ONED_LOCK = threading.Lock()

def obtener_metricas_oned_1d(forzar_actualizacion=False):
    """
    Extrae las métricas Tokenized Volume y Transaction Volume de ONED.
    Lógica blindada: Espera el número gigante por defecto -> Clic en 1d -> Espera el nuevo número.
    """
    with _ONED_LOCK:
        ahora = time.time()
        if (
            not forzar_actualizacion
            and _CACHE_ONED["data"] is not None
            and (ahora - _CACHE_ONED["timestamp"]) < TTL_SEGUNDOS
        ):
            print("⚡ [ONED] Retornando métricas desde caché en memoria.")
            return _CACHE_ONED["data"]

        url = "https://oned.global/#/"
        max_intentos = 2
        user_agent_real = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        if platform.system() == "Windows":
            launch_args = ["--no-sandbox", "--disable-gpu"]
        else:
            launch_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-first-run",
                "--no-zygote",
            ]

        for intento in range(1, max_intentos + 1):
            print(f"🕵️‍♂️ [ONED] Intento {intento} de {max_intentos}...")

            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True, args=launch_args)

                    try:
                        context = browser.new_context(
                            user_agent=user_agent_real,
                            viewport={"width": 1024, "height": 600},
                            locale="en-US"
                        )

                        page = context.new_page()

                        # Bloqueamos recursos visuales para mantener la RAM baja
                        page.route(
                            "**/*",
                            lambda route: route.abort()
                            if route.request.resource_type in ("image", "stylesheet", "font", "media")
                            else route.continue_()
                        )

                        page.goto(url, wait_until="domcontentloaded", timeout=35000)

                        script_JS = """
                        async () => {
                          const delay = ms => new Promise(res => setTimeout(res, ms));
                          
                          // 1. Esperar a que las tarjetas existan en el DOM
                          let cards = [];
                          for(let i = 0; i < 30; i++) {
                             cards = Array.from(document.querySelectorAll('app-bs-card'));
                             if(cards.length > 0) break;
                             await delay(500);
                          }

                          // 2. OBLIGATORIO: Esperar a que el número GIGANTE por defecto se pinte (> 0)
                          let initialTokenized = 0;
                          for(let i = 0; i < 30; i++) {
                             for (let card of cards) {
                                const h3 = card.querySelector('h3.bs-card__label');
                                if (h3 && h3.innerText.trim() === 'Tokenized Volume') {
                                   const strong = card.querySelector('strong.bs-card__value');
                                   if(strong) {
                                      const val = parseInt((strong.getAttribute('aria-label') || strong.innerText).replace(/[^0-9]/g, ''), 10);
                                      if(!isNaN(val) && val > 0) initialTokenized = val;
                                   }
                                }
                             }
                             if (initialTokenized > 0) break;
                             await delay(500);
                          }

                          // Si la página se quedó en blanco, abortar intento
                          if (initialTokenized === 0) return { tokenized: 0, transaction: 0 };

                          // 3. Hacer clic en el botón '1d'
                          for (let card of cards) {
                            const h3 = card.querySelector('h3.bs-card__label');
                            if (!h3) continue;
                            const titulo = h3.innerText.trim();
                            if (titulo === 'Tokenized Volume' || titulo === 'Transaction Volume') {
                              const btn1d = Array.from(card.querySelectorAll('button.bs-card__range'))
                                                .find(b => b.innerText.trim().toLowerCase() === '1d');
                              if (btn1d) {
                                 btn1d.click();
                                 // Forzar el evento por si Angular lo necesita
                                 btn1d.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                                 btn1d.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                              }
                            }
                          }

                          let tokenized = 0;
                          let transaction = 0;
                          
                          // 4. Esperar a que el número CAMBIE (sea diferente al initialTokenized gigante)
                          for(let i = 0; i < 40; i++) { 
                             await delay(500); // Dar tiempo a la API de ONED para responder
                             
                             for (let card of cards) {
                                const h3 = card.querySelector('h3.bs-card__label');
                                const strong = card.querySelector('strong.bs-card__value');
                                if (h3 && strong) {
                                  const titulo = h3.innerText.trim();
                                  const val = parseInt((strong.getAttribute('aria-label') || strong.innerText).replace(/[^0-9]/g, ''), 10);
                                  
                                  if (titulo === 'Tokenized Volume' && !isNaN(val)) tokenized = val;
                                  if (titulo === 'Transaction Volume' && !isNaN(val)) transaction = val;
                                }
                             }
                             
                             // CRÍTICO: Solo salimos si el valor actual es diferente al inicial
                             if (tokenized > 0 && tokenized !== initialTokenized) {
                                 await delay(1000); // Dar 1 seg extra para que 'Transaction' también actualice
                                 
                                 // Leer los valores finales
                                 for (let card of cards) {
                                    const h3 = card.querySelector('h3.bs-card__label');
                                    const strong = card.querySelector('strong.bs-card__value');
                                    if (h3 && strong) {
                                      const titulo = h3.innerText.trim();
                                      const val = parseInt((strong.getAttribute('aria-label') || strong.innerText).replace(/[^0-9]/g, ''), 10);
                                      if (titulo === 'Tokenized Volume' && !isNaN(val)) tokenized = val;
                                      if (titulo === 'Transaction Volume' && !isNaN(val)) transaction = val;
                                    }
                                 }
                                 return { tokenized, transaction };
                             }
                          }
                          
                          return { tokenized, transaction };
                        }
                        """

                        datos = page.evaluate(script_JS)
                        tokenized_val = datos.get("tokenized", 0)
                        transaction_val = datos.get("transaction", 0)

                    finally:
                        browser.close()
                        gc.collect()

                    # Validamos que el resultado no sea el valor gigante de contingencia
                    if tokenized_val > 0 and tokenized_val < 50000000:
                        resultado = {"tokenized": tokenized_val, "transaction": transaction_val}
                        _CACHE_ONED["data"] = resultado
                        _CACHE_ONED["timestamp"] = time.time()
                        print(f"✅ [ONED 1d] Éxito en intento {intento}: {resultado}")
                        return resultado
                    else:
                        print(f"  ⚠️ Intento {intento}: El valor no cambió al rango diario.")

            except Exception as e:
                print(f"⚠️ Intento {intento} fallido: {e}")
                gc.collect()

            if intento < max_intentos:
                time.sleep(1.5)

        print("❌ [ONED] Se agotaron los intentos. Retornando ceros de contingencia.")
        return {"tokenized": 0, "transaction": 0}