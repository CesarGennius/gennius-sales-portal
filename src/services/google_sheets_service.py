import os
from datetime import datetime
import gspread
import pandas as pd
import re

# Diccionario de equivalencias de meses Español / Inglés
MESES_ES_EN = {
    1: ["ene", "jan"], 2: ["feb", "feb"], 3: ["mar", "mar"], 4: ["abr", "apr"],
    5: ["may", "may"], 6: ["jun", "jun"], 7: ["jul", "jul"], 8: ["ago", "aug"],
    9: ["sep", "sep"], 10: ["oct", "oct"], 11: ["nov", "nov"], 12: ["dic", "dec"]
}

# Diccionario global para guardar el historial de ONED recuperado de la nube
oned_historico_cache = {
    "630am": {"tokenized": "", "transaction": ""},
    "1230pm": {"tokenized": "", "transaction": ""},
    "630pm": {"tokenized": "", "transaction": ""}
}

def obtener_ruta_secret_file(nombre_archivo: str) -> str:
    """
    Busca un archivo sensible priorizando:
    1. ./data/<nombre_archivo> (Desarrollo Local)
    2. ./<nombre_archivo> (Render Secret Files en raíz)
    3. /etc/secrets/<nombre_archivo> (Ruta absoluta por defecto de Render)
    """
    ruta_local = os.path.join("data", nombre_archivo)
    if os.path.exists(ruta_local):
        return ruta_local
    
    if os.path.exists(nombre_archivo):
        return nombre_archivo
        
    ruta_render_etc = os.path.join("/etc/secrets", nombre_archivo)
    if os.path.exists(ruta_render_etc):
        return ruta_render_etc

    return ruta_local  # Retorno fallback para creación inicial si aplica

def obtener_cliente_gspread():
    """Inicializa el cliente oficial usando OAuth de escritorio con fallback seguro para servidores headless"""
    ruta_client_secrets = obtener_ruta_secret_file("credentials.json")
    ruta_token = obtener_ruta_secret_file("token.json")
    
    if not os.path.exists(ruta_client_secrets):
        print("⚠️ [GoogleSheets] No se encontró credentials.json en las rutas especificadas.")
        return None

    try:
        # Conexión directa estándar usando los archivos resueltos dinámicamente
        return gspread.oauth(
            credentials_filename=ruta_client_secrets, 
            authorized_user_filename=ruta_token
        )
    except Exception as e:
        print(f"❌ Error al autenticar con Google Sheets OAuth: {e}")
        return None

def _obtener_credenciales_hoja():
    """Obtiene SHEET_ID y GID_HOJA de os.environ o directamente de users_db.json como fallback."""
    spreadsheet_id = os.getenv("SHEET_ID", "").strip()
    gid_pestana = str(os.getenv("GID_HOJA", "0")).strip()

    if not spreadsheet_id:
        try:
            from src.services.auth_service import AuthService
            db = AuthService._get_db()
            for email, u in db.items():
                cfg = u.get("config_env", {})
                if cfg.get("SHEET_ID"):
                    spreadsheet_id = str(cfg.get("SHEET_ID", "")).strip()
                    gid_pestana = str(cfg.get("GID_HOJA", "0")).strip()
                    os.environ["SHEET_ID"] = spreadsheet_id
                    os.environ["GID_HOJA"] = gid_pestana
                    break
        except Exception as e:
            print(f"  [Info] Error leyendo fallback de credenciales: {e}")

    return spreadsheet_id, gid_pestana

def recuperar_historial_desde_nube(label_corte):
    """
    Localiza dinámicamente las coordenadas de fechas y cortes en Google Sheets.
    Crea un entorno local limpio si no existe información previa.
    """
    global oned_historico_cache
    try:
        print("  Sincronizando historial local y ONED con Google Sheets de forma dinámica...")
        
        spreadsheet_id, gid_pestana = _obtener_credenciales_hoja()
        
        if not spreadsheet_id:
            print("  [Info] SHEET_ID no configurado en la sesión activa ni en la base de datos.")
            return

        gc = obtener_cliente_gspread()
        if not gc: 
            return

        libro = gc.open_by_key(spreadsheet_id)
                
        sheet = None
        # Búsqueda estricta por string id de la pestaña
        for worksheet in libro.worksheets():
            if str(worksheet.id) == gid_pestana:
                sheet = worksheet
                break
        
        if sheet is None: 
            sheet = libro.get_worksheet(0)
            print(f"  [Info] Pestaña con GID '{gid_pestana}' no hallada directamente. Usando pestaña 0: '{sheet.title}'")

        # 1. VARIACIONES DE FECHA ADAPTADAS
        ahora = datetime.now()
        dia_num = ahora.day
        ano_4d = str(ahora.year)
        ano_2d = ahora.strftime('%y')
                
        meses_posibles = MESES_ES_EN.get(ahora.month, [ahora.strftime('%b').lower()])
        variaciones_fecha = []
        for m_abr in meses_posibles:
            variaciones_fecha.extend([
                f"{dia_num} {m_abr} {ano_4d}",
                f"{dia_num:02d} {m_abr} {ano_4d}",
                f"{dia_num}-{m_abr}-{ano_2d}",
                f"{dia_num:02d}-{m_abr}-{ano_2d}"
            ])
            
        valores = sheet.get_all_values()
        indice_columna_dia = -1
                
        # 2. BÚSQUEDA FLEXIBLE EN LA MATRIZ
        for r_idx, fila in enumerate(valores):
            for c_idx, celda in enumerate(fila):
                celda_minuscula = celda.lower().strip()
                                
                if any(f_var in celda_minuscula for f_var in variaciones_fecha):
                    for step_c in range(c_idx, min(c_idx + 15, len(fila))):
                        if "6:30am" in fila[step_c].lower().replace(" ", ""):
                            indice_columna_dia = step_c + 1
                            break
                                        
                    if indice_columna_dia == -1 and r_idx + 1 < len(valores):
                        for step_c in range(c_idx, min(c_idx + 15, len(valores[r_idx + 1]))):
                            if "6:30am" in valores[r_idx + 1][step_c].lower().replace(" ", ""):
                                indice_columna_dia = step_c + 1
                                break
                if indice_columna_dia != -1: break
            if indice_columna_dia != -1: break
            
        clean_label = label_corte.replace(":", "").lower().replace(" ", "")
                
        # 3. CONTROL DE CORTE DE EMERGENCIA
        if indice_columna_dia == -1:
            print(f"  [Info] No se encontró la columna para el día de hoy en Sheets (Corte inicial).")
            ruta_dia = os.path.join('data', 'data_dia')
            archivo_csv = os.path.join(ruta_dia, f"corte_{clean_label}.csv")
            if not os.path.exists(archivo_csv):
                os.makedirs(ruta_dia, exist_ok=True)
                programas_orden = ["VLS", "CIBC", "NCB", "FC", "Cuscatlan", "Scotia", "MilesCare LifeMiles"]
                filas_vacias = [{'Programa': p, 'TPV': 0.0, 'Q_Juniper': 0} for p in programas_orden]
                pd.DataFrame(filas_vacias).to_csv(archivo_csv, index=False)
            return

        if "630am" in clean_label:
            columna_final_num = indice_columna_dia
        elif "1230pm" in clean_label:
            columna_final_num = indice_columna_dia + 1
        else:
            columna_final_num = indice_columna_dia + 2
                    
        cortes_cronologicos = [
            {"tag": "630am", "col_idx": indice_columna_dia},
            {"tag": "1230pm", "col_idx": indice_columna_dia + 1},
            {"tag": "630pm", "col_idx": indice_columna_dia + 2}
        ]
                
        programas_orden = ["VLS", "CIBC", "NCB", "FC", "Cuscatlan", "Scotia", "MilesCare LifeMiles"]
        ruta_dia = os.path.join('data', 'data_dia')
                
        # 4. EXTRACCIÓN Y RECONSTRUCCIÓN CORREGIDA
        for corte in cortes_cronologicos:
            if corte["col_idx"] <= (indice_columna_dia + 2) and corte["col_idx"] < len(valores[0]):
                valores_columna = sheet.col_values(corte["col_idx"])
                                
                for current_r_idx, fila_datos in enumerate(valores):
                    if len(fila_datos) < 2: continue
                    for search_c_idx in range(min(5, len(fila_datos))):
                        texto_fila = fila_datos[search_c_idx].strip().lower()
                        if current_r_idx < len(valores_columna):
                            valor_celda_raw = str(valores_columna[current_r_idx])
                            if "tokenized" in texto_fila or "oned tokenized" in texto_fila:
                                tok_raw = re.sub(r'[^0-9]', '', valor_celda_raw)
                                if tok_raw: oned_historico_cache[corte["tag"]]["tokenized"] = int(tok_raw)
                            elif "transaction" in texto_fila or "oned transaction" in texto_fila:
                                trn_raw = re.sub(r'[^0-9]', '', valor_celda_raw)
                                if trn_raw: oned_historico_cache[corte["tag"]]["transaction"] = int(trn_raw)

                if corte["col_idx"] < columna_final_num:
                    archivo_csv = os.path.join(ruta_dia, f"corte_{corte['tag']}.csv")
                    if not os.path.exists(archivo_csv):
                        filas_csv = []
                                                
                        for prog in programas_orden:
                            tpv_encontrado = 0.0
                            q_encontrado = 0
                                                        
                            for scan_r_idx, fila_scan in enumerate(valores):
                                if len(fila_scan) < 2: continue
                                for scan_c_idx in range(min(5, len(fila_scan))):
                                    if fila_scan[scan_c_idx].strip().lower() == prog.lower():
                                        if scan_r_idx < len(valores_columna):
                                            val_raw = re.sub(r'[^0-9.]', '', str(valores_columna[scan_r_idx]).replace(',', ''))
                                            tpv_encontrado = float(val_raw) if val_raw else 0.0
                                        if prog != "MilesCare LifeMiles" and (scan_r_idx + 1) < len(valores_columna):
                                            val_q = re.sub(r'[^0-9]', '', str(valores_columna[scan_r_idx + 1]))
                                            q_encontrado = int(val_q) if val_q else 0
                                        break
                                                        
                            filas_csv.append({'Programa': prog, 'TPV': tpv_encontrado, 'Q_Juniper': q_encontrado})
                                                
                        if filas_csv:
                            os.makedirs(ruta_dia, exist_ok=True)
                            pd.DataFrame(filas_csv).to_csv(archivo_csv, index=False)

    except Exception as e:
        print(f"  [Info] Nota en pre-recuperación de Sheets: {e}")


def procesar_e_inyectar_todo(label_corte, datos_tabla_arriba, data_oned_lista=None):
    """
    Inyecta datos en Google Sheets localizando dinámicamente la columna exacta.
    Calcula e inyecta totales generales y previene desalineaciones de filas.
    """
    try:
        clean_label = label_corte.replace(":", "").replace(" ", "").lower()

        print("📊 Conectando a Google Sheets para inyección...")
        
        spreadsheet_id, gid_pestana = _obtener_credenciales_hoja()

        if not spreadsheet_id:
            print("❌ Error: SHEET_ID no configurado.")
            return False

        gc = obtener_cliente_gspread()
        if not gc: return False
        
        libro = gc.open_by_key(spreadsheet_id)
        
        sheet = None
        for worksheet in libro.worksheets():
            if str(worksheet.id) == gid_pestana:
                sheet = worksheet
                break
        if sheet is None: sheet = libro.get_worksheet(0)
        
        # 1. LOCALIZACIÓN DE LA COLUMNA
        ahora = datetime.now()
        dia_num = ahora.day
        ano_4d = str(ahora.year) 
        ano_2d = ahora.strftime('%y') 

        meses_posibles = MESES_ES_EN.get(ahora.month, [ahora.strftime('%b').lower()])

        variaciones_fecha = []
        for m_abr in meses_posibles:
            variaciones_fecha.extend([
                f"{dia_num} {m_abr} {ano_4d}",
                f"{dia_num:02d} {m_abr} {ano_4d}",
                f"{dia_num}-{m_abr}-{ano_2d}",
                f"{dia_num:02d}-{m_abr}-{ano_2d}"
            ])

        if "630am" in clean_label:
            hora_buscada = "6:30am"
        elif "1230pm" in clean_label:
            hora_buscada = "12:30pm"
        else:
            hora_buscada = "6:30pm"

        valores = sheet.get_all_values()
        columna_final_num = None

        mapeo_filas_datos = {
            ("vls", "tpv puntos"): 0, ("vls", "q ventas juniper"): 1,
            ("cibc", "tpv puntos"): 2, ("cibc", "q ventas juniper"): 3,
            ("ncb", "tpv puntos"): 4, ("ncb", "q ventas juniper"): 5,
            ("fc", "tpv puntos"): 6, ("fc", "q ventas juniper"): 7,
            ("cuscatlan", "tpv puntos"): 8, ("cuscatlan", "q ventas juniper"): 9,
            ("scotia", "tpv puntos"): 10, ("scotia", "q ventas juniper"): 11,
            ("milescare lifemiles", "tpv puntos"): 12, ("milescare lifemiles", "q ventas juniper"): 13
        }

        for r_idx, fila in enumerate(valores):
            for c_idx, celda in enumerate(fila):
                celda_minuscula = celda.lower().strip()
                if any(f_var in celda_minuscula for f_var in variaciones_fecha):
                    for step_c in range(c_idx, min(c_idx + 6, len(fila))):
                        encabezado_hora = fila[step_c].lower().replace(" ", "")
                        if hora_buscada in encabezado_hora:
                            columna_final_num = step_c + 1
                            break
                    if not columna_final_num and r_idx + 1 < len(valores):
                        fila_abajo = valores[r_idx + 1]
                        for step_c in range(c_idx, min(c_idx + 6, len(fila_abajo))):
                            encabezado_hora = fila_abajo[step_c].lower().replace(" ", "")
                            if hora_buscada in encabezado_hora:
                                columna_final_num = step_c + 1
                                break
                if columna_final_num: break
            if columna_final_num: break

        if columna_final_num is None:
            print(f"❌ Error: No se encontró la columna en Sheets para {ahora.strftime('%d %b %Y')} {hora_buscada}")
            return False

        letras_columna = ""
        temp_num = columna_final_num
        while temp_num > 0:
            temp_num, residuo = divmod(temp_num - 1, 26)
            letras_columna = chr(65 + residuo) + letras_columna

        print(f"🎯 Columna de destino localizada con éxito: Columna {letras_columna} (Índice {columna_final_num})")

        total_tpv = 0
        total_q_ventas = 0
        programa_actual = ""
        
        # 2. ESCRITURA EN HOJA
        for r_idx, fila in enumerate(valores):
            if len(fila) < 2: continue
            
            col_a = fila[0].strip().lower()
            col_b = fila[1].strip().lower()
            
            if col_a != "":
                programa_actual = col_a
            
            llave_busqueda = (programa_actual, col_b)
            if llave_busqueda in mapeo_filas_datos:
                idx_array = mapeo_filas_datos[llave_busqueda]
                dato_str = str(datos_tabla_arriba[idx_array])
                
                try: valor_numerico = float(dato_str) if "." in dato_str else int(dato_str)
                except ValueError: valor_numerico = 0
                
                if "tpv puntos" in col_b:
                    total_tpv += valor_numerico
                elif "q ventas juniper" in col_b:
                    total_q_ventas += valor_numerico
                
                sheet.update_cell(r_idx + 1, columna_final_num, valor_numerico)

            elif programa_actual == "total":
                if "tpv puntos" in col_b or "tpv" in col_b:
                    sheet.update_cell(r_idx + 1, columna_final_num, total_tpv)
                elif "q ventas juniper" in col_b:
                    sheet.update_cell(r_idx + 1, columna_final_num, total_q_ventas)

            if data_oned_lista and str(data_oned_lista[0]) != "Cargando..." and int(data_oned_lista[0]) > 0:
                if "oned" in col_a:
                    if "tokenized" in col_b:
                        sheet.update_cell(r_idx + 1, columna_final_num, int(data_oned_lista[0]))
                    elif "transaction" in col_b:
                        sheet.update_cell(r_idx + 1, columna_final_num, int(data_oned_lista[1]))

        print(f"✅ Inyección completada de forma limpia en la Columna {letras_columna}.")
        return True
    except Exception as e:
        print(f"❌ Error crítico en GoogleSheetsService: {e}")
        return False