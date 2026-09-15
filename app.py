import os
import json
import tempfile
import traceback
import pandas as pd
import xml.etree.ElementTree as ET
from PIL import Image
from cryptography.fernet import Fernet, InvalidToken
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.services.auth_service import AuthService
from src.time_manager import TimeManager
from src.tableau_extractor import TableauExtractor
from src.processor import ReservationProcessor
from src.logic.data_handler import DataHandler
from src.logic.oned_global import obtener_metricas_oned_1d
from src.services.email_service import EmailService
from src.services.google_sheets_service import (
    recuperar_historial_desde_nube,
    procesar_e_inyectar_todo,
    oned_historico_cache
)
from src.logic.whatsapp_service import WhatsAppService


app = FastAPI(title="Gennius Sales Portal", version="2.0")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/src", StaticFiles(directory="src"), name="src")
templates = Jinja2Templates(directory="templates")

CACHE_PROCESAMIENTO = {
    "label_corte": "6:30am",
    "col_idx": 2,
    "data_total": None,
    "df_tpv": None,
    "conteo_juniper": {},
    "conteo_quos": {},
    "data_oned": {"tokenized": 0, "transaction": 0},
    "alertas_list": [],
    "whatsapp_url": ""
}

# Esquema Pydantic para el correo a aprobar
class ApproveUserSchema(BaseModel):
    email: str

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/config-sheets")
def get_config_sheets():
    return {
        "sheet_id": os.getenv("SHEET_ID", "").strip(),
        "gid_hoja": os.getenv("GID_HOJA", "0").strip()
    }

@app.get("/api/init-background")
def init_background():
    try:
        start_dt, end_dt, label_corte, col_idx = TimeManager.get_current_cutoff_range()
        recuperar_historial_desde_nube(label_corte)
        
        data_oned = {"tokenized": 0, "transaction": 0}
        try:
            data_oned = obtener_metricas_oned_1d()
        except Exception as e:
            print(f"⚠️ Alerta precargando ONED: {e}")
            
        CACHE_PROCESAMIENTO["label_corte"] = label_corte
        CACHE_PROCESAMIENTO["col_idx"] = col_idx
        CACHE_PROCESAMIENTO["data_oned"] = data_oned
        
        return JSONResponse({"status": "success", "oned": data_oned, "oned_historico": oned_historico_cache})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})

@app.post("/api/auth/register")
def register_endpoint(payload: dict):
    exito, msg = AuthService.register_user(payload)
    return JSONResponse({"status": "success" if exito else "error", "message": msg})

@app.post("/api/auth/login")
def login_endpoint(payload: dict):
    email = payload.get("email", "")
    password = payload.get("password", "")
    valido, msg, user_data = AuthService.verify_credentials(email, password)
    if not valido:
        return JSONResponse({"status": "error", "message": msg}, status_code=401)
        
    if user_data.get("requiere_cambio_pwd"):
        return JSONResponse({"status": "forced_password_change", "message": "Debes cambiar la clave."})

    exito_2fa, msg_2fa = AuthService.send_2fa_code(email)
    if exito_2fa:
        return JSONResponse({
            "status": "2fa_required",
            "user_preview": {
                "email": email,
                "nombre": f"{user_data.get('nombre', '')} {user_data.get('apellido', '')}".strip() or email,
                "es_admin": user_data.get("es_admin", False),
                "avatar": user_data.get("avatar", "")
            }
        })
    return JSONResponse({"status": "error", "message": msg_2fa}, status_code=500)

@app.post("/api/auth/load-session")
def load_session_endpoint(payload: dict):
    try:
        email = payload.get("email", "").strip().lower()
        if not email:
            return JSONResponse({"status": "error", "message": "Email requerido."}, status_code=400)
        
        exito, msg = AuthService.cargar_config_memoria(email)
        if exito:
            u = AuthService.obtener_usuario_por_email(email) or {}
            return JSONResponse({
                "status": "success", 
                "message": "Sesión cargada exitosamente.",
                "user": {
                    "email": email,
                    "nombre": f"{u.get('nombre', '')} {u.get('apellido', '')}".strip() or email,
                    "es_admin": u.get("es_admin", False),
                    "avatar": u.get("avatar", "")
                }
            })
        return JSONResponse({"status": "error", "message": msg}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/auth/verify-2fa")
def verify_2fa_endpoint(payload: dict):
    email = payload.get("email")
    code = payload.get("code")
    valido, msg = AuthService.verify_2fa(email, code)
    if valido:
        AuthService.cargar_config_memoria(email)
        return JSONResponse({"status": "success"})
    return JSONResponse({"status": "error", "message": msg}, status_code=400)

@app.post("/api/auth/reset-password")
def reset_pwd_endpoint(payload: dict):
    try:
        email = payload.get("email", "").strip().lower()
        if not email:
            return JSONResponse({"status": "error", "message": "El correo es requerido."}, status_code=400)

        exito, msg = AuthService.reset_password_and_email(email)
        return JSONResponse({"status": "success" if exito else "error", "message": msg})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/auth/change-password")
def change_pwd_endpoint(payload: dict):
    exito, msg = AuthService.cambiar_password(payload.get("email", ""), payload.get("new_password", ""))
    return JSONResponse({"status": "success" if exito else "error", "message": msg})

@app.get("/api/auth/admin/users")
def get_users_endpoint():
    return JSONResponse(AuthService.obtener_todos_usuarios())

@app.delete("/api/auth/admin/users/{email}")
def delete_user_endpoint(email: str):
    exito, msg = AuthService.eliminar_usuario(email)
    return JSONResponse({"status": "success" if exito else "error", "message": msg})

# 🟢 RUTAS DE APROBACIÓN CORREGIDAS (Aceptan con /api/auth/admin/users/approve y con /admin/users/approve)
@app.post("/api/auth/admin/users/approve")
@app.post("/admin/users/approve")
async def approve_user_endpoint(data: ApproveUserSchema):
    exito, mensaje = AuthService.aprobar_usuario(data.email)
    if not exito:
        raise HTTPException(status_code=400, detail=mensaje)
    return {"status": "success", "message": mensaje}

@app.get("/api/auth/get-user-config")
def get_user_config_endpoint(email: str):
    try:
        u = AuthService.obtener_usuario_por_email(email)
        if not u:
            return JSONResponse({"status": "error", "message": "Usuario no encontrado."}, status_code=404)
        cfg = u.get("config_env", {})
        return JSONResponse({
            "status": "success",
            "config": {
                "MODELO_IA_ACTIVO": cfg.get("MODELO_IA_ACTIVO", "gemini"),
                "GEMINI_API_KEY": AuthService.desencriptar_texto(cfg.get("GEMINI_API_KEY", "")),
                "GROQ_API_KEY": AuthService.desencriptar_texto(cfg.get("GROQ_API_KEY", "")),
                "HF_API_KEY": AuthService.desencriptar_texto(cfg.get("HF_API_KEY", ""))
            }
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/auth/update-user-config")
def update_user_config_endpoint(payload: dict):
    try:
        email = payload.get("email")
        config_env = payload.get("config_env", {})
        if not email:
            return JSONResponse({"status": "error", "message": "Email requerido."}, status_code=400)
        exito, msg = AuthService.update_ai_config(email, config_env)
        if exito:
            AuthService.cargar_config_memoria(email)
            return JSONResponse({"status": "success", "message": msg})
        return JSONResponse({"status": "error", "message": msg}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/api/auth/profile")
def get_profile_endpoint(email: str):
    try:
        if not email:
            return JSONResponse({"status": "error", "message": "Email es requerido"}, status_code=400)

        target_email = email.strip().lower()
        user_data = AuthService.obtener_usuario_por_email(target_email)

        if not user_data:
            return JSONResponse({"status": "error", "message": "Usuario no encontrado"}, status_code=404)

        cfg = user_data.get("config_env", {}) if isinstance(user_data.get("config_env"), dict) else user_data

        res_payload = {
            "nombre": user_data.get("nombre", ""),
            "apellido": user_data.get("apellido", ""),
            "email": target_email,
            "avatar": user_data.get("avatar", ""),
            "gemini_api_key": AuthService.desencriptar_texto(cfg.get("GEMINI_API_KEY", "")),
            "remitente": cfg.get("REMITENTE", ""),
            "google_app_password": AuthService.desencriptar_texto(cfg.get("PASSWORD", "")),
            "mi_correo": cfg.get("MI_CORREO", ""),
            "destinatarios_finales": cfg.get("DESTINATARIOS_FINALES", []),
            "destinatarios_bcc": cfg.get("DESTINATARIOS_BCC", []),
            "nombre_firma": cfg.get("NOMBRE_FIRMA", ""),
            "cargo_firma": cfg.get("CARGO_FIRMA", ""),
            "sheet_id": cfg.get("SHEET_ID", ""),
            "gid_hoja": str(cfg.get("GID_HOJA", "0"))
        }

        return JSONResponse({"status": "success", "user": res_payload})

    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/auth/profile/update")
def update_profile_endpoint(payload: dict):
    try:
        email = payload.get("email")
        if not email:
            return JSONResponse({"status": "error", "message": "Email no proporcionado"}, status_code=400)

        exito, msg = AuthService.update_profile(email, payload)
        if exito:
            AuthService.cargar_config_memoria(email)
            return JSONResponse({"status": "success", "message": msg})
            
        return JSONResponse({"status": "error", "message": msg}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/auth/request-email-change")
def req_email_change(payload: dict):
    try:
        email_actual = payload.get("email_actual") or payload.get("email")
        nuevo_email = payload.get("nuevo_email")

        if not email_actual or not nuevo_email:
            return JSONResponse({"status": "error", "message": "Email actual y nuevo son requeridos."}, status_code=400)

        exito, msg = AuthService.send_2fa_code(email_actual)
        if exito:
            return JSONResponse({"status": "success", "message": "Código enviado."})
        return JSONResponse({"status": "error", "message": msg}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/auth/confirm-email-change")
def conf_email_change(payload: dict):
    try:
        email_actual = payload.get("email_actual") or payload.get("email")
        nuevo_email = payload.get("nuevo_email")
        code = payload.get("code") or payload.get("codigo")

        if not email_actual or not nuevo_email or not code:
            return JSONResponse({"status": "error", "message": "Faltan datos requeridos."}, status_code=400)

        valido, msg_2fa = AuthService.verify_2fa(email_actual, code)
        if not valido:
            return JSONResponse({"status": "error", "message": msg_2fa}, status_code=400)

        exito, msg_change = AuthService.cambiar_email(email_actual, nuevo_email)
        if exito:
            return JSONResponse({"status": "success", "message": "Correo actualizado correctamente."})
        return JSONResponse({"status": "error", "message": msg_change}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/auth/request-password-change")
def req_pass_change(payload: dict):
    try:
        email = payload.get("email")
        if not email:
            return JSONResponse({"status": "error", "message": "Email requerido"}, status_code=400)

        exito, msg = AuthService.send_2fa_code(email)
        if exito:
            return JSONResponse({"status": "success", "message": "Código de verificación enviado."})
        return JSONResponse({"status": "error", "message": msg}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/auth/confirm-password-change")
def conf_pass_change(payload: dict):
    try:
        email = payload.get("email")
        new_password = payload.get("new_password") or payload.get("nueva_password")
        code = payload.get("code") or payload.get("codigo")

        if not email or not new_password or not code:
            return JSONResponse({"status": "error", "message": "Faltan datos requeridos."}, status_code=400)

        valido, msg_2fa = AuthService.verify_2fa(email, code)
        if not valido:
            return JSONResponse({"status": "error", "message": msg_2fa}, status_code=400)

        exito, msg_change = AuthService.cambiar_password(email, new_password)
        if exito:
            return JSONResponse({"status": "success", "message": "Contraseña actualizada correctamente."})
        return JSONResponse({"status": "error", "message": msg_change}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/procesar")
def procesar_datos(
    imagen: UploadFile = File(None),
    excel: UploadFile = File(...),
    texto_manual: str = Form(None),
    email_usuario: str = Form(None)
):
    try:
        start_dt, end_dt, label_corte, col_idx = TimeManager.get_current_cutoff_range()
        handler = DataHandler()
        if label_corte == "6:30am":
            handler.limpiar_directorio_dia()

        extractor = TableauExtractor()
        gemini_error = False
        gemini_msg = ""
        
        programas_base = ["VLS", "CIBC", "NCB", "FC", "Cuscatlan", "Scotia", "MilesCare LifeMiles"]
        df_tpv = pd.DataFrame({"Programa": programas_base, "TPV": [0.0] * len(programas_base)})

        if texto_manual and texto_manual.strip():
            print("📝 Procesando TPV desde texto manual...")
            df_tpv_extracted = extractor.limpiar_datos(texto_manual)
            if not df_tpv_extracted.empty:
                df_tpv = df_tpv_extracted
        elif imagen and imagen.file:
            print("🧠 Procesando TPV mediante IA (Extractor)...")
            try:
                img_pil = Image.open(imagen.file)
                user_env = {}
                if email_usuario:
                    u = AuthService.obtener_usuario_por_email(email_usuario)
                    if u and "config_env" in u:
                        cfg = u["config_env"]
                        user_env = {
                            "MODELO_IA_ACTIVO": cfg.get("MODELO_IA_ACTIVO", "gemini"),
                            "GEMINI_API_KEY": AuthService.desencriptar_texto(cfg.get("GEMINI_API_KEY", "")),
                            "GROQ_API_KEY": AuthService.desencriptar_texto(cfg.get("GROQ_API_KEY", "")),
                            "HF_API_KEY": AuthService.desencriptar_texto(cfg.get("HF_API_KEY", ""))
                        }

                raw_text = extractor.procesar_vision_gemini_silencioso(img_pil, config_env=user_env)
                df_tpv_extracted = extractor.limpiar_datos(raw_text)
                if not df_tpv_extracted.empty:
                    df_tpv = df_tpv_extracted
            except Exception as e_gemini:
                gemini_error = True
                gemini_msg = str(e_gemini)
                print(f"⚠️ Alerta en IA Extractor: {e_gemini}")

        conteo_juniper, conteo_quos = {}, {}
        contents = excel.file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xls") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        try:
            tree = ET.parse(tmp_path)
            root = tree.getroot()
            ns = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}
            rows = []
            for row in root.findall('.//ss:Table/ss:Row', ns):
                rows.append([c.find('ss:Data', ns).text if c.find('ss:Data', ns) is not None else None for c in row.findall('ss:Cell', ns)])
            
            df_excel = pd.DataFrame(rows)
            h_idx = next(i for i, r in df_excel.iterrows() if any("localizador" in str(v).lower() for v in r))
            df_res = df_excel[h_idx + 1:].copy()
            df_res.columns = [str(c).strip() for c in df_excel.iloc[h_idx]]
            
            conteo_juniper, conteo_quos = ReservationProcessor().count_reservations_by_bank(df_res, start_dt, end_dt)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        handler.guardar_corte_actual(label_corte, df_tpv, conteo_juniper, conteo_quos)
        
        try:
            recuperar_historial_desde_nube(label_corte)
        except Exception as e_sheets:
            print(f"⚠️ Alerta en historial nube: {e_sheets}")
            
        data_total = handler.obtener_data_acumulada()
        data_oned = CACHE_PROCESAMIENTO.get("data_oned", {"tokenized": 0, "transaction": 0})

        alertas_lista = []
        if gemini_error:
            alertas_lista.append("⚠️ Se presentó una novedad extrayendo con la IA. Los datos sin procesar se marcaron con '?' pero puedes editarlos manualmente.")
            
        programas_quo_alerta = []
        for banco, cant_quo in conteo_quos.items():
            cant_ok = conteo_juniper.get(banco, 0)
            if cant_ok == 0 and cant_quo > 0:
                programas_quo_alerta.append({"prog": banco, "quos": cant_quo})
                alertas_lista.append(f"📌 {banco}: Se detectaron {cant_quo} reserva(s) en estado PRESUPUESTO (QUO) sin reservas confirmadas.")

        if programas_quo_alerta:
            WhatsAppService.acumular_alerta_quo(programas_quo_alerta)

        if data_oned["tokenized"] == 0:
            WhatsAppService.acumular_alerta_oned("Tokenized Volume (1d)", None, 0)
            alertas_lista.append("🌐 ONED Global: El indicador Tokenized Volume (1d) se encuentra en 0.")
            
        if data_oned["transaction"] == 0:
            WhatsAppService.acumular_alerta_oned("Transaction Volume (1d)", None, 0)
            alertas_lista.append("🌐 ONED Global: El indicador Transaction Volume (1d) se encuentra en 0.")

        whatsapp_url = WhatsAppService.obtener_url_whatsapp(label_corte)

        CACHE_PROCESAMIENTO["label_corte"] = label_corte
        CACHE_PROCESAMIENTO["col_idx"] = col_idx
        CACHE_PROCESAMIENTO["data_total"] = data_total
        CACHE_PROCESAMIENTO["df_tpv"] = df_tpv
        CACHE_PROCESAMIENTO["conteo_juniper"] = conteo_juniper
        CACHE_PROCESAMIENTO["conteo_quos"] = conteo_quos
        CACHE_PROCESAMIENTO["data_oned"] = data_oned
        CACHE_PROCESAMIENTO["alertas_list"] = alertas_lista
        CACHE_PROCESAMIENTO["whatsapp_url"] = whatsapp_url

        data_total_json = {}
        for k, v in data_total.items():
            if v is not None and isinstance(v, pd.DataFrame):
                data_total_json[k] = v.fillna(0).to_dict(orient="records")
            else:
                data_total_json[k] = []

        return JSONResponse({
            "status": "partial_success" if gemini_error else "success",
            "gemini_error": gemini_error,
            "message": gemini_msg if gemini_error else "",
            "label_corte": label_corte,
            "data_total": data_total_json,
            "oned": data_oned,
            "oned_historico": oned_historico_cache,
            "alertas": alertas_lista,
            "whatsapp_url": whatsapp_url
        })

    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/actualizar-cache-tpv")
def actualizar_cache_tpv_endpoint(payload: dict):
    try:
        label_corte = payload.get("label_corte", "6:30am")
        cambios_tpv = payload.get("cambios_tpv", {})
        
        clean_label = label_corte.replace(":", "").lower().replace(" ", "")
        data_total = CACHE_PROCESAMIENTO.get("data_total")
        
        if data_total and clean_label in data_total and data_total[clean_label] is not None:
            df = data_total[clean_label]
            for prog, val in cambios_tpv.items():
                try:
                    val_num = float(val)
                except ValueError:
                    val_num = 0.0
                df.loc[df['Programa'].str.lower() == prog.lower(), 'TPV'] = val_num
                
            handler = DataHandler()
            path = os.path.join(handler.data_dia_dir, f"corte_{clean_label}.csv")
            df.to_csv(path, index=False, encoding='utf-8')
            CACHE_PROCESAMIENTO["data_total"] = handler.obtener_data_acumulada()
            
        return JSONResponse({"status": "success", "message": "Datos de TPV actualizados en memoria."})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/google-sheets")
def copiar_a_google_sheets():
    try:
        label_corte = CACHE_PROCESAMIENTO.get("label_corte", "6:30am")
        data_total = CACHE_PROCESAMIENTO.get("data_total")
        data_oned = CACHE_PROCESAMIENTO.get("data_oned", {"tokenized": 0, "transaction": 0})
        
        if not data_total:
            return JSONResponse({"status": "error", "message": "No hay datos procesados para copiar."}, status_code=400)
            
        key_corte = label_corte.replace(":", "").lower().replace(" ", "")
        df_corte = data_total.get(key_corte)
        
        programas_orden = ["VLS", "CIBC", "NCB", "FC", "Cuscatlan", "Scotia", "MilesCare LifeMiles"]
        datos_tabla_arriba = []
        
        for prog in programas_orden:
            tpv_val = 0
            q_val = 0
            if df_corte is not None and not df_corte.empty:
                coinc = df_corte[df_corte['Programa'].str.lower() == prog.lower()]
                if not coinc.empty:
                    tpv_val = coinc['TPV'].values[0]
                    q_val = coinc['Q_Juniper'].values[0]
            datos_tabla_arriba.extend([tpv_val, q_val])
            
        data_oned_lista = [data_oned.get("tokenized", 0), data_oned.get("transaction", 0)]
        exito = procesar_e_inyectar_todo(label_corte, datos_tabla_arriba, data_oned_lista)
        
        if exito:
            return JSONResponse({"status": "success", "message": "Datos copiados a Google Sheets correctamente."})
        else:
            return JSONResponse({"status": "error", "message": "No se pudo actualizar Google Sheets."}, status_code=500)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/enviar-email")
def enviar_email_endpoint(modo_final: bool = Form(False)):
    try:
        label_corte = CACHE_PROCESAMIENTO.get("label_corte", "6:30am")
        data_total = CACHE_PROCESAMIENTO.get("data_total")
        
        clean_label = label_corte.replace(":", "").lower().replace(" ", "")
        col_idx_map = {"630am": 0, "1230pm": 1, "630pm": 2}
        col_idx_actual = col_idx_map.get(clean_label, 0)
        
        if not data_total:
            return JSONResponse({"status": "error", "message": "No hay datos para enviar por correo."}, status_code=400)
            
        programas_orden = ["VLS", "CIBC", "NCB", "FC", "Cuscatlan", "Scotia", "MilesCare LifeMiles"]
        cortes = ["630am", "1230pm", "630pm"]
        
        filas_html = ""
        t_tpv_list = [0, 0, 0]
        t_q_list = [0, 0, 0]
        
        for prg in programas_orden:
            row_tpv = f"<tr><td rowspan='{'1' if prg == 'MilesCare LifeMiles' else '2'}' style='border:1px solid black; padding:2px 4px; font-weight:bold; text-align:center; vertical-align:middle;'>{prg}</td><td style='border:1px solid black; padding:2px 4px;'>TPV puntos</td>"
            row_q = f"<tr><td style='border:1px solid black; padding:2px 4px;'>Q ventas Juniper</td>"
            
            for i, c_tag in enumerate(cortes):
                es_corte_futuro = (i > col_idx_actual)
                
                df_c = data_total.get(c_tag)
                tpv_val, q_val = 0, 0
                if df_c is not None and not df_c.empty and not es_corte_futuro:
                    coinc = df_c[df_c['Programa'].str.lower() == prg.lower()]
                    if not coinc.empty:
                        tpv_val = coinc['TPV'].values[0]
                        q_val = coinc['Q_Juniper'].values[0]
                        
                if not es_corte_futuro:
                    t_tpv_list[i] += tpv_val
                    t_q_list[i] += q_val
                
                if es_corte_futuro:
                    tpv_str = ""
                    q_str = ""
                else:
                    tpv_str = f"{tpv_val:,.0f}".replace(",", ".") if tpv_val > 0 else "0"
                    q_str = str(int(q_val))
                
                row_tpv += f"<td style='border:1px solid black; padding:2px 4px; text-align:center;'>{tpv_str}</td>"
                row_q += f"<td style='border:1px solid black; padding:2px 4px; text-align:center;'>{q_str}</td>"
                
            row_tpv += "</tr>"
            row_q += "</tr>"
            
            filas_html += row_tpv
            if prg != 'MilesCare LifeMiles':
                filas_html += row_q
                
        service = EmailService()
        exito, _ = service.enviar_reporte(label_corte, filas_html, t_tpv_list, t_q_list, col_idx_actual, data_total, modo_final)
        
        wa_url = CACHE_PROCESAMIENTO.get("whatsapp_url", "") if modo_final else ""
        
        if exito:
            return JSONResponse({"status": "success", "message": "Correo enviado con éxito.", "whatsapp_url": wa_url})
        else:
            return JSONResponse({"status": "error", "message": "Fallo al enviar el correo vía SMTP."}, status_code=500)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)