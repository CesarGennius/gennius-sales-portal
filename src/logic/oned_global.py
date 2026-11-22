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
    Usando JS nativo para ignorar bloqueos visuales por falta de CSS.
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

                        # 🟢 Bloqueamos estilos e imágenes para ahorrar RAM
                        page.route(
                            "**/*",
                            lambda route: route.abort()
                            if route.request.resource_type in ("image", "stylesheet", "font", "media")
                            else route.continue_()
                        )

                        page.goto(url, wait_until="domcontentloaded", timeout=35000)

                        # 🟢 ELIMINAMOS page.wait_for_selector()
                        # 🟢 Usamos JS puro para esperar a que Angular cree el HTML interno
                        script_JS = """
                        async () => {
                          const delay = ms => new Promise(res => setTimeout(res, ms));
                          
                          // Intentar hasta 20 veces (aprox 15-20 seg)
                          for (let i = 0; i < 20; i++) { 
                            let tokenized = 0;
                            let transaction = 0;
                            const cards = Array.from(document.querySelectorAll('app-bs-card'));
                            
                            if (cards.length > 0) {
                              // Asegurar clic en '1d' (clic JS ignora si el elemento mide 0px)
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

                              await delay(1200); // Esperar que Angular renderice los números

                              // Extraer los datos
                              cards.forEach(card => {
                                const h3 = card.querySelector('h3.bs-card__label');
                                const strong = card.querySelector('strong.bs-card__value');
                                if (h3 && strong) {
                                  const titulo = h3.innerText.trim();
                                  const valAria = strong.getAttribute('aria-label') || strong.innerText;
                                  const num = parseInt(valAria.replace(/[^0-9]/g, ''), 10);
                                  
                                  if (titulo === 'Tokenized Volume' && !isNaN(num)) tokenized = num;
                                  if (titulo === 'Transaction Volume' && !isNaN(num)) transaction = num;
                                }
                              });
                              
                              // Si ya leyó datos válidos, retornar de inmediato
                              if (tokenized > 0 || transaction > 0) {
                                return { tokenized, transaction };
                              }
                            }
                            // Si aún no hay tarjetas o números, esperar medio segundo y reintentar
                            await delay(500);
                          }
                          return { tokenized: 0, transaction: 0 };
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
                        print(f"  ⚠️ Intento {intento}: Angular no inyectó los números a tiempo.")

            except Exception as e:
                print(f"⚠️ Intento {intento} fallido: {e}")
                gc.collect()

            if intento < max_intentos:
                time.sleep(1.5)

        print("❌ [ONED] Se agotaron los intentos. Retornando ceros de contingencia.")
        return {"tokenized": 0, "transaction": 0}