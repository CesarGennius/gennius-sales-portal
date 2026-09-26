import os
import base64
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

class EmailService:
    def __init__(self):
        self.remitente = os.getenv("REMITENTE", "").strip()
        self.password = os.getenv("PASSWORD", "").strip().replace(" ", "")
        self.mi_correo = os.getenv("MI_CORREO", "").strip()
        self.finales = [d.strip() for d in os.getenv("DESTINATARIOS_FINALES", "").split(",") if d.strip()]
        self.bcc = [d.strip() for d in os.getenv("DESTINATARIOS_BCC", "").split(",") if d.strip()]
        self.doc_id = os.getenv("SHEET_ID", "").strip()
        self.gid = os.getenv("GID_HOJA", "").strip()
        self.nombre_firma = os.getenv("NOMBRE_FIRMA", "").strip()
        self.cargo_firma = os.getenv("CARGO_FIRMA", "").strip()

    def enviar_reporte(self, label_corte, filas_html, t_tpv_list, t_q_list, col_idx, data_total, modo_final=False):
        # 🟢 Determinar destinatarios principales (To) y copias ocultas (Bcc)
        if modo_final:
            dest_to = self.finales if self.finales else ([self.mi_correo] if self.mi_correo else [])
            dest_bcc = self.bcc
        else:
            dest_to = [self.mi_correo] if self.mi_correo else []
            dest_bcc = []

        if not dest_to and not dest_bcc:
            print("⚠️ [EmailService] No hay destinatarios 'To' ni 'BCC' configurados.")
            return False, []

        sujeto = f"Revisión monitoreo operacional de ventas_corte {label_corte}"

        # 1. Diccionario bilingüe para las abreviaturas de los meses
        MESES = {
            "es": {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
                   7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"},
            "en": {1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "may", 6: "jun",
                   7: "jul", 8: "aug", 9: "sep", 10: "oct", 11: "nov", 12: "dec"}
        }

        idioma = "es"
        ahora = datetime.now()
        fecha_hoy = f"{ahora.strftime('%d')}-{MESES[idioma][ahora.month]}-{ahora.strftime('%y')}"
        p_sty = "padding: 2px 4px;"

        # --- LÓGICA DE NOTA PARA RESERVAS EN ESTADO QUO ---
        html_nota_quo = ""
        key_corte = label_corte.replace(":", "").lower().replace(" ", "")
        df_actual = data_total.get(key_corte)
        notas_lista = []

        if df_actual is not None:
            programas_alertas = []
            for _, fila in df_actual.iterrows():
                prog = fila['Programa']
                if str(prog).upper() == "TOTAL":
                    continue

                oks = fila['Q_Juniper']
                quos = fila.get('QUO', 0)
                if oks == 0 and quos > 0:
                    programas_alertas.append({"prog": prog, "quos": int(quos)})

            if programas_alertas:
                rango_txt = {
                    "6:30am": "6:30 p. m. del día de ayer y las 6:30 a. m. del día de hoy",
                    "12:30pm": "6:30 a. m. y las 12:30 p. m. del día de hoy",
                    "6:30pm": "12:30 p. m. y las 6:30 p. m. del día de hoy"
                }.get(label_corte, label_corte)

                estilo_contenedor = (
                    "background-color: #f6f7f8 !important; "
                    "border-left: 5px solid #1974ff !important; "
                    "padding: 14px 16px !important; "
                    "margin: 20px 0 !important; "
                    "border-radius: 4px;"
                )

                estilo_titulo = (
                    "color: #1974ff !important; "
                    "font-family: Arial, sans-serif !important; "
                    "font-size: 13px !important; "
                    "font-weight: bold !important; "
                    "font-style: normal !important; "
                    "letter-spacing: 0.5px; "
                    "line-height: 1 !important;"
                )

                estilo_texto_negro = (
                    "color: #000000 !important; "
                    "font-family: Arial, sans-serif !important; "
                    "font-size: 13px !important; "
                    "font-style: normal !important; "
                    "line-height: normal !important;"
                )

                if len(programas_alertas) == 1:
                    p = programas_alertas[0]
                    v_evid = "evidencia" if p['quos'] == 1 else "evidencian"
                    s_res = "reserva" if p['quos'] == 1 else "reservas"

                    texto_interno = f"""
                    <div style="{estilo_contenedor}">
                        <span style="{estilo_texto_negro}"><b style="{estilo_titulo}"> Nota importante:</b> En el corte correspondiente a las {rango_txt} del programa <b>{p['prog']}</b>, en Juniper se reportan 0 reservas confirmadas; sin embargo, se {v_evid} <b>{p['quos']}</b> {s_res} en estado QUO.</span>
                    </div>
                    """
                else:
                    listado_partes = []
                    for pa in programas_alertas:
                        s_cant = f"{pa['quos']} {'reserva' if pa['quos'] == 1 else 'reservas'}"
                        listado_partes.append(f"<b>{s_cant}</b> en estado QUO para <b>{pa['prog']}</b>")
                    
                    if len(listado_partes) > 1:
                        texto_programas = ", ".join(listado_partes[:-1]) + " y " + listado_partes[-1]
                    else:
                        texto_programas = listado_partes[0]

                    texto_interno = f"""
                    <div style="{estilo_contenedor}">
                        <span style="{estilo_texto_negro}"><b style="{estilo_titulo}"> Nota importante:</b> En el corte de las {rango_txt} se reporta que, para los siguientes programas hay 0 reservas confirmadas; sin embargo, se evidencian {texto_programas}.</span>
                    </div>
                    """

                html_nota_quo = f"""
                <div style='margin-top: 25px; font-family: Arial, sans-serif;'>
                    {texto_interno}
                </div>
                """
                notas_lista = programas_alertas

        # --- CONSTRUCCIÓN DE TOTALES ---
        t_tpv_h = "".join([
            f"<td style='border:1px solid black;{p_sty}text-align:center;'><b>"
            f"{f'{v:,.0f}'.replace(',', '.') if i <= col_idx else ''}"
            f"</b></td>"
            for i, v in enumerate(t_tpv_list)
        ])
        t_q_h = "".join([
            f"<td style='border:1px solid black;{p_sty}text-align:center;'><b>"
            f"{f'{int(v)}' if i <= col_idx else ''}"
            f"</b></td>"
            for i, v in enumerate(t_q_list)
        ])

        url_sheets = f"https://docs.google.com/spreadsheets/d/{self.doc_id}/edit?gid={self.gid}#gid={self.gid}"
        disclaimer = ("This message and any file transmitted with it contain confidential information and are intended solely for the use of the individual to whom it is addressed. Unless you are the addressee you may not use, modify, copy or disclose to anyone the message or any information contained in the message. Any point of views or opinions presented is solely those of the author and do not necessary represent those of the company if you have received the message because of an error, please advise the sender by replying to the message, and delete the material from any computer.")

        cuerpo_html = f"""
        <html>
        <head><meta charset="UTF-8"></head>
        <body style='font-family: Arial, sans-serif; color: black; line-height: 1.4;'>
            <p>Buenas equipo,<br> Espero se encuentren todos muy bien!</p>
            <p>Comparto el informe de seguimiento diario de ventas, con corte a las <b>{label_corte}</b>.</p>
            <p>En la casilla <b> TPV puntos </b> se incluye el total de <i>spend</i> en millas, según la información del panel de Tableau.<br>
            En la casilla <b> Q ventas Juniper </b> se registra el número de ventas durante la franja, de acuerdo con los datos de Juniper.</p>
            <br>
            <table style='border-collapse: collapse; width: 560px; border: 1px solid black; font-family: Arial, sans-serif;'>
                <tr style='background-color: #D9E9F3;'>
                    <th rowspan='2' style='border: 1px solid black; {p_sty} text-align: center; vertical-align: middle;'>Programa</th>
                    <th style='border: 1px solid black; {p_sty} text-align: center;'>Día</th>
                    <th colspan='3' style='border: 1px solid black; {p_sty} text-align: center;'>{fecha_hoy}</th>
                </tr>
                <tr style='background-color: #D9E9F3;'>
                    <th style='border: 1px solid black; {p_sty} text-align: center;'>Hora corte</th>
                    <th style='border: 1px solid black; {p_sty} text-align: center;'>6:30am</th>
                    <th style='border: 1px solid black; {p_sty} text-align: center;'>12:30pm</th>
                    <th style='border: 1px solid black; {p_sty} text-align: center;'>6:30pm</th>
                </tr>
                {filas_html}
                <tr>
                    <td rowspan='2' style='border: 1px solid black; {p_sty} text-align: center; vertical-align: middle;'><b>Total</b></td>
                    <td style='border: 1px solid black; {p_sty} text-align: left;'><b>TPV</b></td>{t_tpv_h}
                </tr>
                <tr><td style='border: 1px solid black; {p_sty} text-align: left;'><b>Q ventas Juniper</b></td>{t_q_h}</tr>
            </table>

            {html_nota_quo}
            <br>
            <p style='margin-bottom: 20px;'>Adjunto el enlace con el detalle del seguimiento para mayor información:<br>
            <a href='{url_sheets}' style='color: #0563C1;'>Ver detalle del seguimiento</a></p>

            <p style='margin-bottom: 0px;'>Saludos,</p>

            <div style='margin-top: 50px; font-family: Arial, sans-serif;'>
                <div style='margin-bottom: 20px; line-height: 1.2;'>
                    <span style='color: #1974ff; font-weight: bold; font-size: 17px;'>{self.nombre_firma}</span> 
                    <span style='color: #999999; font-weight: bold; font-size: 16px;'> | </span>
                    <span style='color: #001233; font-size: 14px;'>{self.cargo_firma}</span>
                </div>

                <div style='line-height: 1.2;'>
                    <span style='color: #001233; font-size: 15px;'>Now we're </span>
                    <a href='https://gennius.xyz/#/home' style='text-decoration: underline; color: #001233;'>
                        <span style='font-weight: bold; font-size: 17px; color: #001233;'>gennius</span><span style='color: #1bd0ff; font-weight: bold; font-size: 17px;'> X</span><span style='color: #1c74ff; font-weight: bold; font-size: 17px;'>Y</span><span style='color: #0a3ff2; font-weight: bold; font-size: 17px;'>Z</span>
                    </a>
                    <span style='color: #001233; font-size: 15px;'>&nbsp; building Human-to-Human technologies</span>
                </div>
            </div>

            <div style='margin-top: 18px; font-size: 10px; color: #7f7f7f; text-align: left; line-height: 1.2;'>
                {disclaimer}
            </div>
        </body>
        </html>
        """

        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from src.services.google_sheets_service import obtener_ruta_secret_file

            ruta_token = obtener_ruta_secret_file("token.json")
            if not os.path.exists(ruta_token):
                print("❌ [EmailService] No se encontró token.json para la API de Gmail")
                return False, []

            creds = Credentials.from_authorized_user_file(ruta_token)
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e_ref:
                    print(f"⚠️ Error al refrescar token de Google: {e_ref}")

            # 🟢 CONSTRUCCIÓN DEL MENSAJE UNIFICADO (UN SOLO CORREO GRUPAL)
            msg = MIMEMultipart()
            msg['From'] = self.remitente
            if dest_to:
                msg['To'] = ", ".join(dest_to)
            if dest_bcc:
                msg['Bcc'] = ", ".join(dest_bcc)
            msg['Subject'] = sujeto
            msg.attach(MIMEText(cuerpo_html, 'html', 'utf-8'))

            raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')

            url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
            headers = {
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json"
            }

            response = requests.post(url, json={"raw": raw_message}, headers=headers, timeout=15)

            if response.status_code in (200, 201):
                print(f"✅ Correo GRUPAL enviado exitosamente a TO: {dest_to} | BCC: {dest_bcc}")
                return True, notas_lista
            else:
                print(f"❌ Error HTTP Gmail API ({response.status_code}): {response.text}")
                return False, []

        except Exception as e:
            print(f"❌ ERROR ENVIANDO REPORTES ({type(e).__name__}): {e}")
            import traceback
            traceback.print_exc()
            return False, []