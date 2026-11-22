from datetime import datetime, timedelta, timezone


class TimeManager:
    @staticmethod
    def get_current_cutoff_range():
        # 🟢 Hora exacta de Colombia (UTC-5 fijo, sin horario de verano)
        # Funciona idéntico en Windows local y en Render (UTC) sin depender de tzdata
        tz_bogota = timezone(timedelta(hours=-5))
        now = datetime.now(tz_bogota).replace(tzinfo=None)

        # Entre 00:00 y 06:29 operamos como el cierre de ayer (6:30pm)
        if now.hour < 6 or (now.hour == 6 and now.minute < 30):
            referencia = now - timedelta(days=1)
            label = "6:30pm"
            start_dt = referencia.replace(hour=12, minute=30, second=1, microsecond=0)
            end_dt = referencia.replace(hour=18, minute=30, second=0, microsecond=0)
            col_idx = 4
        # Entre 06:30 y 12:29 -> corte 6:30am
        elif now.hour < 12 or (now.hour == 12 and now.minute < 30):
            label = "6:30am"
            start_dt = (now - timedelta(days=1)).replace(hour=18, minute=30, second=1, microsecond=0)
            end_dt = now.replace(hour=6, minute=30, second=0, microsecond=0)
            col_idx = 2
        # Entre 12:30 y 18:29 -> corte 12:30pm
        elif now.hour < 18 or (now.hour == 18 and now.minute < 30):
            label = "12:30pm"
            start_dt = now.replace(hour=6, minute=30, second=1, microsecond=0)
            end_dt = now.replace(hour=12, minute=30, second=0, microsecond=0)
            col_idx = 3
        # Desde las 18:30 hasta las 23:59 -> corte 6:30pm
        else:
            label = "6:30pm"
            start_dt = now.replace(hour=12, minute=30, second=1, microsecond=0)
            end_dt = now.replace(hour=18, minute=30, second=0, microsecond=0)
            col_idx = 4

        return start_dt, end_dt, label, col_idx