import urllib.parse
import os

class WhatsAppService:
    # Contenedores temporales en memoria para consolidar el reporte final
    _alertas_quo_cache = []
    _alertas_oned_cache = []

    @classmethod
    def acumular_alerta_quo(cls, alertas):
        """Guarda en memoria las alertas de QUO detectadas en el extractor"""
        if alertas:
            cls._alertas_quo_cache = alertas

    @classmethod
    def acumular_alerta_oned(cls, metrica_falla, val_anterior, val_actual):
        """Guarda en memoria las anomalías de ONED detectadas en la UI"""
        try:
            cifra_actual = float(str(val_actual).replace('.', '').replace(',', '').strip()) if val_actual else 0.0
        except (ValueError, TypeError):
            cifra_actual = 0.0

        if cifra_actual == 0:
            cls._alertas_oned_cache.append({
                "metrica": metrica_falla
            })

    @classmethod
    def generar_mensaje_unificado(cls, label_corte):
        """
        Toma todas las anomalías acumuladas (QUOs + ONED) en el corte actual
        y unifica el texto según las reglas de negocio exactas de forma profesional.
        """
        if not cls._alertas_quo_cache and not cls._alertas_oned_cache:
            return None

        clean_label = label_corte.replace(":", "").lower().replace(" ", "")
        saludo = "Buenos días" if "630am" in clean_label else "Buenas tardes"
        link_oned = "*ONED* (oned.global/#/)"

        rango_txt = {
            "630am": "6:30 p. m. del día de ayer y las 6:30 a. m. del día de hoy",
            "1230pm": "6:30 a. m. y las 12:30 p. m. del día de hoy",
            "630pm": "12:30 p. m. y las 6:30 p. m. del día de hoy"
        }.get(clean_label, label_corte)

        es_caso_mixto = bool(cls._alertas_quo_cache and cls._alertas_oned_cache)
        cantidad_oned = len(cls._alertas_oned_cache)

        # 🟢 AUXILIAR: Construye la frase fluida de programas con QUO
        partes_quo = []
        for p in cls._alertas_quo_cache:
            cant = int(p['quos'])
            s_res = "reserva" if cant == 1 else "reservas"
            partes_quo.append(f"*{cant}* {s_res} en estado *QUO* para *{p['prog']}*")

        if len(partes_quo) > 1:
            texto_quo_fluido = ", ".join(partes_quo[:-1]) + " y " + partes_quo[-1]
        elif len(partes_quo) == 1:
            texto_quo_fluido = partes_quo[0]
        else:
            texto_quo_fluido = ""

        # --- CASO 1: SOLO ALERTAS DE QUO ---
        if cls._alertas_quo_cache and not cls._alertas_oned_cache:
            if len(cls._alertas_quo_cache) == 1:
                p = cls._alertas_quo_cache[0]
                cant = int(p['quos'])
                s_res = "reserva" if cant == 1 else "reservas"
                s_evid = "evidencia" if cant == 1 else "evidencian"
                mensaje = (
                    f"{saludo}, reporto que en el corte correspondiente a las *{rango_txt}* del programa *{p['prog']}*, "
                    f"en Juniper se reportan *0* reservas confirmadas; sin embargo, se {s_evid} *{cant}* {s_res} en estado *QUO*."
                )
            else:
                mensaje = (
                    f"{saludo}, reporto que en el corte de las *{rango_txt}* se reporta que, para los siguientes programas "
                    f"hay *0* reservas confirmadas; sin embargo, se evidencian {texto_quo_fluido}."
                )

        # --- CASO 2: SOLO ALERTAS DE ONED ---
        elif cls._alertas_oned_cache and not cls._alertas_quo_cache:
            if cantidad_oned == 1:
                metrica = cls._alertas_oned_cache[0]['metrica']
                mensaje = (
                    f"{saludo}, reporto que en el corte reciente de las *{label_corte}* se identificó que el indicador "
                    f"*{metrica}* de la plataforma {link_oned} se encuentra en *0*."
                )
            else:
                mensaje = (
                    f"{saludo}, reporto que en el corte reciente de las *{label_corte}* se identificó que los indicadores "
                    f"*Tokenized Volume* y *Transaction Volume* de la plataforma {link_oned} se encuentran en *0*."
                )

        # --- CASO 3: CASO MIXTO (QUO + ONED) ---
        else:
            if cantidad_oned == 1:
                metrica = cls._alertas_oned_cache[0]['metrica']
                texto_oned_mixto = f"el indicador *{metrica}* de la plataforma {link_oned} se encuentra en *0*."
            else:
                texto_oned_mixto = f"los indicadores principales de la plataforma {link_oned} se encuentran en *0*."

            mensaje = (
                f"{saludo}, reporto que en el corte de las *{rango_txt}* se identificaron novedades operacionales:\n\n"
                f"📌 *RESERVAS EN ESTADO QUO*\n"
                f"Para los programas indicados hay *0* reservas confirmadas; sin embargo, se evidencian {texto_quo_fluido}.\n\n"
                f"🌐 *PLATAFORMA ONED*\n"
                f"Asimismo, se identificó que {texto_oned_mixto}"
            )

        # Limpieza absoluta de caché
        cls._alertas_quo_cache = []
        cls._alertas_oned_cache = []

        return mensaje.strip()

    @classmethod
    def obtener_url_whatsapp(cls, label_corte):
        """Genera la URL codificada lista para abrir en la web"""
        mensaje = cls.generar_mensaje_unificado(label_corte)
        if not mensaje:
            return ""

        grupo_id = os.getenv("ID_GRUPO_WA_PRUEBA")
        mensaje_url = urllib.parse.quote(mensaje)
        
        if grupo_id:
            return f"https://web.whatsapp.com/send/?chat_id={grupo_id}@g.us&text={mensaje_url}&type=custom_url&app_absent=0"
        else:
            return f"https://web.whatsapp.com/send?text={mensaje_url}"