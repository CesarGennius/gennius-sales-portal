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
    Extrae las métricas Tokenized Volume y Transaction Volume de ONED
    Usando JS nativo avanzado para asegurar la lectura de la pestaña '1d'
    y no los valores acumulados por defecto.
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

                        page.route(
                            "**/*",
                            lambda route: route.abort()
                            if route.request.resource_type in ("image", "stylesheet", "font", "media")
                            else route.continue_()
                        )

                        page.goto(url, wait_until="domcontentloaded", timeout=35000)

                        # 🟢 JS inteligente: captura el valor gigante por defecto,
                        # hace clic en 1d y ESPERA hasta que el valor en pantalla cambie.
                        script_JS = """
                        async () => {
                          const delay = ms => new Promise(res => setTimeout(res, ms));
                          
                          let cards = Array.from(document.querySelectorAll('app-bs-card'));
                          let attempts = 0;
                          
                          // Esperar a que Angular dibuje las tarjetas
                          while(cards.length === 0 && attempts < 20) {
                             await delay(1000);
                             cards = Array.from(document.querySelectorAll('app-bs-card'));
                             attempts++;
                          }

                          let oldTokenized = 0;
                          
                          // 1. Leer el valor por defecto que carga la página (ej. los 619 Millones)
                          for (let card of cards) {
                              const h3 = card.querySelector('h3.bs-card__label');
                              const strong = card.querySelector('strong.bs-card__value');
                              if (h3 && strong && h3.innerText.trim() === 'Tokenized Volume') {
                                  const valAria = strong.getAttribute('aria-label') || strong.innerText;
                                  oldTokenized = parseInt(valAria.replace(/[^0-9]/g, ''), 10);
                              }
                          }

                          // 2. Hacer clic en '1d' en ambas tarjetas
                          for (let card of cards) {
                            const h3 = card.querySelector('h3.bs-card__label');
                            if (!h3) continue;
                            const titulo = h3.innerText.trim();
                            if (titulo === 'Tokenized Volume' || titulo === 'Transaction Volume') {
                              const btn1d = Array.from(card.querySelectorAll('button.bs-card__range'))
                                                .find(b => b.innerText.trim().toLowerCase() === '1d');
                              if (btn1d) btn1d.click();
                            }
                          }

                          let tokenized = 0;
                          let transaction = 0;

                          // 3. Polling: chequear la pantalla cada 0.5s hasta que los números cambien
                          for(let i = 0; i < 20; i++) {
                             await delay(500); // Hasta 10 segundos máximo
                             
                             for (let card of cards) {
                                const h3 = card.querySelector('h3.bs-card__label');
                                const strong = card.querySelector('strong.bs-card__value');
                                if (h3 && strong) {
                                  const titulo = h3.innerText.trim();
                                  const valAria = strong.getAttribute('aria-label') || strong.innerText;
                                  const num = parseInt(valAria.replace(/[^0-9]/g, ''), 10);
                                  
                                  if (titulo === 'Tokenized Volume' && !isNaN(num)) tokenized = num;
                                  if (titulo === 'Transaction Volume' && !isNaN(num)) transaction = num;
                                }
                             }
                             
                             // Si el valor ya no es igual al inicial (la API ya respondió)
                             if (tokenized > 0 && tokenized !== oldTokenized) {
                                 return { tokenized, transaction };
                             }
                             
                             // Si desde el principio cargó un valor pequeño (rango diario < 50 Millones)
                             if (tokenized > 0 && tokenized < 50000000) {
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

                    if tokenized_val > 0 or transaction_val > 0:
                        resultado = {"tokenized": tokenized_val, "transaction": transaction_val}
                        _CACHE_ONED["data"] = resultado
                        _CACHE_ONED["timestamp"] = time.time()
                        print(f"✅ [ONED 1d] Éxito en intento {intento}: {resultado}")
                        return resultado
                    else:
                        print(f"  ⚠️ Intento {intento}: La SPA de Angular no terminó de cargar los datos.")

            except Exception as e:
                print(f"⚠️ Intento {intento} fallido: {e}")
                gc.collect()

            if intento < max_intentos:
                time.sleep(1.5)

        print("❌ [ONED] Se agotaron los intentos. Retornando ceros de contingencia.")
        return {"tokenized": 0, "transaction": 0}