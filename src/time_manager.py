from datetime import datetime, timedelta

class TimeManager:
    @staticmethod
    def get_current_cutoff_range():
        now = datetime.now()
        
        # Si estamos entre las 00:00 y las 06:30, operamos como el cierre de ayer
        if now.hour < 6 or (now.hour == 6 and now.minute <= 30):
            referencia = now - timedelta(days=1)
            label = "6:30pm"
            start_dt = referencia.replace(hour=12, minute=30, second=1, microsecond=0)
            end_dt = referencia.replace(hour=18, minute=30, second=0, microsecond=0)
            col_idx = 4
        else:
            if now.hour < 12 or (now.hour == 12 and now.minute <= 30):
                label = "6:30am"
                start_dt = (now - timedelta(days=1)).replace(hour=18, minute=30, second=1, microsecond=0)
                end_dt = now.replace(hour=6, minute=30, second=0, microsecond=0)
                col_idx = 2
            elif now.hour < 18 or (now.hour == 18 and now.minute <= 30):
                label = "12:30pm"
                start_dt = now.replace(hour=6, minute=30, second=1, microsecond=0)
                end_dt = now.replace(hour=12, minute=30, second=0, microsecond=0)
                col_idx = 3
            else:
                label = "6:30pm"
                start_dt = now.replace(hour=12, minute=30, second=1, microsecond=0)
                end_dt = now.replace(hour=18, minute=30, second=0, microsecond=0)
                col_idx = 4
                
        return start_dt, end_dt, label, col_idx