import os
import json
import random
import time
import string
import smtplib
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from cryptography.fernet import Fernet

USERS_DB_PATH = os.path.join("data", "users_db.json")
ADMIN_EMAILS = ["carodriguez@wearegennius.com", "lcesartellezl@gmail.com"]

# 🟢 Búsqueda inteligente y dinámica de la llave (Soporta Local y Render Secret Files)
def _obtener_key_path():
    # 1. Ruta local en subcarpeta data/
    local_path = os.path.join("data", "secret.key")
    if os.path.exists(local_path):
        return local_path
    
    # 2. Ruta en la raíz del proyecto (donde Render coloca los Secret Files)
    root_path = "secret.key"
    if os.path.exists(root_path):
        return root_path
        
    # 3. Ruta absoluta estándar de Secret Files en Render
    etc_path = "/etc/secrets/secret.key"
    if os.path.exists(etc_path):
        return etc_path
        
    return local_path


class AuthService:
    _otps_in_memory = {}
    _fernet = None

    @classmethod
    def _get_cipher(cls):
        if cls._fernet is None:
            os.makedirs("data", exist_ok=True)
            key_path = _obtener_key_path() # 🟢 Evaluación dinámica en tiempo de ejecución
            
            if not os.path.exists(key_path):
                key = Fernet.generate_key()
                with open(key_path, "wb") as key_file:
                    key_file.write(key)
            else:
                with open(key_path, "rb") as key_file:
                    key = key_file.read().strip() # 🟢 Limpieza de saltos de línea invisibles (\n / \r)
            
            try:
                cls._fernet = Fernet(key)
            except Exception as e:
                print(f"❌ ERROR CRÍTICO INSTANCIANDO FERNET CON LLAVE ({key_path}): {e}")
                traceback.print_exc()
                # Fallback defensivo para evitar que el proceso colapse con HTTP 500
                cls._fernet = Fernet(Fernet.generate_key())
                
        return cls._fernet

    @classmethod
    def _encrypt_text(cls, text: str) -> str:
        if not text: return ""
        try:
            cipher = cls._get_cipher()
            return cipher.encrypt(text.encode('utf-8')).decode('utf-8')
        except Exception as e:
            print(f"❌ Error encriptando texto: {e}")
            return text

    @classmethod
    def _decrypt_text(cls, encrypted_text: str) -> str:
        if not encrypted_text: return ""
        try:
            cipher = cls._get_cipher()
            return cipher.decrypt(encrypted_text.encode('utf-8')).decode('utf-8')
        except Exception as e:
            # 🟢 Si falla la desencriptación (por desincronización de secret.key), captura el error sin dar HTTP 500
            print(f"⚠️ Error desencriptando texto (Posible discrepancia de secret.key): {e}")
            return encrypted_text

    @staticmethod
    def _init_db():
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(USERS_DB_PATH) or os.path.getsize(USERS_DB_PATH) == 0:
            with open(USERS_DB_PATH, "w", encoding="utf-8") as f:
                json.dump({}, f)

    @classmethod
    def _get_db(cls):
        cls._init_db()
        try:
            with open(USERS_DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            db_limpia = {}
            cls._save_db(db_limpia)
            return db_limpia

    @classmethod
    def _save_db(cls, db):
        with open(USERS_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2)

    @classmethod
    def register_user(cls, user_data: dict):
        import re
        db = cls._get_db()
        email = user_data.get("email", "").strip().lower()
        if not email:
            return False, "El correo electrónico es obligatorio."
        if email in db:
            return False, "Este correo ya se encuentra registrado."

        password = user_data.get("password", "")
        patron_pwd = r'^(?=.*[0-9])(?=.*[@$!%*?&.#_-])[A-Za-z0-9@$!%*?&.#_-]{12,}$'
        if not password or not re.match(patron_pwd, password):
            return False, "La contraseña no cumple con los requisitos (mínimo 12 caracteres, 1 número y 1 carácter especial)."

        gemini_key = user_data.get("gemini_api_key", "").strip()
        if gemini_key and (not gemini_key.startswith("A") or len(gemini_key) < 20):
            return False, "Formato de GEMINI_API_KEY no válido."

        es_admin = email in [a.lower() for a in ADMIN_EMAILS]
        
        nombre_completo = f"{user_data.get('nombre', '')} {user_data.get('apellido', '')}".strip() or email
        avatar_defecto = user_data.get("avatar") or f"https://api.dicebear.com/7.x/adventurer/svg?seed={email.split('@')[0]}&backgroundColor=ff8fab,ffb703,4cc9a7,4d96ff,b57bff"

        db[email] = {
            "password": cls._encrypt_text(password),
            "nombre": user_data.get("nombre", ""),
            "apellido": user_data.get("apellido", ""),
            "avatar": avatar_defecto,
            "es_admin": es_admin,
            "requiere_cambio_pwd": False,
            "config_env": {
                "MODELO_IA_ACTIVO": "gemini",
                "GEMINI_API_KEY": cls._encrypt_text(gemini_key),
                "GROQ_API_KEY": "",
                "HF_API_KEY": "",
                "REMITENTE": user_data.get("remitente", ""),
                "PASSWORD": cls._encrypt_text(user_data.get("google_app_password", "")),
                "MI_CORREO": user_data.get("mi_correo", ""),
                "DESTINATARIOS_FINALES": user_data.get("destinatarios_finales", []),
                "DESTINATARIOS_BCC": user_data.get("destinatarios_bcc", []),
                "NOMBRE_FIRMA": user_data.get("nombre_firma", ""),
                "CARGO_FIRMA": user_data.get("cargo_firma", ""),
                "SHEET_ID": user_data.get("sheet_id", ""),
                "GID_HOJA": user_data.get("gid_hoja", "0")
            }
        }
        cls._save_db(db)
        return True, "Cuenta registrada exitosamente."

    @classmethod
    def verify_credentials(cls, email: str, password: str):
        db = cls._get_db()
        email = email.strip().lower()
        msg_error = "Correo o contraseña incorrectos."
        if email not in db:
            return False, msg_error, None
        pwd_desencriptada = cls._decrypt_text(db[email]["password"])
        if pwd_desencriptada != password:
            return False, msg_error, None
        return True, "Credenciales válidas.", db[email]

    @classmethod
    def cargar_config_memoria(cls, email: str):
        db = cls._get_db()
        email = email.strip().lower()
        if email in db:
            cfg = db[email].get("config_env", {})
            os.environ["MODELO_IA_ACTIVO"] = cfg.get("MODELO_IA_ACTIVO", "gemini")
            os.environ["GEMINI_API_KEY"] = cls._decrypt_text(cfg.get("GEMINI_API_KEY", ""))
            os.environ["GROQ_API_KEY"] = cls._decrypt_text(cfg.get("GROQ_API_KEY", ""))
            os.environ["HF_API_KEY"] = cls._decrypt_text(cfg.get("HF_API_KEY", ""))
            os.environ["PASSWORD"] = cls._decrypt_text(cfg.get("PASSWORD", ""))
            os.environ["REMITENTE"] = cfg.get("REMITENTE", "")
            os.environ["MI_CORREO"] = cfg.get("MI_CORREO", "")
            os.environ["NOMBRE_FIRMA"] = cfg.get("NOMBRE_FIRMA", "")
            os.environ["CARGO_FIRMA"] = cfg.get("CARGO_FIRMA", "")
            os.environ["SHEET_ID"] = str(cfg.get("SHEET_ID", "")).strip()
            os.environ["GID_HOJA"] = str(cfg.get("GID_HOJA", "0")).strip()
            
            dest_finales = cfg.get("DESTINATARIOS_FINALES", [])
            os.environ["DESTINATARIOS_FINALES"] = ",".join(dest_finales) if isinstance(dest_finales, list) else str(dest_finales)
            
            dest_bcc = cfg.get("DESTINATARIOS_BCC", [])
            os.environ["DESTINATARIOS_BCC"] = ",".join(dest_bcc) if isinstance(dest_bcc, list) else str(dest_bcc)
            return True, "Configuración cargada en memoria."
        return False, "Usuario no encontrado."

    @classmethod
    def reset_password_and_email(cls, email: str):
        db = cls._get_db()
        email = email.strip().lower()
        if email not in db:
            return False, "El correo no está registrado."
        
        temp_pwd = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        db[email]["password"] = cls._encrypt_text(temp_pwd)
        db[email]["requiere_cambio_pwd"] = True
        cls._save_db(db)
        
        config = db[email].get("config_env", {})
        remitente = config.get("REMITENTE") or os.getenv("REMITENTE")
        google_pwd = cls._decrypt_text(config.get("PASSWORD", "")) or os.getenv("PASSWORD")
        
        # 🟢 Limpieza de la clave de aplicación de Google para evitar espacios accidentales de Render
        if google_pwd:
            google_pwd = google_pwd.replace(" ", "").strip()

        msg = MIMEMultipart()
        msg['From'] = remitente
        msg['To'] = email
        msg['Subject'] = "Reseteo de Contraseña - Gennius Sales"
        
        html_body = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; background-color: #0f172a; color: #f8fafc;">
          <div style="max-width: 500px; margin: 0 auto; background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 24px;">
            <h2 style="color: #38bdf8;">Reseteo de Contraseña</h2>
            <p>Se ha generado una contraseña temporal para tu cuenta:</p>
            <div style="background-color: #0f172a; border: 1px solid #0284c7; border-radius: 6px; text-align: center; padding: 14px; margin: 16px 0;">
              <span style="font-size: 24px; font-weight: bold; color: #38bdf8; letter-spacing: 2px;">{temp_pwd}</span>
            </div>
            <p style="font-size: 13px; color: #94a3b8;">Al iniciar sesión con esta clave, deberás definir tu nueva contraseña.</p>
          </div>
        </div>
        """
        msg.attach(MIMEText(html_body, 'html'))
        
        try:
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30)
            server.login(remitente, google_pwd)
            server.sendmail(remitente, [email], msg.as_string())
            server.quit()
            return True, "Se ha enviado la contraseña temporal a tu correo."
        except Exception as e:
            print(f"❌ Error enviando correo vía SMTP en reset_password_and_email: {e}")
            return False, f"Error enviando correo via SMTP: {str(e)}"

    @classmethod
    def cambiar_password(cls, email: str, nueva_pwd: str):
        db = cls._get_db()
        email = email.strip().lower()
        if email in db:
            db[email]["password"] = cls._encrypt_text(nueva_pwd)
            db[email]["requiere_cambio_pwd"] = False
            cls._save_db(db)
            return True, "Contraseña actualizada con éxito."
        return False, "Usuario no encontrado."

    @classmethod
    def send_2fa_code(cls, email: str):
        db = cls._get_db()
        email = email.strip().lower()
        if email not in db: return False, "Usuario no existe."
        
        config = db[email].get("config_env", {})
        remitente = config.get("REMITENTE") or os.getenv("REMITENTE")
        google_pwd = cls._decrypt_text(config.get("PASSWORD", "")) or os.getenv("PASSWORD")
        
        if google_pwd:
            google_pwd = google_pwd.replace(" ", "").strip()

        otp_code = f"{random.randint(100000, 999999)}"
        cls._otps_in_memory[email] = {"code": otp_code, "expires": time.time() + 600}
        
        msg = MIMEMultipart()
        msg['From'] = remitente
        msg['To'] = email
        msg['Subject'] = f"Código 2FA Gennius: {otp_code}"
        
        html_body = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; background-color: #0f172a; color: #ffffff;">
          <div style="max-width: 480px; margin: 0 auto; background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 24px;">
            <h2 style="color: #38bdf8;">Código de Verificación</h2>
            <p>Usa el siguiente código de 6 dígitos para ingresar:</p>
            <div style="background-color: #0f172a; border: 1px solid #0284c7; border-radius: 6px; text-align: center; padding: 16px; margin: 20px 0;">
              <span style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #38bdf8;">{otp_code}</span>
            </div>
          </div>
        </div>
        """
        msg.attach(MIMEText(html_body, 'html'))
        
        try:
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30)
            server.login(remitente, google_pwd)
            server.sendmail(remitente, [email], msg.as_string())
            server.quit()
            return True, "Código enviado."
        except Exception as e:
            print(f"❌ Error enviando código 2FA: {e}")
            return False, str(e)

    @classmethod
    def verify_2fa(cls, email: str, code: str):
        email = email.strip().lower()
        record = cls._otps_in_memory.get(email)
        if not record: return False, "Sin código pendiente."
        if time.time() > record["expires"]: return False, "El código expiró."
        if record["code"] != code.strip(): return False, "Código incorrecto."
        del cls._otps_in_memory[email]
        return True, "2FA OK."

    @classmethod
    def obtener_todos_usuarios(cls):
        db = cls._get_db()
        lista = []
        for em, u in db.items():
            lista.append({
                "email": em,
                "nombre": u.get("nombre"),
                "apellido": u.get("apellido"),
                "avatar": u.get("avatar"),
                "es_admin": u.get("es_admin", False)
            })
        return lista

    @classmethod
    def eliminar_usuario(cls, email: str):
        db = cls._get_db()
        email = email.strip().lower()
        if email in db:
            del db[email]
            cls._save_db(db)
            return True, "Usuario eliminado."
        return False, "Usuario no existe."

    @classmethod
    def obtener_usuario_por_email(cls, email: str):
        db = cls._get_db()
        email = email.strip().lower()
        return db.get(email)

    @classmethod
    def desencriptar_texto(cls, texto_encriptado: str) -> str:
        return cls._decrypt_text(texto_encriptado)

    @classmethod
    def update_ai_config(cls, email: str, config_env: dict):
        db = cls._get_db()
        email = email.strip().lower()
        if email not in db:
            return False, "Usuario no encontrado."
        cfg = db[email].setdefault("config_env", {})
        if "MODELO_IA_ACTIVO" in config_env:
            cfg["MODELO_IA_ACTIVO"] = config_env["MODELO_IA_ACTIVO"]
        if "GEMINI_API_KEY" in config_env and config_env["GEMINI_API_KEY"]:
            cfg["GEMINI_API_KEY"] = cls._encrypt_text(config_env["GEMINI_API_KEY"])
        if "GROQ_API_KEY" in config_env and config_env["GROQ_API_KEY"]:
            cfg["GROQ_API_KEY"] = cls._encrypt_text(config_env["GROQ_API_KEY"])
        if "HF_API_KEY" in config_env and config_env["HF_API_KEY"]:
            cfg["HF_API_KEY"] = cls._encrypt_text(config_env["HF_API_KEY"])
        cls._save_db(db)
        return True, "Configuración de IA actualizada."

    @classmethod
    def update_profile(cls, email: str, profile_data: dict):
        db = cls._get_db()
        email = email.strip().lower()
        if email not in db:
            return False, "Usuario no encontrado."
        user = db[email]
        if "nombre" in profile_data: user["nombre"] = profile_data["nombre"]
        if "apellido" in profile_data: user["apellido"] = profile_data["apellido"]
        if "avatar" in profile_data and profile_data["avatar"]: user["avatar"] = profile_data["avatar"]
        
        cfg = user.setdefault("config_env", {})
        if "gemini_api_key" in profile_data:
            val = profile_data["gemini_api_key"]
            cfg["GEMINI_API_KEY"] = cls._encrypt_text(val) if val and not val.startswith("gAAAAA") else val
        if "google_app_password" in profile_data:
            val = profile_data["google_app_password"]
            cfg["PASSWORD"] = cls._encrypt_text(val) if val and not val.startswith("gAAAAA") else val
        if "remitente" in profile_data: cfg["REMITENTE"] = profile_data["remitente"]
        if "mi_correo" in profile_data: cfg["MI_CORREO"] = profile_data["mi_correo"]
        if "destinatarios_finales" in profile_data: cfg["DESTINATARIOS_FINALES"] = profile_data["destinatarios_finales"]
        if "destinatarios_bcc" in profile_data: cfg["DESTINATARIOS_BCC"] = profile_data["destinatarios_bcc"]
        if "nombre_firma" in profile_data: cfg["NOMBRE_FIRMA"] = profile_data["nombre_firma"]
        if "cargo_firma" in profile_data: cfg["CARGO_FIRMA"] = profile_data["cargo_firma"]
        if "sheet_id" in profile_data: cfg["SHEET_ID"] = profile_data["sheet_id"]
        if "gid_hoja" in profile_data: cfg["GID_HOJA"] = profile_data["gid_hoja"]
        cls._save_db(db)
        return True, "Perfil actualizado exitosamente."

    @classmethod
    def cambiar_email(cls, email_actual: str, nuevo_email: str):
        db = cls._get_db()
        email_actual = email_actual.strip().lower()
        nuevo_email = nuevo_email.strip().lower()
        if email_actual not in db:
            return False, "El usuario actual no existe."
        if nuevo_email in db:
            return False, "El nuevo correo ya está registrado por otra cuenta."
        db[nuevo_email] = db.pop(email_actual)
        cls._save_db(db)
        return True, "Correo actualizado con éxito."