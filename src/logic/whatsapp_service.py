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
        # 🟢 REGLA DE NEGOCIO ESTRICTA: Solo alerta si el valor del corte ACTUAL cae a cero
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
        y unifica el texto según las reglas de negocio exactas.
        """
        if not cls._alertas_quo_cache and not cls._alertas_oned_cache:
            return None

        clean_label = label_corte.replace(":", "").lower().replace(" ", "")
        saludo = "Buenos días" if "630am" in clean_label else "Buenas tardes"
        link_oned = "*ONED* (oned.global/#/)"
        
        es_caso_mixto = bool(cls._alertas_quo_cache and cls._alertas_oned_cache)
        cantidad_oned = len(cls._alertas_oned_cache)

        # --- BLOQUE 1: INTRODUCCIÓN DINÁMICA ---
        if es_caso_mixto:
            mensaje = f"{saludo}, reporto que en el corte reciente de las *{label_corte}* se identificaron novedades tanto en el volumen de ventas como en las métricas de la plataforma {link_oned}.\n\n"
        elif cls._alertas_quo_cache:
            if len(cls._alertas_quo_cache) == 1:
                p = cls._alertas_quo_cache[0]
                s_wa = "reserva" if int(p['quos']) == 1 else "reservas"
                mensaje = f"{saludo}, reporto que en el corte reciente de las *{label_corte}* del programa *{p['prog']}* llevamos *0* ventas en Juniper; sin embargo, contamos con *{p['quos']}* {s_wa} en estado *QUO*.\n"
            else:
                mensaje = f"{saludo}, reporto que en el corte reciente de las *{label_corte}*, en los siguientes programas llevamos *0* ventas en Juniper; sin embargo, sí cuentan con reservas en estado *QUO*:\n"
        else:
            if cantidad_oned == 1:
                metrica_unica = cls._alertas_oned_cache[0]['metrica']
                mensaje = f"{saludo}, reporto que en el corte reciente de las *{label_corte}* se identificó que el indicador *{metrica_unica}* de la plataforma {link_oned} se encuentra en *0*.\n"
            else:
                mensaje = f"{saludo}, reporto que en el corte reciente de las *{label_corte}* se identificó que ambos indicadores principales de la plataforma {link_oned} se encuentran en *0*.\n"

        # --- BLOQUE 2: DETALLE DE ALERTAS QUO ---
        if cls._alertas_quo_cache:
            if es_caso_mixto:
                mensaje += "──────────────────────────\n"
                mensaje += "RESERVAS EN ESTADO QUO\n"
                mensaje += "En los siguientes programas llevamos *0* ventas en Juniper; sin embargo, sí cuentan con registros pendientes:\n"
            
            for p in cls._alertas_quo_cache:
                mensaje += f"- *{p['prog']}*: {p['quos']}\n"
            mensaje += "\n"

        # --- BLOQUE 3: DETALLE DE ALERTAS ONED ---
        if cls._alertas_oned_cache and es_caso_mixto:
            mensaje += "──────────────────────────\n"
            mensaje += "MÉTRICAS PLATAFORMA *ONED*\n"
            
            if cantidad_oned == 1:
                metrica_unica = cls._alertas_oned_cache[0]['metrica']
                mensaje += f"Se identificó que el indicador *{metrica_unica}* se encuentra en *0*.\n"
            else:
                mensaje += "Se identificó que ambos indicadores operacionales se encuentran en *0*.\n"

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