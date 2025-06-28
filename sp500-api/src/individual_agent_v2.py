#!/usr/bin/env python3
"""
Agent Individuel Avancé V3 COMPLET - Système de Scoring Précis et Équitable
Version complète avec TOUTES les fonctions préservées + améliorations V3
FICHIER À COPIER/COLLER : sp500-api/src/individual_agent_v3_complete.py
"""

import asyncio
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
import yfinance as yf
import requests
import warnings
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import os
import sys
import math

warnings.filterwarnings('ignore')

@dataclass
class TechnicalIndicators:
    """Indicateurs techniques calculés manuellement"""
    # RSI Multi-timeframe
    rsi_7: float = 50.0
    rsi_14: float = 50.0
    rsi_21: float = 50.0
    stochastic_rsi: float = 50.0
    
    # MACD
    macd_short: float = 0.0
    macd_signal_short: float = 0.0
    macd_histogram_short: float = 0.0
    macd_standard: float = 0.0
    macd_signal_standard: float = 0.0
    macd_histogram_standard: float = 0.0
    
    # Bandes de Bollinger
    bollinger_upper: float = 0.0
    bollinger_middle: float = 0.0
    bollinger_lower: float = 0.0
    bollinger_position: float = 0.5  # Position dans les bandes (0-1)
    bollinger_width: float = 0.0
    bollinger_squeeze: bool = False
    
    # Moyennes Mobiles
    ema_5: float = 0.0
    ema_10: float = 0.0
    ema_20: float = 0.0
    ema_50: float = 0.0
    sma_100: float = 0.0
    sma_200: float = 0.0
    
    # Volume
    volume_ratio: float = 1.0  # Volume actuel / moyenne 20j
    obv: float = 0.0
    obv_trend: str = "NEUTRAL"
    vwap: float = 0.0
    volume_price_trend: float = 0.0
    
    # Patterns et Signaux
    pattern_detected: str = "NO_PATTERN"
    pattern_confidence: float = 0.0
    support_level: float = 0.0
    resistance_level: float = 0.0
    
    # Métriques de Risque
    atr: float = 0.0
    volatility_percentile: float = 50.0
    beta_adjusted: float = 1.0

@dataclass
class MarketData:
    """Données de marché enrichies"""
    symbol: str
    current_price: float
    change_percent: float
    volume: int
    market_cap: float
    sector: str
    industry: str
    beta: float
    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    price_to_book: Optional[float] = None
    debt_to_equity: Optional[float] = None

@dataclass
class AIAnalysisResult:
    """Résultat d'analyse IA complet avec scoring précis"""
    overall_score: float
    final_equitable_score: float
    
    # Scores par composant (précision décimale)
    rsi_score: float
    macd_score: float
    bollinger_score: float
    ma_score: float
    volume_score: float
    pattern_score: float
    risk_score: float
    
    # Classification équitable
    sector_rank: int
    quintile_bonus: float
    
    # Signaux
    buy_signals: List[str]
    sell_signals: List[str]
    recommendation: str
    confidence: float
    reasoning: List[str]
    
    # Nouveaux composants V3 avec valeurs par défaut (À LA FIN)
    momentum_score: float = 50.0  # Nouveau composant V3
    diversity_bonus: float = 0.0  # Nouveau bonus V3
    
    # Métadonnées
    analysis_version: str = "V3_Complete"
    timestamp: datetime = None

class TechnicalCalculator:
    """Calculateur d'indicateurs techniques sans TA-Lib (PRÉSERVÉ + AMÉLIORÉ)"""
    
    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
        """Calcule le RSI manuellement avec précision améliorée"""
        try:
            if len(prices) < period + 1:
                return 50.0
            
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            # Éviter division par zéro (amélioration V3)
            loss = loss.replace(0, 0.0001)
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            result = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
            return round(result, 2)  # Précision V3
        except:
            return 50.0
    
    @staticmethod
    def calculate_stochastic_rsi(prices: pd.Series, period: int = 14) -> float:
        """Calcule le Stochastic RSI avec précision améliorée"""
        try:
            if len(prices) < period * 2:
                return 50.0
            
            # Calcul RSI sur toute la série
            rsi_values = []
            for i in range(period, len(prices)):
                rsi = TechnicalCalculator.calculate_rsi(prices.iloc[:i+1], period)
                rsi_values.append(rsi)
            
            if len(rsi_values) < period:
                return 50.0
            
            rsi_series = pd.Series(rsi_values)
            lowest_rsi = rsi_series.rolling(window=period).min().iloc[-1]
            highest_rsi = rsi_series.rolling(window=period).max().iloc[-1]
            
            if highest_rsi == lowest_rsi:
                return 50.0
            
            stoch_rsi = (rsi_values[-1] - lowest_rsi) / (highest_rsi - lowest_rsi) * 100
            return round(float(stoch_rsi), 2)  # Précision V3
        except:
            return 50.0
    
    @staticmethod
    def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
        """Calcule MACD, Signal et Histogramme avec précision améliorée"""
        try:
            if len(prices) < slow + signal:
                return 0.0, 0.0, 0.0
            
            # EMA rapide et lente
            ema_fast = prices.ewm(span=fast).mean()
            ema_slow = prices.ewm(span=slow).mean()
            
            # MACD Line
            macd_line = ema_fast - ema_slow
            
            # Signal Line
            signal_line = macd_line.ewm(span=signal).mean()
            
            # Histogramme
            histogram = macd_line - signal_line
            
            return (
                round(float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else 0.0, 4),  # Précision V3
                round(float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else 0.0, 4),
                round(float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else 0.0, 4)
            )
        except:
            return 0.0, 0.0, 0.0
    
    @staticmethod
    def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[float, float, float, float, float]:
        """Calcule les Bandes de Bollinger avec précision améliorée"""
        try:
            if len(prices) < period:
                current_price = float(prices.iloc[-1])
                return current_price, current_price, current_price, 0.5, 0.0
            
            # Moyenne mobile simple
            sma = prices.rolling(window=period).mean()
            
            # Écart-type
            std = prices.rolling(window=period).std()
            
            # Bandes
            upper_band = sma + (std * std_dev)
            lower_band = sma - (std * std_dev)
            
            current_price = float(prices.iloc[-1])
            upper = float(upper_band.iloc[-1])
            middle = float(sma.iloc[-1])
            lower = float(lower_band.iloc[-1])
            
            # Position dans les bandes (0 = bande basse, 1 = bande haute)
            if upper != lower:
                position = (current_price - lower) / (upper - lower)
            else:
                position = 0.5
            
            # Largeur des bandes (volatilité)
            width = (upper - lower) / middle if middle != 0 else 0.0
            
            return (
                round(upper, 2),      # Précision V3
                round(middle, 2),
                round(lower, 2),
                round(position, 3),
                round(width, 4)
            )
        except:
            current_price = float(prices.iloc[-1]) if len(prices) > 0 else 0.0
            return current_price, current_price, current_price, 0.5, 0.0
    
    @staticmethod
    def calculate_ema(prices: pd.Series, period: int) -> float:
        """Calcule la Moyenne Mobile Exponentielle"""
        try:
            if len(prices) < period:
                return float(prices.mean()) if len(prices) > 0 else 0.0
            
            ema = prices.ewm(span=period).mean()
            result = float(ema.iloc[-1]) if not pd.isna(ema.iloc[-1]) else 0.0
            return round(result, 2)  # Précision V3
        except:
            return 0.0
    
    @staticmethod
    def calculate_sma(prices: pd.Series, period: int) -> float:
        """Calcule la Moyenne Mobile Simple"""
        try:
            if len(prices) < period:
                return float(prices.mean()) if len(prices) > 0 else 0.0
            
            sma = prices.rolling(window=period).mean()
            result = float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else 0.0
            return round(result, 2)  # Précision V3
        except:
            return 0.0
    
    @staticmethod
    def calculate_obv(prices: pd.Series, volumes: pd.Series) -> Tuple[float, str]:
        """Calcule l'On-Balance Volume"""
        try:
            if len(prices) < 2 or len(volumes) < 2:
                return 0.0, "NEUTRAL"
            
            obv = 0.0
            obv_values = [0.0]
            
            for i in range(1, len(prices)):
                if prices.iloc[i] > prices.iloc[i-1]:
                    obv += volumes.iloc[i]
                elif prices.iloc[i] < prices.iloc[i-1]:
                    obv -= volumes.iloc[i]
                obv_values.append(obv)
            
            # Tendance OBV (comparaison 5 dernières valeurs)
            if len(obv_values) >= 5:
                recent_trend = np.polyfit(range(5), obv_values[-5:], 1)[0]
                if recent_trend > 0:
                    trend = "UP"
                elif recent_trend < 0:
                    trend = "DOWN"
                else:
                    trend = "NEUTRAL"
            else:
                trend = "NEUTRAL"
            
            return float(obv), trend
        except:
            return 0.0, "NEUTRAL"
    
    @staticmethod
    def calculate_vwap(prices: pd.Series, volumes: pd.Series) -> float:
        """Calcule le Volume Weighted Average Price"""
        try:
            if len(prices) == 0 or len(volumes) == 0:
                return 0.0
            
            # VWAP = Σ(Price × Volume) / Σ(Volume)
            price_volume = prices * volumes
            vwap = price_volume.sum() / volumes.sum()
            
            result = float(vwap) if not pd.isna(vwap) else 0.0
            return round(result, 2)  # Précision V3
        except:
            return 0.0
    
    @staticmethod
    def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
        """Calcule l'Average True Range"""
        try:
            if len(high) < 2 or len(low) < 2 or len(close) < 2:
                return 0.0
            
            # True Range
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # ATR
            atr = true_range.rolling(window=period).mean()
            
            result = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0
            return round(result, 4)  # Précision V3
        except:
            return 0.0

class PatternDetector:
    """Détecteur de patterns techniques (PRÉSERVÉ INTÉGRALEMENT)"""
    
    @staticmethod
    def detect_patterns(prices: pd.Series, volumes: pd.Series) -> Tuple[str, float]:
        """Détecte les patterns techniques principaux"""
        try:
            if len(prices) < 20:
                return "NO_PATTERN", 0.0
            
            # Double Bottom
            if PatternDetector._is_double_bottom(prices):
                return "DOUBLE_BOTTOM", 0.75
            
            # Double Top
            if PatternDetector._is_double_top(prices):
                return "DOUBLE_TOP", 0.75
            
            # Head and Shoulders
            if PatternDetector._is_head_and_shoulders(prices):
                return "HEAD_AND_SHOULDERS", 0.80
            
            # Triangle Ascendant
            if PatternDetector._is_ascending_triangle(prices):
                return "ASCENDING_TRIANGLE", 0.65
            
            # Triangle Descendant
            if PatternDetector._is_descending_triangle(prices):
                return "DESCENDING_TRIANGLE", 0.65
            
            # Breakout de volume
            if PatternDetector._is_volume_breakout(prices, volumes):
                return "VOLUME_BREAKOUT", 0.70
            
            return "NO_PATTERN", 0.0
            
        except:
            return "NO_PATTERN", 0.0
    
    @staticmethod
    def _is_double_bottom(prices: pd.Series) -> bool:
        """Détecte un pattern Double Bottom"""
        try:
            if len(prices) < 20:
                return False
            
            # Recherche de deux minimums similaires
            recent_prices = prices.tail(20)
            min_indices = []
            
            for i in range(2, len(recent_prices) - 2):
                if (recent_prices.iloc[i] < recent_prices.iloc[i-1] and 
                    recent_prices.iloc[i] < recent_prices.iloc[i-2] and
                    recent_prices.iloc[i] < recent_prices.iloc[i+1] and 
                    recent_prices.iloc[i] < recent_prices.iloc[i+2]):
                    min_indices.append(i)
            
            if len(min_indices) >= 2:
                # Vérifier si les minimums sont similaires (±3%)
                min1 = recent_prices.iloc[min_indices[-2]]
                min2 = recent_prices.iloc[min_indices[-1]]
                
                if abs(min1 - min2) / min1 < 0.03:
                    return True
            
            return False
        except:
            return False
    
    @staticmethod
    def _is_double_top(prices: pd.Series) -> bool:
        """Détecte un pattern Double Top"""
        try:
            if len(prices) < 20:
                return False
            
            # Recherche de deux maximums similaires
            recent_prices = prices.tail(20)
            max_indices = []
            
            for i in range(2, len(recent_prices) - 2):
                if (recent_prices.iloc[i] > recent_prices.iloc[i-1] and 
                    recent_prices.iloc[i] > recent_prices.iloc[i-2] and
                    recent_prices.iloc[i] > recent_prices.iloc[i+1] and 
                    recent_prices.iloc[i] > recent_prices.iloc[i+2]):
                    max_indices.append(i)
            
            if len(max_indices) >= 2:
                # Vérifier si les maximums sont similaires (±3%)
                max1 = recent_prices.iloc[max_indices[-2]]
                max2 = recent_prices.iloc[max_indices[-1]]
                
                if abs(max1 - max2) / max1 < 0.03:
                    return True
            
            return False
        except:
            return False
    
    @staticmethod
    def _is_head_and_shoulders(prices: pd.Series) -> bool:
        """Détecte un pattern Head and Shoulders"""
        try:
            if len(prices) < 15:
                return False
            
            recent_prices = prices.tail(15)
            
            # Recherche de 3 pics avec le pic central plus haut
            max_indices = []
            for i in range(2, len(recent_prices) - 2):
                if (recent_prices.iloc[i] > recent_prices.iloc[i-1] and 
                    recent_prices.iloc[i] > recent_prices.iloc[i-2] and
                    recent_prices.iloc[i] > recent_prices.iloc[i+1] and 
                    recent_prices.iloc[i] > recent_prices.iloc[i+2]):
                    max_indices.append(i)
            
            if len(max_indices) >= 3:
                # Vérifier la formation tête-épaules
                left_shoulder = recent_prices.iloc[max_indices[-3]]
                head = recent_prices.iloc[max_indices[-2]]
                right_shoulder = recent_prices.iloc[max_indices[-1]]
                
                # La tête doit être plus haute que les épaules
                if (head > left_shoulder and head > right_shoulder and
                    abs(left_shoulder - right_shoulder) / left_shoulder < 0.05):
                    return True
            
            return False
        except:
            return False
    
    @staticmethod
    def _is_ascending_triangle(prices: pd.Series) -> bool:
        """Détecte un triangle ascendant"""
        try:
            if len(prices) < 10:
                return False
            
            recent_prices = prices.tail(10)
            
            # Résistance horizontale (maximums similaires)
            highs = recent_prices.rolling(window=3).max()
            resistance_level = highs.tail(5).mean()
            
            # Support ascendant (minimums croissants)
            lows = recent_prices.rolling(window=3).min()
            
            # Vérifier la tendance ascendante des minimums
            if len(lows) >= 5:
                low_trend = np.polyfit(range(5), lows.tail(5), 1)[0]
                if low_trend > 0:  # Tendance ascendante
                    return True
            
            return False
        except:
            return False
    
    @staticmethod
    def _is_descending_triangle(prices: pd.Series) -> bool:
        """Détecte un triangle descendant"""
        try:
            if len(prices) < 10:
                return False
            
            recent_prices = prices.tail(10)
            
            # Support horizontal (minimums similaires)
            lows = recent_prices.rolling(window=3).min()
            support_level = lows.tail(5).mean()
            
            # Résistance descendante (maximums décroissants)
            highs = recent_prices.rolling(window=3).max()
            
            # Vérifier la tendance descendante des maximums
            if len(highs) >= 5:
                high_trend = np.polyfit(range(5), highs.tail(5), 1)[0]
                if high_trend < 0:  # Tendance descendante
                    return True
            
            return False
        except:
            return False
    
    @staticmethod
    def _is_volume_breakout(prices: pd.Series, volumes: pd.Series) -> bool:
        """Détecte un breakout de volume"""
        try:
            if len(volumes) < 10:
                return False
            
            # Volume actuel vs moyenne des 10 derniers jours
            current_volume = volumes.iloc[-1]
            avg_volume = volumes.tail(10).mean()
            
            # Breakout si volume > 150% de la moyenne
            if current_volume > avg_volume * 1.5:
                # Vérifier aussi le mouvement de prix
                price_change = abs(prices.iloc[-1] - prices.iloc[-2]) / prices.iloc[-2]
                if price_change > 0.02:  # Mouvement > 2%
                    return True
            
            return False
        except:
            return False

class AdvancedScoringEngineV3:
    """Moteur de scoring avancé V3 avec précision décimale et équité"""
    
    def __init__(self):
        self.logger = logging.getLogger("ScoringEngineV3")
    
    def calculate_precise_rsi_score(self, indicators: TechnicalIndicators) -> float:
        """Calcule le score RSI avec précision décimale et nuances (NOUVEAU V3)"""
        rsi_14 = indicators.rsi_14
        rsi_7 = indicators.rsi_7
        rsi_21 = indicators.rsi_21
        stoch_rsi = indicators.stochastic_rsi
        
        # Score de base RSI 14 avec seuils précis
        if rsi_14 <= 20:
            base_score = 92.5  # Signal d'achat très fort
        elif rsi_14 <= 25:
            base_score = 87.3
        elif rsi_14 <= 30:
            base_score = 78.6
        elif rsi_14 <= 35:
            base_score = 68.2
        elif rsi_14 <= 40:
            base_score = 58.7
        elif rsi_14 <= 45:
            base_score = 52.1
        elif rsi_14 <= 55:
            base_score = 49.8
        elif rsi_14 <= 60:
            base_score = 47.3
        elif rsi_14 <= 65:
            base_score = 41.6
        elif rsi_14 <= 70:
            base_score = 32.4
        elif rsi_14 <= 75:
            base_score = 21.8
        elif rsi_14 <= 80:
            base_score = 12.7
        else:
            base_score = 7.5  # Signal de vente très fort
        
        # Ajustements multi-timeframe
        if rsi_7 < rsi_14 < rsi_21:  # Convergence haussière
            base_score += 3.2
        elif rsi_7 > rsi_14 > rsi_21:  # Convergence baissière
            base_score -= 3.2
        
        # Ajustement Stochastic RSI
        if stoch_rsi <= 20 and rsi_14 <= 35:
            base_score += 4.7  # Double confirmation survente
        elif stoch_rsi >= 80 and rsi_14 >= 65:
            base_score -= 4.7  # Double confirmation surachat
        
        return round(max(0.0, min(100.0, base_score)), 1)
    
    def calculate_precise_momentum_score(self, indicators: TechnicalIndicators, market_data: MarketData) -> float:
        """Calcule un score de momentum composite (NOUVEAU V3)"""
        change_pct = market_data.change_percent
        volume_ratio = indicators.volume_ratio
        rsi_7 = indicators.rsi_7
        
        # Score selon performance du jour
        if change_pct >= 5.0:
            base_score = 94.2
        elif change_pct >= 3.0:
            base_score = 83.6
        elif change_pct >= 2.0:
            base_score = 72.8
        elif change_pct >= 1.0:
            base_score = 63.4
        elif change_pct >= 0.5:
            base_score = 56.7
        elif change_pct >= 0:
            base_score = 51.3
        elif change_pct >= -0.5:
            base_score = 48.7
        elif change_pct >= -1.0:
            base_score = 43.3
        elif change_pct >= -2.0:
            base_score = 36.6
        elif change_pct >= -3.0:
            base_score = 27.2
        elif change_pct >= -5.0:
            base_score = 16.4
        else:
            base_score = 5.8
        
        # Ajustement volume
        if volume_ratio > 1.5 and change_pct > 0:
            base_score += 6.3  # Hausse confirmée par volume
        elif volume_ratio > 1.5 and change_pct < 0:
            base_score -= 6.3  # Baisse confirmée par volume
        
        # Ajustement RSI court terme
        if rsi_7 > 70 and change_pct > 0:
            base_score -= 4.2  # Possible surachat
        elif rsi_7 < 30 and change_pct < 0:
            base_score += 4.2  # Possible survente
        
        return round(max(0.0, min(100.0, base_score)), 1)
    
    # PRÉSERVATION DES MÉTHODES ORIGINALES AVEC AMÉLIORATIONS
    def _calculate_rsi_score(self, indicators: TechnicalIndicators) -> float:
        """Version originale préservée + améliorations V3"""
        return self.calculate_precise_rsi_score(indicators)
    
    def _calculate_macd_score(self, indicators: TechnicalIndicators) -> float:
        """Calcule le score MACD avec nuances précises (AMÉLIORÉ V3)"""
        macd = indicators.macd_standard
        signal = indicators.macd_signal_standard
        histogram = indicators.macd_histogram_standard
        
        # Score de base selon position MACD
        if macd > signal:
            if histogram > 0.05:
                base_score = 82.4  # Croisement haussier fort
            elif histogram > 0.02:
                base_score = 74.6  # Croisement haussier modéré
            elif histogram > 0:
                base_score = 63.8  # Début croisement haussier
            else:
                base_score = 55.2  # MACD au-dessus mais faible
        else:
            if histogram < -0.05:
                base_score = 17.6  # Croisement baissier fort
            elif histogram < -0.02:
                base_score = 25.4  # Croisement baissier modéré
            elif histogram < 0:
                base_score = 36.2  # Début croisement baissier
            else:
                base_score = 44.8  # MACD en-dessous mais faible
        
        # Ajustement selon position par rapport à zéro
        if macd > 0 and signal > 0:
            base_score += 5.3  # Territoire positif
        elif macd < 0 and signal < 0:
            base_score -= 5.3  # Territoire négatif
        
        # Ajustement momentum court terme
        macd_short = indicators.macd_short
        if abs(macd_short) > abs(macd):
            base_score += 2.1  # Momentum court terme fort
        
        return round(max(0.0, min(100.0, base_score)), 1)
    
    def _calculate_bollinger_score(self, indicators: TechnicalIndicators, current_price: float) -> float:
        """Calcule le score Bollinger avec précision (AMÉLIORÉ V3)"""
        position = indicators.bollinger_position
        width = indicators.bollinger_width
        squeeze = indicators.bollinger_squeeze
        
        # Score selon position dans les bandes avec plus de granularité
        if position <= 0.05:
            base_score = 89.7  # Très proche bande basse
        elif position <= 0.10:
            base_score = 81.3
        elif position <= 0.15:
            base_score = 72.6
        elif position <= 0.20:
            base_score = 64.8
        elif position <= 0.30:
            base_score = 58.4
        elif position <= 0.40:
            base_score = 53.2
        elif position <= 0.60:
            base_score = 49.5  # Zone neutre
        elif position <= 0.70:
            base_score = 46.8
        elif position <= 0.80:
            base_score = 41.6
        elif position <= 0.85:
            base_score = 35.2
        elif position <= 0.90:
            base_score = 27.4
        elif position <= 0.95:
            base_score = 18.7
        else:
            base_score = 10.3  # Très proche bande haute
        
        # Ajustement squeeze
        if squeeze:
            base_score += 6.8  # Préparation breakout
        
        # Ajustement largeur des bandes
        if width < 0.03:
            base_score += 3.4  # Faible volatilité
        elif width > 0.08:
            base_score -= 2.7  # Haute volatilité
        
        return round(max(0.0, min(100.0, base_score)), 1)
    
    def _calculate_ma_score(self, indicators: TechnicalIndicators, current_price: float) -> float:
        """Calcule le score moyennes mobiles avec précision (AMÉLIORÉ V3)"""
        ema_5 = indicators.ema_5
        ema_10 = indicators.ema_10
        ema_20 = indicators.ema_20
        ema_50 = indicators.ema_50
        sma_200 = indicators.sma_200
        
        base_score = 50.0
        
        # Alignement des moyennes mobiles avec scores précis
        if ema_5 > ema_10 > ema_20 > ema_50:
            base_score = 87.9  # Alignement parfait haussier
        elif ema_5 > ema_10 > ema_20:
            base_score = 76.4  # Bon alignement haussier
        elif ema_5 > ema_10:
            base_score = 64.7  # Début tendance haussière
        elif ema_5 < ema_10 < ema_20 < ema_50:
            base_score = 12.1  # Alignement parfait baissier
        elif ema_5 < ema_10 < ema_20:
            base_score = 23.6  # Bon alignement baissier
        elif ema_5 < ema_10:
            base_score = 35.3  # Début tendance baissière
        
        # Position par rapport à SMA 200 avec calculs précis
        if current_price > sma_200:
            distance_pct = (current_price - sma_200) / sma_200
            if distance_pct > 0.10:
                base_score += 8.2  # Bien au-dessus SMA 200
            elif distance_pct > 0.05:
                base_score += 4.6
            else:
                base_score += 2.3
        else:
            distance_pct = (sma_200 - current_price) / sma_200
            if distance_pct > 0.10:
                base_score -= 8.2  # Bien en-dessous SMA 200
            elif distance_pct > 0.05:
                base_score -= 4.6
            else:
                base_score -= 2.3
        
        return round(max(0.0, min(100.0, base_score)), 1)
    
    def _calculate_volume_score(self, indicators: TechnicalIndicators) -> float:
        """Calcule le score volume avec précision (AMÉLIORÉ V3)"""
        volume_ratio = indicators.volume_ratio
        obv_trend = indicators.obv_trend
        vpt = indicators.volume_price_trend
        
        # Score selon ratio de volume avec plus de granularité
        if volume_ratio >= 3.0:
            base_score = 91.8  # Volume exceptionnel
        elif volume_ratio >= 2.5:
            base_score = 84.3
        elif volume_ratio >= 2.0:
            base_score = 76.9
        elif volume_ratio >= 1.8:
            base_score = 69.4
        elif volume_ratio >= 1.5:
            base_score = 62.7
        elif volume_ratio >= 1.3:
            base_score = 57.1
        elif volume_ratio >= 1.1:
            base_score = 52.8
        elif volume_ratio >= 0.9:
            base_score = 48.5
        elif volume_ratio >= 0.7:
            base_score = 42.3
        elif volume_ratio >= 0.5:
            base_score = 34.6
        else:
            base_score = 25.2  # Volume très faible
        
        # Ajustement OBV
        if obv_trend == "UP":
            base_score += 7.4
        elif obv_trend == "DOWN":
            base_score -= 7.4
        
        # Ajustement Volume Price Trend
        if vpt > 0:
            base_score += 3.8
        elif vpt < 0:
            base_score -= 3.8
        
        return round(max(0.0, min(100.0, base_score)), 1)
    
    def _calculate_pattern_score(self, indicators: TechnicalIndicators) -> float:
        """Calcule le score patterns avec précision (AMÉLIORÉ V3)"""
        pattern = indicators.pattern_detected
        confidence = indicators.pattern_confidence
        
        if pattern == "NO_PATTERN":
            return 50.0
        
        # Patterns haussiers avec scores précis
        if pattern == "DOUBLE_BOTTOM":
            base_score = 50.0 + (confidence * 38.7)  # 50-88.7
        elif pattern == "ASCENDING_TRIANGLE":
            base_score = 50.0 + (confidence * 32.4)  # 50-82.4
        elif pattern == "VOLUME_BREAKOUT":
            base_score = 50.0 + (confidence * 35.6)  # 50-85.6
        
        # Patterns baissiers avec scores précis
        elif pattern == "DOUBLE_TOP":
            base_score = 50.0 - (confidence * 38.7)  # 11.3-50
        elif pattern == "HEAD_AND_SHOULDERS":
            base_score = 50.0 - (confidence * 42.1)  # 7.9-50
        elif pattern == "DESCENDING_TRIANGLE":
            base_score = 50.0 - (confidence * 32.4)  # 17.6-50
        
        else:
            base_score = 50.0
        
        return round(max(0.0, min(100.0, base_score)), 1)
    
    def _calculate_risk_score(self, indicators: TechnicalIndicators, market_data: MarketData) -> float:
        """Calcule le score de risque (plus haut = moins risqué) (PRÉSERVÉ + AMÉLIORÉ)"""
        volatility_percentile = indicators.volatility_percentile
        beta = market_data.beta
        atr = indicators.atr
        
        score = 50.0
        
        # Volatilité (plus basse = mieux)
        if volatility_percentile <= 20:
            score += 20.0  # Faible volatilité
        elif volatility_percentile <= 40:
            score += 10.0  # Volatilité modérée
        elif volatility_percentile >= 80:
            score -= 20.0  # Haute volatilité
        elif volatility_percentile >= 60:
            score -= 10.0  # Volatilité élevée
        
        # Beta (proche de 1 = mieux)
        if 0.8 <= beta <= 1.2:
            score += 10.0  # Beta normal
        elif beta > 1.5:
            score -= 15.0  # Très volatil vs marché
        elif beta < 0.5:
            score -= 5.0   # Peu corrélé au marché
        
        return round(max(0.0, min(100.0, score)), 1)

class EquitableDistributionEngine:
    """Moteur de distribution équitable pour éviter la concentration (NOUVEAU V3)"""
    
    def __init__(self):
        self.logger = logging.getLogger("EquitableEngine")
    
    def calculate_diversity_bonus(self, market_data: MarketData, sector_stats: Dict, quintile_stats: Dict) -> float:
        """Calcule le bonus de diversité pour équilibrer la sélection"""
        
        # Bonus selon quintile de capitalisation (favorise les plus petites caps)
        quintile = self._determine_quintile(market_data.market_cap)
        quintile_bonuses = {
            1: 0.0,   # Large Cap - pas de bonus
            2: 3.7,   # Large-Mid Cap
            3: 7.2,   # Mid Cap
            4: 11.8,  # Small-Mid Cap
            5: 16.4   # Small Cap - bonus maximum
        }
        
        # Bonus selon sous-représentation sectorielle
        sector = market_data.sector
        sector_count = sector_stats.get(sector, 0)
        if sector_count == 0:
            sector_bonus = 12.7  # Premier du secteur
        elif sector_count == 1:
            sector_bonus = 5.7   # Deuxième du secteur
        elif sector_count == 2:
            sector_bonus = 3.1   # Troisième du secteur
        else:
            sector_bonus = 0.0   # Secteur déjà bien représenté
        
        # Bonus anti-concentration
        total_analyzed = sum(sector_stats.values())
        if total_analyzed > 0:
            sector_concentration = sector_count / total_analyzed
            if sector_concentration > 0.22:  # Plus de 22% du même secteur
                concentration_penalty = -8.5
            elif sector_concentration > 0.15:  # Plus de 15%
                concentration_penalty = -4.2
            else:
                concentration_penalty = 0.0
        else:
            concentration_penalty = 0.0
        
        total_bonus = quintile_bonuses[quintile] + sector_bonus + concentration_penalty
        return round(total_bonus, 1)
    
    def _determine_quintile(self, market_cap: float) -> int:
        """Détermine le quintile basé sur la capitalisation boursière"""
        if market_cap >= 100_000_000_000:  # 100B+
            return 1
        elif market_cap >= 50_000_000_000:  # 50-100B
            return 2
        elif market_cap >= 10_000_000_000:  # 10-50B
            return 3
        elif market_cap >= 2_000_000_000:   # 2-10B
            return 4
        else:                               # <2B
            return 5

class AdvancedIndividualAgentV3:
    """Agent individuel avancé V3 COMPLET avec toutes les fonctions préservées"""
    
    def __init__(self, symbol: str, polygon_key: str, sector_data: Dict = None, quintile_data: Dict = None):
        self.symbol = symbol.upper()
        self.polygon_key = polygon_key
        self.sector_data = sector_data or {}
        self.quintile_data = quintile_data or {}
        
        # Configuration logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(f"AgentV3_{self.symbol}")
        
        # Moteurs de calcul (V3 + préservés)
        self.tech_calc = TechnicalCalculator()
        self.pattern_detector = PatternDetector()
        self.scoring_engine = AdvancedScoringEngineV3()
        self.distribution_engine = EquitableDistributionEngine()
        
        # Cache des données
        self.market_data = None
        self.technical_indicators = None
        self.historical_data = None
        
        self.logger.info(f"🤖 Agent V3 Complet initialisé pour {self.symbol}")
    
    async def run_complete_analysis(self) -> Dict[str, Any]:
        """Exécute l'analyse complète avec scoring précis (PRÉSERVÉ + AMÉLIORÉ)"""
        try:
            start_time = time.time()
            
            # 1. Récupération des données de marché
            self.logger.info(f"📊 Récupération données de marché pour {self.symbol}")
            market_data = await self._fetch_market_data()
            
            if not market_data:
                return {'error': f'Impossible de récupérer les données pour {self.symbol}'}
            
            # 2. Récupération des données historiques
            self.logger.info(f"📈 Récupération données historiques pour {self.symbol}")
            historical_data = await self._fetch_historical_data()
            
            if historical_data is None or len(historical_data) < 50:
                return {'error': f'Données historiques insuffisantes pour {self.symbol}'}
            
            # 3. Calcul des indicateurs techniques
            self.logger.info(f"🔧 Calcul indicateurs techniques pour {self.symbol}")
            technical_indicators = self._calculate_all_technical_indicators(historical_data)
            
            # 4. Analyse IA et scoring (V3 amélioré)
            self.logger.info(f"🤖 Analyse IA et scoring V3 pour {self.symbol}")
            ai_analysis = self._perform_ai_analysis(market_data, technical_indicators, historical_data)
            
            # 5. Compilation du résultat final
            analysis_time = time.time() - start_time
            
            result = {
                'symbol': self.symbol,
                'market_data': asdict(market_data),
                'technical_indicators': asdict(technical_indicators),
                'ai_analysis': asdict(ai_analysis),
                'analysis_time': round(analysis_time, 2),
                'analysis_version': 'V3_Complete',
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.info(f"✅ Analyse V3 complète terminée pour {self.symbol} en {analysis_time:.2f}s")
            self.logger.info(f"🎯 Score équitable final: {ai_analysis.final_equitable_score:.1f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Erreur analyse V3 complète {self.symbol}: {e}")
            return {'error': str(e)}
    
    async def _fetch_market_data(self) -> Optional[MarketData]:
        """Récupère les données de marché actuelles (PRÉSERVÉ INTÉGRALEMENT)"""
        try:
            # Utilisation de yfinance pour les données de base
            ticker = yf.Ticker(self.symbol)
            info = ticker.info
            
            # Données de base
            current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            change_percent = info.get('regularMarketChangePercent', 0)
            volume = info.get('volume', info.get('regularMarketVolume', 0))
            market_cap = info.get('marketCap', 0)
            
            # Informations sectorielles
            sector = info.get('sector', 'Unknown')
            industry = info.get('industry', 'Unknown')
            
            # Métriques financières
            beta = info.get('beta', 1.0)
            pe_ratio = info.get('trailingPE')
            dividend_yield = info.get('dividendYield')
            price_to_book = info.get('priceToBook')
            debt_to_equity = info.get('debtToEquity')
            
            return MarketData(
                symbol=self.symbol,
                current_price=float(current_price) if current_price else 0.0,
                change_percent=float(change_percent) if change_percent else 0.0,
                volume=int(volume) if volume else 0,
                market_cap=float(market_cap) if market_cap else 0.0,
                sector=sector,
                industry=industry,
                beta=float(beta) if beta else 1.0,
                pe_ratio=float(pe_ratio) if pe_ratio else None,
                dividend_yield=float(dividend_yield) if dividend_yield else None,
                price_to_book=float(price_to_book) if price_to_book else None,
                debt_to_equity=float(debt_to_equity) if debt_to_equity else None
            )
            
        except Exception as e:
            self.logger.warning(f"Erreur récupération données marché {self.symbol}: {e}")
            return None
    
    async def _fetch_historical_data(self, period: str = "6mo") -> Optional[pd.DataFrame]:
        """Récupère les données historiques (PRÉSERVÉ INTÉGRALEMENT)"""
        try:
            ticker = yf.Ticker(self.symbol)
            data = ticker.history(period=period)
            
            if data.empty:
                return None
            
            # Nettoyage et préparation des données
            data = data.dropna()
            
            # Ajout de colonnes calculées
            data['Returns'] = data['Close'].pct_change()
            data['HL_Ratio'] = (data['High'] - data['Low']) / data['Close']
            data['Volume_MA'] = data['Volume'].rolling(window=20).mean()
            
            return data
            
        except Exception as e:
            self.logger.warning(f"Erreur récupération données historiques {self.symbol}: {e}")
            return None
    
    def _calculate_all_technical_indicators(self, data: pd.DataFrame) -> TechnicalIndicators:
        """Calcule tous les indicateurs techniques (PRÉSERVÉ + AMÉLIORÉ V3)"""
        try:
            prices = data['Close']
            volumes = data['Volume']
            high = data['High']
            low = data['Low']
            
            # RSI Multi-timeframe (amélioré V3)
            rsi_7 = self.tech_calc.calculate_rsi(prices, 7)
            rsi_14 = self.tech_calc.calculate_rsi(prices, 14)
            rsi_21 = self.tech_calc.calculate_rsi(prices, 21)
            stochastic_rsi = self.tech_calc.calculate_stochastic_rsi(prices, 14)
            
            # MACD (amélioré V3)
            macd_short, signal_short, hist_short = self.tech_calc.calculate_macd(prices, 5, 15, 9)
            macd_std, signal_std, hist_std = self.tech_calc.calculate_macd(prices, 12, 26, 9)
            
            # Bandes de Bollinger (amélioré V3)
            bb_upper, bb_middle, bb_lower, bb_position, bb_width = self.tech_calc.calculate_bollinger_bands(prices)
            bb_squeeze = bb_width < 0.05  # Squeeze si largeur < 5%
            
            # Moyennes Mobiles (amélioré V3)
            ema_5 = self.tech_calc.calculate_ema(prices, 5)
            ema_10 = self.tech_calc.calculate_ema(prices, 10)
            ema_20 = self.tech_calc.calculate_ema(prices, 20)
            ema_50 = self.tech_calc.calculate_ema(prices, 50)
            sma_100 = self.tech_calc.calculate_sma(prices, 100)
            sma_200 = self.tech_calc.calculate_sma(prices, 200)
            
            # Volume (amélioré V3)
            volume_ratio = round(volumes.iloc[-1] / volumes.rolling(window=20).mean().iloc[-1] if len(volumes) >= 20 else 1.0, 2)
            obv, obv_trend = self.tech_calc.calculate_obv(prices, volumes)
            vwap = self.tech_calc.calculate_vwap(prices, volumes)
            
            # Volume Price Trend
            vpt = 0.0
            if len(prices) >= 2:
                price_change = (prices.iloc[-1] - prices.iloc[-2]) / prices.iloc[-2]
                vpt = round(volumes.iloc[-1] * price_change, 2)
            
            # Patterns (préservé intégralement)
            pattern, pattern_confidence = self.pattern_detector.detect_patterns(prices, volumes)
            
            # Support et Résistance
            support_level = round(prices.rolling(window=20).min().iloc[-1] if len(prices) >= 20 else prices.iloc[-1], 2)
            resistance_level = round(prices.rolling(window=20).max().iloc[-1] if len(prices) >= 20 else prices.iloc[-1], 2)
            
            # Métriques de Risque (amélioré V3)
            atr = self.tech_calc.calculate_atr(high, low, prices)
            
            # Volatilité percentile
            returns = prices.pct_change().dropna()
            if len(returns) >= 50:
                current_vol = returns.tail(20).std()
                historical_vols = returns.rolling(window=20).std().dropna()
                volatility_percentile = round((historical_vols < current_vol).mean() * 100, 1)
            else:
                volatility_percentile = 50.0
            
            return TechnicalIndicators(
                rsi_7=rsi_7,
                rsi_14=rsi_14,
                rsi_21=rsi_21,
                stochastic_rsi=stochastic_rsi,
                macd_short=macd_short,
                macd_signal_short=signal_short,
                macd_histogram_short=hist_short,
                macd_standard=macd_std,
                macd_signal_standard=signal_std,
                macd_histogram_standard=hist_std,
                bollinger_upper=bb_upper,
                bollinger_middle=bb_middle,
                bollinger_lower=bb_lower,
                bollinger_position=bb_position,
                bollinger_width=bb_width,
                bollinger_squeeze=bb_squeeze,
                ema_5=ema_5,
                ema_10=ema_10,
                ema_20=ema_20,
                ema_50=ema_50,
                sma_100=sma_100,
                sma_200=sma_200,
                volume_ratio=volume_ratio,
                obv=obv,
                obv_trend=obv_trend,
                vwap=vwap,
                volume_price_trend=vpt,
                pattern_detected=pattern,
                pattern_confidence=pattern_confidence,
                support_level=support_level,
                resistance_level=resistance_level,
                atr=atr,
                volatility_percentile=volatility_percentile,
                beta_adjusted=1.0  # Sera calculé avec les données de marché
            )
            
        except Exception as e:
            self.logger.error(f"Erreur calcul indicateurs techniques {self.symbol}: {e}")
            return TechnicalIndicators()
    
    def _perform_ai_analysis(self, market_data: MarketData, indicators: TechnicalIndicators, historical_data: pd.DataFrame) -> AIAnalysisResult:
        """Effectue l'analyse IA complète avec scoring V3 (PRÉSERVÉ + AMÉLIORÉ)"""
        try:
            # 1. Calcul des scores par composant (V3 amélioré)
            rsi_score = self.scoring_engine._calculate_rsi_score(indicators)
            macd_score = self.scoring_engine._calculate_macd_score(indicators)
            bollinger_score = self.scoring_engine._calculate_bollinger_score(indicators, market_data.current_price)
            ma_score = self.scoring_engine._calculate_ma_score(indicators, market_data.current_price)
            volume_score = self.scoring_engine._calculate_volume_score(indicators)
            pattern_score = self.scoring_engine._calculate_pattern_score(indicators)
            risk_score = self.scoring_engine._calculate_risk_score(indicators, market_data)
            momentum_score = self.scoring_engine.calculate_precise_momentum_score(indicators, market_data)  # NOUVEAU V3
            
            # 2. Score composite de base avec pondération optimisée V3
            weights = {
                'rsi': 0.18,
                'macd': 0.17,
                'bollinger': 0.14,
                'ma': 0.13,
                'volume': 0.12,
                'momentum': 0.15,  # NOUVEAU V3
                'pattern': 0.08,
                'risk': 0.03
            }
            
            overall_score = (
                rsi_score * weights['rsi'] +
                macd_score * weights['macd'] +
                bollinger_score * weights['bollinger'] +
                ma_score * weights['ma'] +
                volume_score * weights['volume'] +
                momentum_score * weights['momentum'] +
                pattern_score * weights['pattern'] +
                risk_score * weights['risk']
            )
            
            # 3. Normalisation sectorielle (préservée)
            sector_factor = self._get_sector_factor(market_data.sector)
            
            # 4. Bonus par quintile de capitalisation (préservé)
            quintile_rank = self._determine_quintile(market_data.market_cap)
            quintile_bonus = self._get_quintile_bonus(quintile_rank)
            
            # 5. Bonus de diversité V3 (NOUVEAU)
            diversity_bonus = self.distribution_engine.calculate_diversity_bonus(
                market_data, self.sector_data, self.quintile_data
            )
            
            # 6. Score équitable final V3
            equitable_score = min(100.0, overall_score * sector_factor * (1 + quintile_bonus/100) + diversity_bonus)
            
            # 7. Génération des signaux (préservée + améliorée)
            buy_signals, sell_signals = self._generate_signals(indicators, market_data)
            
            # 8. Recommandation finale V3 (seuils précis)
            recommendation, confidence = self._generate_recommendation_v3(equitable_score, buy_signals, sell_signals)
            
            # 9. Raisonnement (préservé + amélioré)
            reasoning = self._generate_reasoning(indicators, market_data, equitable_score)
            
            return AIAnalysisResult(
                overall_score=round(overall_score, 1),
                final_equitable_score=round(equitable_score, 1),
                rsi_score=rsi_score,
                macd_score=macd_score,
                bollinger_score=bollinger_score,
                ma_score=ma_score,
                volume_score=volume_score,
                pattern_score=pattern_score,
                risk_score=risk_score,
                momentum_score=momentum_score,  # NOUVEAU V3
                sector_rank=50,  # Sera calculé par l'orchestrateur
                quintile_bonus=quintile_bonus,
                diversity_bonus=diversity_bonus,  # NOUVEAU V3
                buy_signals=buy_signals,
                sell_signals=sell_signals,
                recommendation=recommendation,
                confidence=confidence,
                reasoning=reasoning,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Erreur analyse IA {self.symbol}: {e}")
            return AIAnalysisResult(
                overall_score=50.0,
                final_equitable_score=50.0,
                rsi_score=50.0,
                macd_score=50.0,
                bollinger_score=50.0,
                ma_score=50.0,
                volume_score=50.0,
                pattern_score=50.0,
                risk_score=50.0,
                momentum_score=50.0,
                sector_rank=50,
                quintile_bonus=0.0,
                diversity_bonus=0.0,
                buy_signals=[],
                sell_signals=[],
                recommendation="HOLD",
                confidence=0.5,
                reasoning=["Analyse par défaut"],
                timestamp=datetime.now()
            )
    
    # TOUTES LES MÉTHODES ORIGINALES PRÉSERVÉES
    
    def _get_sector_factor(self, sector: str) -> float:
        """Retourne le facteur de normalisation sectorielle (PRÉSERVÉ)"""
        sector_factors = {
            'Technology': 1.05,
            'Healthcare': 1.03,
            'Financial Services': 1.02,
            'Consumer Cyclical': 1.01,
            'Consumer Defensive': 1.01,
            'Energy': 1.02,
            'Industrials': 1.01,
            'Materials': 1.01,
            'Utilities': 1.00,
            'Real Estate': 1.00,
            'Communication Services': 1.03
        }
        
        return sector_factors.get(sector, 1.00)
    
    def _determine_quintile(self, market_cap: float) -> int:
        """Détermine le quintile basé sur la capitalisation boursière (PRÉSERVÉ)"""
        if market_cap >= 100_000_000_000:  # 100B+
            return 1
        elif market_cap >= 50_000_000_000:  # 50-100B
            return 2
        elif market_cap >= 10_000_000_000:  # 10-50B
            return 3
        elif market_cap >= 2_000_000_000:   # 2-10B
            return 4
        else:                               # <2B
            return 5
    
    def _get_quintile_bonus(self, quintile: int) -> float:
        """Retourne le bonus équitable par quintile (PRÉSERVÉ)"""
        quintile_bonuses = {
            1: 0.00,  # Large Cap - pas de bonus
            2: 5.0,   # Large-Mid Cap - 5% bonus
            3: 10.0,  # Mid Cap - 10% bonus
            4: 15.0,  # Small-Mid Cap - 15% bonus
            5: 20.0   # Small Cap - 20% bonus
        }
        
        return quintile_bonuses.get(quintile, 0.00)
    
    def _generate_signals(self, indicators: TechnicalIndicators, market_data: MarketData) -> Tuple[List[str], List[str]]:
        """Génère les signaux d'achat et de vente (PRÉSERVÉ + AMÉLIORÉ V3)"""
        buy_signals = []
        sell_signals = []
        
        # Signaux RSI précis V3
        if indicators.rsi_14 <= 25:
            buy_signals.append(f"RSI très survendu ({indicators.rsi_14:.1f})")
        elif indicators.rsi_14 <= 30:
            buy_signals.append(f"RSI survendu ({indicators.rsi_14:.1f})")
        elif indicators.rsi_14 >= 75:
            sell_signals.append(f"RSI très suracheté ({indicators.rsi_14:.1f})")
        elif indicators.rsi_14 >= 70:
            sell_signals.append(f"RSI suracheté ({indicators.rsi_14:.1f})")
        
        # Signaux MACD précis V3
        if indicators.macd_standard > indicators.macd_signal_standard:
            if indicators.macd_histogram_standard > 0.05:
                buy_signals.append("MACD croisement haussier fort")
            elif indicators.macd_histogram_standard > 0:
                buy_signals.append("MACD croisement haussier")
        else:
            if indicators.macd_histogram_standard < -0.05:
                sell_signals.append("MACD croisement baissier fort")
            elif indicators.macd_histogram_standard < 0:
                sell_signals.append("MACD croisement baissier")
        
        # Signaux Bollinger précis V3
        if indicators.bollinger_position <= 0.1:
            buy_signals.append(f"Prix proche bande Bollinger basse ({indicators.bollinger_position:.1%})")
        elif indicators.bollinger_position >= 0.9:
            sell_signals.append(f"Prix proche bande Bollinger haute ({indicators.bollinger_position:.1%})")
        
        # Signaux Moyennes Mobiles (préservés)
        if indicators.ema_5 > indicators.ema_10 > indicators.ema_20:
            buy_signals.append("Alignement moyennes mobiles haussier")
        elif indicators.ema_5 < indicators.ema_10 < indicators.ema_20:
            sell_signals.append("Alignement moyennes mobiles baissier")
        
        # Signaux Volume précis V3
        if indicators.volume_ratio >= 2.0:
            if market_data.change_percent > 0:
                buy_signals.append(f"Volume exceptionnel + hausse ({indicators.volume_ratio:.1f}x)")
            else:
                sell_signals.append(f"Volume exceptionnel + baisse ({indicators.volume_ratio:.1f}x)")
        elif indicators.volume_ratio >= 1.5 and indicators.obv_trend == "UP":
            buy_signals.append("Volume élevé + OBV haussier")
        elif indicators.volume_ratio >= 1.5 and indicators.obv_trend == "DOWN":
            sell_signals.append("Volume élevé + OBV baissier")
        
        # Signaux Patterns (préservés)
        if indicators.pattern_detected in ["DOUBLE_BOTTOM", "ASCENDING_TRIANGLE"]:
            buy_signals.append(f"Pattern haussier: {indicators.pattern_detected}")
        elif indicators.pattern_detected in ["DOUBLE_TOP", "HEAD_AND_SHOULDERS"]:
            sell_signals.append(f"Pattern baissier: {indicators.pattern_detected}")
        
        # Signaux Momentum V3 (NOUVEAU)
        if market_data.change_percent >= 3.0 and indicators.volume_ratio >= 1.5:
            buy_signals.append(f"Forte hausse confirmée par volume (+{market_data.change_percent:.1f}%)")
        elif market_data.change_percent <= -3.0 and indicators.volume_ratio >= 1.5:
            sell_signals.append(f"Forte baisse confirmée par volume ({market_data.change_percent:.1f}%)")
        
        return buy_signals, sell_signals
    
    def _generate_recommendation_v3(self, score: float, buy_signals: List[str], sell_signals: List[str]) -> Tuple[str, float]:
        """Génère la recommandation finale avec seuils précis V3 (NOUVEAU)"""
        signal_balance = len(buy_signals) - len(sell_signals)
        
        # Seuils précis V3 pour les recommandations
        if score >= 82.4 and signal_balance >= 2:
            return "STRONG_BUY", 0.92
        elif score >= 76.9 and signal_balance >= 1:
            return "BUY", 0.84
        elif score >= 63.7 and signal_balance >= 0:
            return "WEAK_BUY", 0.73
        elif score <= 17.6 and signal_balance <= -2:
            return "STRONG_SELL", 0.92
        elif score <= 23.1 and signal_balance <= -1:
            return "SELL", 0.84
        elif score <= 36.3 and signal_balance <= 0:
            return "WEAK_SELL", 0.73
        else:
            return "HOLD", 0.65
    
    def _generate_recommendation(self, score: float, buy_signals: List[str], sell_signals: List[str]) -> Tuple[str, float]:
        """Version originale préservée pour compatibilité"""
        return self._generate_recommendation_v3(score, buy_signals, sell_signals)
    
    def _generate_reasoning(self, indicators: TechnicalIndicators, market_data: MarketData, score: float) -> List[str]:
        """Génère le raisonnement de l'analyse (PRÉSERVÉ + AMÉLIORÉ V3)"""
        reasoning = []
        
        # Score global avec seuils V3
        if score >= 82.4:
            reasoning.append(f"Score équitable excellent ({score:.1f}/100) - Signal STRONG_BUY")
        elif score >= 76.9:
            reasoning.append(f"Score équitable très élevé ({score:.1f}/100) - Signal BUY")
        elif score >= 63.7:
            reasoning.append(f"Score équitable élevé ({score:.1f}/100) - Signal WEAK_BUY")
        elif score <= 17.6:
            reasoning.append(f"Score équitable très faible ({score:.1f}/100) - Signal STRONG_SELL")
        elif score <= 23.1:
            reasoning.append(f"Score équitable faible ({score:.1f}/100) - Signal SELL")
        elif score <= 36.3:
            reasoning.append(f"Score équitable bas ({score:.1f}/100) - Signal WEAK_SELL")
        else:
            reasoning.append(f"Score équitable neutre ({score:.1f}/100) - Position HOLD")
        
        # RSI (préservé)
        if indicators.rsi_14 <= 30:
            reasoning.append(f"RSI en zone de survente ({indicators.rsi_14:.1f}) - signal d'achat potentiel")
        elif indicators.rsi_14 >= 70:
            reasoning.append(f"RSI en zone de surachat ({indicators.rsi_14:.1f}) - signal de vente potentiel")
        
        # MACD (préservé)
        if indicators.macd_histogram_standard > 0:
            reasoning.append("MACD en territoire positif - momentum haussier")
        elif indicators.macd_histogram_standard < 0:
            reasoning.append("MACD en territoire négatif - momentum baissier")
        
        # Volume (préservé + amélioré)
        if indicators.volume_ratio >= 2.0:
            reasoning.append(f"Volume exceptionnel ({indicators.volume_ratio:.1f}x) confirme le mouvement")
        elif indicators.volume_ratio >= 1.5:
            reasoning.append(f"Volume élevé ({indicators.volume_ratio:.1f}x) confirme le mouvement")
        
        # Pattern (préservé)
        if indicators.pattern_detected != "NO_PATTERN":
            reasoning.append(f"Pattern détecté: {indicators.pattern_detected} (confiance: {indicators.pattern_confidence:.0%})")
        
        # Secteur et capitalisation (préservé)
        quintile = self._determine_quintile(market_data.market_cap)
        quintile_names = {1: "Large Cap", 2: "Large-Mid Cap", 3: "Mid Cap", 4: "Small-Mid Cap", 5: "Small Cap"}
        reasoning.append(f"Action {quintile_names[quintile]} du secteur {market_data.sector}")
        
        return reasoning

# === FONCTIONS UTILITAIRES PRÉSERVÉES ===

def create_advanced_agent(symbol: str, polygon_key: str) -> AdvancedIndividualAgentV3:
    """Factory function pour créer un agent avancé V3 (PRÉSERVÉ + AMÉLIORÉ)"""
    return AdvancedIndividualAgentV3(symbol, polygon_key)

async def analyze_symbol_advanced(symbol: str, polygon_key: str) -> Dict[str, Any]:
    """Fonction utilitaire pour analyser un symbole V3 (PRÉSERVÉ + AMÉLIORÉ)"""
    agent = AdvancedIndividualAgentV3(symbol, polygon_key)
    return await agent.run_complete_analysis()

# NOUVELLES FONCTIONS V3

def create_precise_agent(symbol: str, polygon_key: str, sector_stats: Dict = None, quintile_stats: Dict = None) -> AdvancedIndividualAgentV3:
    """Factory function pour créer un agent précis V3"""
    return AdvancedIndividualAgentV3(symbol, polygon_key, sector_stats, quintile_stats)

async def analyze_symbol_precise(symbol: str, polygon_key: str, sector_stats: Dict = None, quintile_stats: Dict = None) -> Dict[str, Any]:
    """Fonction utilitaire pour analyser un symbole avec précision V3"""
    agent = AdvancedIndividualAgentV3(symbol, polygon_key, sector_stats, quintile_stats)
    return await agent.run_complete_analysis()

if __name__ == "__main__":
    # Test de l'agent V3 complet
    async def test_agent_v3():
        agent = AdvancedIndividualAgentV3("AAPL", "test_key")
        result = await agent.run_complete_analysis()
        print(json.dumps(result, indent=2, default=str))
    
    asyncio.run(test_agent_v3())










