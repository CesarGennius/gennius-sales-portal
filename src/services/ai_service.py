import os
import io
import time
import base64
from abc import ABC, abstractmethod
from PIL import Image

# -------------------------------------------------------------------
# PROVEEDORES DE IA (STRATEGY PATTERN)
# -------------------------------------------------------------------
class BaseAIProvider(ABC):
    @abstractmethod
    def extraer_texto_de_imagen(self, img_pil: Image.Image, prompt: str, api_key: str) -> str:
        pass


class GroqVisionProvider(BaseAIProvider):
    def extraer_texto_de_imagen(self, img_pil: Image.Image, prompt: str, api_key: str) -> str:
        if not api_key:
            raise ValueError("GROQ_API_KEY no configurada.")

        from groq import Groq

        buffered = io.BytesIO()
        img_pil.save(buffered, format="JPEG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        client = Groq(api_key=api_key)
        
        # 🟢 Nombres oficiales estables de visión en Groq
        modelos_groq = [
            "llama-3.2-11b-vision-instruct",
            "llama-3.2-90b-vision-instruct"
        ]

        for model in modelos_groq:
            try:
                print(f"  [Groq Vision] Probando OCR con [{model}]...")
                completion = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}
                                }
                            ]
                        }
                    ],
                    temperature=0.0,
                    max_tokens=1024
                )
                res_text = completion.choices[0].message.content
                if res_text and res_text.strip():
                    print(f"  ✅ [Groq Vision] Éxito en extracción con [{model}]")
                    return res_text
            except Exception as e:
                print(f"  ⚠️ [Groq Vision] Modelo [{model}] no disponible: {str(e)[:100]}...")

        raise RuntimeError("Groq no tiene modelos de Visión/OCR activos en tu cuenta.")


class GeminiVisionProvider(BaseAIProvider):
    def extraer_texto_de_imagen(self, img_pil: Image.Image, prompt: str, api_key: str) -> str:
        if not api_key:
            raise ValueError("GEMINI_API_KEY no configurada.")

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        
        # 🟢 Modelos vigentes oficiales en Google AI Studio (Evita 404 / 503)
        modelos_gemini = ['gemini-2.5-flash', 'gemini-2.5-flash-lite']

        for mod in modelos_gemini:
            for intento in range(3):
                try:
                    print(f"  [Gemini Vision] Probando OCR con [{mod}] (Intento {intento + 1})...")
                    respuesta = client.models.generate_content(
                        model=mod,
                        contents=[prompt, img_pil],
                        config=types.GenerateContentConfig(temperature=0.0)
                    )
                    if respuesta and respuesta.text:
                        print(f"  ✅ [Gemini Vision] Éxito en extracción con [{mod}]")
                        return respuesta.text
                except Exception as e_mod:
                    err_str = str(e_mod)
                    print(f"  ⚠️ [Gemini Vision] Aviso en [{mod}]: {err_str[:100]}...")
                    if "503" in err_str or "UNAVAILABLE" in err_str:
                        time.sleep(1.0)
                    else:
                        break

        raise RuntimeError("Gemini Vision no pudo procesar la imagen.")


class HuggingFaceVisionProvider(BaseAIProvider):
    def extraer_texto_de_imagen(self, img_pil: Image.Image, prompt: str, api_key: str) -> str:
        import requests

        buffered = io.BytesIO()
        img_pil.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')

        # 🟢 Endpoint Serverless optimizado
        url_hf = "https://api-inference.huggingface.co/models/Qwen/Qwen2-VL-7B-Instruct"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        payload = {
            "inputs": {
                "image": f"data:image/jpeg;base64,{img_str}",
                "prompt": prompt
            }
        }

        print("  [Hugging Face] Probando OCR con Qwen2-VL...")
        try:
            res = requests.post(url_hf, headers=headers, json=payload, timeout=15)
            if res.status_code == 200:
                out = res.json()
                texto_hf = out[0].get("generated_text", "") if isinstance(out, list) else str(out)
                if texto_hf:
                    print("  ✅ [Hugging Face] Éxito en extracción OCR.")
                    return texto_hf
        except Exception as e_hf:
            print(f"  ⚠️ [Hugging Face] Error de red / DNS: {e_hf}")

        raise RuntimeError("Hugging Face no pudo procesar la imagen.")


# -------------------------------------------------------------------
# ORQUESTRADOR INTELIGENTE POR USUARIO
# -------------------------------------------------------------------
class AIService:
    MAPA_PROVEEDORES = {
        "gemini": ("Gemini", GeminiVisionProvider(), "GEMINI_API_KEY"),
        "groq": ("Groq", GroqVisionProvider(), "GROQ_API_KEY"),
        "huggingface": ("HuggingFace", HuggingFaceVisionProvider(), "HF_API_KEY")
    }

    @classmethod
    def extraer_texto_ocr(cls, img_pil: Image.Image, prompt: str, config_env: dict) -> str:
        if img_pil.mode in ("RGBA", "P"):
            img_pil = img_pil.convert("RGB")

        modelo_activo = config_env.get("MODELO_IA_ACTIVO", "gemini").lower()
        
        orden_ejecucion = []
        if modelo_activo in cls.MAPA_PROVEEDORES:
            orden_ejecucion.append(modelo_activo)

        for key in cls.MAPA_PROVEEDORES:
            if key not in orden_ejecucion:
                orden_ejecucion.append(key)

        errores = []

        for key_prov in orden_ejecucion:
            nombre_label, provider, env_var_key = cls.MAPA_PROVEEDORES[key_prov]
            api_key = config_env.get(env_var_key, "").strip()

            if not api_key:
                continue

            try:
                print(f"🚀 [AIService] Intentando extracción OCR con modelo [{nombre_label}]...")
                resultado = provider.extraer_texto_de_imagen(img_pil, prompt, api_key)
                if resultado and resultado.strip():
                    return resultado
            except Exception as e:
                msg_err = f"Fallo [{nombre_label}]: {e}"
                print(f"🔄 [AIService Fallback] {msg_err}. Intentando con otro proveedor...")
                errores.append(msg_err)

        raise RuntimeError(f"No se pudo extraer la información con ningún modelo de IA configurado. Detalles: {' | '.join(errores)}")