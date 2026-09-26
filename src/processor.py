import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import pandas as pd

class ReservationProcessor:
    def __init__(self):
        self.mapeo_interno = {
            'SCOTIA VOYAGE': 'Scotia',
            'SCOTIA': 'Scotia',
            'HANDYU WL': 'VLS',
            'CIBC': 'CIBC', 
            'FCB': 'FC', 
            'FIRST CITIZENS': 'FC',
            'NCB': 'NCB', 
            'CUSCATLAN': 'Cuscatlan',
            'MILESCARE': 'MilesCare LifeMiles'
        }

    def count_reservations_by_bank(self, df, start_dt, end_dt):
        try:
            print("\n" + "="*50)
            print("🚀 INICIANDO RASTREO DE RESERVAS JUNIPER")
            print("="*50)
            
            # Limpiar nombres de columnas
            df.columns = [str(c).strip().lower() for c in df.columns]
            
            # 1. Buscar columnas clave
            col_fecha = next((c for c in df.columns if 'fecha reserva' in c or 'fecha_reserva' in c), None)
            col_agencia = next((c for c in df.columns if 'agencia' in c), None)
            col_estado = next((c for c in df.columns if 'estado' in c), None)
            col_titular = next((c for c in df.columns if 'titular de la reserva' in c or 'titular' in c), None)

            if not col_fecha or not col_agencia:
                print("❌ ERROR CRÍTICO: No se encontró columna de fecha o agencia en el archivo.")
                return {}, {}

            df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
            if hasattr(df[col_fecha].dt, 'tz_localize') and df[col_fecha].dt.tz is not None:
                df[col_fecha] = df[col_fecha].dt.tz_localize(None)
            
            start_dt = pd.to_datetime(start_dt).tz_localize(None)
            end_dt = pd.to_datetime(end_dt).tz_localize(None)
            
            print(f"📊 Total filas crudas en el Excel: {len(df)}")
            print(f"⏰ Rango del corte: Desde [{start_dt}] Hasta [{end_dt}]")
            
            # 🎯 2. FILTRO ACTIVADO: Filtrar estrictamente las reservas de la franja de la tarde
            df_filtrado = df[(df[col_fecha] >= start_dt) & (df[col_fecha] <= end_dt)].copy()
            print(f"🎯 Filas que entran en la franja de tiempo: {len(df_filtrado)}")
            print("-"*50)

            # --- LISTA NEGRA ---
            lista_negra_agencia = ["PROMIE"] 
            apellidos_omitir = ['RUPERTOFF', 'VOKLIM', 'PRITZ', 'GENNINO', 'SORMING', 'CLEPS']

            conteo_ok = {}
            conteo_quo = {}

            # 3. Iterar por filas con impresión en tiempo real
            for idx, fila in df_filtrado.iterrows():
                nombre_raw = str(fila[col_agencia]).upper().strip()
                titular_raw = str(fila[col_titular]).upper().strip() if col_titular else ""
                estado_raw = str(fila[col_estado]).upper() if col_estado else "OK"
                fecha_fila = str(fila[col_fecha])
                
                print(f"🔍 Fila {idx} | Fecha: {fecha_fila} | Agencia: '{nombre_raw}' | Estado: '{estado_raw}' | Titular: '{titular_raw}'")
                
                # Filtro de exclusión por Agencia
                if any(negro in nombre_raw for negro in lista_negra_agencia):
                    print(f"   🚫 OMITIDA: Agencia en Lista Negra ({lista_negra_agencia})")
                    continue 

                # Filtro de exclusión por Apellido del Titular
                if any(apellido in titular_raw for apellido in apellidos_omitir):
                    print(f"   🚫 OMITIDA: Apellido en Lista Negra ({apellidos_omitir})")
                    continue

                # Identificar el banco/programa
                banco_final = "VLS"
                hizo_match = False
                for clave, estandar in self.mapeo_interno.items():
                    if clave.upper() in nombre_raw:
                        banco_final = estandar
                        hizo_match = True
                        break
                
                if not hizo_match:
                    print(f"   ⚠️ Alerta: No hubo match explícito en diccionario. Cae en VLS por defecto.")
                
                # --- LÓGICA DE ESTADOS ---
                if "PRESUPUESTO" in estado_raw or "QUO" in estado_raw:
                    conteo_quo[banco_final] = conteo_quo.get(banco_final, 0) + 1
                    print(f"   ✅ ASIGNADA A ➔ [{banco_final}] como [QUO]")
                elif "OK" in estado_raw or "CONFIRMADA" in estado_raw:
                    conteo_ok[banco_final] = conteo_ok.get(banco_final, 0) + 1
                    print(f"   ✅ ASIGNADA A ➔ [{banco_final}] como [OK]")
                else:
                    print(f"   ❓ OMITIDA: Estado raro no clasificado.")
                    pass

            print("="*50)
            print("🏁 CONTEO FINAL DETECTADO:")
            print(f"   CONFIRMADAS (OK): {conteo_ok}")
            print(f"   ALERTAS (QUO):    {conteo_quo}")
            print("="*50 + "\n")

            return conteo_ok, conteo_quo

        except Exception as e:
            print(f"❌ ERROR EN PROCESSOR: {e}")
            return {}, {}