#!/usr/bin/env python3
"""
API Flask Complète V2 - Système S&P 500 Multi-Agents Équitable + Trading Alpaca
Version complète intégrant TOUTES les fonctionnalités existantes + améliorations équitables
FICHIER À COPIER/COLLER : sp500-api/src/main.py
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
import os
import sys
import asyncio
import threading
from datetime import datetime, timedelta
import yfinance as yf
import numpy as np
from textblob import TextBlob
import requests
import warnings
import time
import schedule
from threading import Timer
import json

# AJOUT DES IMPORTS POUR LE NOUVEAU SYSTÈME ÉQUITABLE
from dotenv import load_dotenv
load_dotenv()

# NOUVEAUX IMPORTS POUR LE MODE AUTOMATIQUE AVEC HORLOGE
import pytz
from schedule_manager import schedule_manager

# Import des nouveaux modules améliorés (avec fallback si non disponibles)
try:
    from individual_agent_v2 import AdvancedIndividualAgentV3, create_advanced_agent, analyze_symbol_advanced
    from central_orchestrator import AdvancedCentralOrchestratorV3, create_advanced_orchestrator
    EQUITABLE_SYSTEM_AVAILABLE = True
    print("✅ Système équitable V3 chargé")
except ImportError as e:
    EQUITABLE_SYSTEM_AVAILABLE = False
    print(f"⚠️ Système équitable V3 non disponible: {e}")

# Import du module de trading Alpaca CORRIGÉ
try:
    from alpaca_trading import trading_agent, execute_immediate_buy_from_recommendation
    ALPACA_AVAILABLE = True
    print("✅ Module Alpaca Trading SANS heure d'achat chargé")
except ImportError:
    ALPACA_AVAILABLE = False

# ===== CORRECTION DOUBLE ORDRE: VARIABLE DE CONTRÔLE =====
# Désactive le déclencheur équitable pour éviter les doubles ordres
DISABLE_EQUITABLE_TRIGGER = True
print(f"🔧 Déclencheur équitable: {'DÉSACTIVÉ' if DISABLE_EQUITABLE_TRIGGER else 'ACTIVÉ'}")

warnings.filterwarnings('ignore')

def validate_time_format(time_str):
    """Valide le format d'heure HH:MM"""
    try:
        datetime.strptime(time_str, '%H:%M')
        return True
    except ValueError:
        return False

# Chargement des variables d'environnement depuis .env
def load_env_file(env_path):
    """Charge les variables d'environnement depuis un fichier .env"""
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        return True
    except Exception as e:
        print(f"Erreur chargement .env: {e}")
        return False

# Charger le fichier .env au démarrage
env_file_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
if os.path.exists(env_file_path):
    load_env_file(env_file_path)
    print(f"📁 Fichier .env chargé: {env_file_path}")
else:
    print(f"⚠️ Fichier .env non trouvé: {env_file_path}")

# Configuration Flask
app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'

# Configuration CORS pour Render + Netlify
CORS(app, origins=[
    'http://localhost:3000',  # Pour le développement local
    'http://localhost:3001',  # Pour le développement local
    'https://sensational-pavlova-7f2b18.netlify.app',  # Votre URL Netlify réelle
    'https://sp500-day-tradingbot-dashboard.netlify.app',  # URL alternative
    'https://main--sp500-day-tradingbot-dashboard.netlify.app'  # URL de branche
], supports_credentials=True )

# Instance globale de l'orchestrateur équitable V3 (si disponible)
if EQUITABLE_SYSTEM_AVAILABLE:
    orchestrator_v2 = AdvancedCentralOrchestratorV3()
    print("🚀 Orchestrateur Central Avancé V3 initialisé")
else:
    orchestrator_v2 = None


# ===== FONCTION DE SYNCHRONISATION AJOUTÉE =====

def sync_trading_config_with_analysis():
    """
    FONCTION MODIFIÉE: Synchronise la configuration du trading avec l'analyse
    Assure que l'heure de vente est cohérente - ACHAT IMMÉDIAT activé
    """
    try:
        if not ALPACA_AVAILABLE:
            return {'success': False, 'message': 'Module Alpaca non disponible'}
        
        # Récupérer l'heure de vente configurée dans l'interface
        auto_sell_time = trading_agent.config.get('auto_sell_time', '15:50')   # Utilise l'heure de vente de la configuration trading
        
        # Mettre à jour la configuration du trading (SANS heure d'achat)
        trading_config_update = {
            'auto_sell_time': auto_sell_time
        }
        
        result = trading_agent.update_config(trading_config_update)
        
        if result.get('success', False):
            print(f"✅ Configuration trading synchronisée:")
            print(f"   - Heure de vente: {auto_sell_time}")
            print(f"   - Achat immédiat: ACTIVÉ (plus d'heure d'achat)")
        else:
            print(f"❌ Erreur synchronisation config: {result.get('message', 'Erreur inconnue')}")
        
        return result
        
    except Exception as e:
        print(f"❌ Erreur synchronisation configuration: {e}")
        return {'success': False, 'message': str(e)}

# Variables globales pour les modes (système original conservé)
system_status = {
    'running': False,
    'analyzed_stocks': 0,
    'total_stocks': 0,
    'start_time': None,
    'last_update': None,
    'top_opportunities': [],
    'mode': 'manual',  # 'manual' ou 'auto'
    'auto_timer_500': 0,  # Timer pour analyse 500 tickers (en minutes) - DEPRECATED
    'auto_timer_10': 0,   # Timer pour analyse 10 finalistes (en minutes) - DEPRECATED
    'schedule_500_time': None,  # Heure programmée pour analyse 500 (format "HH:MM")
    'schedule_10_time': None,   # Heure programmée pour analyse 10 (format "HH:MM")
    'schedule_500_enabled': False,  # Activation de l'horaire 500
    'schedule_10_enabled': False,   # Activation de l'horaire 10
    'phase': 'idle',      # 'analyzing_500', 'analyzing_10', 'completed'
    'top_10_candidates': [],
    'final_recommendation': None,
    # Nouveaux champs pour le système équitable
    'equitable_mode': False,  # Mode équitable activé
    'diversity_metrics': None,
    'performance_stats': {},
    # Option pour utiliser la recommandation finale en mode auto
    'use_final_recommendation': False,
    # NOUVEAU: Tracker pour éviter les doubles achats
    'processed_recommendations': set()  # Set des recommandations déjà traitées (symbol + timestamp)
}
analysis_thread = None
stop_analysis_flag = False
auto_timer_500 = None  # DEPRECATED - à remplacer par schedule_job_500
auto_timer_10 = None   # DEPRECATED - à remplacer par schedule_job_10
schedule_job_500 = None  # Job de planification pour analyse 500
schedule_job_10 = None   # Job de planification pour analyse 10

print("🚀 API Flask V2 avec Système Équitable + Trading Alpaca initialisée")
print("⚖️ Système de sélection équitable disponible" if EQUITABLE_SYSTEM_AVAILABLE else "⚠️ Système équitable en mode fallback")
print("💰 Trading Alpaca disponible" if ALPACA_AVAILABLE else "⚠️ Trading Alpaca en mode fallback")

# ===== CORRECTION PRINCIPALE: NOUVELLE FONCTION POUR DÉCLENCHER L'ACHAT IMMÉDIAT =====

def get_recommendation_id(recommendation):
    """
    NOUVELLE FONCTION: Génère un identifiant unique pour une recommandation
    Basé sur le symbole et le timestamp pour éviter les doubles traitements
    """
    if not recommendation:
        return None
    
    symbol = recommendation.get('symbol', 'UNKNOWN')
    timestamp = recommendation.get('timestamp', 'NO_TIME')
    
    # Créer un ID unique basé sur le symbole et le timestamp
    return f"{symbol}_{timestamp}"

def is_recommendation_already_processed(recommendation):
    """
    NOUVELLE FONCTION: Vérifie si une recommandation a déjà été traitée pour un achat
    """
    rec_id = get_recommendation_id(recommendation)
    if not rec_id:
        return False
    
    return rec_id in system_status['processed_recommendations']

def mark_recommendation_as_processed(recommendation):
    """
    NOUVELLE FONCTION: Marque une recommandation comme déjà traitée
    """
    rec_id = get_recommendation_id(recommendation)
    if rec_id:
        system_status['processed_recommendations'].add(rec_id)
        print(f"📝 Recommandation marquée comme traitée: {rec_id}")

def trigger_immediate_auto_buy_on_recommendation():
    """
    FONCTION CORRIGÉE: Déclenche l'achat automatique immédiat seulement si autorisé
    Vérifie le flag can_send_to_trading avant d'exécuter l'achat
    """
    try:
        if not ALPACA_AVAILABLE:
            print("⚠️ Module Alpaca Trading non disponible - pas d'achat automatique")
            return
        
        # Vérifier si le mode auto trading est activé
        if not trading_agent.config.get('auto_trading_enabled', False):
            print("ℹ️ Mode auto trading non activé - pas d'achat automatique")
            return
        
        # Récupérer la recommandation finale
        final_recommendation = system_status.get('final_recommendation')
        if not final_recommendation:
            print("ℹ️ Aucune recommandation finale disponible")
            return
        
        # NOUVELLE VÉRIFICATION: Éviter les doubles achats
        if is_recommendation_already_processed(final_recommendation):
            symbol = final_recommendation.get('symbol', 'N/A')
            print(f"🔄 ACHAT DÉJÀ EFFECTUÉ pour {symbol} - Éviter la duplication")
            return
        
        # CORRECTION CRITIQUE: Vérifier si l'envoi vers trading est autorisé
        can_send = final_recommendation.get('can_send_to_trading', True)
        if not can_send:
            symbol = final_recommendation.get('symbol', 'N/A')
            score = final_recommendation.get('score', 0)
            print(f"🚫 ACHAT BLOQUÉ pour {symbol} - Score {score}% insuffisant (mode seuil actif)")
            return
        
        symbol = final_recommendation.get('symbol')
        if not symbol:
            print("⚠️ Symbole manquant dans la recommandation finale")
            return
        
        score = final_recommendation.get('score', 0)
        print(f"🚀 DÉCLENCHEMENT ACHAT AUTOMATIQUE IMMÉDIAT pour {symbol} (Score validé: {score}%)")
        
        # Exécuter l'achat immédiat
        result = execute_immediate_buy_from_recommendation(symbol)
        
        if result.get('success', False):
            print(f"✅ ACHAT AUTOMATIQUE IMMÉDIAT RÉUSSI: {result.get('message', '')}")
            # NOUVEAU: Marquer la recommandation comme traitée pour éviter les doubles achats
            mark_recommendation_as_processed(final_recommendation)
        else:
            print(f"❌ ÉCHEC ACHAT AUTOMATIQUE IMMÉDIAT: {result.get('message', 'Erreur inconnue')}")
            
    except Exception as e:
        print(f"❌ Erreur critique dans trigger_immediate_auto_buy_on_recommendation: {e}")
        import traceback
        traceback.print_exc()

# ===== FONCTIONS DE CALCUL MANUEL DES INDICATEURS TECHNIQUES (CONSERVÉES) =====

def calculate_rsi(prices, period=14):
    """Calcul manuel du RSI"""
    if len(prices) < period + 1:
        return 50
    
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calcul manuel du MACD"""
    if len(prices) < slow:
        return 0, 0, 0
    
    def ema(data, period):
        multiplier = 2 / (period + 1)
        ema_values = [data[0]]
        for i in range(1, len(data)):
            ema_values.append((data[i] * multiplier) + (ema_values[-1] * (1 - multiplier)))
        return ema_values
    
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)
    
    macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(ema_slow))]
    signal_line = ema(macd_line, signal)
    histogram = [macd_line[i] - signal_line[i] for i in range(len(signal_line))]
    
    return macd_line[-1] if macd_line else 0, signal_line[-1] if signal_line else 0, histogram[-1] if histogram else 0

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calcul manuel des Bollinger Bands"""
    if len(prices) < period:
        return prices[-1], prices[-1], prices[-1]
    
    sma = sum(prices[-period:]) / period
    variance = sum([(p - sma) ** 2 for p in prices[-period:]]) / period
    std = variance ** 0.5
    
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)
    
    return upper, sma, lower

# ===== FONCTIONS D'ANALYSE (CONSERVÉES ET AMÉLIORÉES) =====

def analyze_stock_with_polygon(symbol):
    """Analyse d'une action avec Polygon uniquement"""
    try:
        # Utilisation de Polygon
        polygon_key = os.getenv('POLYGON_API_KEY')
        if polygon_key:
            try:
                url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev"
                params = {"apikey": polygon_key}
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('results'):
                        result = data['results'][0]
                        # Simulation de données historiques pour les calculs
                        current_price = result['c']
                        prices = [current_price * (1 + np.random.normal(0, 0.01)) for _ in range(50)]
                        volumes = [result['v']] * 50
                        
                        return analyze_with_prices(symbol, prices, volumes, "Polygon")
            except Exception as e:
                print(f"Erreur Polygon pour {symbol}: {e}")
        
        # Fallback: Yahoo Finance
        return analyze_stock_simple(symbol)
        
    except Exception as e:
        print(f"Erreur analyse pour {symbol}: {e}")
        return analyze_stock_simple(symbol)

def analyze_with_prices(symbol, prices, volumes, source):
    """Analyse avec données de prix et volumes"""
    try:
        if not prices:
            return None
        
        # Calculs des indicateurs
        rsi = calculate_rsi(prices)
        macd, macd_signal, macd_hist = calculate_macd(prices)
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(prices)
        
                # Calcul du score amélioré GRANULAIRE
        score = 50.0  # Score de base (float pour précision)
        
        # Ajustements RSI granulaires
        if rsi <= 15:
            score += 45.0 + (15 - rsi) * 0.5
        elif rsi <= 20:
            score += 40.0 + (20 - rsi) * 1.0
        elif rsi <= 25:
            score += 32.0 + (25 - rsi) * 1.6
        elif rsi <= 30:
            score += 22.0 + (30 - rsi) * 2.0
        elif rsi <= 35:
            score += 12.0 + (35 - rsi) * 2.0
        elif rsi <= 40:
            score += 4.0 + (40 - rsi) * 1.6
        elif rsi <= 45:
            score -= 2.0 + (rsi - 40) * 1.2
        elif rsi <= 55:
            score -= 4.0 + (rsi - 45) * 0.2
        elif rsi <= 60:
            score -= 8.0 + (rsi - 55) * 0.8
        elif rsi <= 65:
            score -= 14.0 + (rsi - 60) * 1.2
        elif rsi <= 70:
            score -= 22.0 + (rsi - 65) * 1.6
        elif rsi <= 75:
            score -= 32.0 + (rsi - 70) * 2.0
        elif rsi <= 80:
            score -= 40.0 + (rsi - 75) * 1.6
        else:
            score -= 45.0 + (rsi - 80) * 1.0
        
        # Ajustements MACD granulaires
        if macd > macd_signal:
            hist_strength = abs(macd_hist) * 1000
            score += 8.0 + min(hist_strength * 2.5, 12.0)
        else:
            hist_strength = abs(macd_hist) * 1000
            score -= 6.0 + min(hist_strength * 2.0, 10.0)
        
        # Ajustements Bollinger granulaires
        current_price = prices[-1]
        if bb_upper != bb_lower:
            bb_position = (current_price - bb_lower) / (bb_upper - bb_lower)
            if bb_position <= 0.1:
                score += 12.0 + (0.1 - bb_position) * 30.0
            elif bb_position <= 0.2:
                score += 6.0 + (0.2 - bb_position) * 60.0
            elif bb_position >= 0.9:
                score -= 12.0 + (bb_position - 0.9) * 30.0
            elif bb_position >= 0.8:
                score -= 6.0 + (bb_position - 0.8) * 60.0
            else:
                score += (0.5 - abs(bb_position - 0.5)) * 4.0
        
        # Ajustement volume granulaire
        if volumes and len(volumes) > 1:
            avg_vol = np.mean(volumes[:-1])
            if avg_vol > 0:
                vol_ratio = volumes[-1] / avg_vol
                if vol_ratio >= 2.0:
                    score += 8.0 + min((vol_ratio - 2.0) * 2.0, 4.0)
                elif vol_ratio >= 1.5:
                    score += 4.0 + (vol_ratio - 1.5) * 8.0
                elif vol_ratio >= 1.2:
                    score += (vol_ratio - 1.2) * 13.3
                elif vol_ratio < 0.8:
                    score -= (0.8 - vol_ratio) * 15.0
        
        # Limitation du score avec précision
        score = max(1.0, min(99.0, score))
        score = round(score, 1)  # Arrondi à 1 décimale

        
        # Ajustement volume (confirmation des signaux)
        if volumes and volumes[-1] > np.mean(volumes):
            score += 10  # Volume élevé confirme le signal
        
        # Limitation du score
        score = max(0, min(100, score))
        
        # Détermination de la recommandation
        if score >= 85:
            recommendation = "STRONG_BUY"
        elif score >= 70:
            recommendation = "BUY"
        elif score >= 55:
            recommendation = "WEAK_BUY"
        elif score >= 45:
            recommendation = "HOLD"
        elif score >= 30:
            recommendation = "WEAK_SELL"
        elif score >= 15:
            recommendation = "SELL"
        else:
            recommendation = "STRONG_SELL"
        
        # Calcul du changement de prix
        if len(prices) >= 2:
            change = ((prices[-1] - prices[-2]) / prices[-2]) * 100
        else:
            change = 0
        
        return {
            'symbol': symbol,
            'price': round(current_price, 2),
            'change': round(change, 2),
            'score': round(score, 1),
            'recommendation': recommendation,
            'rsi': round(rsi, 2),
            'macd': round(macd, 4),
            'volume': volumes[-1] if volumes else 0,
            'source': source,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"Erreur analyse avec prix pour {symbol}: {e}")
        return None

def analyze_stock_simple(symbol):
    """Analyse simplifiée d'une action avec Yahoo Finance (fallback)"""
    try:
        # Récupération des données
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="3mo")
        
        if hist.empty:
            return None
        
        prices = hist['Close'].tolist()
        volumes = hist['Volume'].tolist()
        
        return analyze_with_prices(symbol, prices, volumes, "Yahoo Finance")
        
    except Exception as e:
        print(f"Erreur analyse simple pour {symbol}: {e}")
        return None

def load_sp500_symbols():
    """Charge la liste complète des symboles S&P 500"""
    try:
        # Essayer de charger le fichier CSV
        csv_path = os.path.join(os.path.dirname(__file__), 'S&P_list.csv')
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            symbols = df['symbol'].tolist()
            print(f"Chargé {len(symbols)} symboles depuis {csv_path}")
            return symbols
        else:
            print(f"Fichier CSV non trouvé: {csv_path}")
    except Exception as e:
        print(f"Erreur chargement S&P 500: {e}")
    
    # Liste complète des symboles S&P 500 (version étendue pour 500 symboles)
    sp500_symbols = [
        # Technology (80 symboles)
        'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'GOOG', 'META', 'TSLA', 'NFLX', 'ADBE', 'CRM',
        'ORCL', 'INTC', 'AMD', 'QCOM', 'AVGO', 'NOW', 'INTU', 'AMAT', 'LRCX', 'KLAC',
        'SNPS', 'CDNS', 'MRVL', 'ADI', 'NXPI', 'MCHP', 'FTNT', 'PANW', 'CRWD', 'ZS',
        'OKTA', 'DDOG', 'NET', 'SNOW', 'PLTR', 'RBLX', 'U', 'TWLO', 'ZM', 'DOCU',
        'WORK', 'TEAM', 'SHOP', 'SQ', 'PYPL', 'COIN', 'HOOD', 'SOFI', 'AFRM', 'UBER',
        'LYFT', 'DASH', 'ABNB', 'BKNG', 'EXPE', 'TRIP', 'EBAY', 'ETSY', 'AMZN', 'MELI',
        'CSCO', 'IBM', 'HPQ', 'DELL', 'VMW', 'CTSH', 'ACN', 'TXN', 'MU', 'WDC',
        
        # Healthcare (60 symboles)
        'UNH', 'JNJ', 'PFE', 'ABBV', 'LLY', 'TMO', 'ABT', 'MRK', 'DHR', 'BMY',
        'AMGN', 'GILD', 'VRTX', 'REGN', 'ISRG', 'SYK', 'BSX', 'MDT', 'EW', 'DXCM',
        'ZBH', 'BDX', 'BAX', 'HOLX', 'IDXX', 'IQV', 'A', 'ALGN', 'MRNA', 'BNTX',
        'NVAX', 'INO', 'SRNE', 'VXRT', 'CODX', 'QDEL', 'FLGT', 'TDOC', 'VEEV', 'AMWL',
        'ONEM', 'HIMS', 'ACCD', 'DOCS', 'CERT', 'OMCL', 'PRGO', 'TEVA', 'BIIB', 'ILMN',
        'INCY', 'TECH', 'CELG', 'ALXN', 'BMRN', 'SGEN', 'EXAS', 'PTCT', 'RARE', 'FOLD',
        
        # Financial Services (60 symboles)
        'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'AXP', 'BLK', 'SCHW', 'SPGI',
        'CME', 'ICE', 'MCO', 'COF', 'TFC', 'USB', 'PNC', 'BK', 'STT', 'NTRS',
        'RF', 'KEY', 'FITB', 'HBAN', 'CFG', 'MTB', 'ZION', 'CMA', 'PBCT', 'SIVB',
        'ALLY', 'LC', 'SOFI', 'UPST', 'AFRM', 'SQ', 'PYPL', 'MA', 'V', 'DFS',
        'SYF', 'CACC', 'WRLD', 'TREE', 'ENVA', 'CURO', 'FCFS', 'BRK.A', 'BRK.B', 'AIG',
        'PRU', 'MET', 'AFL', 'ALL', 'TRV', 'PGR', 'CB', 'AON', 'MMC', 'WTW',
        
        # Consumer Cyclical (50 symboles)
        'AMZN', 'HD', 'MCD', 'NKE', 'SBUX', 'TJX', 'LOW', 'BKNG', 'MAR', 'GM',
        'F', 'TSLA', 'CCL', 'RCL', 'NCLH', 'MGM', 'WYNN', 'LVS', 'DIS', 'CMCSA',
        'NFLX', 'T', 'VZ', 'CHTR', 'TMUS', 'DISH', 'SIRI', 'YUM', 'QSR', 'DPZ',
        'CMG', 'SHAK', 'WING', 'TXRH', 'DENN', 'CAKE', 'RUTH', 'ROST', 'COST', 'WMT',
        'TGT', 'KSS', 'M', 'JWN', 'BBY', 'BEST', 'GPS', 'ANF', 'AEO', 'URBN',
        
        # Consumer Defensive (40 symboles)
        'WMT', 'PG', 'KO', 'PEP', 'COST', 'MDLZ', 'CL', 'KMB', 'GIS', 'K',
        'HSY', 'MKC', 'SJM', 'CPB', 'CAG', 'HRL', 'TSN', 'KHC', 'UNFI', 'KR',
        'SYY', 'USFD', 'PFGC', 'CALM', 'SAFM', 'LANC', 'JJSF', 'CVS', 'WBA', 'RAD',
        'RITE', 'FRED', 'DRUG', 'HSKA', 'VLGEA', 'INGR', 'POST', 'SMPL', 'BGFV', 'BIG',
        
        # Energy (40 symboles)
        'XOM', 'CVX', 'COP', 'EOG', 'SLB', 'MPC', 'VLO', 'PSX', 'OXY', 'BKR',
        'HAL', 'DVN', 'FANG', 'MRO', 'APA', 'HES', 'KMI', 'OKE', 'EPD', 'ET',
        'WMB', 'ENB', 'TRP', 'PPL', 'ETP', 'ETE', 'SEP', 'MPLX', 'ANDX', 'SMLP',
        'USAC', 'NGL', 'CAPL', 'PBFX', 'DMLP', 'ENLC', 'ENLK', 'EEP', 'EEQ', 'CEQP',
        
        # Industrials (50 symboles)
        'BA', 'CAT', 'GE', 'MMM', 'HON', 'UPS', 'RTX', 'LMT', 'NOC', 'GD',
        'DE', 'EMR', 'ETN', 'ITW', 'PH', 'CMI', 'FDX', 'CSX', 'UNP', 'NSC',
        'LUV', 'DAL', 'AAL', 'UAL', 'JBLU', 'ALK', 'SAVE', 'HA', 'MESA', 'SKYW',
        'WM', 'RSG', 'CWST', 'CLH', 'GFL', 'CSTM', 'HURN', 'PLOW', 'BOOM', 'FAST',
        'MSM', 'SNA', 'IR', 'DOV', 'ROK', 'XYL', 'FLS', 'FLOW', 'PUMP', 'VLTO',
        
        # Materials (30 symboles)
        'LIN', 'APD', 'SHW', 'FCX', 'NEM', 'DOW', 'DD', 'PPG', 'ECL', 'IFF',
        'ALB', 'CE', 'VMC', 'MLM', 'NUE', 'STLD', 'RS', 'RPM', 'SEE', 'PKG',
        'IP', 'WRK', 'SON', 'SLGN', 'KWR', 'TROX', 'HWKN', 'IOSP', 'MTRN', 'BCPC',
        
        # Utilities (30 symboles)
        'NEE', 'DUK', 'SO', 'D', 'EXC', 'AEP', 'SRE', 'PEG', 'XEL', 'ED',
        'EIX', 'WEC', 'ES', 'DTE', 'PPL', 'CMS', 'NI', 'LNT', 'EVRG', 'AEE',
        'FE', 'CNP', 'ETR', 'ATO', 'NWE', 'OGE', 'UGI', 'SWX', 'SR', 'MDU',
        
        # Real Estate (25 symboles)
        'AMT', 'PLD', 'CCI', 'EQIX', 'PSA', 'WELL', 'DLR', 'O', 'SBAC', 'EXR',
        'AVB', 'EQR', 'VTR', 'ESS', 'MAA', 'UDR', 'CPT', 'FRT', 'BXP', 'KIM',
        'REG', 'HST', 'ARE', 'VNO', 'SLG',
        
        # Communication Services (25 symboles)
        'GOOGL', 'META', 'NFLX', 'DIS', 'CMCSA', 'VZ', 'T', 'CHTR', 'TMUS', 'DISH',
        'TWTR', 'SNAP', 'PINS', 'MTCH', 'IAC', 'FOXA', 'FOX', 'PARA', 'WBD', 'SIRI',
        'LUMN', 'CTL', 'FTR', 'CNSL', 'ATUS'
    ]
    
    print(f"Utilisation de la liste étendue avec {len(sp500_symbols)} symboles")
    return sp500_symbols

def analyze_news_sentiment(symbol):
    """Analyse du sentiment des news Yahoo Finance"""
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        
        if not news:
            return 0.0
        
        sentiments = []
        for article in news[:5]:  # Analyser les 5 derniers articles
            title = article.get('title', '')
            if title:
                blob = TextBlob(title)
                sentiments.append(blob.sentiment.polarity)
        
        return np.mean(sentiments) if sentiments else 0.0
        
    except Exception as e:
        print(f"Erreur analyse news pour {symbol}: {e}")
        return 0.0

# ===== FONCTIONS DE PLANIFICATION AUTOMATIQUE (CONSERVÉES) =====

def start_auto_schedule_500():
    """Démarre la planification automatique pour l'analyse des 500 tickers"""
    global schedule_job_500
    
    if system_status['schedule_500_enabled'] and system_status['schedule_500_time']:
        schedule_time = system_status['schedule_500_time']
        print(f"⏰ Planification automatique 500 tickers: {schedule_time}")
        
        def auto_start_500():
            print(f"🕐 Démarrage automatique de l'analyse des 500 tickers à {schedule_time}")
            if start_analysis_500():
                print("✅ Analyse 500 démarrée automatiquement")
            else:
                print("❌ Impossible de démarrer l'analyse 500 automatiquement")
        
        # Programmer l'exécution quotidienne à l'heure spécifiée
        schedule.every().day.at(schedule_time).do(auto_start_500)
        schedule_job_500 = True
        print(f"📅 Analyse 500 tickers programmée quotidiennement à {schedule_time}")

def start_auto_schedule_10():
    """Démarre la planification automatique pour l'analyse des 10 finalistes"""
    global schedule_job_10
    
    if system_status['schedule_10_enabled'] and system_status['schedule_10_time']:
        schedule_time = system_status['schedule_10_time']
        print(f"⏰ Planification automatique 10 finalistes: {schedule_time}")
        
        def auto_start_10():
            print(f"🕐 Démarrage automatique de l'analyse des 10 finalistes à {schedule_time}")
            # Vérifier qu'on a bien un Top 10 avant de lancer
            if system_status.get('phase') == 'completed_500' and system_status.get('top_10_candidates'):
                if start_analysis_10():
                    print("✅ Analyse 10 finalistes démarrée automatiquement")
                else:
                    print("❌ Impossible de démarrer l'analyse 10 finalistes automatiquement")
            else:
                print("❌ Pas de Top 10 disponible pour l'analyse automatique")
        
        # Programmer l'exécution quotidienne à l'heure spécifiée
        schedule.every().day.at(schedule_time).do(auto_start_10)
        schedule_job_10 = True
        print(f"📅 Analyse 10 finalistes programmée quotidiennement à {schedule_time}")

def start_auto_schedule_sequence():
    """Démarre la séquence automatique avec horaires programmés"""
    global schedule_job_500, schedule_job_10
    
    # Arrêter les planifications existantes
    schedule.clear()
    schedule_job_500 = None
    schedule_job_10 = None
    
    print("🚀 Configuration de la séquence automatique avec horaires")
    
    # Programmer l'analyse des 500 tickers si activée
    if system_status['schedule_500_enabled']:
        start_auto_schedule_500()
    
    # Programmer l'analyse des 10 finalistes si activée
    if system_status['schedule_10_enabled']:
        start_auto_schedule_10()
    
    # Démarrer le thread de surveillance des planifications
    start_schedule_monitor()

def start_schedule_monitor():
    """Démarre le thread de surveillance des planifications"""
    def schedule_monitor():
        while True:
            schedule.run_pending()
            time.sleep(60)  # Vérifier toutes les minutes
    
    monitor_thread = threading.Thread(target=schedule_monitor)
    monitor_thread.daemon = True
    monitor_thread.start()
    print("📊 Moniteur de planification démarré")

# ===== FONCTIONS D'ANALYSE PRINCIPALES =====

def start_analysis_500():
    """Démarre l'analyse des 500 tickers"""
    global analysis_thread, stop_analysis_flag
    
    if system_status['running']:
        return False
    
    stop_analysis_flag = False
    
    # Choisir le mode d'analyse selon la disponibilité du système équitable
    if system_status.get('equitable_mode', False) and EQUITABLE_SYSTEM_AVAILABLE:
        analysis_thread = threading.Thread(target=run_equitable_analysis_500)
    else:
        analysis_thread = threading.Thread(target=run_analysis_500)
    
    analysis_thread.daemon = True
    analysis_thread.start()
    
    return True

def start_analysis_10():
    """Démarre l'analyse des 10 finalistes"""
    global analysis_thread, stop_analysis_flag
    
    if system_status['running']:
        return False
    
    # Vérifier qu'on a des candidats
    if not system_status.get('top_10_candidates'):
        print("❌ Aucun candidat Top 10 disponible")
        return False
    
    stop_analysis_flag = False
    
    # Choisir le mode d'analyse selon la disponibilité du système équitable
    if system_status.get('equitable_mode', False) and EQUITABLE_SYSTEM_AVAILABLE:
        analysis_thread = threading.Thread(target=run_equitable_analysis_10)
    else:
        analysis_thread = threading.Thread(target=run_analysis_10)
    
    analysis_thread.daemon = True
    analysis_thread.start()
    
    return True

def run_analysis_500():
    """Exécute l'analyse des 500 tickers S&P 500 (mode original)"""
    global stop_analysis_flag
    
    try:
        symbols = load_sp500_symbols()
        
        # Mise à jour du statut initial
        system_status.update({
            'running': True,
            'analyzed_stocks': 0,
            'total_stocks': len(symbols),
            'start_time': datetime.now().isoformat(),
            'phase': 'analyzing_500'
        })
        
        print(f"🚀 Démarrage de l'analyse de {len(symbols)} tickers S&P 500 (mode original)")
        
        results = []
        
        for i, symbol in enumerate(symbols):
            if stop_analysis_flag:
                print("⏹️ Analyse arrêtée par l'utilisateur")
                break
                
            try:
                print(f"📊 Analyse {i+1}/{len(symbols)}: {symbol}")
                
                # Analyse de l'action
                analysis = analyze_stock_with_polygon(symbol)
                
                if analysis:
                    results.append(analysis)
                    print(f"✅ {symbol}: Score {analysis['score']} - {analysis['recommendation']} (Source: {analysis.get('source', 'Unknown')})")
                else:
                    print(f"❌ Échec analyse {symbol}")
                
                # Mise à jour du statut
                system_status.update({
                    'analyzed_stocks': i + 1,
                    'last_update': datetime.now().isoformat()
                })
                
                # Pause entre analyses
                time.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Erreur analyse {symbol}: {e}")
        
        # Tri et sélection du Top 10
        results.sort(key=lambda x: x['score'], reverse=True)
        top_10 = results[:10]
        
        # Mise à jour du statut final
        system_status.update({
            'running': False,
            'phase': 'completed_500',
            'last_update': datetime.now().isoformat(),
            'top_10_candidates': top_10,
            'top_opportunities': results[:20]  # Top 20 pour affichage
        })
        
        print(f"✅ Analyse des 500 tickers terminée - Top 10 sélectionné")
        
    except Exception as e:
        print(f"❌ Erreur critique dans l'analyse 500: {e}")
        system_status.update({
            'running': False,
            'phase': 'error',
            'last_update': datetime.now().isoformat()
        })

def run_equitable_analysis_500():
    """Exécute l'analyse équitable des 500 tickers avec le système V2"""
    global stop_analysis_flag
    
    try:
        print("🚀 Démarrage de l'analyse équitable des 500 tickers (Système V2)")
        
        # Utilisation de l'orchestrateur équitable V2
        result = asyncio.run(orchestrator_v2.start_equitable_analysis_500())
        
        if result['success']:
            print("✅ Analyse équitable démarrée avec succès")
            
            # Surveillance de l'avancement
            while orchestrator_v2.status.running and not stop_analysis_flag:
                status = orchestrator_v2.get_status()
                
                # Mise à jour du statut système
                system_status.update({
                    'running': True,
                    'analyzed_stocks': status.get('analyzed_stocks', 0),
                    'total_stocks': status.get('total_stocks', 500),
                    'phase': 'analyzing_500_equitable',
                    'last_update': datetime.now().isoformat()
                })
                
                time.sleep(2)  # Vérifier toutes les 2 secondes
            
            # Récupération des résultats finaux
            if not stop_analysis_flag:
                top_10_result = orchestrator_v2.get_top_10()
                diversity_metrics = orchestrator_v2.status.diversity_metrics
                
                # Conversion pour compatibilité avec l'interface existante
                if top_10_result.get('top_10'):
                    system_status.update({
                        'running': False,
                        'phase': 'completed_500_equitable',
                        'top_10_candidates': top_10_result['top_10'],
                        'diversity_metrics': diversity_metrics.__dict__ if diversity_metrics else None,
                        'last_update': datetime.now().isoformat()
                    })
                    
                    print(f"✅ Analyse équitable terminée - Top 10 équitable sélectionné")
                    print(f"🎯 Score de diversité: {diversity_metrics.diversity_score:.1f}/100" if diversity_metrics else "")
                else:
                    raise Exception("Aucun résultat Top 10 équitable obtenu")
            else:
                print("⏹️ Analyse équitable arrêtée par l'utilisateur")
        else:
            raise Exception(f"Échec démarrage analyse équitable: {result.get('message', 'Erreur inconnue')}")
            
    except Exception as e:
        print(f"❌ Erreur critique dans l'analyse équitable 500: {e}")
        system_status.update({
            'running': False,
            'phase': 'error',
            'last_update': datetime.now().isoformat()
        })

def run_analysis_10():
    """Exécute l'analyse approfondie des 10 finalistes (mode original)"""
    global stop_analysis_flag
    
    try:
        candidates = system_status.get('top_10_candidates', [])
        
        if not candidates:
            print("❌ Aucun candidat disponible pour l'analyse des 10")
            return
        
        # Mise à jour du statut initial
        system_status.update({
            'running': True,
            'analyzed_stocks': 0,
            'total_stocks': len(candidates),
            'start_time': datetime.now().isoformat(),
            'phase': 'analyzing_10'
        })
        
        print(f"🔍 Analyse approfondie des {len(candidates)} finalistes (mode original)")
        
        enhanced_results = []
        
        for i, candidate in enumerate(candidates):
            if stop_analysis_flag:
                print("⏹️ Analyse arrêtée par l'utilisateur")
                break
                
            try:
                symbol = candidate['symbol']
                print(f"🔬 Analyse approfondie {i+1}/{len(candidates)}: {symbol}")
                
                # Analyse approfondie avec sentiment
                enhanced_analysis = analyze_stock_with_polygon(symbol)
                
                if enhanced_analysis:
                    # Ajout de l'analyse de sentiment
                    sentiment = analyze_news_sentiment(symbol)
                    enhanced_analysis['sentiment'] = round(sentiment, 3)
                    
                    # Ajustement du score avec le sentiment
                    sentiment_bonus = sentiment * 10  # Bonus/malus basé sur le sentiment
                    enhanced_analysis['score'] = min(100, max(0, enhanced_analysis['score'] + sentiment_bonus))
                    enhanced_analysis['score'] = round(enhanced_analysis['score'], 1)
                    
                    enhanced_results.append(enhanced_analysis)
                    print(f"✅ {symbol}: Score final {enhanced_analysis['score']:.1f} (sentiment: {sentiment:.3f})")
                
                # Mise à jour du statut
                system_status.update({
                    'analyzed_stocks': i + 1,
                    'last_update': datetime.now().isoformat()
                })
                
                # Pause plus longue pour l'analyse approfondie
                time.sleep(1)
                
            except Exception as e:
                print(f"❌ Erreur analyse approfondie {candidate['symbol']}: {e}")
        
        # CORRECTION FINALE: Tri final et création de la recommandation (toujours créée pour l'affichage)
        enhanced_results.sort(key=lambda x: x['score'], reverse=True)
        final_recommendation = enhanced_results[0] if enhanced_results else None
        
        if final_recommendation:
            score = final_recommendation.get('score', 0)
            symbol = final_recommendation.get('symbol', 'N/A')
            print(f"✅ Recommandation finale créée: {symbol} (Score: {score}%)")
            
            # Vérifier si elle peut être envoyée vers trading (mode seuil)
            can_send_to_trading = True
            if auto_threshold_config.get('enabled', False) and auto_threshold_config.get('running', False):
                target_score = auto_threshold_config.get('target_score', 70.0)
                if score < target_score:
                    can_send_to_trading = False
                    print(f"🚫 Envoi vers trading bloqué: {score}% < {target_score}% (mode seuil actif)")
                else:
                    print(f"✅ Envoi vers trading autorisé: {score}% >= {target_score}% (mode seuil actif)")
            else:
                print(f"✅ Envoi vers trading autorisé (mode normal)")
            
            # Stocker l'information de validation pour l'envoi vers trading
            final_recommendation['can_send_to_trading'] = can_send_to_trading
        
        # Mise à jour du statut final
        system_status.update({
            'running': False,
            'phase': 'completed_10',
            'last_update': datetime.now().isoformat(),
            'top_10_candidates': enhanced_results,
            'final_recommendation': final_recommendation
        })
        
        print(f"✅ Analyse des 10 finalistes terminée")
        
        # ===== CORRECTION FINALE: DÉCLENCHER L'ACHAT IMMÉDIAT SEULEMENT SI AUTORISÉ =====
        if final_recommendation:
            symbol = final_recommendation.get('symbol', 'N/A')
            can_send = final_recommendation.get('can_send_to_trading', True)
            
            print(f"🎯 RECOMMANDATION FINALE DISPONIBLE: {symbol}")
            
            if can_send:
                print(f"🚀 Déclenchement achat automatique autorisé pour {symbol}")
                # POINT D'ENTRÉE PRINCIPAL: Seul appel conservé pour éviter les doubles ordres
                trigger_immediate_auto_buy_on_recommendation()
            else:
                print(f"🚫 Achat automatique bloqué pour {symbol} - score insuffisant")
        else:
            print("ℹ️ Aucune recommandation finale disponible")
        
    except Exception as e:
        print(f"❌ Erreur critique dans l'analyse 10: {e}")
        system_status.update({
            'running': False,
            'phase': 'error',
            'last_update': datetime.now().isoformat()
        })

def run_equitable_analysis_10():
    """Exécute l'analyse équitable approfondie des 10 finalistes"""
    global stop_analysis_flag
    
    try:
        print("🔍 Démarrage de l'analyse équitable approfondie des 10 finalistes")
        
        # Utilisation de l'orchestrateur équitable V2
        result = asyncio.run(orchestrator_v2.start_deep_analysis_10())
        
        if result['success']:
            print("✅ Analyse équitable approfondie démarrée avec succès")
            
            # Surveillance de l'avancement
            while orchestrator_v2.status.running and not stop_analysis_flag:
                status = orchestrator_v2.get_status()
                
                # Mise à jour du statut système
                system_status.update({
                    'running': True,
                    'analyzed_stocks': status.get('analyzed_stocks', 0),
                    'total_stocks': status.get('total_stocks', 10),
                    'phase': 'analyzing_10_equitable',
                    'last_update': datetime.now().isoformat()
                })
                
                time.sleep(1)  # Vérifier toutes les secondes
            
            # Récupération des résultats finaux
            if not stop_analysis_flag:
                final_result = orchestrator_v2.get_final_recommendation()
                top_10_result = orchestrator_v2.get_top_10()
                
                # Mise à jour du statut final
                system_status.update({
                    'running': False,
                    'phase': 'completed_10_equitable',
                    'top_10_candidates': top_10_result.get('top_10', []),
                    'final_recommendation': final_result.get('recommendation'),
                    'last_update': datetime.now().isoformat()
                })
                
                print(f"✅ Analyse équitable approfondie terminée")
                
                # ===== CORRECTION DOUBLE ORDRE: DÉCLENCHEUR CONTRÔLÉ =====
                if final_result.get('recommendation'):
                    print(f"🎯 RECOMMANDATION FINALE ÉQUITABLE DISPONIBLE: {final_result.get('recommendation', {}).get('symbol', 'N/A')}")
                    
                    # CORRECTION: Vérifier si on est en mode seuil avant d'envoyer vers trading
                    if auto_threshold_config.get('enabled', False) and auto_threshold_config.get('running', False):
                        score = final_result.get('recommendation', {}).get('score', 0)
                        target_score = auto_threshold_config.get('target_score', 70.0)
                        print(f"🎯 Mode seuil actif - Score: {score}% | Cible: {target_score}%")
                        
                        if score >= target_score:
                            if not DISABLE_EQUITABLE_TRIGGER:
                                print(f"✅ Score cible atteint - Envoi vers trading autorisé")
                                trigger_immediate_auto_buy_on_recommendation()
                            else:
                                print(f"✅ Score cible atteint - Déclencheur équitable désactivé (évite double ordre)")
                        else:
                            print(f"❌ Score insuffisant - Pas d'envoi vers trading")
                    else:
                        # Mode normal - vérifier si le déclencheur équitable est activé
                        if not DISABLE_EQUITABLE_TRIGGER:
                            print(f"✅ Recommandation équitable créée - Envoi vers trading")
                            trigger_immediate_auto_buy_on_recommendation()
                        else:
                            print(f"✅ Recommandation équitable créée - Déclencheur équitable désactivé (évite double ordre)")
            else:
                print("⏹️ Analyse équitable approfondie arrêtée par l'utilisateur")
        else:
            raise Exception(f"Échec démarrage analyse équitable approfondie: {result.get('message', 'Erreur inconnue')}")
            
    except Exception as e:
        print(f"❌ Erreur critique dans l'analyse équitable 10: {e}")
        system_status.update({
            'running': False,
            'phase': 'error',
            'last_update': datetime.now().isoformat()
        })

# ===== FONCTIONS UTILITAIRES =====

def reset_analysis_data():
    """Réinitialise les données d'analyse en mémoire"""
    global system_status
    
    print("🧹 Réinitialisation des données d'analyse...")
    
    # Sauvegarder les paramètres de configuration
    mode = system_status.get('mode', 'manual')
    schedule_500_time = system_status.get('schedule_500_time')
    schedule_10_time = system_status.get('schedule_10_time')
    schedule_500_enabled = system_status.get('schedule_500_enabled', False)
    schedule_10_enabled = system_status.get('schedule_10_enabled', False)
    equitable_mode = system_status.get('equitable_mode', False)
    
    # Réinitialiser les données d'analyse
    system_status.update({
        'running': False,
        'analyzed_stocks': 0,
        'total_stocks': 0,
        'start_time': None,
        'last_update': None,
        'top_opportunities': [],
        'phase': 'idle',
        'top_10_candidates': [],
        'final_recommendation': None,
        'diversity_metrics': None,
        'performance_stats': {}
    })
    
    # Restaurer les paramètres de configuration
    system_status.update({
        'mode': mode,
        'schedule_500_time': schedule_500_time,
        'schedule_10_time': schedule_10_time,
        'schedule_500_enabled': schedule_500_enabled,
        'schedule_10_enabled': schedule_10_enabled,
        'equitable_mode': equitable_mode
    })
    
    print("✅ Données d'analyse réinitialisées")

# ===== VIDAGE QUOTIDIEN AUTOMATIQUE DU CACHE =====
def daily_cache_cleanup():
    """
    Vidage quotidien automatique du cache à minuit US
    Timing parfait : après market fermé, avant pre-market
    Une seule opération par jour en mode auto
    """
    try:
        print("🌙 VIDAGE QUOTIDIEN AUTOMATIQUE - Minuit US")
        print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        reset_analysis_data()
        print("✅ Cache vidé avec succès - Prêt pour le trading de demain")
        try:
            with open('cache_cleanup.log', 'a') as f:
                f.write(f"{datetime.now().isoformat()} - Cache vidé automatiquement\n")
        except:
            pass
    except Exception as e:
        print(f"❌ Erreur lors du vidage quotidien: {e}")
        try:
            with open('cache_cleanup.log', 'a') as f:
                f.write(f"{datetime.now().isoformat()} - ERREUR: {e}\n")
        except:
            pass

def setup_daily_cache_cleanup():
    """Configure le vidage quotidien à minuit US (EST)"""
    try:
        # Programmer pour minuit heure US (EST)
        schedule.every().day.at("00:00").do(daily_cache_cleanup)
        print("📅 Vidage quotidien programmé à minuit US (EST)")
        # TEST - À ACTIVER POUR TESTER SANS ATTENDRE MINUIT
        # schedule.every(2).minutes.do(daily_cache_cleanup)  # Test toutes les 2 minutes
        def run_scheduler():
            while True:
                try:
                    schedule.run_pending()
                    time.sleep(60)
                except Exception as e:
                    print(f"⚠️ Erreur scheduler: {e}")
                    time.sleep(300)
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        print("🚀 Scheduler de vidage quotidien démarré")
    except Exception as e:
        print(f"❌ Erreur configuration scheduler: {e}")

# ===== ENDPOINTS API PRINCIPAUX =====

@app.route('/')
def home():
    """Page d'accueil de l'API"""
    return jsonify({
        'message': 'API S&P 500 Multi-Agents Complète V2 avec Trading Alpaca',
        'version': '2.0.0',
        'features': {
            'original_analysis': True,
            'equitable_analysis': EQUITABLE_SYSTEM_AVAILABLE,
            'alpaca_trading': ALPACA_AVAILABLE,
            'automatic_scheduling': True,
            'news_sentiment': True,
            'cache_management': True,
            'diversity_metrics': EQUITABLE_SYSTEM_AVAILABLE
        },
        'endpoints': {
            'status': '/api/status',
            'analysis_500': '/api/start-analysis-500',
            'analysis_10': '/api/start-analysis-10',
            'stop': '/api/stop-analysis',
            'configure': '/api/set-mode',
            'top_10': '/api/get-top-10',
            'final_recommendation': '/api/get-final-recommendation',
            'trading': '/api/trading/*',
            'equitable': '/api/equitable/*'
        }
    })

@app.route('/api/status', methods=['GET'])
def get_status():
    """Retourne le statut actuel du système"""
    # Récupération des paramètres de configuration
    mode = system_status.get('mode', 'manual')
    schedule_500_time = system_status.get('schedule_500_time')
    schedule_10_time = system_status.get('schedule_10_time')
    schedule_500_enabled = system_status.get('schedule_500_enabled', False)
    schedule_10_enabled = system_status.get('schedule_10_enabled', False)
    equitable_mode = system_status.get('equitable_mode', False)
    
    # Ajouter les données manquantes pour le frontend
    status_response = system_status.copy()
    
    # CORRECTION: Exclure les champs non-sérialisables en JSON
    if 'processed_recommendations' in status_response:
        del status_response['processed_recommendations']
    
    # S'assurer que top_10_candidates et final_recommendation sont inclus
    if 'top_10_candidates' not in status_response:
        status_response['top_10_candidates'] = []
    if 'final_recommendation' not in status_response:
        status_response['final_recommendation'] = None
    
    # Ajouter des informations de debug
    status_response['debug_info'] = {
        'top_10_count': len(status_response.get('top_10_candidates', [])),
        'has_final_recommendation': status_response.get('final_recommendation') is not None,
        'equitable_system_available': EQUITABLE_SYSTEM_AVAILABLE,
        'alpaca_available': ALPACA_AVAILABLE
    }
    
    # Ajouter les paramètres de configuration
    status_response.update({
        'mode': mode,
        'schedule_500_time': schedule_500_time,
        'schedule_10_time': schedule_10_time,
        'schedule_500_enabled': schedule_500_enabled,
        'schedule_10_enabled': schedule_10_enabled,
        'equitable_mode': equitable_mode
    })
    
    # Ajouter les métriques du système équitable si disponible
    if EQUITABLE_SYSTEM_AVAILABLE and orchestrator_v2:
        try:
            equitable_status = orchestrator_v2.get_status()
            status_response['equitable_status'] = equitable_status
        except:
            pass
    
    return jsonify(status_response)

@app.route('/api/start-analysis-500', methods=['POST'])
def start_analysis_500_endpoint():
    """Démarre l'analyse des 500 tickers"""
    if start_analysis_500():
        return jsonify({'success': True, 'message': 'Analyse des 500 tickers démarrée'})
    else:
        return jsonify({'success': False, 'message': 'Analyse déjà en cours'})

@app.route('/api/start-analysis-10', methods=['POST'])
def start_analysis_10_endpoint():
    """Démarre l'analyse des 10 finalistes"""
    if start_analysis_10():
        return jsonify({'success': True, 'message': 'Analyse des 10 finalistes démarrée'})
    else:
        return jsonify({'success': False, 'message': 'Analyse déjà en cours ou aucun candidat disponible'})

@app.route('/api/stop-analysis', methods=['POST'])
def stop_analysis():
    """Arrête l'analyse en cours"""
    global stop_analysis_flag
    stop_analysis_flag = True
    
    # Arrêter aussi l'orchestrateur équitable si actif
    if EQUITABLE_SYSTEM_AVAILABLE and orchestrator_v2:
        try:
            orchestrator_v2.stop_analysis()
        except:
            pass
    
    return jsonify({'success': True, 'message': 'Arrêt de l\'analyse demandé'})

@app.route('/api/set-mode', methods=['POST'])
def set_mode():
    """Configure le mode et les timers"""
    try:
        data = request.get_json()
        
        # Mise à jour des paramètres
        system_status['mode'] = data.get('mode', 'manual')
        system_status['auto_timer_500'] = data.get('timer_500', 30)
        system_status['auto_timer_10'] = data.get('timer_10', 15)
        
        # Nouveaux paramètres d'horloges
        system_status['schedule_500_time'] = data.get('schedule_500_time')
        system_status['schedule_10_time'] = data.get('schedule_10_time')
        system_status['schedule_500_enabled'] = data.get('schedule_500_enabled', False)
        system_status['schedule_10_enabled'] = data.get('schedule_10_enabled', False)
        
        # Mode équitable
        system_status['equitable_mode'] = data.get('equitable_mode', False)
        
        print(f"Configuration mise à jour: {system_status['mode']}")
        print(f"Mode équitable: {system_status['equitable_mode']}")
        print(f"Horaire 500: {system_status['schedule_500_time']} (activé: {system_status['schedule_500_enabled']})")
        print(f"Horaire 10: {system_status['schedule_10_time']} (activé: {system_status['schedule_10_enabled']})")
        # CORRECTION: Synchroniser la configuration du trading
        if ALPACA_AVAILABLE:
            sync_result = sync_trading_config_with_analysis()
            if not sync_result.get('success', False):
                print(f"⚠️ Avertissement synchronisation trading: {sync_result.get('message', 'Erreur inconnue')}")
        

        
        # Configuration de l'orchestrateur équitable si disponible
        if EQUITABLE_SYSTEM_AVAILABLE and orchestrator_v2 and system_status['equitable_mode']:
            diversity_settings = data.get('diversity_settings', {})
            if diversity_settings:
                orchestrator_v2.configure_advanced_mode('manual', diversity_settings)
        
        # Démarrer la planification automatique si le mode auto est activé
        if system_status['mode'] == 'auto':
            start_auto_schedule_sequence()
        
        return jsonify({'success': True, 'message': 'Configuration mise à jour'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})

@app.route('/api/get-top-10', methods=['GET'])
def get_top_10():
    """Retourne les 10 candidats sélectionnés"""
    top_10 = system_status.get('top_10_candidates', [])
    
    print(f"🔍 DEBUG get-top-10: {len(top_10)} candidats trouvés")
    if top_10:
        print(f"🔍 Premier candidat: {top_10[0]}")
    
    return jsonify({
        'success': True,
        'top_10': top_10,
        'count': len(top_10),
        'last_update': system_status.get('last_update'),
        'phase': system_status.get('phase'),
        'diversity_metrics': system_status.get('diversity_metrics')
    })

@app.route('/api/get-final-recommendation', methods=['GET'])
def get_final_recommendation():
    """Retourne la recommandation finale avec logique conditionnelle selon le mode"""
    recommendation = system_status.get('final_recommendation')
    
    print(f"🔍 DEBUG get-final-recommendation: {recommendation}")
    
    if recommendation:
        # CORRECTION: Logique conditionnelle selon le mode
        # 1. En mode manuel : toujours afficher la recommandation
        # 2. En mode automatique sans seuil : toujours afficher la recommandation  
        # 3. En mode automatique avec seuil : afficher seulement si score >= seuil
        
        auto_threshold_enabled = auto_threshold_config.get('enabled', False)
        system_mode = system_status.get('mode', 'manual')
        
        print(f"🔍 Mode système: {system_mode}")
        print(f"🔍 Mode seuil automatique: {auto_threshold_enabled}")
        
        # Si le mode seuil automatique est activé, vérifier le score
        if auto_threshold_enabled and system_mode == 'auto':
            score = recommendation.get('score', 0)
            target_score = auto_threshold_config.get('target_score', 70.0)
            
            print(f"🔍 Vérification seuil pour affichage:")
            print(f"   Score obtenu: {score}%")
            print(f"   Score cible: {target_score}%")
            
            if score >= target_score:
                print(f"✅ Recommandation finale validée - Score respecte le seuil")
                return jsonify({
                    'success': True,
                    'recommendation': recommendation,
                    'timestamp': system_status.get('last_update')
                })
            else:
                print(f"🚫 Recommandation finale bloquée - Score insuffisant pour le seuil configuré")
                return jsonify({
                    'success': False,
                    'message': 'Aucune recommandation finale disponible (score insuffisant)',
                    'debug_info': {
                        'score': score,
                        'target_score': target_score,
                        'threshold_mode_enabled': auto_threshold_enabled,
                        'system_mode': system_mode
                    }
                })
        else:
            # Mode manuel OU mode automatique sans seuil : toujours afficher
            print(f"✅ Recommandation finale affichée - Mode: {system_mode}, Seuil: {auto_threshold_enabled}")
            return jsonify({
                'success': True,
                'recommendation': recommendation,
                'timestamp': system_status.get('last_update')
            })
    else:
        return jsonify({
            'success': False,
            'message': 'Aucune recommandation finale disponible'
        })

@app.route('/api/get-opportunities', methods=['GET'])
def get_opportunities():
    """Retourne les opportunités d'investissement"""
    opportunities = system_status.get('top_opportunities', [])
    return jsonify({
        'success': True,
        'opportunities': opportunities,
        'count': len(opportunities),
        'last_update': system_status.get('last_update')
    })

@app.route('/api/analyze-stock', methods=['POST'])
def analyze_single_stock():
    """Analyse une action spécifique"""
    data = request.get_json()
    symbol = data.get('symbol', '').upper()
    
    if not symbol:
        return jsonify({'success': False, 'message': 'Symbole requis'})
    
    try:
        # Utiliser le système équitable si disponible et activé
        if system_status.get('equitable_mode', False) and EQUITABLE_SYSTEM_AVAILABLE:
            result = asyncio.run(analyze_symbol_advanced(symbol, os.getenv('POLYGON_API_KEY')))
        else:
            result = analyze_stock_with_polygon(symbol)
        
        if result and 'error' not in result:
            return jsonify({
                'success': True,
                'analysis': result,
                'timestamp': datetime.now().isoformat(),
                'analysis_type': 'equitable' if system_status.get('equitable_mode', False) else 'standard'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Impossible d\'analyser {symbol}',
                'error': result.get('error') if result else 'Aucun résultat'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erreur analyse {symbol}: {str(e)}'
        })

@app.route('/api/health', methods=['GET'])
def health_check():
    """Vérification de santé de l'API"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0.0',
        'features': {
            'polygon': bool(os.getenv('POLYGON_API_KEY')),
            'yahoo_finance': True,
            'auto_mode': True,
            'scheduling': True,
            'alpaca_trading': ALPACA_AVAILABLE,
            'equitable_system': EQUITABLE_SYSTEM_AVAILABLE,
            'news_sentiment': True,
            'cache_management': True
        }
    })

# ===== ENDPOINTS SYSTÈME ÉQUITABLE V2 =====

@app.route('/api/equitable/configure', methods=['POST'])
def configure_equitable_system():
    """Configure le système équitable"""
    if not EQUITABLE_SYSTEM_AVAILABLE:
        return jsonify({'success': False, 'message': 'Système équitable non disponible'})
    
    try:
        data = request.get_json() or {}
        mode = data.get('mode', 'manual')
        diversity_settings = data.get('diversity_settings', {})
        
        result = orchestrator_v2.configure_advanced_mode(mode, diversity_settings)
        
        return jsonify({
            'success': result['success'],
            'message': result['message'],
            'configuration': result,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/equitable/analyze/500', methods=['POST'])
def start_equitable_analysis_500():
    """Démarre l'analyse équitable des 500 tickers"""
    if not EQUITABLE_SYSTEM_AVAILABLE:
        return jsonify({'success': False, 'message': 'Système équitable non disponible'})
    
    try:
        # Activer le mode équitable
        system_status['equitable_mode'] = True
        
        # Démarrer l'analyse
        if start_analysis_500():
            return jsonify({
                'success': True,
                'message': 'Analyse équitable des 500 tickers démarrée',
                'analysis_type': 'Equitable Analysis V2',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Analyse déjà en cours',
                'timestamp': datetime.now().isoformat()
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/equitable/analyze/10', methods=['POST'])
def start_equitable_analysis_10():
    """Démarre l'analyse équitable approfondie des 10 finalistes"""
    if not EQUITABLE_SYSTEM_AVAILABLE:
        return jsonify({'success': False, 'message': 'Système équitable non disponible'})
    
    try:
        # Activer le mode équitable
        system_status['equitable_mode'] = True
        
        # Démarrer l'analyse
        if start_analysis_10():
            return jsonify({
                'success': True,
                'message': 'Analyse équitable approfondie des 10 finalistes démarrée',
                'analysis_type': 'Deep Equitable Analysis V2',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Analyse déjà en cours ou aucun candidat disponible',
                'timestamp': datetime.now().isoformat()
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/equitable/diversity', methods=['GET'])
def get_diversity_metrics():
    """Retourne les métriques de diversité détaillées"""
    if not EQUITABLE_SYSTEM_AVAILABLE:
        return jsonify({'success': False, 'message': 'Système équitable non disponible'})
    
    try:
        diversity_metrics = system_status.get('diversity_metrics')
        
        if not diversity_metrics:
            return jsonify({
                'success': False,
                'message': 'Aucune métrique de diversité disponible',
                'timestamp': datetime.now().isoformat()
            })
        
        return jsonify({
            'success': True,
            'data': {
                'diversity_metrics': diversity_metrics,
                'interpretation': {
                    'diversity_score': {
                        'value': diversity_metrics.get('diversity_score', 0),
                        'interpretation': _interpret_diversity_score(diversity_metrics.get('diversity_score', 0))
                    },
                    'sector_concentration': {
                        'max_concentration': diversity_metrics.get('max_sector_concentration', 0),
                        'interpretation': _interpret_concentration(diversity_metrics.get('max_sector_concentration', 0))
                    }
                }
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/equitable/performance', methods=['GET'])
def get_equitable_performance():
    """Retourne les statistiques de performance du système équitable"""
    if not EQUITABLE_SYSTEM_AVAILABLE:
        return jsonify({'success': False, 'message': 'Système équitable non disponible'})
    
    try:
        performance_stats = system_status.get('performance_stats', {})
        
        return jsonify({
            'success': True,
            'data': {
                'performance_stats': performance_stats,
                'system_health': {
                    'error_rate': performance_stats.get('error_rate', 0),
                    'success_rate': 100 - performance_stats.get('error_rate', 0),
                    'average_analysis_time': performance_stats.get('average_analysis_time', 0),
                    'total_analyses': performance_stats.get('total_analyses', 0)
                }
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ===== ENDPOINTS TRADING ALPACA (CONSERVÉS INTÉGRALEMENT) =====

@app.route('/api/trading/configure', methods=['POST'])
def configure_trading():
    """Configure les clés API Alpaca"""
    if not ALPACA_AVAILABLE:
        return jsonify({'success': False, 'message': 'Module Alpaca Trading non disponible'})
    
    try:
        data = request.get_json()
        
        paper_key = data.get('paper_api_key', '')
        paper_secret = data.get('paper_secret_key', '')
        live_key = data.get('live_api_key', '')
        live_secret = data.get('live_secret_key', '')
        mode = data.get('mode', 'paper')
        
        result = trading_agent.configure_api_keys(
            paper_key, paper_secret, live_key, live_secret, mode
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/trading/status', methods=['GET'])
def get_trading_status_route():
    """Récupère le statut de connexion trading"""
    if not ALPACA_AVAILABLE:
        return jsonify({'success': False, 'message': 'Module Alpaca Trading non disponible'})
    
    try:
        from alpaca_trading import get_trading_status
        status = get_trading_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/trading/portfolio', methods=['GET'])
def get_portfolio_route():
    """Récupère le portefeuille"""
    if not ALPACA_AVAILABLE:
        return jsonify({'success': False, 'message': 'Module Alpaca Trading non disponible'})
    
    try:
        from alpaca_trading import get_portfolio
        portfolio = get_portfolio()
        return jsonify(portfolio)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/trading/buy', methods=['POST'])
def buy_stock():
    """Achète une action"""
    if not ALPACA_AVAILABLE:
        return jsonify({'success': False, 'message': 'Module Alpaca Trading non disponible'})
    
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        amount = data.get('amount')
        
        if not symbol or not amount:
            return jsonify({'success': False, 'message': 'Symbole et montant requis'})
        
        result = trading_agent.buy_stock(symbol, amount)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/trading/sell', methods=['POST'])
def sell_stock():
    """Vend une action"""
    if not ALPACA_AVAILABLE:
        return jsonify({'success': False, 'message': 'Module Alpaca Trading non disponible'})
    
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        qty = data.get('qty')
        
        if not symbol:
            return jsonify({'success': False, 'message': 'Symbole requis'})
        
        result = trading_agent.sell_stock(symbol, qty)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    
@app.route('/api/trading/order', methods=['POST'])
def place_order():
    """Place un ordre d'achat ou de vente unifié"""
    if not ALPACA_AVAILABLE:
        return jsonify({'success': False, 'message': 'Module Alpaca Trading non disponible'})
    
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        qty = data.get('qty')
        side = data.get('side')  # 'buy' ou 'sell'
        order_type = data.get('order_type', 'market')
        
        if not symbol or not qty or not side:
            return jsonify({'success': False, 'message': 'Symbole, quantité et side requis'})
        
        if side not in ['buy', 'sell']:
            return jsonify({'success': False, 'message': 'Side doit être "buy" ou "sell"'})
        
        # Utiliser la fonction place_manual_order du trading_agent
        result = trading_agent.place_manual_order(symbol, qty, side, order_type)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/trading/config', methods=['POST'])
def update_trading_config():
    """Met à jour la configuration de trading"""
    if not ALPACA_AVAILABLE:
        return jsonify({'success': False, 'message': 'Module Alpaca Trading non disponible'})
    
    try:
        data = request.get_json()
        
        # Validations spécifiques pour les paramètres de trading
        if 'auto_sell_time' in data:
            auto_sell_time = data['auto_sell_time']
            if not validate_time_format(auto_sell_time):
                return jsonify({'success': False, 'message': 'Format d\'heure invalide pour auto_sell_time'})
        
        # Validation pour take_profit_percent
        if 'take_profit_percent' in data:
            try:
                take_profit = float(data['take_profit_percent'])
                if not (0.0 <= take_profit <= 5.0):
                    return jsonify({'success': False, 'message': 'Take profit doit être entre 0 et 5%'})
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'Take profit doit être un nombre valide'})
        
        # Validation pour stop_loss_percent
        if 'stop_loss_percent' in data:
            try:
                stop_loss = float(data['stop_loss_percent'])
                if not (0.0 <= stop_loss <= 5.0):
                    return jsonify({'success': False, 'message': 'Stop loss doit être entre 0 et 5%'})
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'Stop loss doit être un nombre valide'})
        
        # Validation pour investment_percent
        if 'investment_percent' in data:
            try:
                investment = float(data['investment_percent'])
                if not (1.0 <= investment <= 100.0):
                    return jsonify({'success': False, 'message': 'Pourcentage d\'investissement doit être entre 1 et 100%'})
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'Pourcentage d\'investissement doit être un nombre valide'})
        
        result = trading_agent.update_config(data)
        
        # Plus de reprogrammation nécessaire - achat immédiat activé
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/trading/auto/start', methods=['POST'])
def start_auto_trading():
    """Démarre le trading automatique"""
    if not ALPACA_AVAILABLE:
        return jsonify({'success': False, 'message': 'Module Alpaca Trading non disponible'})
    
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        use_recommendation = data.get('use_recommendation', False)
        
        # CORRECTION: Stocker l'option use_recommendation globalement
        system_status['use_final_recommendation'] = use_recommendation
        print(f"🎯 Option 'utiliser la recommandation finale': {'Activée' if use_recommendation else 'Désactivée'}")
        
        if not symbol:
            return jsonify({'success': False, 'message': 'Symbole requis'})
        
        result = trading_agent.start_auto_trading_with_recommendation(use_recommendation, symbol)
        
        if result.get('success', False) and use_recommendation:
            # Si une recommandation finale est déjà disponible, elle sera traitée par le système principal
            if system_status.get('final_recommendation'):
                print("🎯 Recommandation finale déjà disponible - Sera traitée par le système principal")
                # CORRECTION DOUBLE ORDRE: Appel supprimé pour éviter la duplication
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/trading/auto/stop', methods=['POST'])
def stop_auto_trading():
    """Arrête le trading automatique"""
    if not ALPACA_AVAILABLE:
        return jsonify({'success': False, 'message': 'Module Alpaca Trading non disponible'})
    
    try:
        # CORRECTION: Réinitialiser l'option use_final_recommendation
        system_status['use_final_recommendation'] = False
        print("🎯 Option 'utiliser la recommandation finale' réinitialisée")
        
        result = trading_agent.stop_auto_trading_mode()
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/trading/auto/status', methods=['GET'])
def get_auto_trading_status():
    """Récupère le statut du trading automatique"""
    if not ALPACA_AVAILABLE:
        return jsonify({'success': False, 'message': 'Module Alpaca Trading non disponible'})
    
    try:
        status = trading_agent.get_auto_trading_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/trading/calculate-investment', methods=['POST'])
def calculate_investment():
    """Calcule le montant d'investissement pour un symbole"""
    if not ALPACA_AVAILABLE:
        return jsonify({'success': False, 'message': 'Module Alpaca Trading non disponible'})
    
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        
        if not symbol:
            return jsonify({'success': False, 'message': 'Symbole requis'})
        
        qty, amount = trading_agent.calculate_investment_amount(symbol)
        
        return jsonify({
            'success': True,
            'symbol': symbol,
            'qty': qty,
            'amount': amount,
            'investment_percent': trading_agent.config['investment_percent']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/trading/auto/buy-immediate', methods=['POST'])
def trigger_immediate_buy():
    """NOUVEAU ENDPOINT: Déclenche un achat immédiat en mode auto trading"""
    if not ALPACA_AVAILABLE:
        return jsonify({'success': False, 'message': 'Module Alpaca Trading non disponible'})
    
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        final_recommendation = None
        
        if not symbol:
            # Utiliser la recommandation finale si disponible
            final_recommendation = system_status.get('final_recommendation')
            if final_recommendation:
                symbol = final_recommendation.get('symbol')
            
            if not symbol:
                return jsonify({'success': False, 'message': 'Symbole requis ou aucune recommandation disponible'})
        else:
            # Si un symbole est fourni, récupérer la recommandation correspondante pour la vérification
            final_recommendation = system_status.get('final_recommendation')
        
        # NOUVELLE VÉRIFICATION: Éviter les doubles achats si on utilise la recommandation finale
        if final_recommendation and final_recommendation.get('symbol') == symbol:
            if is_recommendation_already_processed(final_recommendation):
                print(f"🔄 ACHAT DÉJÀ EFFECTUÉ pour {symbol} - Éviter la duplication dans trigger_immediate_buy")
                return jsonify({'success': False, 'message': f'Achat déjà effectué pour {symbol}'})
        
        # Exécuter l'achat immédiat
        result = execute_immediate_buy_from_recommendation(symbol)
        
        # NOUVEAU: Marquer la recommandation comme traitée si l'achat réussit et qu'on utilise la recommandation finale
        if result.get('success', False) and final_recommendation and final_recommendation.get('symbol') == symbol:
            mark_recommendation_as_processed(final_recommendation)
            print(f"📝 Recommandation marquée comme traitée après achat via API: {symbol}")
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ===== ENDPOINTS DE GESTION DU CACHE (CONSERVÉS) =====

@app.route('/api/cache-schedule-status', methods=['GET'])
def cache_schedule_status():
    """Vérifie le statut du vidage automatique quotidien"""
    try:
        jobs = schedule.get_jobs()
        cache_jobs = [job for job in jobs if 'daily_cache_cleanup' in str(job.job_func)]
        return jsonify({
            'success': True,
            'scheduled_jobs': len(cache_jobs),
            'next_run': str(cache_jobs[0].next_run) if cache_jobs else None,
            'status': 'active' if cache_jobs else 'inactive',
            'timezone': 'US Eastern (EST)',
            'description': 'Vidage automatique à minuit US - après market, avant pre-market'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        })

@app.route('/api/trigger-cache-cleanup', methods=['POST'])
def trigger_cache_cleanup():
    """Déclenche manuellement le vidage du cache (pour test)"""
    try:
        daily_cache_cleanup()
        return jsonify({
            'success': True,
            'message': 'Vidage du cache déclenché manuellement',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        })


@app.route('/api/refresh-cache', methods=['POST'])
def refresh_cache():
    """Endpoint pour rafraîchir le cache (réinitialiser les données en mémoire)"""
    try:
        reset_analysis_data()
        
        return jsonify({
            'success': True,
            'message': 'Cache rafraîchi avec succès',
            'timestamp': datetime.now().isoformat(),
            'status': {
                'phase': system_status.get('phase'),
                'top_10_count': len(system_status.get('top_10_candidates', [])),
                'opportunities_count': len(system_status.get('top_opportunities', []))
            }
        })
        
    except Exception as e:
        print(f"❌ Erreur lors du rafraîchissement du cache: {e}")
        return jsonify({
            'success': False,
            'message': f'Erreur lors du rafraîchissement: {str(e)}'
        })

@app.route('/api/cache-info', methods=['GET'])
def cache_info():
    """Endpoint pour obtenir des informations sur l'état du cache"""
    try:
        top_10 = system_status.get('top_10_candidates', [])
        opportunities = system_status.get('top_opportunities', [])
        
        # Analyser les timestamps pour détecter des données figées
        timestamps = []
        if top_10:
            timestamps = [item.get('timestamp', '') for item in top_10 if item.get('timestamp')]
        
        unique_timestamps = len(set(timestamps)) if timestamps else 0
        
        return jsonify({
            'success': True,
            'cache_status': {
                'phase': system_status.get('phase'),
                'last_update': system_status.get('last_update'),
                'top_10_count': len(top_10),
                'opportunities_count': len(opportunities),
                'unique_timestamps': unique_timestamps,
                'total_timestamps': len(timestamps),
                'potentially_stale': unique_timestamps <= 1 and len(timestamps) > 1,
                'running': system_status.get('running', False),
                'equitable_mode': system_status.get('equitable_mode', False)
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erreur lors de la récupération des infos cache: {str(e)}'
        })

# ===== ENDPOINTS DE COMPATIBILITÉ (CONSERVÉS) =====

@app.route('/api/start_analysis_500', methods=['POST'])
def start_analysis_500_compat():
    """Route de compatibilité pour start_analysis_500"""
    return start_analysis_500_endpoint()

@app.route('/api/start_analysis_10', methods=['POST'])
def start_analysis_10_compat():
    """Route de compatibilité pour start_analysis_10"""
    return start_analysis_10_endpoint()

@app.route('/api/get_top_10', methods=['GET'])
def get_top_10_compat():
    """Route de compatibilité pour get_top_10"""
    return get_top_10()

@app.route('/api/get_final_recommendation', methods=['GET'])
def get_final_recommendation_compat():
    """Route de compatibilité pour get_final_recommendation"""
    return get_final_recommendation()

@app.route('/api/stop_analysis', methods=['POST'])
def stop_analysis_compat():
    """Route de compatibilité pour stop_analysis"""
    return stop_analysis()

# ===== FONCTIONS UTILITAIRES POUR INTERPRÉTATION =====

def _interpret_diversity_score(score: float) -> str:
    """Interprète le score de diversité"""
    if score >= 80:
        return "Excellente diversité"
    elif score >= 60:
        return "Bonne diversité"
    elif score >= 40:
        return "Diversité modérée"
    elif score >= 20:
        return "Diversité faible"
    else:
        return "Diversité très faible"

def _interpret_concentration(concentration: float) -> str:
    """Interprète le niveau de concentration"""
    if concentration <= 20:
        return "Concentration très faible (idéal)"
    elif concentration <= 30:
        return "Concentration acceptable"
    elif concentration <= 40:
        return "Concentration modérée"
    elif concentration <= 50:
        return "Concentration élevée"
    else:
        return "Concentration très élevée (problématique)"
# ===== GESTION DES ERREURS =====

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'success': False,
        'error': 'Méthode non autorisée',
        'message': 'Vérifiez la méthode HTTP utilisée',
        'timestamp': datetime.now().isoformat()
    }), 405

# ===== NOUVEAU SYSTÈME D'ANALYSE AUTOMATIQUE SEUIL 70% =====

# Variables globales pour le mode analyse automatique seuil
auto_threshold_config = {
    'enabled': False,
    'target_score': 70.0,
    'max_cycles': 5,
    'delay_between_cycles': 30,  # minutes
    'current_cycle': 0,
    'running': False,
    'last_score': 0.0,
    'start_time': None
}
auto_threshold_timer = None

# ===== NOUVEAU SYSTÈME DE MODE AUTOMATIQUE AVEC HORLOGE =====

# Configuration du mode automatique avec horloge
auto_schedule_config = {
    'enabled': False,           # Mode automatique activé
    'threshold_time': None,     # Heure de déclenchement (format "HH:MM")
    'timezone': 'Europe/Paris', # Fuseau horaire
    'weekdays_only': True,      # Seulement les jours de semaine
    'auto_threshold_config': {  # Configuration du mode seuil pour l'auto
        'target_score': 70.0,
        'max_cycles': 5,
        'delay_between_cycles': 30
    }
}

# ===== FONCTIONS DU MODE AUTOMATIQUE AVEC HORLOGE =====

def validate_timezone(tz_str):
    """Valide un fuseau horaire"""
    try:
        pytz.timezone(tz_str)
        return True
    except pytz.exceptions.UnknownTimeZoneError:
        return False

def start_auto_schedule():
    """Démarre le mode automatique avec horloge"""
    try:
        if not auto_schedule_config['enabled']:
            return {'success': False, 'message': 'Mode automatique non activé'}
        
        if not auto_schedule_config['threshold_time']:
            return {'success': False, 'message': 'Heure de déclenchement non configurée'}
        
        # Démarrer le gestionnaire d'horaires s'il n'est pas déjà en cours
        if not schedule_manager.running:
            if not schedule_manager.start_scheduler():
                return {'success': False, 'message': 'Impossible de démarrer le gestionnaire d\'horaires'}
        
        # Ajouter la tâche programmée
        success = schedule_manager.add_schedule(
            time_str=auto_schedule_config['threshold_time'],
            callback=trigger_auto_threshold,
            job_id='auto_threshold',
            weekdays_only=auto_schedule_config['weekdays_only'],
            enabled=True
        )
        
        if success:
            print(f"🕐 Mode automatique démarré - Déclenchement à {auto_schedule_config['threshold_time']}")
            return {'success': True, 'message': f'Mode automatique démarré à {auto_schedule_config["threshold_time"]}'}
        else:
            return {'success': False, 'message': 'Erreur lors de la programmation de la tâche'}
            
    except Exception as e:
        print(f"Erreur démarrage mode automatique: {e}")
        return {'success': False, 'message': f'Erreur: {str(e)}'}

def stop_auto_schedule():
    """Arrête le mode automatique avec horloge"""
    try:
        # Supprimer la tâche programmée
        schedule_manager.remove_schedule('auto_threshold')
        
        # Arrêter le gestionnaire si aucune autre tâche n'est programmée
        if len(schedule_manager.scheduled_jobs) == 0:
            schedule_manager.stop_scheduler()
        
        print("⏹️ Mode automatique arrêté")
        return {'success': True, 'message': 'Mode automatique arrêté'}
        
    except Exception as e:
        print(f"Erreur arrêt mode automatique: {e}")
        return {'success': False, 'message': f'Erreur: {str(e)}'}

def trigger_auto_threshold():
    """
    CORRECTION PRINCIPALE: Déclenche automatiquement le mode seuil ET le trading à l'heure programmée
    Cette fonction est appelée par le gestionnaire d'horaires selon l'heure configurée
    """
    try:
        print("🕐 DÉCLENCHEMENT AUTOMATIQUE DU MODE SEUIL + TRADING")
        
        # Vérifier que l'analyse n'est pas déjà en cours
        if auto_threshold_config.get('running', False):
            print("⚠️ Analyse automatique déjà en cours - ignorer ce déclenchement")
            return
                
        # CORRECTION 1: Démarrer l'analyse automatique seuil
        analysis_result = start_auto_threshold_analysis()
        
        if not analysis_result.get('success', False):
            print(f"❌ Erreur démarrage analyse automatique: {analysis_result.get('message', 'Erreur inconnue')}")
            return
        
        print("✅ Analyse automatique démarrée")
        
        # CORRECTION 2: Démarrer le trading automatique en parallèle
        if ALPACA_AVAILABLE:
            # Utiliser la configuration pour déterminer si on attend la recommandation
            use_recommendation = system_status.get('equitable_mode', False)
            fallback_symbol = 'SPY'  # Symbole par défaut pour le S&P 500
            
            trading_result = trading_agent.start_auto_trading_with_recommendation(
                use_recommendation=use_recommendation, 
                fallback_symbol=fallback_symbol
            )
            
            if trading_result.get('success', False):
                print("✅ Trading automatique démarré en parallèle")
                print(f"📊 Mode recommandation: {'Activé' if use_recommendation else 'Désactivé'}")
                print(f"📈 Symbole de fallback: {fallback_symbol}")
            else:
                print(f"❌ Erreur démarrage trading automatique: {trading_result.get('message', 'Erreur inconnue')}")
        else:
            print("⚠️ Module Alpaca Trading non disponible - analyse seulement")
            
    except Exception as e:
        print(f"❌ Erreur critique dans trigger_auto_threshold: {e}")
        import traceback
        traceback.print_exc()

def configure_auto_schedule(config_data):
    """Configure le mode automatique avec horloge"""
    try:
        # Validation des paramètres
        if 'threshold_time' in config_data:
            if not validate_time_format(config_data['threshold_time']):
                return {'success': False, 'message': 'Format d\'heure invalide (utilisez HH:MM)'}
        
        if 'timezone' in config_data:
            if not validate_timezone(config_data['timezone']):
                return {'success': False, 'message': 'Fuseau horaire invalide'}
        
        # Mettre à jour la configuration
        auto_schedule_config.update(config_data)
        
        # Si le mode automatique est activé et en cours, redémarrer avec la nouvelle configuration
        if auto_schedule_config['enabled'] and 'auto_threshold' in schedule_manager.scheduled_jobs:
            stop_auto_schedule()
            start_auto_schedule()
        
        print(f"⚙️ Configuration mode automatique mise à jour")
        return {'success': True, 'message': 'Configuration mise à jour'}
        
    except Exception as e:
        print(f"Erreur configuration mode automatique: {e}")
        return {'success': False, 'message': f'Erreur: {str(e)}'}

def start_auto_threshold_analysis():
    """Démarre le mode analyse automatique avec seuil"""
    global auto_threshold_timer
    if not auto_threshold_config['enabled']:
        return {'success': False, 'message': 'Mode analyse automatique seuil non activé'}
    if auto_threshold_config['running']:
        return {'success': False, 'message': 'Analyse automatique seuil déjà en cours'}
    # Réinitialiser les paramètres
    auto_threshold_config.update({
        'running': True,
        'current_cycle': 0,
        'last_score': 0.0,
        'target_reached': False,  # CORRECTION: Réinitialiser le flag
        'start_time': datetime.now().isoformat()
    })
    print(f"🎯 Démarrage analyse automatique seuil {auto_threshold_config['target_score']}%")
    print(f"📊 Maximum {auto_threshold_config['max_cycles']} cycles, délai {auto_threshold_config['delay_between_cycles']} min")
    _execute_threshold_cycle()
    return {'success': True, 'message': 'Analyse automatique seuil démarrée'}

def stop_auto_threshold_analysis():
    """Arrête le mode analyse automatique avec seuil"""
    global auto_threshold_timer
    auto_threshold_config['running'] = False
    if auto_threshold_timer:
        auto_threshold_timer.cancel()
        auto_threshold_timer = None
    print("⏹️ Analyse automatique seuil arrêtée")
    return {'success': True, 'message': 'Analyse automatique seuil arrêtée'}

def _execute_threshold_cycle():
    """Exécute un cycle d'analyse avec seuil"""
    global auto_threshold_timer
    if not auto_threshold_config['running']:
        return
    
    # CORRECTION: Vérifier si le seuil a été atteint
    if auto_threshold_config.get('target_reached', False):
        print("🎯 Seuil déjà atteint - arrêt de l'exécution des cycles")
        auto_threshold_config['running'] = False
        return
    
    auto_threshold_config['current_cycle'] += 1
    cycle_num = auto_threshold_config['current_cycle']
    print(f"🔄 Cycle {cycle_num}/{auto_threshold_config['max_cycles']} - Analyse automatique seuil")
    if start_analysis_500():
        _monitor_threshold_analysis_500()
    else:
        print(f"❌ Impossible de démarrer le cycle {cycle_num}")
        auto_threshold_config['running'] = False

def _monitor_threshold_analysis_500():
    """Surveille l'analyse des 500 tickers pour le mode seuil"""
    def check_500_completion():
        if not auto_threshold_config['running']:
            return
        if system_status.get('phase') == 'completed_500' and not system_status.get('running'):
            print("✅ Analyse 500 terminée, démarrage analyse 10 finalistes")
            if start_analysis_10():
                _monitor_threshold_analysis_10()
            else:
                print("❌ Impossible de démarrer l'analyse des 10 finalistes")
                _schedule_next_threshold_cycle()
        elif system_status.get('running'):
            threading.Timer(10, check_500_completion).start()
        else:
            print("❌ Analyse 500 échouée")
            _schedule_next_threshold_cycle()
    threading.Timer(5, check_500_completion).start()

def _monitor_threshold_analysis_10():
    """Surveille l'analyse des 10 finalistes pour le mode seuil"""
    def check_10_completion():
        if not auto_threshold_config['running']:
            return
        if system_status.get('phase') == 'completed_10' and not system_status.get('running'):
            print("✅ Analyse 10 finalistes terminée, vérification du score")
            _check_threshold_score()
        elif system_status.get('running'):
            threading.Timer(10, check_10_completion).start()
        else:
            print("❌ Analyse 10 finalistes échouée")
            _schedule_next_threshold_cycle()
    threading.Timer(5, check_10_completion).start()

def _check_threshold_score():
    """Vérifie si le score de la recommandation finale atteint le seuil"""
    recommendation = system_status.get('final_recommendation')
    if recommendation and 'score' in recommendation:
        score = recommendation['score']
        auto_threshold_config['last_score'] = score
        target_score = auto_threshold_config['target_score']
        print(f"📊 Score obtenu: {score}% (seuil: {target_score}%)")
        
        # CORRECTION: Vérifier le mode pour décider de l'envoi vers trading
        if score >= target_score:
            print(f"🎯 SEUIL ATTEINT! Score {score}% >= {target_score}%")
            print(f"✅ Recommandation finale: {recommendation['symbol']} envoyée au trading")
            # Arrêter définitivement tous les cycles
            auto_threshold_config['running'] = False
            auto_threshold_config['target_reached'] = True
            # Annuler tout timer en cours
            global auto_threshold_timer
            if auto_threshold_timer:
                auto_threshold_timer.cancel()
                auto_threshold_timer = None
            _send_recommendation_to_trading(recommendation)
            return
        else:
            print(f"❌ Score insuffisant: {score}% < {target_score}%")
            print("🚫 Aucun envoi vers trading - score en dessous du seuil")
    else:
        print(f"❌ Score insuffisant: {auto_threshold_config['last_score']}% < {auto_threshold_config['target_score']}%")
        print("🚫 Aucun envoi vers trading - score en dessous du seuil")
    
    # Programmer le prochain cycle seulement si le seuil n'a pas été atteint
    _schedule_next_threshold_cycle()

def _schedule_next_threshold_cycle():
    """Programme le prochain cycle d'analyse"""
    global auto_threshold_timer
    if not auto_threshold_config['running']:
        return
    
    # CORRECTION: Vérifier si le seuil a été atteint dans un cycle précédent
    if auto_threshold_config.get('target_reached', False):
        print("🎯 Seuil déjà atteint - arrêt définitif des cycles")
        auto_threshold_config['running'] = False
        return
    
    current_cycle = auto_threshold_config['current_cycle']
    max_cycles = auto_threshold_config['max_cycles']
    if current_cycle >= max_cycles:
        print(f"⏰ Maximum de cycles atteint ({max_cycles})")
        print(f"📊 Meilleur score obtenu: {auto_threshold_config['last_score']}%")
        print("❌ Aucune recommandation n'a atteint le seuil - arrêt des analyses")
        auto_threshold_config['running'] = False
        return
    delay_minutes = auto_threshold_config['delay_between_cycles']
    delay_seconds = delay_minutes * 60
    print(f"⏰ Prochain cycle dans {delay_minutes} minutes...")
    auto_threshold_timer = threading.Timer(delay_seconds, _execute_threshold_cycle)
    auto_threshold_timer.start()

def _send_recommendation_to_trading(recommendation):
    """Envoie la recommandation finale au système de trading"""
    try:
        # NOUVELLE VÉRIFICATION: Éviter les doubles achats
        if is_recommendation_already_processed(recommendation):
            symbol = recommendation.get('symbol', 'N/A')
            print(f"🔄 ACHAT DÉJÀ EFFECTUÉ pour {symbol} - Éviter la duplication dans _send_recommendation_to_trading")
            return
        
        if ALPACA_AVAILABLE and system_status.get('mode') == 'auto':
            symbol = recommendation['symbol']
            
            # CORRECTION: Distinguer les deux modes
            # Mode 1: Configuration Mode et Timer (auto_schedule_config)
            # Mode 2: Configuration Mode Analyse Seuil (auto_threshold_config)
            
            if auto_schedule_config.get('enabled', False):
                # Mode "Configuration Mode et Timer" - Envoie quel que soit le score
                print(f"💰 Mode Timer: Envoi de la recommandation {symbol} au système de trading automatique")
                result = trading_agent.start_auto_trading_with_recommendation(
                    use_recommendation=False,
                    fallback_symbol=symbol
                )
                if result['success']:
                    print(f"✅ Trading automatique démarré pour {symbol}")
                    # NOUVEAU: Marquer la recommandation comme traitée
                    mark_recommendation_as_processed(recommendation)
                else:
                    print(f"❌ Erreur démarrage trading: {result['message']}")
            elif auto_threshold_config.get('enabled', False):
                # Mode "Configuration Mode Analyse Seuil" - Envoie seulement si score ≥ seuil
                score = recommendation.get('score', 0)
                target_score = auto_threshold_config.get('target_score', 70.0)
                
                if score >= target_score:
                    print(f"💰 Mode Seuil: Envoi de la recommandation {symbol} au système de trading automatique")
                    result = trading_agent.start_auto_trading_with_recommendation(
                        use_recommendation=False,
                        fallback_symbol=symbol
                    )
                    if result['success']:
                        print(f"✅ Trading automatique démarré pour {symbol}")
                        # NOUVEAU: Marquer la recommandation comme traitée
                        mark_recommendation_as_processed(recommendation)
                    else:
                        print(f"❌ Erreur démarrage trading: {result['message']}")
                else:
                    print(f"🚫 Mode Seuil: Score {score}% < {target_score}% - Aucun envoi vers trading")
            else:
                print("ℹ️ Aucun mode automatique activé - recommandation disponible pour consultation")
        else:
            print("ℹ️ Mode manuel ou trading non disponible - recommandation disponible pour consultation")
    except Exception as e:
        print(f"❌ Erreur envoi recommandation au trading: {e}")
# ===== ENDPOINTS POUR LE MODE ANALYSE AUTOMATIQUE SEUIL =====

@app.route('/api/auto-threshold/configure', methods=['POST'])
def configure_auto_threshold():
    """Configure le mode analyse automatique seuil"""
    try:
        data = request.get_json() or {}
        enabled = data.get('enabled', False)
        target_score = float(data.get('target_score', 70.0))
        max_cycles = int(data.get('max_cycles', 5))
        delay_between_cycles = int(data.get('delay_between_cycles', 30))
        if not (60.0 <= target_score <= 100.0):
            return jsonify({'success': False, 'message': 'Le score cible doit être entre 60% et 100%'})
        if not (1 <= max_cycles <= 40):
            return jsonify({'success': False, 'message': 'Le nombre de cycles doit être entre 1 et 40'})
        if not (1 <= delay_between_cycles <= 60):
            return jsonify({'success': False, 'message': 'Le délai doit être entre 5 et 120 minutes'})
        auto_threshold_config.update({
            'enabled': enabled,
            'target_score': target_score,
            'max_cycles': max_cycles,
            'delay_between_cycles': delay_between_cycles
        })
        print(f"⚙️ Configuration analyse automatique seuil mise à jour:")
        print(f"   - Activé: {enabled}")
        print(f"   - Score cible: {target_score}%")
        print(f"   - Cycles max: {max_cycles}")
        print(f"   - Délai: {delay_between_cycles} min")
        return jsonify({
            'success': True,
            'message': 'Configuration mise à jour',
            'config': auto_threshold_config.copy()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})

@app.route('/api/auto-threshold/start', methods=['POST'])
def start_auto_threshold_endpoint():
    """Démarre le mode analyse automatique seuil"""
    return jsonify(start_auto_threshold_analysis())

@app.route('/api/auto-threshold/stop', methods=['POST'])
def stop_auto_threshold_endpoint():
    """Arrête le mode analyse automatique seuil"""
    return jsonify(stop_auto_threshold_analysis())

@app.route('/api/auto-threshold/status', methods=['GET'])
def get_auto_threshold_status():
    """Retourne le statut du mode analyse automatique seuil"""
    return jsonify({
        'success': True,
        'config': auto_threshold_config.copy(),
        'timestamp': datetime.now().isoformat()
    })

# ===== NOUVEAUX ENDPOINTS API POUR LE MODE AUTOMATIQUE AVEC HORLOGE =====

@app.route('/api/auto-schedule/config', methods=['POST'])
def configure_auto_schedule_endpoint():
    """Configure le mode automatique avec horloge"""
    try:
        data = request.get_json()
        return jsonify(configure_auto_schedule(data))
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})

@app.route('/api/auto-schedule/config', methods=['GET'])
def get_auto_schedule_config():
    """Retourne la configuration du mode automatique"""
    return jsonify({
        'success': True,
        'config': auto_schedule_config.copy(),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/auto-schedule/enable', methods=['POST'])
def enable_auto_schedule():
    """Active le mode automatique"""
    auto_schedule_config['enabled'] = True
    result = start_auto_schedule()
    return jsonify(result)

@app.route('/api/auto-schedule/disable', methods=['POST'])
def disable_auto_schedule():
    """Désactive le mode automatique"""
    auto_schedule_config['enabled'] = False
    result = stop_auto_schedule()
    return jsonify(result)

@app.route('/api/auto-schedule/status', methods=['GET'])
def get_auto_schedule_status():
    """Retourne le statut du mode automatique"""
    scheduler_status = schedule_manager.get_status()
    
    return jsonify({
        'success': True,
        'config': auto_schedule_config.copy(),
        'scheduler': scheduler_status,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/auto-schedule/start', methods=['POST'])
def start_auto_schedule_endpoint():
    """Démarre le mode automatique (endpoint)"""
    return jsonify(start_auto_schedule())

@app.route('/api/auto-schedule/stop', methods=['POST'])
def stop_auto_schedule_endpoint():
    """Arrête le mode automatique (endpoint)"""
    return jsonify(stop_auto_schedule())

# ===== MODIFICATION DE L'ENDPOINT SET-MODE POUR INCLURE LE NOUVEAU MODE =====

@app.route('/api/set-mode-extended', methods=['POST'])
def set_mode_extended():
    """Configure le mode étendu avec analyse automatique seuil"""
    try:
        data = request.get_json()
        system_status['mode'] = data.get('mode', 'manual')
        system_status['auto_timer_500'] = data.get('timer_500', 30)
        system_status['auto_timer_10'] = data.get('timer_10', 15)
        system_status['schedule_500_time'] = data.get('schedule_500_time')
        system_status['schedule_10_time'] = data.get('schedule_10_time')
        system_status['schedule_500_enabled'] = data.get('schedule_500_enabled', False)
        system_status['schedule_10_enabled'] = data.get('schedule_10_enabled', False)
        system_status['equitable_mode'] = data.get('equitable_mode', False)
        
        # Configuration du mode automatique avec horloge
        auto_schedule_data = data.get('auto_schedule', {})
        if auto_schedule_data:
            configure_auto_schedule(auto_schedule_data)
        
        auto_threshold_data = data.get('auto_threshold', {})
        if auto_threshold_data:
            auto_threshold_config.update({
                'enabled': auto_threshold_data.get('enabled', False),
                'target_score': float(auto_threshold_data.get('target_score', 70.0)),
                'max_cycles': int(auto_threshold_data.get('max_cycles', 5)),
                'delay_between_cycles': int(auto_threshold_data.get('delay_between_cycles', 30))
            })
        print(f"Configuration étendue mise à jour: {system_status['mode']}")
        print(f"Mode équitable: {system_status['equitable_mode']}")
        print(f"Analyse automatique seuil: {auto_threshold_config['enabled']} (seuil: {auto_threshold_config['target_score']}%)")
        if EQUITABLE_SYSTEM_AVAILABLE and orchestrator_v2 and system_status['equitable_mode']:
            diversity_settings = data.get('diversity_settings', {})
            if diversity_settings:
                orchestrator_v2.configure_advanced_mode('manual', diversity_settings)
        if system_status['mode'] == 'auto':
            start_auto_schedule_sequence()
        
        # Démarrer le mode automatique avec horloge si activé
        if auto_schedule_config['enabled'] and auto_schedule_config['threshold_time']:
            start_auto_schedule()
        
        return jsonify({
            'success': True, 
            'message': 'Configuration étendue mise à jour',
            'auto_threshold_config': auto_threshold_config.copy(),
            'auto_schedule_config': auto_schedule_config.copy()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
    
# ===== CORRECTIONS ET AMÉLIORATIONS =====

def initialize_schedule_manager():
    """Initialise et démarre le gestionnaire d'horaires au lancement - CORRECTION"""
    try:
        if not schedule_manager.running:
            success = schedule_manager.start_scheduler()
            if success:
                print("✅ Gestionnaire d'horaires démarré automatiquement")
            else:
                print("❌ Erreur démarrage gestionnaire d'horaires")
        else:
            print("ℹ️ Gestionnaire d'horaires déjà en cours")
    except Exception as e:
        print(f"❌ Erreur initialisation gestionnaire: {e}")

@app.route('/api/debug/schedule', methods=['GET'])
def debug_schedule():
    """Endpoint de debug pour vérifier l'état du système de programmation"""
    try:
        status = {
            'schedule_manager_running': schedule_manager.running,
            'schedule_manager_jobs': len(schedule_manager.scheduled_jobs),
            'auto_schedule_config': auto_schedule_config.copy(),
            'auto_threshold_config': auto_threshold_config.copy(),
            'scheduled_jobs': schedule_manager.get_status()['jobs'] if schedule_manager.running else {},
            'current_time': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'debug_info': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/debug/trigger-test', methods=['POST'])
def debug_trigger_test():
    """Endpoint pour tester manuellement le déclenchement automatique"""
    try:
        print("🧪 TEST MANUEL DU DÉCLENCHEMENT AUTOMATIQUE")
        trigger_auto_threshold()
        return jsonify({
            'success': True,
            'message': 'Test de déclenchement exécuté - vérifiez les logs'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/trigger-auto-trading', methods=['POST'])
def trigger_auto_trading_manual():
    """
    NOUVELLE ROUTE: Déclenche manuellement le trading automatique pour les tests
    """
    try:
        data = request.get_json() or {}
        use_recommendation = data.get('use_recommendation', False)
        fallback_symbol = data.get('fallback_symbol', 'SPY')
        
        print(f"🧪 Test manuel du déclenchement automatique")
        print(f"📊 Mode recommandation: {'Activé' if use_recommendation else 'Désactivé'}")
        print(f"📈 Symbole: {fallback_symbol}")
        
        # Déclencher la fonction corrigée
        trigger_auto_threshold()
        
        return jsonify({
            'success': True, 
            'message': 'Déclenchement automatique testé - vérifiez les logs',
            'use_recommendation': use_recommendation,
            'fallback_symbol': fallback_symbol
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ===== POINT D'ENTRÉE PRINCIPAL =====

# ===== NETTOYAGE À L'ARRÊT =====

def cleanup_scheduler():
    """Nettoie le gestionnaire d'horaires lors de l'arrêt"""
    try:
        if schedule_manager.running:
            schedule_manager.stop_scheduler()
        print("🧹 Gestionnaire d'horaires nettoyé")
    except Exception as e:
        print(f"Erreur nettoyage gestionnaire: {e}")

# Enregistrer la fonction de nettoyage
import atexit
atexit.register(cleanup_scheduler)

print("🕐 Système de mode automatique avec horloge initialisé")

def check_score_threshold_before_trading(final_recommendation):
    """
    NOUVELLE FONCTION: Vérifie si le score de la recommandation atteint le seuil configuré
    Retourne True si l'envoi vers trading est autorisé, False sinon
    """
    try:
        if not auto_threshold_config.get('enabled', False):
            # Mode seuil désactivé - toujours autoriser
            return True
        
        if not final_recommendation:
            print("❌ Aucune recommandation à vérifier")
            return False
        
        score = final_recommendation.get('score', 0)
        target_score = auto_threshold_config.get('target_score', 70.0)
        
        print(f"🔍 Vérification score seuil:")
        print(f"   Score obtenu: {score}%")
        print(f"   Score cible: {target_score}%")
        print(f"   Mode seuil: {'Activé' if auto_threshold_config.get('enabled', False) else 'Désactivé'}")
        
        if score >= target_score:
            print(f"✅ SCORE VALIDE - Envoi vers trading autorisé")
            return True
        else:
            print(f"❌ SCORE INSUFFISANT - Envoi vers trading bloqué")
            return False
            
    except Exception as e:
        print(f"❌ Erreur vérification score seuil: {e}")
        return False

# Démarrer le vidage quotidien automatique
print("🔧 Configuration du vidage quotidien du cache...")
setup_daily_cache_cleanup()

if __name__ == '__main__':
    # CORRECTION: Démarrer le gestionnaire d'horaires automatiquement
    initialize_schedule_manager()
    
    print("🚀 Démarrage de l'API S&P 500 Multi-Agents Complète V2 avec Trading Alpaca - VERSION CORRIGÉE")
    print(f"⚡ Polygon: {'✅' if os.getenv('POLYGON_API_KEY') else '❌'}")
    print(f"🔄 Yahoo Finance: ✅")
    print(f"💰 Alpaca Trading: {'✅' if ALPACA_AVAILABLE else '❌'}")
    print(f"⚖️ Système Équitable V2: {'✅' if EQUITABLE_SYSTEM_AVAILABLE else '❌'}")
    print(f"📊 Planification Automatique: ✅")
    print(f"🧹 Gestion du Cache: ✅")
    print(f"📰 Analyse de Sentiment: ✅")
    print(f"🕐 Gestionnaire d'horaires: {'✅' if schedule_manager.running else '❌'}")
    print("🔧 CORRECTIONS APPLIQUÉES:")
    print("   - Déclenchement automatique analyse + trading intégré")
    print("   - Synchronisation des configurations")
    print("   - Amélioration de la planification automatique")
    
    # Configuration pour Render (modifié pour Render)
    host = '0.0.0.0'
    port = int(os.environ.get('PORT', 5000))  # Render utilise la variable PORT
    debug = False  # Toujours False en production sur Render
    print(f"🌐 Serveur démarré sur http://{host}:{port}" )
    print(f"🔧 Mode debug: {debug}")
    app.run(host=host, port=port, debug=debug, threaded=True)












































































































































