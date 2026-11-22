import gc
import time
import platform
import threading
from playwright.sync_api import sync_playwright

# Caché en memoria para evitar abrir Chromium en cada recarga (TTL: 15 min)
_CACHE_ONED = {"data": None, "timestamp": 0}
TTL_SEGUNDOS = 900

# Lock de concurrencia para garantizar que nunca se abran 2 Chromium simultáneos en Render
_ONED_LOCK = threading.Lock()


def obtener_metricas_oned_1d(forzar_actualizacion=False):
    """
    Extrae las métricas Tokenized Volume y Transaction Volume de ONED
    haciendo clic explícito en la pestaña '1d' de cada tarjeta.
    Optimizado para bajo consumo de RAM en Render Free y compatibilidad con Windows.
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

        # Banderas seguras según Sistema Operativo (evita cierre inesperado en Windows)
        if platform.system() == "Windows":
            launch_args = ["--no-sandbox", "--disable-gpu"]
        else:
            launch_args = [
                "--single-process",
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
                    browser = p.chromium.launch(
                        headless=True,
                        args=launch_args
                    )

                    try:
                        context = browser.new_context(
                            user_agent=user_agent_real,
                            viewport={"width": 1024, "height": 600},
                            locale="en-US"
                        )

                        page = context.new_page()

                        # Bloquear recursos pesados (imágenes, CSS, fuentes, media) para ahorrar RAM
                        page.route(
                            "**/*",
                            lambda route: route.abort()
                            if route.request.resource_type in ("image", "stylesheet", "font", "media")
                            else route.continue_()
                        )

                        # Navegar y esperar a que Angular renderice los componentes bs-card
                        page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        page.wait_for_selector("app-bs-card", timeout=15000)
                        page.wait_for_timeout(1500)

                        # 🟢 JavaScript para hacer clic en "1d" y extraer el aria-label
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

                    finally:
                        browser.close()
                        gc.collect()

                    if tokenized_val > 0 or transaction_val > 0:
                        resultado = {"tokenized": tokenized_val, "transaction": transaction_val}
                        _CACHE_ONED["data"] = resultado
                        _CACHE_ONED["timestamp"] = time.time()
                        print(f"✅ [ONED 1d] Éxito en intento {intento}: Tokenized={tokenized_val}, Transaction={transaction_val}")
                        return resultado
                    else:
                        print(f"  ⚠️ Intento {intento}: La SPA de Angular no había completado el renderizado.")

            except Exception as e:
                print(f"⚠️ Intento {intento} fallido: {e}")
                gc.collect()

            if intento < max_intentos:
                time.sleep(1.5)

        print("❌ [ONED] Se agotaron los intentos. Retornando ceros de contingencia.")
        return {"tokenized": 0, "transaction": 0}