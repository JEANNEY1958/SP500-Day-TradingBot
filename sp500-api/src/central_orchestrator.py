#!/usr/bin/env python3
"""
Orchestrateur Central Avancé V3 COMPLET - Système de Scoring Précis et Distribution Équitable
Version complète avec TOUTES les fonctions préservées + améliorations V3
FICHIER À COPIER/COLLER : sp500-api/src/central_orchestrator_v3_complete.py
"""

import asyncio
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
import threading
from threading import Timer
import os
import sys
from collections import defaultdict, Counter
import random

# Import du nouveau système avancé V3
from individual_agent_v2 import AdvancedIndividualAgentV3

@dataclass
class EquitableAnalysisResult:
    """Résultat d'analyse équitable enrichi V3"""
    symbol: str
    overall_score: float
    equitable_score: float  # Score après normalisation équitable
    rsi_score: float
    macd_score: float
    bollinger_score: float
    ma_score: float
    volume_score: float
    pattern_score: float
    risk_score: float
    
    # Données de marché
    price: float
    change_percent: float
    volume: int
    market_cap: float
    sector: str
    industry: str
    beta: float
    
    # Classification équitable
    sector_rank: int
    quintile_rank: int
    quintile_name: str
    
    # Signaux et recommandation
    buy_signals: List[str]
    sell_signals: List[str]
    recommendation: str
    confidence: float
    reasoning: List[str]
    
    # Métadonnées
    source: str
    timestamp: datetime
    analysis_version: str
    
    # NOUVEAU V3 - avec valeurs par défaut (DOIT être à la fin)
    momentum_score: float = 50.0

@dataclass
class DiversityMetrics:
    """Métriques de diversité du portefeuille V3 améliorées"""
    sectors_represented: int
    quintiles_represented: int
    max_sector_concentration: float  # En pourcentage
    max_quintile_concentration: float
    sector_distribution: Dict[str, int]
    quintile_distribution: Dict[int, int]
    diversity_score: float  # Score global de diversité (0-100)
    herfindahl_index: float  # Index de concentration
    gini_coefficient: float = 0.0  # NOUVEAU V3
    balance_score: float = 0.0  # NOUVEAU V3

@dataclass
class AdvancedSystemStatus:
    """Statut avancé du système avec métriques de diversité V3"""
    mode: str = 'manual'
    phase: str = 'idle'
    running: bool = False
    analyzed_stocks: int = 0
    total_stocks: int = 0
    start_time: Optional[str] = None
    last_update: Optional[str] = None
    
    # Résultats d'analyse
    analysis_results_500: List[EquitableAnalysisResult] = None
    top_10_candidates: List[Dict] = None
    final_recommendation: Optional[Dict] = None
    
    # Statistiques
    successful_analyses: int = 0
    error_count: int = 0
    average_score: float = 0.0
    
    # Métriques de diversité
    diversity_metrics: Optional[DiversityMetrics] = None
    
    # Configuration équitable
    diversity_settings: Dict = None
    
    # Nouveaux paramètres V3
    precise_settings: Dict = None
    score_distribution: Dict[str, int] = None

class PreciseDistributionEngine:
    """Moteur de distribution précise V3 pour équilibrer la sélection"""
    
    def __init__(self):
        self.logger = logging.getLogger("PreciseDistribution")
        
        # Objectifs de distribution équitable
        self.distribution_targets = {
            'max_sector_concentration': 22,  # Max 22% par secteur
            'min_sectors_represented': 7,    # Min 7 secteurs différents
            'max_quintile_concentration': 35, # Max 35% par quintile
            'min_quintiles_represented': 4,   # Min 4 quintiles
            'small_cap_target': 15,          # 15% de small caps minimum
            'mid_cap_target': 25,            # 25% de mid caps minimum
            'large_cap_max': 60              # 60% de large caps maximum
        }
    
    def calculate_advanced_diversity_metrics(self, results: List[EquitableAnalysisResult]) -> DiversityMetrics:
        """Calcule les métriques de diversité avancées V3"""
        if not results:
            return DiversityMetrics(0, 0, 0.0, 0.0, {}, {}, 0.0, 1.0, 1.0, 0.0)
        
        # Distribution par secteur
        sector_counts = Counter([r.sector for r in results])
        sectors_represented = len(sector_counts)
        
        # Distribution par quintile
        quintile_counts = Counter([r.quintile_rank for r in results])
        quintiles_represented = len(quintile_counts)
        
        total_count = len(results)
        
        # Concentrations maximales
        max_sector_concentration = max(sector_counts.values()) / total_count * 100
        max_quintile_concentration = max(quintile_counts.values()) / total_count * 100
        
        # Index de Herfindahl (concentration)
        sector_shares = [count / total_count for count in sector_counts.values()]
        herfindahl_index = sum(share ** 2 for share in sector_shares)
        
        # Coefficient de Gini (inégalité) - NOUVEAU V3
        scores = sorted([r.equitable_score for r in results])
        n = len(scores)
        gini_coefficient = 0.0
        if n > 1:
            cumsum = np.cumsum(scores)
            gini_coefficient = (n + 1 - 2 * sum((n + 1 - i) * score for i, score in enumerate(scores, 1)) / cumsum[-1]) / n
        
        # Score de diversité global (0-100, plus élevé = plus diversifié)
        diversity_score = self._calculate_diversity_score(
            sectors_represented, quintiles_represented, 
            max_sector_concentration, max_quintile_concentration,
            herfindahl_index
        )
        
        # Score d'équilibre (0-100, plus élevé = mieux équilibré) - NOUVEAU V3
        balance_score = self._calculate_balance_score(sector_counts, quintile_counts, total_count)
        
        return DiversityMetrics(
            sectors_represented=sectors_represented,
            quintiles_represented=quintiles_represented,
            max_sector_concentration=round(max_sector_concentration, 1),
            max_quintile_concentration=round(max_quintile_concentration, 1),
            sector_distribution=dict(sector_counts),
            quintile_distribution=dict(quintile_counts),
            diversity_score=round(diversity_score, 1),
            herfindahl_index=round(herfindahl_index, 3),
            gini_coefficient=round(gini_coefficient, 3),
            balance_score=round(balance_score, 1)
        )
    
    def _calculate_diversity_score(self, sectors: int, quintiles: int, 
                                 max_sector_conc: float, max_quintile_conc: float,
                                 herfindahl: float) -> float:
        """Calcule le score de diversité composite"""
        # Score basé sur le nombre de secteurs (0-30 points)
        sector_score = min(30, sectors * 4)
        
        # Score basé sur le nombre de quintiles (0-20 points)
        quintile_score = min(20, quintiles * 5)
        
        # Score basé sur la concentration sectorielle (0-25 points)
        concentration_score = max(0, 25 - max_sector_conc)
        
        # Score basé sur l'index de Herfindahl (0-25 points)
        herfindahl_score = max(0, 25 * (1 - herfindahl))
        
        return sector_score + quintile_score + concentration_score + herfindahl_score
    
    def _calculate_balance_score(self, sector_counts: Counter, quintile_counts: Counter, total: int) -> float:
        """Calcule le score d'équilibre de la distribution"""
        if total == 0:
            return 0.0
        
        # Écart-type des distributions (plus bas = plus équilibré)
        sector_percentages = [count / total * 100 for count in sector_counts.values()]
        quintile_percentages = [count / total * 100 for count in quintile_counts.values()]
        
        sector_std = np.std(sector_percentages) if len(sector_percentages) > 1 else 0
        quintile_std = np.std(quintile_percentages) if len(quintile_percentages) > 1 else 0
        
        # Score d'équilibre (plus l'écart-type est faible, plus le score est élevé)
        sector_balance = max(0, 50 - sector_std * 2)
        quintile_balance = max(0, 50 - quintile_std * 2)
        
        return (sector_balance + quintile_balance) / 2

class AdvancedCentralOrchestratorV3:
    """Orchestrateur central avancé V3 COMPLET avec toutes les fonctions préservées"""
    
    def __init__(self):
        # Configuration logging AVANT tout autre appel
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("AdvancedOrchestratorV3")
        
        # Configuration
        self.polygon_key = os.getenv('POLYGON_API_KEY', 'GDl2XTcDZ9cLBoHuBnQEKK9oJOvcQghs')
        
        # État du système
        self.status = AdvancedSystemStatus()
        self.status.analysis_results_500 = []
        self.status.top_10_candidates = []
        self.status.diversity_settings = self._get_default_diversity_settings()
        self.status.precise_settings = self._get_default_precise_settings()  # NOUVEAU V3
        self.status.score_distribution = {}  # NOUVEAU V3
        
        # Données S&P 500
        self.sp500_symbols = self.load_sp500_symbols_extended()
        self.sector_data = self._load_sector_data()
        self.quintile_data = self._calculate_quintile_data()
        
        # Moteurs V3
        self.distribution_engine = PreciseDistributionEngine()  # NOUVEAU V3
        
        # Contrôle des threads
        self.stop_flag = False
        self.analysis_thread = None
        
        # Statistiques de performance
        self.performance_stats = {
            'total_analyses': 0,
            'successful_analyses': 0,
            'error_rate': 0.0,
            'average_analysis_time': 0.0,
            'sector_coverage': {},
            'quintile_coverage': {},
            'score_ranges': {  # NOUVEAU V3
                'strong_buy': 0,
                'buy': 0,
                'weak_buy': 0,
                'hold': 0,
                'weak_sell': 0,
                'sell': 0,
                'strong_sell': 0
            }
        }
        
        self.logger.info("🚀 Orchestrateur Central Avancé V3 COMPLET initialisé")
        self.logger.info(f"📊 {len(self.sp500_symbols)} symboles S&P 500 chargés")
        self.logger.info("⚖️ Système de sélection équitable V3 activé")
        self.logger.info("🎯 Distribution précise et diversité forcée configurées")
        self.logger.info("🔢 Scoring décimal précis activé")
    
    def _get_default_diversity_settings(self) -> Dict:
        """Configuration par défaut de la diversité (PRÉSERVÉ)"""
        return {
            'max_sector_concentration': 30,    # % max par secteur dans le Top 10
            'min_sectors_represented': 5,      # Nombre min de secteurs
            'max_quintile_concentration': 40,  # % max par quintile
            'min_quintiles_represented': 3,    # Nombre min de quintiles
            'small_cap_bonus': 20,            # Bonus % pour small caps (quintile 5)
            'mid_cap_bonus': 15,              # Bonus % pour mid caps (quintile 4)
            'large_mid_cap_bonus': 10,        # Bonus % pour large-mid caps (quintile 3)
            'sector_rotation_enabled': True,   # Rotation sectorielle
            'force_small_cap_inclusion': True, # Forcer inclusion small caps
            'diversity_weight': 0.3            # Poids de la diversité dans le score final
        }
    
    def _get_default_precise_settings(self) -> Dict:
        """Configuration par défaut du système précis V3 (NOUVEAU)"""
        return {
            'strong_buy_threshold': 82.4,
            'buy_threshold': 76.9,
            'weak_buy_threshold': 63.7,
            'weak_sell_threshold': 36.3,
            'sell_threshold': 23.1,
            'strong_sell_threshold': 17.6,
            'decimal_precision': 1,
            'momentum_weight': 0.15,
            'diversity_bonus_enabled': True,
            'anti_concentration_penalty': -8.5,
            'sector_bonus_first': 12.7,
            'sector_bonus_second': 5.7,
            'quintile_bonus_small_cap': 16.4,
            'quintile_bonus_mid_cap': 11.8,
            'quintile_bonus_large_mid': 7.2,
            'quintile_bonus_large_mid_2': 3.7
        }
    
    def load_sp500_symbols_extended(self) -> List[str]:
        """Charge la liste étendue des symboles S&P 500 avec diversité sectorielle (PRÉSERVÉ INTÉGRALEMENT)"""
        try:
            # Essayer de charger depuis le fichier CSV
            csv_path = 'S&P_list.csv'
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                symbols = df['symbol'].tolist()
                self.logger.info(f"📁 Chargé {len(symbols)} symboles depuis {csv_path}")
                return symbols
        except Exception as e:
            self.logger.warning(f"Erreur chargement CSV: {e}")
        
        # Liste étendue avec diversité sectorielle garantie (500+ symboles)
        extended_symbols = [
            # Technology (80 symboles)
            'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'GOOG', 'META', 'TSLA', 'NFLX', 'ADBE', 'CRM',
            'ORCL', 'INTC', 'AMD', 'QCOM', 'AVGO', 'NOW', 'INTU', 'AMAT', 'LRCX', 'KLAC',
            'SNPS', 'CDNS', 'MRVL', 'ADI', 'NXPI', 'MCHP', 'FTNT', 'PANW', 'CRWD', 'ZS',
            'OKTA', 'DDOG', 'NET', 'SNOW', 'PLTR', 'RBLX', 'U', 'TWLO', 'ZM', 'DOCU',
            'WORK', 'TEAM', 'ATLASSIAN', 'SHOP', 'SQ', 'PYPL', 'COIN', 'HOOD', 'SOFI', 'AFRM',
            'UBER', 'LYFT', 'DASH', 'ABNB', 'AIRB', 'BKNG', 'EXPE', 'TRIP', 'PCLN', 'GRUB',
            'EBAY', 'ETSY', 'AMZN', 'MELI', 'BABA', 'JD', 'PDD', 'BIDU', 'NTES', 'TME',
            'BILI', 'IQ', 'VIPS', 'WB', 'SINA', 'SOHU', 'FENG', 'TOUR', 'JOBS', 'WUBA',
            
            # Healthcare (60 symboles)
            'UNH', 'JNJ', 'PFE', 'ABBV', 'LLY', 'TMO', 'ABT', 'MRK', 'DHR', 'BMY',
            'AMGN', 'GILD', 'VRTX', 'REGN', 'ISRG', 'SYK', 'BSX', 'MDT', 'EW', 'DXCM',
            'ZBH', 'BDX', 'BAX', 'HOLX', 'IDXX', 'IQV', 'A', 'ALGN', 'MRNA', 'BNTX',
            'PFE', 'NVAX', 'OCGN', 'INO', 'SRNE', 'VXRT', 'CODX', 'QDEL', 'FLGT', 'TDOC',
            'VEEV', 'DOCU', 'AMWL', 'ONEM', 'HIMS', 'ACCD', 'DOCS', 'CERT', 'OMCL', 'PRGO',
            'TEVA', 'MYL', 'AGN', 'ALXN', 'CELG', 'BIIB', 'ILMN', 'INCY', 'TECH', 'VRTX',
            
            # Financial Services (60 symboles)
            'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'AXP', 'BLK', 'SCHW', 'SPGI',
            'CME', 'ICE', 'MCO', 'COF', 'TFC', 'USB', 'PNC', 'BK', 'STT', 'NTRS',
            'RF', 'KEY', 'FITB', 'HBAN', 'CFG', 'MTB', 'ZION', 'CMA', 'PBCT', 'SIVB',
            'ALLY', 'LC', 'SOFI', 'UPST', 'AFRM', 'SQ', 'PYPL', 'MA', 'V', 'AXP',
            'DFS', 'SYF', 'COF', 'CACC', 'WRLD', 'TREE', 'ENVA', 'CURO', 'FCFS', 'OPORTUN',
            'BRK.A', 'BRK.B', 'AIG', 'PRU', 'MET', 'AFL', 'ALL', 'TRV', 'PGR', 'CB',
            
            # Consumer Cyclical (50 symboles)
            'AMZN', 'HD', 'MCD', 'NKE', 'SBUX', 'TJX', 'LOW', 'BKNG', 'MAR', 'GM',
            'F', 'TSLA', 'CCL', 'RCL', 'NCLH', 'MGM', 'WYNN', 'LVS', 'DIS', 'CMCSA',
            'NFLX', 'T', 'VZ', 'CHTR', 'TMUS', 'DISH', 'SIRI', 'LUMN', 'CTL', 'FTR',
            'YUM', 'QSR', 'DPZ', 'CMG', 'SHAK', 'WING', 'TXRH', 'DENN', 'CAKE', 'RUTH',
            'ROST', 'TJX', 'COST', 'WMT', 'TGT', 'KSS', 'M', 'JWN', 'NILE', 'BBY',
            
            # Consumer Defensive (40 symboles)
            'WMT', 'PG', 'KO', 'PEP', 'COST', 'MDLZ', 'CL', 'KMB', 'GIS', 'K',
            'HSY', 'MKC', 'SJM', 'CPB', 'CAG', 'HRL', 'TSN', 'TYSON', 'KHC', 'UNFI',
            'KR', 'SYY', 'USFD', 'PFGC', 'CALM', 'SAFM', 'LANC', 'JJSF', 'SENEA', 'SENEB',
            'CVS', 'WBA', 'RAD', 'RITE', 'FRED', 'DRUG', 'HSKA', 'OMAB', 'VLGEA', 'INGR',
            
            # Energy (40 symboles)
            'XOM', 'CVX', 'COP', 'EOG', 'SLB', 'MPC', 'VLO', 'PSX', 'OXY', 'BKR',
            'HAL', 'DVN', 'FANG', 'MRO', 'APA', 'HES', 'KMI', 'OKE', 'EPD', 'ET',
            'WMB', 'KINDER', 'ENB', 'TRP', 'PPL', 'ETP', 'ETE', 'SEP', 'MPLX', 'ANDX',
            'SMLP', 'USAC', 'NGL', 'CAPL', 'PBFX', 'DMLP', 'ENLC', 'ENLK', 'EEP', 'EEQ',
            
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
        
        # Assurer qu'on a exactement 500 symboles uniques
        unique_symbols = list(set(extended_symbols))
        if len(unique_symbols) < 500:
            # Ajouter des symboles supplémentaires si nécessaire
            additional_symbols = [f"SYM{i:03d}" for i in range(500 - len(unique_symbols))]
            unique_symbols.extend(additional_symbols)
        
        final_symbols = unique_symbols[:500]  # Limiter à 500
        
        self.logger.info(f"📊 Liste étendue créée avec {len(final_symbols)} symboles")
        return final_symbols
    
    def _load_sector_data(self) -> Dict[str, Dict]:
        """Charge les données sectorielles pour normalisation (PRÉSERVÉ INTÉGRALEMENT)"""
        return {
            'Technology': {
                'avg_volatility': 0.25,
                'avg_volume_ratio': 1.2,
                'growth_factor': 1.15,
                'risk_factor': 1.1
            },
            'Healthcare': {
                'avg_volatility': 0.18,
                'avg_volume_ratio': 0.9,
                'growth_factor': 1.08,
                'risk_factor': 0.9
            },
            'Financial Services': {
                'avg_volatility': 0.22,
                'avg_volume_ratio': 1.1,
                'growth_factor': 1.05,
                'risk_factor': 1.0
            },
            'Consumer Cyclical': {
                'avg_volatility': 0.20,
                'avg_volume_ratio': 1.0,
                'growth_factor': 1.03,
                'risk_factor': 1.0
            },
            'Consumer Defensive': {
                'avg_volatility': 0.15,
                'avg_volume_ratio': 0.8,
                'growth_factor': 1.02,
                'risk_factor': 0.8
            },
            'Energy': {
                'avg_volatility': 0.30,
                'avg_volume_ratio': 1.1,
                'growth_factor': 1.04,
                'risk_factor': 1.3
            },
            'Industrials': {
                'avg_volatility': 0.19,
                'avg_volume_ratio': 1.0,
                'growth_factor': 1.04,
                'risk_factor': 1.0
            },
            'Materials': {
                'avg_volatility': 0.24,
                'avg_volume_ratio': 1.0,
                'growth_factor': 1.03,
                'risk_factor': 1.2
            },
            'Utilities': {
                'avg_volatility': 0.12,
                'avg_volume_ratio': 0.7,
                'growth_factor': 1.01,
                'risk_factor': 0.7
            },
            'Real Estate': {
                'avg_volatility': 0.16,
                'avg_volume_ratio': 0.9,
                'growth_factor': 1.02,
                'risk_factor': 0.9
            },
            'Communication Services': {
                'avg_volatility': 0.23,
                'avg_volume_ratio': 1.1,
                'growth_factor': 1.06,
                'risk_factor': 1.1
            }
        }
    
    def _calculate_quintile_data(self) -> Dict[int, Dict]:
        """Calcule les données par quintile de capitalisation (PRÉSERVÉ INTÉGRALEMENT)"""
        return {
            1: {  # Large Cap (Top 20%)
                'name': 'Large Cap',
                'min_market_cap': 100_000_000_000,  # 100B+
                'bonus_factor': 1.00,
                'liquidity_factor': 1.2,
                'stability_factor': 1.1
            },
            2: {  # Large-Mid Cap (20-40%)
                'name': 'Large-Mid Cap',
                'min_market_cap': 50_000_000_000,   # 50-100B
                'bonus_factor': 1.05,
                'liquidity_factor': 1.1,
                'stability_factor': 1.05
            },
            3: {  # Mid Cap (40-60%)
                'name': 'Mid Cap',
                'min_market_cap': 10_000_000_000,   # 10-50B
                'bonus_factor': 1.10,
                'liquidity_factor': 1.0,
                'stability_factor': 1.0
            },
            4: {  # Small-Mid Cap (60-80%)
                'name': 'Small-Mid Cap',
                'min_market_cap': 2_000_000_000,    # 2-10B
                'bonus_factor': 1.15,
                'liquidity_factor': 0.9,
                'stability_factor': 0.95
            },
            5: {  # Small Cap (Bottom 20%)
                'name': 'Small Cap',
                'min_market_cap': 0,                # <2B
                'bonus_factor': 1.20,
                'liquidity_factor': 0.8,
                'stability_factor': 0.9
            }
        }
    
    # ===== GESTION DES MODES AVANCÉS (PRÉSERVÉ INTÉGRALEMENT) =====
    
    def configure_advanced_mode(self, mode: str, diversity_settings: Optional[Dict] = None) -> Dict:
        """Configure le mode d'opération avancé avec paramètres de diversité (PRÉSERVÉ)"""
        try:
            if mode not in ['manual', 'auto']:
                return {'success': False, 'message': 'Mode invalide. Utilisez "manual" ou "auto"'}
            
            # Configuration du mode
            self.status.mode = mode
            self.status.last_update = datetime.now().isoformat()
            
            # Configuration de la diversité
            if diversity_settings:
                self.status.diversity_settings.update(diversity_settings)
            
            self.logger.info(f"🔧 Mode configuré: {mode}")
            if diversity_settings:
                self.logger.info(f"⚖️ Paramètres de diversité mis à jour: {diversity_settings}")
            
            return {
                'success': True, 
                'message': f'Mode {mode} configuré avec succès',
                'current_settings': self.status.diversity_settings
            }
            
        except Exception as e:
            self.logger.error(f"Erreur configuration mode avancé: {e}")
            return {'success': False, 'message': f'Erreur: {str(e)}'}
    
    def get_status(self) -> Dict:
        """Retourne le statut détaillé du système (PRÉSERVÉ + AMÉLIORÉ V3)"""
        try:
            # Calcul du pourcentage de progression
            progress_percentage = 0
            if self.status.total_stocks > 0:
                progress_percentage = (self.status.analyzed_stocks / self.status.total_stocks) * 100
            
            # Estimation du temps restant
            estimated_remaining = "N/A"
            if self.status.running and self.status.start_time and self.status.analyzed_stocks > 0:
                start_time = datetime.fromisoformat(self.status.start_time)
                elapsed_time = (datetime.now() - start_time).total_seconds()
                avg_time_per_stock = elapsed_time / self.status.analyzed_stocks
                remaining_stocks = self.status.total_stocks - self.status.analyzed_stocks
                estimated_remaining = f"{int(remaining_stocks * avg_time_per_stock / 60)} minutes"
            
            # Métriques de performance
            error_rate = 0
            if self.status.analyzed_stocks > 0:
                error_rate = (self.status.error_count / self.status.analyzed_stocks) * 100
            
            return {
                'mode': self.status.mode,
                'phase': self.status.phase,
                'running': self.status.running,
                'progress': {
                    'analyzed_stocks': self.status.analyzed_stocks,
                    'total_stocks': self.status.total_stocks,
                    'percentage': round(progress_percentage, 1),
                    'estimated_remaining': estimated_remaining
                },
                'timing': {
                    'start_time': self.status.start_time,
                    'last_update': self.status.last_update
                },
                'results': {
                    'successful_analyses': self.status.successful_analyses,
                    'error_count': self.status.error_count,
                    'error_rate': round(error_rate, 1),
                    'average_score': round(self.status.average_score, 1),
                    'total_results': len(self.status.analysis_results_500) if self.status.analysis_results_500 else 0
                },
                'diversity_metrics': asdict(self.status.diversity_metrics) if self.status.diversity_metrics else None,
                'diversity_settings': self.status.diversity_settings,
                'precise_settings': self.status.precise_settings,  # NOUVEAU V3
                'score_distribution': self.status.score_distribution,  # NOUVEAU V3
                'top_10_count': len(self.status.top_10_candidates) if self.status.top_10_candidates else 0,
                'final_recommendation': self.status.final_recommendation
            }
            
        except Exception as e:
            self.logger.error(f"Erreur récupération statut: {e}")
            return {'error': str(e)}
    
    def get_precise_status(self) -> Dict:
        """Retourne le statut précis du système V3 (NOUVEAU)"""
        try:
            base_status = self.get_status()
            
            # Ajout des métriques précises V3
            precise_metrics = {
                'scoring_precision': self.status.precise_settings['decimal_precision'],
                'recommendation_thresholds': {
                    'STRONG_BUY': f"≥ {self.status.precise_settings['strong_buy_threshold']}",
                    'BUY': f"≥ {self.status.precise_settings['buy_threshold']}",
                    'WEAK_BUY': f"≥ {self.status.precise_settings['weak_buy_threshold']}",
                    'HOLD': f"{self.status.precise_settings['weak_sell_threshold']} - {self.status.precise_settings['weak_buy_threshold'] - 0.1}",
                    'WEAK_SELL': f"≤ {self.status.precise_settings['weak_sell_threshold']}",
                    'SELL': f"≤ {self.status.precise_settings['sell_threshold']}",
                    'STRONG_SELL': f"≤ {self.status.precise_settings['strong_sell_threshold']}"
                },
                'distribution_targets': self.distribution_engine.distribution_targets,
                'momentum_integration': self.status.precise_settings['momentum_weight'] > 0,
                'diversity_bonus_active': self.status.precise_settings['diversity_bonus_enabled']
            }
            
            base_status['precise_metrics'] = precise_metrics
            return base_status
            
        except Exception as e:
            self.logger.error(f"Erreur récupération statut précis: {e}")
            return {'error': str(e)}
    
    # ===== ANALYSE ÉQUITABLE AVANCÉE (PRÉSERVÉ + AMÉLIORÉ V3) =====
    
    async def start_equitable_analysis_500(self) -> Dict:
        """Démarre l'analyse équitable des 500 actions S&P (PRÉSERVÉ)"""
        if self.status.running:
            return {'success': False, 'message': 'Une analyse est déjà en cours'}
        
        try:
            # Réinitialisation
            self.stop_flag = False
            
            # Mise à jour du statut
            self.status.running = True
            self.status.phase = 'analyzing_500'
            self.status.analyzed_stocks = 0
            self.status.total_stocks = len(self.sp500_symbols)
            self.status.start_time = datetime.now().isoformat()
            self.status.analysis_results_500 = []
            self.status.successful_analyses = 0
            self.status.error_count = 0
            
            self.logger.info("🚀 Démarrage analyse équitable S&P 500")
            
            # Lancement en arrière-plan
            self.analysis_thread = threading.Thread(target=self._run_equitable_analysis_500_background)
            self.analysis_thread.daemon = True
            self.analysis_thread.start()
            
            return {'success': True, 'message': 'Analyse équitable des 500 tickers démarrée'}
            
        except Exception as e:
            self.logger.error(f"Erreur démarrage analyse équitable 500: {e}")
            self.status.running = False
            return {'success': False, 'message': f'Erreur: {str(e)}'}
    
    async def run_complete_sp500_analysis_precise(self) -> Dict:
        """Lance l'analyse complète des 500 actions avec système précis V3 (NOUVEAU)"""
        if self.status.running:
            return {'success': False, 'message': 'Une analyse est déjà en cours'}
        
        try:
            # Réinitialisation
            self.stop_flag = False
            
            # Mise à jour du statut
            self.status.running = True
            self.status.phase = 'analyzing_500_precise'
            self.status.analyzed_stocks = 0
            self.status.total_stocks = len(self.sp500_symbols)
            self.status.start_time = datetime.now().isoformat()
            self.status.analysis_results_500 = []
            self.status.successful_analyses = 0
            self.status.error_count = 0
            self.status.score_distribution = {
                'STRONG_BUY': 0, 'BUY': 0, 'WEAK_BUY': 0, 'HOLD': 0,
                'WEAK_SELL': 0, 'SELL': 0, 'STRONG_SELL': 0
            }
            
            self.logger.info("🚀 Démarrage analyse précise S&P 500 V3")
            
            # Lancement en arrière-plan
            self.analysis_thread = threading.Thread(target=self._run_precise_analysis_500_background)
            self.analysis_thread.daemon = True
            self.analysis_thread.start()
            
            return {'success': True, 'message': 'Analyse précise V3 des 500 tickers démarrée'}
            
        except Exception as e:
            self.logger.error(f"Erreur démarrage analyse précise 500: {e}")
            self.status.running = False
            return {'success': False, 'message': f'Erreur: {str(e)}'}
    
    def _run_equitable_analysis_500_background(self):
        """Exécute l'analyse équitable des 500 tickers en arrière-plan (PRÉSERVÉ INTÉGRALEMENT)"""
        try:
            start_time = time.time()
            
            # Analyse par batches pour optimiser les performances
            batch_size = 25  # Taille de batch optimisée
            total_batches = (len(self.sp500_symbols) + batch_size - 1) // batch_size
            
            self.logger.info(f"📊 Analyse de {len(self.sp500_symbols)} symboles en {total_batches} batches")
            
            for batch_idx in range(total_batches):
                if self.stop_flag:
                    break
                
                start_idx = batch_idx * batch_size
                end_idx = min(start_idx + batch_size, len(self.sp500_symbols))
                batch_symbols = self.sp500_symbols[start_idx:end_idx]
                
                self.logger.info(f"🔄 Batch {batch_idx + 1}/{total_batches} - Analyse de {len(batch_symbols)} symboles")
                
                # Analyse du batch
                batch_results = asyncio.run(self._analyze_batch_equitable(batch_symbols))
                
                # Ajout des résultats
                self.status.analysis_results_500.extend(batch_results)
                self.status.successful_analyses += len(batch_results)
                self.status.analyzed_stocks = len(self.status.analysis_results_500)
                
                # Mise à jour du statut
                self.status.last_update = datetime.now().isoformat()
                
                # Calcul du score moyen
                if self.status.analysis_results_500:
                    total_score = sum(r.equitable_score for r in self.status.analysis_results_500)
                    self.status.average_score = total_score / len(self.status.analysis_results_500)
                
                # Pause entre les batches
                time.sleep(2)
            
            # Sélection du Top 10 équitable
            if not self.stop_flag and self.status.analysis_results_500:
                self.status.phase = 'selecting_top_10'
                self._select_equitable_top_10()
                self._calculate_comprehensive_diversity_metrics()
            
            # Finalisation
            total_time = time.time() - start_time
            self.status.running = False
            self.status.phase = 'completed'
            self.status.last_update = datetime.now().isoformat()
            
            self.logger.info(f"✅ Analyse équitable terminée en {total_time:.1f}s")
            self.logger.info(f"📊 {len(self.status.analysis_results_500)} actions analysées avec succès")
            self.logger.info(f"🎯 Score moyen équitable: {self.status.average_score:.1f}")
            
            # Mise à jour des statistiques de performance
            self._update_performance_stats(total_time)
            
        except Exception as e:
            self.logger.error(f"❌ Erreur critique analyse équitable 500: {e}")
            self.status.running = False
            self.status.phase = 'error'
            self.status.last_update = datetime.now().isoformat()
    
    def _run_precise_analysis_500_background(self):
        """Exécute l'analyse précise V3 des 500 tickers en arrière-plan (NOUVEAU)"""
        try:
            start_time = time.time()
            
            # Analyse par batches optimisée V3
            batch_size = 20  # Taille réduite pour plus de précision
            total_batches = (len(self.sp500_symbols) + batch_size - 1) // batch_size
            
            self.logger.info(f"📊 Analyse précise V3 de {len(self.sp500_symbols)} symboles en {total_batches} batches")
            
            # Statistiques sectorielles pour bonus de diversité
            sector_stats = {}
            quintile_stats = {}
            
            for batch_idx in range(total_batches):
                if self.stop_flag:
                    break
                
                start_idx = batch_idx * batch_size
                end_idx = min(start_idx + batch_size, len(self.sp500_symbols))
                batch_symbols = self.sp500_symbols[start_idx:end_idx]
                
                self.logger.info(f"🔄 Batch précis {batch_idx + 1}/{total_batches} - Analyse de {len(batch_symbols)} symboles")
                
                # Analyse du batch avec système précis V3
                batch_results = asyncio.run(self._analyze_batch_precise_v3(batch_symbols, sector_stats, quintile_stats))
                
                # Ajout des résultats
                self.status.analysis_results_500.extend(batch_results)
                self.status.successful_analyses += len(batch_results)
                self.status.analyzed_stocks = len(self.status.analysis_results_500)
                
                # Mise à jour des statistiques de distribution
                for result in batch_results:
                    self.status.score_distribution[result.recommendation] += 1
                    sector_stats[result.sector] = sector_stats.get(result.sector, 0) + 1
                    quintile_stats[result.quintile_rank] = quintile_stats.get(result.quintile_rank, 0) + 1
                
                # Mise à jour du statut
                self.status.last_update = datetime.now().isoformat()
                
                # Calcul du score moyen précis
                if self.status.analysis_results_500:
                    total_score = sum(r.equitable_score for r in self.status.analysis_results_500)
                    self.status.average_score = total_score / len(self.status.analysis_results_500)
                
                # Pause entre les batches
                time.sleep(1.5)
            
            # Sélection équilibrée du Top avec système V3
            if not self.stop_flag and self.status.analysis_results_500:
                self.status.phase = 'selecting_top_balanced'
                self._select_top_candidates_balanced()
                self._calculate_advanced_diversity_metrics()
            
            # Finalisation
            total_time = time.time() - start_time
            self.status.running = False
            self.status.phase = 'completed_precise'
            self.status.last_update = datetime.now().isoformat()
            
            self.logger.info(f"✅ Analyse précise V3 terminée en {total_time:.1f}s")
            self.logger.info(f"📊 {len(self.status.analysis_results_500)} actions analysées avec succès")
            self.logger.info(f"🎯 Score moyen équitable: {self.status.average_score:.1f}")
            self.logger.info(f"📈 Distribution: {self.status.score_distribution}")
            
            # Mise à jour des statistiques de performance V3
            self._update_performance_stats_v3(total_time)
            
        except Exception as e:
            self.logger.error(f"❌ Erreur critique analyse précise V3: {e}")
            self.status.running = False
            self.status.phase = 'error'
            self.status.last_update = datetime.now().isoformat()
    
    async def _analyze_batch_equitable(self, symbols: List[str]) -> List[EquitableAnalysisResult]:
        """Analyse un lot de symboles avec le système équitable (PRÉSERVÉ INTÉGRALEMENT)"""
        results = []
        
        # Analyse parallèle pour optimiser les performances
        tasks = []
        for symbol in symbols:
            if self.stop_flag:
                break
            task = self._analyze_single_symbol_equitable(symbol)
            tasks.append(task)
        
        # Exécution parallèle avec limite de concurrence
        if tasks:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for symbol, result in zip(symbols, batch_results):
                if isinstance(result, Exception):
                    self.logger.warning(f"❌ Erreur analyse {symbol}: {result}")
                elif result:
                    results.append(result)
                    self.logger.debug(f"✅ {symbol} - Score équitable: {result.equitable_score:.1f}")
        
        return results
    
    async def _analyze_batch_precise_v3(self, symbols: List[str], sector_stats: Dict, quintile_stats: Dict) -> List[EquitableAnalysisResult]:
        """Analyse un lot de symboles avec le système précis V3 (NOUVEAU)"""
        results = []
        
        # Analyse parallèle optimisée pour V3
        tasks = []
        for symbol in symbols:
            if self.stop_flag:
                break
            task = self._analyze_single_symbol_precise_v3(symbol, sector_stats, quintile_stats)
            tasks.append(task)
        
        # Exécution parallèle avec limite de concurrence
        if tasks:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for symbol, result in zip(symbols, batch_results):
                if isinstance(result, Exception):
                    self.logger.warning(f"❌ Erreur analyse précise {symbol}: {result}")
                    self.status.error_count += 1
                elif result:
                    results.append(result)
                    self.logger.debug(f"✅ {symbol} - Score précis: {result.equitable_score:.1f} - Rec: {result.recommendation}")
        
        return results
    
    async def _analyze_single_symbol_equitable(self, symbol: str) -> Optional[EquitableAnalysisResult]:
        """Analyse équitable d'un symbole unique (PRÉSERVÉ INTÉGRALEMENT)"""
        try:
            # Utilisation de l'agent avancé V2
            agent = AdvancedIndividualAgentV3(symbol, self.polygon_key, self.sector_data, self.quintile_data)
            result = await agent.run_complete_analysis()
            
            if result and 'error' not in result:
                return self._convert_to_equitable_result(symbol, result)
            else:
                return None
                
        except Exception as e:
            self.logger.warning(f"Erreur analyse équitable {symbol}: {e}")
            return None
    
    async def _analyze_single_symbol_precise_v3(self, symbol: str, sector_stats: Dict, quintile_stats: Dict) -> Optional[EquitableAnalysisResult]:
        """Analyse précise V3 d'un symbole unique (NOUVEAU)"""
        try:
            # Utilisation de l'agent avancé V3
            agent = AdvancedIndividualAgentV3(symbol, self.polygon_key, sector_stats, quintile_stats)
            result = await agent.run_complete_analysis()
            
            if result and 'error' not in result:
                return self._convert_to_equitable_result_v3(symbol, result)
            else:
                return None
                
        except Exception as e:
            self.logger.warning(f"Erreur analyse précise V3 {symbol}: {e}")
            return None
    
    def _convert_to_equitable_result(self, symbol: str, analysis_result: Dict) -> Optional[EquitableAnalysisResult]:
        """Convertit le résultat d'analyse en EquitableAnalysisResult (PRÉSERVÉ INTÉGRALEMENT)"""
        try:
            ai_analysis = analysis_result.get('ai_analysis', {})
            market_data = analysis_result.get('market_data', {})
            
            # Détermination du quintile
            market_cap = market_data.get('market_cap', 0)
            quintile_rank = self._determine_quintile(market_cap)
            quintile_name = self.quintile_data[quintile_rank]['name']
            
            return EquitableAnalysisResult(
                symbol=symbol,
                overall_score=ai_analysis.get('overall_score', 50.0),
                equitable_score=ai_analysis.get('final_equitable_score', 50.0),
                rsi_score=ai_analysis.get('rsi_score', 50.0),
                macd_score=ai_analysis.get('macd_score', 50.0),
                bollinger_score=ai_analysis.get('bollinger_score', 50.0),
                ma_score=ai_analysis.get('ma_score', 50.0),
                volume_score=ai_analysis.get('volume_score', 50.0),
                pattern_score=ai_analysis.get('pattern_score', 50.0),
                risk_score=ai_analysis.get('risk_score', 50.0),
                
                # Données de marché
                price=market_data.get('current_price', 0.0),
                change_percent=market_data.get('change_percent', 0.0),
                volume=market_data.get('volume', 0),
                market_cap=market_cap,
                sector=market_data.get('sector', 'Unknown'),
                industry=market_data.get('industry', 'Unknown'),
                beta=market_data.get('beta', 1.0),
                
                # Classification équitable
                sector_rank=ai_analysis.get('sector_rank', 50),
                quintile_rank=quintile_rank,
                quintile_name=quintile_name,
                
                # Signaux et recommandation
                buy_signals=ai_analysis.get('buy_signals', []),
                sell_signals=ai_analysis.get('sell_signals', []),
                recommendation=ai_analysis.get('recommendation', 'HOLD'),
                confidence=ai_analysis.get('confidence', 0.5),
                reasoning=ai_analysis.get('reasoning', []),
                
                # Métadonnées
                source='Advanced Equitable System V2',
                timestamp=datetime.now(),
                analysis_version=analysis_result.get('analysis_version', 'V2')
            )
            
        except Exception as e:
            self.logger.warning(f"Erreur conversion résultat équitable {symbol}: {e}")
            return None
    
    def _convert_to_equitable_result_v3(self, symbol: str, analysis_result: Dict) -> Optional[EquitableAnalysisResult]:
        """Convertit le résultat d'analyse V3 en EquitableAnalysisResult (NOUVEAU)"""
        try:
            ai_analysis = analysis_result.get('ai_analysis', {})
            market_data = analysis_result.get('market_data', {})
            
            # Détermination du quintile
            market_cap = market_data.get('market_cap', 0)
            quintile_rank = self._determine_quintile(market_cap)
            quintile_name = self.quintile_data[quintile_rank]['name']
            
            return EquitableAnalysisResult(
                symbol=symbol,
                overall_score=ai_analysis.get('overall_score', 50.0),
                equitable_score=ai_analysis.get('final_equitable_score', 50.0),
                rsi_score=ai_analysis.get('rsi_score', 50.0),
                macd_score=ai_analysis.get('macd_score', 50.0),
                bollinger_score=ai_analysis.get('bollinger_score', 50.0),
                ma_score=ai_analysis.get('ma_score', 50.0),
                volume_score=ai_analysis.get('volume_score', 50.0),
                pattern_score=ai_analysis.get('pattern_score', 50.0),
                risk_score=ai_analysis.get('risk_score', 50.0),
                momentum_score=ai_analysis.get('momentum_score', 50.0),  # NOUVEAU V3
                
                # Données de marché
                price=market_data.get('current_price', 0.0),
                change_percent=market_data.get('change_percent', 0.0),
                volume=market_data.get('volume', 0),
                market_cap=market_cap,
                sector=market_data.get('sector', 'Unknown'),
                industry=market_data.get('industry', 'Unknown'),
                beta=market_data.get('beta', 1.0),
                
                # Classification équitable
                sector_rank=ai_analysis.get('sector_rank', 50),
                quintile_rank=quintile_rank,
                quintile_name=quintile_name,
                
                # Signaux et recommandation
                buy_signals=ai_analysis.get('buy_signals', []),
                sell_signals=ai_analysis.get('sell_signals', []),
                recommendation=ai_analysis.get('recommendation', 'HOLD'),
                confidence=ai_analysis.get('confidence', 0.5),
                reasoning=ai_analysis.get('reasoning', []),
                
                # Métadonnées
                source='Advanced Precise System V3',
                timestamp=datetime.now(),
                analysis_version=analysis_result.get('analysis_version', 'V3_Complete')
            )
            
        except Exception as e:
            self.logger.warning(f"Erreur conversion résultat précis V3 {symbol}: {e}")
            return None
    
    def _determine_quintile(self, market_cap: float) -> int:
        """Détermine le quintile basé sur la capitalisation boursière (PRÉSERVÉ INTÉGRALEMENT)"""
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
    
    # ===== SÉLECTION ÉQUITABLE DU TOP 10 (PRÉSERVÉ + AMÉLIORÉ V3) =====
    
    def _select_equitable_top_10(self):
        """Sélectionne le Top 10 avec diversité forcée (PRÉSERVÉ INTÉGRALEMENT)"""
        try:
            if not self.status.analysis_results_500:
                self.logger.warning("Aucun résultat d'analyse disponible pour sélection Top 10")
                return
            
            self.logger.info("🎯 Sélection équitable du Top 10")
            
            # Tri par score équitable décroissant
            sorted_results = sorted(
                self.status.analysis_results_500, 
                key=lambda x: x.equitable_score, 
                reverse=True
            )
            
            # Sélection avec diversité forcée
            selected_candidates = []
            sector_counts = {}
            quintile_counts = {}
            
            # Paramètres de diversité
            max_per_sector = 3  # Maximum 3 actions par secteur
            max_per_quintile = 4  # Maximum 4 actions par quintile
            min_sectors = 5  # Minimum 5 secteurs différents
            
            # Phase 1: Sélection des meilleurs avec contraintes
            for result in sorted_results:
                if len(selected_candidates) >= 10:
                    break
                
                sector = result.sector
                quintile = result.quintile_rank
                
                # Vérifier les contraintes de diversité
                sector_count = sector_counts.get(sector, 0)
                quintile_count = quintile_counts.get(quintile, 0)
                
                # Accepter si les contraintes sont respectées
                if (sector_count < max_per_sector and 
                    quintile_count < max_per_quintile):
                    
                    selected_candidates.append(result)
                    sector_counts[sector] = sector_count + 1
                    quintile_counts[quintile] = quintile_count + 1
                    
                    self.logger.debug(f"✅ Sélectionné: {result.symbol} - Score: {result.equitable_score:.1f} - Secteur: {sector}")
            
            # Phase 2: Compléter si nécessaire en assouplissant les contraintes
            if len(selected_candidates) < 10:
                remaining_needed = 10 - len(selected_candidates)
                selected_symbols = {r.symbol for r in selected_candidates}
                
                for result in sorted_results:
                    if len(selected_candidates) >= 10:
                        break
                    
                    if result.symbol not in selected_symbols:
                        selected_candidates.append(result)
                        self.logger.debug(f"➕ Complété: {result.symbol} - Score: {result.equitable_score:.1f}")
            
            # Conversion en format dictionnaire pour compatibilité
            self.status.top_10_candidates = []
            for i, result in enumerate(selected_candidates[:10], 1):
                candidate = {
                    'rank': i,
                    'symbol': result.symbol,
                    'equitable_score': round(result.equitable_score, 1),
                    'overall_score': round(result.overall_score, 1),
                    'sector': result.sector,
                    'quintile': result.quintile_name,
                    'market_cap': result.market_cap,
                    'price': result.price,
                    'change_percent': result.change_percent,
                    'recommendation': result.recommendation,
                    'confidence': result.confidence,
                    'buy_signals': result.buy_signals,
                    'sell_signals': result.sell_signals,
                    'reasoning': result.reasoning[:3]  # Top 3 raisons
                }
                self.status.top_10_candidates.append(candidate)
            
            # Statistiques de diversité
            final_sectors = [c['sector'] for c in self.status.top_10_candidates]
            final_quintiles = [c['quintile'] for c in self.status.top_10_candidates]
            
            self.logger.info(f"🎯 Top 10 sélectionné avec {len(set(final_sectors))} secteurs et {len(set(final_quintiles))} quintiles")
            self.logger.info(f"📊 Secteurs: {Counter(final_sectors)}")
            self.logger.info(f"📊 Quintiles: {Counter(final_quintiles)}")
            
        except Exception as e:
            self.logger.error(f"Erreur sélection équitable Top 10: {e}")
    
    def _select_top_candidates_balanced(self):
        """Sélectionne les top candidats avec équilibrage V3 (NOUVEAU)"""
        try:
            if not self.status.analysis_results_500:
                self.logger.warning("Aucun résultat d'analyse disponible pour sélection équilibrée")
                return
            
            self.logger.info("🎯 Sélection équilibrée V3 des top candidats")
            
            # Tri par score équitable décroissant
            sorted_results = sorted(
                self.status.analysis_results_500, 
                key=lambda x: x.equitable_score, 
                reverse=True
            )
            
            # Sélection avec distribution forcée V3
            selected_candidates = []
            sector_counts = {}
            quintile_counts = {}
            
            # Paramètres de distribution V3
            targets = self.distribution_engine.distribution_targets
            max_per_sector = max(1, int(20 * targets['max_sector_concentration'] / 100))  # Top 20
            min_sectors = targets['min_sectors_represented']
            
            # Phase 1: Garantir la diversité sectorielle
            sectors_represented = set()
            for result in sorted_results:
                if len(sectors_represented) >= min_sectors:
                    break
                
                sector = result.sector
                if sector not in sectors_represented:
                    selected_candidates.append(result)
                    sectors_represented.add(sector)
                    sector_counts[sector] = sector_counts.get(sector, 0) + 1
                    quintile_counts[result.quintile_rank] = quintile_counts.get(result.quintile_rank, 0) + 1
                    
                    self.logger.debug(f"🎯 Diversité: {result.symbol} - {sector} - Score: {result.equitable_score:.1f}")
            
            # Phase 2: Compléter avec les meilleurs scores en respectant les limites
            selected_symbols = {r.symbol for r in selected_candidates}
            
            for result in sorted_results:
                if len(selected_candidates) >= 20:  # Top 20 pour plus de choix
                    break
                
                if result.symbol in selected_symbols:
                    continue
                
                sector = result.sector
                sector_count = sector_counts.get(sector, 0)
                
                # Respecter la limite sectorielle
                if sector_count < max_per_sector:
                    selected_candidates.append(result)
                    selected_symbols.add(result.symbol)
                    sector_counts[sector] = sector_count + 1
                    quintile_counts[result.quintile_rank] = quintile_counts.get(result.quintile_rank, 0) + 1
                    
                    self.logger.debug(f"✅ Ajouté: {result.symbol} - Score: {result.equitable_score:.1f}")
            
            # Conversion en format dictionnaire
            self.status.top_10_candidates = []
            for i, result in enumerate(selected_candidates[:20], 1):  # Top 20
                candidate = {
                    'rank': i,
                    'symbol': result.symbol,
                    'equitable_score': round(result.equitable_score, 1),
                    'overall_score': round(result.overall_score, 1),
                    'momentum_score': round(result.momentum_score, 1),  # NOUVEAU V3
                    'sector': result.sector,
                    'quintile': result.quintile_name,
                    'market_cap': result.market_cap,
                    'price': result.price,
                    'change_percent': result.change_percent,
                    'recommendation': result.recommendation,
                    'confidence': result.confidence,
                    'buy_signals': result.buy_signals,
                    'sell_signals': result.sell_signals,
                    'reasoning': result.reasoning[:3]
                }
                self.status.top_10_candidates.append(candidate)
            
            # Statistiques de diversité V3
            final_sectors = [c['sector'] for c in self.status.top_10_candidates]
            final_quintiles = [c['quintile'] for c in self.status.top_10_candidates]
            
            self.logger.info(f"🎯 Top 20 équilibré sélectionné avec {len(set(final_sectors))} secteurs")
            self.logger.info(f"📊 Distribution sectorielle: {dict(Counter(final_sectors))}")
            self.logger.info(f"📊 Distribution par quintile: {dict(Counter(final_quintiles))}")
            
        except Exception as e:
            self.logger.error(f"Erreur sélection équilibrée V3: {e}")
    
    def get_top_candidates_precise(self, count: int = 20) -> List[Dict]:
        """Retourne les top candidats avec scoring précis V3 (NOUVEAU)"""
        try:
            if not self.status.analysis_results_500:
                return []
            
            # Tri par score équitable décroissant
            sorted_results = sorted(
                self.status.analysis_results_500, 
                key=lambda x: x.equitable_score, 
                reverse=True
            )
            
            top_candidates = []
            for i, result in enumerate(sorted_results[:count], 1):
                candidate = {
                    'rank': i,
                    'symbol': result.symbol,
                    'equitable_score': round(result.equitable_score, 1),
                    'overall_score': round(result.overall_score, 1),
                    'momentum_score': round(result.momentum_score, 1),
                    'sector': result.sector,
                    'quintile': result.quintile_name,
                    'market_cap': result.market_cap,
                    'price': result.price,
                    'change_percent': result.change_percent,
                    'recommendation': result.recommendation,
                    'confidence': round(result.confidence, 2),
                    'buy_signals': result.buy_signals,
                    'sell_signals': result.sell_signals,
                    'reasoning': result.reasoning[:3],
                    'analysis_version': result.analysis_version
                }
                top_candidates.append(candidate)
            
            return top_candidates
            
        except Exception as e:
            self.logger.error(f"Erreur récupération top candidats précis: {e}")
            return []
    
    def get_analysis_results_by_score_range(self, min_score: float, max_score: float) -> List[Dict]:
        """Retourne les résultats dans une plage de scores (NOUVEAU V3)"""
        try:
            if not self.status.analysis_results_500:
                return []
            
            filtered_results = [
                {
                    'symbol': r.symbol,
                    'equitable_score': round(r.equitable_score, 1),
                    'overall_score': round(r.overall_score, 1),
                    'momentum_score': round(r.momentum_score, 1),
                    'recommendation': r.recommendation,
                    'confidence': round(r.confidence, 2),
                    'sector': r.sector,
                    'quintile': r.quintile_name,
                    'market_cap': r.market_cap,
                    'price': r.price,
                    'change_percent': r.change_percent,
                    'buy_signals': r.buy_signals,
                    'sell_signals': r.sell_signals
                }
                for r in self.status.analysis_results_500
                if min_score <= r.equitable_score <= max_score
            ]
            
            # Trier par score décroissant
            filtered_results.sort(key=lambda x: x['equitable_score'], reverse=True)
            
            return filtered_results
            
        except Exception as e:
            self.logger.error(f"Erreur filtrage par plage de score: {e}")
            return []
    
    # ===== MÉTRIQUES DE DIVERSITÉ (PRÉSERVÉ + AMÉLIORÉ V3) =====
    
    def _calculate_comprehensive_diversity_metrics(self):
        """Calcule les métriques de diversité complètes (PRÉSERVÉ INTÉGRALEMENT)"""
        try:
            if not self.status.analysis_results_500:
                return
            
            # Distribution par secteur
            sector_counts = Counter([r.sector for r in self.status.analysis_results_500])
            sectors_represented = len(sector_counts)
            
            # Distribution par quintile
            quintile_counts = Counter([r.quintile_rank for r in self.status.analysis_results_500])
            quintiles_represented = len(quintile_counts)
            
            total_count = len(self.status.analysis_results_500)
            
            # Concentrations maximales
            max_sector_concentration = max(sector_counts.values()) / total_count * 100
            max_quintile_concentration = max(quintile_counts.values()) / total_count * 100
            
            # Index de Herfindahl (mesure de concentration)
            sector_shares = [count / total_count for count in sector_counts.values()]
            herfindahl_index = sum(share ** 2 for share in sector_shares)
            
            # Score de diversité global (0-100, plus élevé = plus diversifié)
            diversity_score = self._calculate_diversity_score_comprehensive(
                sectors_represented, quintiles_represented, 
                max_sector_concentration, max_quintile_concentration,
                herfindahl_index
            )
            
            # Création des métriques
            self.status.diversity_metrics = DiversityMetrics(
                sectors_represented=sectors_represented,
                quintiles_represented=quintiles_represented,
                max_sector_concentration=round(max_sector_concentration, 1),
                max_quintile_concentration=round(max_quintile_concentration, 1),
                sector_distribution=dict(sector_counts),
                quintile_distribution=dict(quintile_counts),
                diversity_score=round(diversity_score, 1),
                herfindahl_index=round(herfindahl_index, 3)
            )
            
            self.logger.info(f"📊 Métriques de diversité calculées:")
            self.logger.info(f"   - Secteurs représentés: {sectors_represented}")
            self.logger.info(f"   - Quintiles représentés: {quintiles_represented}")
            self.logger.info(f"   - Score de diversité: {diversity_score:.1f}/100")
            self.logger.info(f"   - Index Herfindahl: {herfindahl_index:.3f}")
            
        except Exception as e:
            self.logger.error(f"Erreur calcul métriques de diversité: {e}")
    
    def _calculate_advanced_diversity_metrics(self):
        """Calcule les métriques de diversité avancées V3 (NOUVEAU)"""
        try:
            if not self.status.analysis_results_500:
                return
            
            # Utiliser le moteur de distribution V3
            self.status.diversity_metrics = self.distribution_engine.calculate_advanced_diversity_metrics(
                self.status.analysis_results_500
            )
            
            metrics = self.status.diversity_metrics
            
            self.logger.info(f"📊 Métriques de diversité avancées V3 calculées:")
            self.logger.info(f"   - Secteurs représentés: {metrics.sectors_represented}")
            self.logger.info(f"   - Quintiles représentés: {metrics.quintiles_represented}")
            self.logger.info(f"   - Score de diversité: {metrics.diversity_score:.1f}/100")
            self.logger.info(f"   - Index Herfindahl: {metrics.herfindahl_index:.3f}")
            self.logger.info(f"   - Coefficient Gini: {metrics.gini_coefficient:.3f}")
            self.logger.info(f"   - Score d'équilibre: {metrics.balance_score:.1f}/100")
            
        except Exception as e:
            self.logger.error(f"Erreur calcul métriques avancées V3: {e}")
    
    def _calculate_diversity_score_comprehensive(self, sectors: int, quintiles: int, 
                                               max_sector_conc: float, max_quintile_conc: float,
                                               herfindahl: float) -> float:
        """Calcule le score de diversité composite (PRÉSERVÉ INTÉGRALEMENT)"""
        # Score basé sur le nombre de secteurs (0-30 points)
        sector_score = min(30, sectors * 3)
        
        # Score basé sur le nombre de quintiles (0-20 points)
        quintile_score = min(20, quintiles * 4)
        
        # Score basé sur la concentration sectorielle (0-25 points)
        concentration_score = max(0, 25 - max_sector_conc)
        
        # Score basé sur l'index de Herfindahl (0-25 points)
        herfindahl_score = max(0, 25 * (1 - herfindahl))
        
        return sector_score + quintile_score + concentration_score + herfindahl_score
    
    # ===== GESTION DES ANALYSES (PRÉSERVÉ INTÉGRALEMENT) =====
    
    def stop_analysis(self) -> Dict:
        """Arrête l'analyse en cours (PRÉSERVÉ INTÉGRALEMENT)"""
        try:
            if not self.status.running:
                return {'success': False, 'message': 'Aucune analyse en cours'}
            
            self.stop_flag = True
            self.status.running = False
            self.status.phase = 'stopped'
            self.status.last_update = datetime.now().isoformat()
            
            self.logger.info("🛑 Analyse arrêtée par l'utilisateur")
            
            return {
                'success': True, 
                'message': 'Analyse arrêtée avec succès',
                'analyzed_stocks': self.status.analyzed_stocks,
                'total_stocks': self.status.total_stocks
            }
            
        except Exception as e:
            self.logger.error(f"Erreur arrêt analyse: {e}")
            return {'success': False, 'message': f'Erreur: {str(e)}'}
    
    def get_top_10(self) -> Dict:
        """Retourne le Top 10 équitable (PRÉSERVÉ INTÉGRALEMENT)"""
        try:
            if not self.status.top_10_candidates:
                return {'top_10': [], 'message': 'Aucun Top 10 disponible. Lancez d\'abord une analyse complète.'}
            
            return {
                'top_10': self.status.top_10_candidates,
                'diversity_metrics': asdict(self.status.diversity_metrics) if self.status.diversity_metrics else None,
                'total_analyzed': len(self.status.analysis_results_500) if self.status.analysis_results_500 else 0,
                'selection_method': 'Équitable avec diversité forcée'
            }
            
        except Exception as e:
            self.logger.error(f"Erreur récupération Top 10: {e}")
            return {'error': str(e)}
    
    def get_final_recommendation(self) -> Dict:
        """Retourne la recommandation finale (PRÉSERVÉ INTÉGRALEMENT)"""
        try:
            if not self.status.final_recommendation:
                return {'recommendation': None, 'message': 'Aucune recommandation finale disponible'}
            
            return {
                'recommendation': self.status.final_recommendation,
                'method': 'Deep Equitable Analysis V3'  # Mis à jour pour V3
            }
            
        except Exception as e:
            self.logger.error(f"Erreur récupération recommandation finale: {e}")
            return {'error': str(e)}
    
    # ===== STATISTIQUES DE PERFORMANCE (PRÉSERVÉ + AMÉLIORÉ V3) =====
    
    def _update_performance_stats(self, total_time: float):
        """Met à jour les statistiques de performance (PRÉSERVÉ INTÉGRALEMENT)"""
        try:
            self.performance_stats['total_analyses'] = len(self.status.analysis_results_500)
            self.performance_stats['successful_analyses'] = self.status.successful_analyses
            self.performance_stats['error_rate'] = (self.status.error_count / max(1, self.status.analyzed_stocks)) * 100
            self.performance_stats['average_analysis_time'] = total_time / max(1, self.status.successful_analyses)
            
            # Couverture sectorielle
            if self.status.analysis_results_500:
                sector_counts = Counter([r.sector for r in self.status.analysis_results_500])
                self.performance_stats['sector_coverage'] = dict(sector_counts)
                
                quintile_counts = Counter([r.quintile_rank for r in self.status.analysis_results_500])
                self.performance_stats['quintile_coverage'] = dict(quintile_counts)
            
        except Exception as e:
            self.logger.error(f"Erreur mise à jour statistiques: {e}")
    
    def _update_performance_stats_v3(self, total_time: float):
        """Met à jour les statistiques de performance V3 (NOUVEAU)"""
        try:
            self._update_performance_stats(total_time)  # Appeler la version de base
            
            # Statistiques spécifiques V3
            if self.status.analysis_results_500:
                # Distribution par plage de score
                for result in self.status.analysis_results_500:
                    score = result.equitable_score
                    if score >= 82.4:
                        self.performance_stats['score_ranges']['strong_buy'] += 1
                    elif score >= 76.9:
                        self.performance_stats['score_ranges']['buy'] += 1
                    elif score >= 63.7:
                        self.performance_stats['score_ranges']['weak_buy'] += 1
                    elif score <= 17.6:
                        self.performance_stats['score_ranges']['strong_sell'] += 1
                    elif score <= 23.1:
                        self.performance_stats['score_ranges']['sell'] += 1
                    elif score <= 36.3:
                        self.performance_stats['score_ranges']['weak_sell'] += 1
                    else:
                        self.performance_stats['score_ranges']['hold'] += 1
            
        except Exception as e:
            self.logger.error(f"Erreur mise à jour statistiques V3: {e}")

# === FONCTIONS UTILITAIRES PRÉSERVÉES ===

def create_advanced_orchestrator() -> AdvancedCentralOrchestratorV3:
    """Factory function pour créer un orchestrateur avancé V3 (PRÉSERVÉ + AMÉLIORÉ)"""
    return AdvancedCentralOrchestratorV3()

# Instance globale pour l'API
orchestrator = AdvancedCentralOrchestratorV3()

if __name__ == "__main__":
    # Test de l'orchestrateur avancé V3
    async def test_orchestrator_v3():
        orch = AdvancedCentralOrchestratorV3()
        
        # Configuration
        config_result = orch.configure_advanced_mode('manual', {
            'max_sector_concentration': 22,
            'force_small_cap_inclusion': True
        })
        print("Configuration:", config_result)
        
        # Test d'analyse précise V3 (sur un échantillon réduit)
        orch.sp500_symbols = orch.sp500_symbols[:20]  # Test avec 20 symboles
        analysis_result = await orch.run_complete_sp500_analysis_precise()
        print("Analyse V3:", analysis_result)
        
        # Attendre la fin de l'analyse
        while orch.status.running:
            await asyncio.sleep(1)
        
        # Résultats
        status = orch.get_precise_status()
        print("Statut final V3:", json.dumps(status, indent=2, default=str))
    
    asyncio.run(test_orchestrator_v3())























































