import pandas as pd
import os
import re
from datetime import datetime

class DataHandler:
    def __init__(self):
        self.base_dir = os.getcwd()
        self.data_dia_dir = os.path.join(self.base_dir, "data", "data_dia")
        if not os.path.exists(self.data_dia_dir):
            os.makedirs(self.data_dia_dir, exist_ok=True)
        
        self.limpiar_archivos_antiguos()

    def limpiar_archivos_antiguos(self):
        """Borra archivos de la carpeta data_dia que no pertenezcan a la fecha actual."""
        if os.path.exists(self.data_dia_dir):
            fecha_hoy = datetime.now().date()
            for f in os.listdir(self.data_dia_dir):
                file_path = os.path.join(self.data_dia_dir, f)
                try:
                    fecha_archivo = datetime.fromtimestamp(os.path.getmtime(file_path)).date()
                    if fecha_archivo < fecha_hoy:
                        os.remove(file_path)
                except Exception as e:
                    print(f"Error limpiando {f}: {e}")

    def limpiar_directorio_dia(self):
        if os.path.exists(self.data_dia_dir):
            for f in os.listdir(self.data_dia_dir):
                try: os.remove(os.path.join(self.data_dia_dir, f))
                except: pass

    def guardar_historial_multiple(self, texto_gpt):
        # Mantenemos tu lógica de procesamiento, ahora agregando QUO si viniera en el prompt
        datos = {"630am": {}, "1230pm": {}, "630pm": {}}
        lineas = texto_gpt.split('\n')
        for linea in lineas:
            if "-" not in linea or ":" not in linea: continue
            try:
                partes, valor_raw = linea.split(":", 1)
                tags = partes.split("-")
                if len(tags) < 3: continue
                
                prog = tags[0].strip()
                corte = tags[1].strip().lower().replace(":", "").replace(" ", "")
                tipo = tags[2].strip().upper()
                
                num_limpio = re.sub(r'[^0-9]', '', valor_raw)
                valor = float(num_limpio) if num_limpio else 0
                
                if corte in datos:
                    if prog not in datos[corte]:
                        # Agregamos la columna QUO inicializada en 0
                        datos[corte][prog] = {'Programa': prog, 'TPV': 0, 'Q_Juniper': 0, 'QUO': 0}
                    
                    if "TPV" in tipo: datos[corte][prog]['TPV'] = valor
                    elif "QUO" in tipo: datos[corte][prog]['QUO'] = int(valor) # Por si GPT extrae QUOs de atrás
                    else: datos[corte][prog]['Q_Juniper'] = int(valor)
            except: continue 

        for c, programas in datos.items():
            if programas:
                df = pd.DataFrame(list(programas.values()))
                path = os.path.join(self.data_dia_dir, f"corte_{c}.csv")
                df.to_csv(path, index=False, encoding='utf-8')

    # --- CAMBIO IMPORTANTE AQUÍ ---
    def guardar_corte_actual(self, label_corte, df_tpv, conteo_juniper, conteo_quos):
        """Ahora recibe también el diccionario de QUOs para guardarlos en el CSV"""
        df = df_tpv.copy()
        df['Q_Juniper'] = df['Programa'].map(conteo_juniper).fillna(0)
        df['QUO'] = df['Programa'].map(conteo_quos).fillna(0) # Mapeamos los QUOs
        
        key = label_corte.replace(":", "").lower().replace(" ", "")
        path = os.path.join(self.data_dia_dir, f"corte_{key}.csv")
        df.to_csv(path, index=False, encoding='utf-8')

    def obtener_data_acumulada(self):
        acum = {}
        for c in ["630am", "1230pm", "630pm"]:
            p = os.path.join(self.data_dia_dir, f"corte_{c}.csv")
            if os.path.exists(p): 
                acum[c] = pd.read_csv(p, encoding='utf-8')
            else: 
                acum[c] = None
        return acum