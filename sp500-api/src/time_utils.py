from datetime import datetime, time
import pytz

BELGIUM_TZ = pytz.timezone('Europe/Brussels')

def now_belgium():
    """Heure actuelle en fuseau horaire belge"""
    return datetime.now(BELGIUM_TZ)

def now_belgium_isoformat():
    """Heure actuelle belge au format ISO"""
    return now_belgium().isoformat()

def now_belgium_time():
    """Heure actuelle belge (objet time)"""
    return now_belgium().time()

def parse_time_belgium(timestr, fmt='%H:%M'):
    """Parse une heure au format belge"""
    return datetime.strptime(timestr, fmt).time()

# Outil de debug

def debug_time_comparison():
    print("Belgium:", now_belgium_isoformat())
    import pytz
    utc_now = datetime.now(pytz.utc)
    print("UTC:", utc_now.isoformat())
