"""
Patch global pour forcer le fuseau horaire belge
À importer en PREMIER dans main.py
"""
import os
import time
import datetime
import pytz

# Forcer le fuseau horaire système
os.environ['TZ'] = 'Europe/Brussels'
time.tzset()

# Patch global de datetime.now
BELGIUM_TZ = pytz.timezone('Europe/Brussels')
_original_now = datetime.datetime.now

def patched_now(tz=None):
    if tz is None:
        return _original_now(BELGIUM_TZ)
    return _original_now(tz)

# Remplacer globalement
# datetime.datetime.now = patched_now  # Commenté pour éviter l'erreur d'immutabilité

print(f"🕐 PATCH FUSEAU HORAIRE APPLIQUÉ - Heure: {datetime.datetime.now().strftime('%H:%M:%S %Z')}")
