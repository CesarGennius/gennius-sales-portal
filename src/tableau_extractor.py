import os
import re
import pandas as pd
from PIL import Image

# Importación segura desde el paquete de servicios
try:
    from src.services.ai_service import AIService
except ModuleNotFoundError:
    # Respaldo si el script se ejecuta directamente desde la carpeta src/services/
    try:
        from services.ai_service import AIService
    except ModuleNotFoundError:
        from services.ai_service import AIService


class TableauExtractor:
    def __init__(self):
        self.extracted_df = None
        self.mapping = {
            "CIBC": "CIBC", "FCIB": "CIBC", "FIRST CITIZENS": "FC", "NCB": "NCB",
            "SCOTIA": "Scotia", "CUSCATLAN": "Cuscatlan", "MILESCARE": "MilesCare LifeMiles",
            "CARIBBEAN": "VLS", "GLOBAL": "VLS", "BUTTERFIELD": "VLS", "CLARIEN": "VLS",
            "CAYMAN": "VLS", "AZUL": "VLS", "VMBS": "VLS", "JN BANK": "VLS"
        }

    def procesar_vision_gemini_silencioso(self, img_pil: Image.Image, config_env: dict = None) -> str:
        prompt_estricto = (
            "Actúa como un extractor de datos OCR de precisión matemática avanzada. Tu única tarea es transcribir la tabla "
            "de Tableau que se encuentra en la imagen adjunta.\n\n"
            "REGLAS CRÍTICAS DE EXTRACCIÓN:\n"
            "1. IGNORA COMPLETAMENTE la columna llamada 'Grand Total' o cualquier columna duplicada con acumulados a la derecha. "
            "Solo debes extraer la primera columna de valores numéricos que corresponde a los datos diarios de cada banco.\n"
            "2. Entrega la lista formateada strictly como BANCO: VALOR (ejemplo: CIBC FCIB Bank: 1397685), una fila por cada banco.\n"
            "3. Transcribe las cifras numéricas EXACTAMENTE como aparecen. No aproximes, no redondees ni inventes datos.\n"
            "4. Devuelve ÚNICAMENTE el listado formateado de bancos. No agregues introducciones, saludos ni bloques markdown (```)."
        )

        # Si no se envía config_env explícita, se usa la variable de entorno local por defecto
        if not config_env:
            config_env = {
                "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
                "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
                "HF_API_KEY": os.getenv("HF_API_KEY", ""),
                "MODELO_IA_ACTIVO": os.getenv("MODELO_IA_ACTIVO", "gemini")
            }

        return AIService.extraer_texto_ocr(img_pil, prompt_estricto, config_env)

    def limpiar_datos(self, texto: str) -> pd.DataFrame:
        data = []
        vls_total = 0.0

        for linea in texto.split('\n'):
            separador = ":" if ":" in linea else ("\t" if "\t" in linea else None)
            if separador:
                parts = linea.split(separador, 1)
                n, v = parts[0], parts[1]
                v_clean = v.strip()

                if "," in v_clean and "." not in v_clean:
                    v_clean = v_clean.replace(",", "")
                elif "." in v_clean and "," in v_clean:
                    v_clean = v_clean.replace(".", "")
                    v_clean = v_clean.replace(",", ".")
                elif "," in v_clean and "." in v_clean:
                    v_clean = v_clean.replace(",", "")

                val_limpio = re.sub(r'[^0-9.]', '', v_clean)
                try:
                    val = float(val_limpio) if val_limpio else 0.0
                except ValueError:
                    val = 0.0

                found = False
                for k, name in self.mapping.items():
                    if k.upper() in n.upper():
                        if name == "VLS":
                            vls_total += val
                        else:
                            data.append({'Programa': name, 'TPV': val})
                        found = True
                        break
                if not found:
                    vls_total += val

        df = pd.DataFrame(data)
        if not df.empty:
            df = df.groupby('Programa')['TPV'].sum().reset_index()
        else:
            df = pd.DataFrame(columns=['Programa', 'TPV'])

        df = pd.concat([df, pd.DataFrame([{'Programa': 'VLS', 'TPV': vls_total}])], ignore_index=True)
        programas_oficiales = ["VLS", "CIBC", "NCB", "FC", "Cuscatlan", "Scotia", "MilesCare LifeMiles"]
        filas_nuevas = [{'Programa': pr, 'TPV': 0.0} for pr in programas_oficiales if pr not in df['Programa'].values]
        if filas_nuevas:
            df = pd.concat([df, pd.DataFrame(filas_nuevas)], ignore_index=True)

        return df