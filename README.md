# 🚀 Gennius Sales Portal - Daily Sales Report

Sistema web de monitoreo y consolidación de ventas operacionales diarias (Tableau TPV + Reservas Juniper) con extracción inteligente mediante IA Vision (Google Gemini / Groq) e integración automática a Google Sheets, correo electrónico y alertas de WhatsApp.

---

## 🌟 Características Principales

* **Doble Modo de Captura TPV:** Extrae datos mediante visión IA (OCR) sobre capturas de Tableau o permite ingreso manual asistido con generador de prompts.
* **Procesamiento de Reservas Juniper:** Carga y limpia automáticamente reportes de reservas `.xls` agrupando por banco/programa.
* **Cortes Automáticos:** Time Manager inteligente que calcula cortes dinámicos (`6:30am`, `12:30pm`, `6:30pm`).
* **Seguridad & Autenticación:** Sesión segura de 7 días con soporte 2FA por correo electrónico y almacenamiento encriptado de claves (`Fernet`).
* **Sincronización en Nube:** Inyección automática en Google Sheets y envío de reportes formateados en HTML vía SMTP.
* **Alertas Inteligentes:** Generación de enlaces deep-link a WhatsApp para notificaciones operacionales de reservas en estado `QUO` e indicadores ONED Global.

---

## 🛠️ Requisitos Previos

* **Python:** 3.10 o superior.
* **Google AI Studio API Key:** Para el motor de visión predeterminado (Gemini).
* **Credenciales SMTP de Google:** Para el envío de códigos 2FA y reportes ejecutivos.

---

## 🚀 Instalación y Ejecución Local

### 1. Clonar el Repositorio
```bash
git clone [https://github.com/TU_USUARIO/gennius-sales-portal.git](https://github.com/TU_USUARIO/gennius-sales-portal.git)
cd gennius-sales-portal
```

### 2. Crear y Activar Entorno Virtual
```bash
# En Windows:
python -m venv venv
venv\Scripts\activate

# En Linux / macOS:
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependencias
```bash
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
```

### 4. Ejecutar Servidor Local
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Accede desde tu navegador web a **http://localhost:8000**.