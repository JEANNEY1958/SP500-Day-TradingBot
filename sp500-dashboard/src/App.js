import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';
import Alpaca from '@alpacahq/alpaca-trade-api';

// Configuration de l'URL de l'API
const API_BASE_URL = process.env.REACT_APP_API_URL || "https://sp500-day-tradingbot.onrender.com"; // Utilise des guillemets simples ou doubles, pas de template string ici

// === CONFIGURATION ALPACA ===
// Remplacez ces valeurs par vos vraies clés ou utilisez un formulaire sécurisé côté interface
const ALPACA_KEY = process.env.REACT_APP_ALPACA_KEY || '';
const ALPACA_SECRET = process.env.REACT_APP_ALPACA_SECRET || '';
const ALPACA_PAPER = true; // ou false si live

// Création de l'instance Alpaca (sera utilisée plus loin si besoin)
const alpaca = new Alpaca({
  keyId: ALPACA_KEY,
  secretKey: ALPACA_SECRET,
  paper: ALPACA_PAPER,
  usePolygon: false
});

// Test de connexion Alpaca au démarrage (affiche dans la console le compte ou l'erreur)
useEffect(() => {
  if (ALPACA_KEY && ALPACA_SECRET) {
    alpaca.getAccount().then(account => {
      console.log('Alpaca API connecté. Compte:', account);
    }).catch(error => {
      console.error('Erreur de connexion à Alpaca:', error.message || error);
    });
  } else {
    console.warn('Clés Alpaca non définies dans les variables d\'environnement.');
  }
}, []);

/*
FICHIER À COPIER/COLLER : sp500-dashboard/src/App.js
Interface React modifiée avec modes manuel/automatique et timers réglables + Trading Alpaca
VERSION FINALE - AVEC DÉTECTION DYNAMIQUE DU STATUT DU MARCHÉ
MODIFICATIONS APPLIQUÉES :
- Suppression de la section répétitive "📊 Analyse détaillée"
- Affichage complet des données DFS dans la zone grisée
- AJOUT: Intégration complète de l'agent de trading Alpaca (SANS MODIFICATION DU CODE EXISTANT)
- AJOUT: Détection dynamique du statut du marché avec jours fériés US
- CORRECTION MINIMALE: Persistance du montant initial avec localStorage
*/

// ===== FONCTION DE DÉTECTION DU STATUT DU MARCHÉ =====
const isUSMarketOpen = () => {
  const now = new Date();
  
  // Convertir en heure EST/EDT
  const estTime = new Date(now.toLocaleString("en-US", {timeZone: "America/New_York"}));
  const year = estTime.getFullYear();
  const month = estTime.getMonth();
  const date = estTime.getDate();
  const day = estTime.getDay(); // 0 = dimanche, 1 = lundi, ..., 6 = samedi
  const hours = estTime.getHours();
  const minutes = estTime.getMinutes();
  
  // Vérifier si c'est un weekend
  if (day === 0 || day === 6) {
    return false;
  }
  
  // Vérifier les heures d'ouverture (9h30 - 16h00 EST)
  const currentTimeInMinutes = hours * 60 + minutes;
  const marketOpen = 9 * 60 + 30; // 9h30
  const marketClose = 16 * 60; // 16h00
  
  if (currentTimeInMinutes < marketOpen || currentTimeInMinutes >= marketClose) {
    return false;
  }
  
  // Vérifier les jours fériés américains
  const holidays = getUSHolidays(year);
  const currentDate = `${year}-${String(month + 1).padStart(2, '0')}-${String(date).padStart(2, '0')}`;
  
  if (holidays.includes(currentDate)) {
    return false;
  }
  
  return true;
};

// Fonction pour obtenir les jours fériés américains pour une année donnée
const getUSHolidays = (year) => {
  const holidays = [];
  
  // New Year's Day - 1er janvier
  holidays.push(`${year}-01-01`);
  
  // Martin Luther King Jr. Day - 3ème lundi de janvier
  const mlkDay = getNthWeekdayOfMonth(year, 0, 1, 3); // 3ème lundi de janvier
  holidays.push(mlkDay);
  
  // Presidents Day - 3ème lundi de février
  const presidentsDay = getNthWeekdayOfMonth(year, 1, 1, 3); // 3ème lundi de février
  holidays.push(presidentsDay);
  
  // Good Friday - vendredi avant Pâques
  const goodFriday = getGoodFriday(year);
  holidays.push(goodFriday);
  
  // Memorial Day - dernier lundi de mai
  const memorialDay = getLastWeekdayOfMonth(year, 4, 1); // dernier lundi de mai
  holidays.push(memorialDay);
  
  // Juneteenth - 19 juin (depuis 2021)
  if (year >= 2021) {
    holidays.push(`${year}-06-19`);
  }
  
  // Independence Day - 4 juillet
  holidays.push(`${year}-07-04`);
  
  // Labor Day - 1er lundi de septembre
  const laborDay = getNthWeekdayOfMonth(year, 8, 1, 1); // 1er lundi de septembre
  holidays.push(laborDay);
  
  // Thanksgiving - 4ème jeudi de novembre
  const thanksgiving = getNthWeekdayOfMonth(year, 10, 4, 4); // 4ème jeudi de novembre
  holidays.push(thanksgiving);
  
  // Christmas Day - 25 décembre
  holidays.push(`${year}-12-25`);
  
  return holidays;
};

// Fonction utilitaire pour obtenir le nième jour de la semaine d'un mois
const getNthWeekdayOfMonth = (year, month, weekday, n) => {
  const firstDay = new Date(year, month, 1);
  const firstWeekday = firstDay.getDay();
  const daysToAdd = (weekday - firstWeekday + 7) % 7;
  const targetDate = new Date(year, month, 1 + daysToAdd + (n - 1) * 7);
  return `${year}-${String(month + 1).padStart(2, '0')}-${String(targetDate.getDate()).padStart(2, '0')}`;
};

// Fonction utilitaire pour obtenir le dernier jour de la semaine d'un mois
const getLastWeekdayOfMonth = (year, month, weekday) => {
  const lastDay = new Date(year, month + 1, 0);
  const lastWeekday = lastDay.getDay();
  // Correction : s'assurer que la date ne devient pas négative
  let day = lastDay.getDate() - ((lastWeekday - weekday + 7) % 7);
  if (day <= 0) day += 7;
  return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
};

// Fonction pour calculer le Vendredi Saint (Good Friday)
const getGoodFriday = (year) => {
  const easter = getEasterDate(year);
  // Ne pas muter l'objet Date easter, créer une nouvelle date
  const goodFriday = new Date(easter.getTime());
  goodFriday.setDate(goodFriday.getDate() - 2); // 2 jours avant Pâques
  return `${goodFriday.getFullYear()}-${String(goodFriday.getMonth() + 1).padStart(2, '0')}-${String(goodFriday.getDate()).padStart(2, '0')}`;
};

// Fonction pour calculer la date de Pâques
const getEasterDate = (year) => {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31);
  const day = ((h + l - 7 * m + 114) % 31) + 1;
  return new Date(year, month - 1, day);
};

// ===== FONCTIONS POUR LE MONTANT INITIAL UNIQUEMENT =====
const saveInitialAmountToStorage = (amount) => {
  try {
    if (!isNaN(amount) && amount !== null && amount !== undefined) {
      localStorage.setItem('trading_initial_amount', amount.toString());
      console.log('Montant initial sauvegardé:', amount);
    } else {
      throw new Error('Montant invalide');
    }
  } catch (error) {
    console.error('Erreur sauvegarde localStorage:', error);
  }
};

const getInitialAmountFromStorage = () => {
  try {
    const saved = localStorage.getItem('trading_initial_amount');
    const amount = saved && !isNaN(parseFloat(saved)) ? parseFloat(saved) : 10000;
    console.log('Montant initial récupéré:', amount);
    return amount;
  } catch (error) {
    console.error('Erreur lecture localStorage:', error);
    return 10000;
  }
};

function App() {
  // État pour le statut du marché
  const [marketOpen, setMarketOpen] = useState(false);
  
  // États pour les données
  const [systemStatus, setSystemStatus] = useState({
    running: false,
    analyzed_stocks: 0,
    total_stocks: 0,
    phase: 'idle', // Remis à 'idle' pour utilisation normale
    mode: 'manual'
  });
  const [loading, setLoading] = useState(false);
  
  // États pour les modes et timers - avec useRef pour éviter les re-renders
  const [mode, setMode] = useState('manual');
  const [timer500, setTimer500] = useState(30);
  const [timer10, setTimer10] = useState(15);
  // Nouveaux états pour les horloges
  const [schedule500Time, setSchedule500Time] = useState('09:30');
  const [schedule10Time, setSchedule10Time] = useState('14:30');
  const [schedule500Enabled, setSchedule500Enabled] = useState(false);
  const [schedule10Enabled, setSchedule10Enabled] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const isConfiguring = useRef(false); // Flag pour éviter les mises à jour pendant configuration
  
  // États pour les résultats
  const [top10Candidates, setTop10Candidates] = useState([]);
  const [finalRecommendation, setFinalRecommendation] = useState(null);
  const [showTop10, setShowTop10] = useState(false);
  const [showRecommendation, setShowRecommendation] = useState(false);

  // ===== ÉTATS POUR LE RAFRAÎCHISSEMENT DU CACHE =====
  const [refreshing, setRefreshing] = useState(false);
  const [cacheInfo, setCacheInfo] = useState(null);

  // ===== NOUVEAUX ÉTATS POUR LE MODE ANALYSE AUTOMATIQUE SEUIL 70% =====
  const [autoThresholdConfig, setAutoThresholdConfig] = useState({
    enabled: false,
    target_score: 70.0,
    max_cycles: 5,
    delay_between_cycles: 30,
    current_cycle: 0,
    running: false,
    last_score: 0.0,
    start_time: null,
    // Nouveaux paramètres pour l'horloge
    schedule_enabled: false,
    schedule_time: '09:30'
  });
  const [showAutoThresholdSettings, setShowAutoThresholdSettings] = useState(false);

  // ===== ÉTATS POUR L'ENVOI AUTOMATIQUE (SIMPLIFIÉ) =====
  const [lastProcessedRecommendation, setLastProcessedRecommendation] = useState(null);
  // eslint-disable-next-line no-unused-vars
const [autoSendLogs, setAutoSendLogs] = useState([]);

  // ===== NOUVEAUX ÉTATS POUR LE TRADING ALPACA =====
  const [tradingStatus, setTradingStatus] = useState({
    api_connected: false,
    mode: 'paper',
    auto_trading_enabled: false,
    market_open: true  // SERA REMPLACÉ PAR LA DÉTECTION DYNAMIQUE
  });
  const [portfolio, setPortfolio] = useState({
    buying_power: 0,
    portfolio_value: 0,
    positions: [],
    initial_amount: 10000,
    updated_balance: 0,
    total_pl: 0
  });
  const [tradingConfig, setTradingConfig] = useState({
    paper_api_key: '',
    paper_secret_key: '',
    live_api_key: '',
    live_secret_key: '',
    mode: 'paper',
    take_profit_percent: 2.0,
    stop_loss_percent: 2.0,
    auto_buy_time: '09:30',
    auto_sell_time: '15:50',
    investment_percent: 10.0,
    initial_amount: 10000.0,
    currency: 'USD'
  });
  const [showTradingSettings, setShowTradingSettings] = useState(false);
  const [tradingSymbol, setTradingSymbol] = useState('AAPL');
  const [tradingQty, setTradingQty] = useState(1);
  const [showTradingSection, setShowTradingSection] = useState(true);
  const [symbolAutoUpdated, setSymbolAutoUpdated] = useState(false);
  const [useRecommendation, setUseRecommendation] = useState(false);
  
  // NOUVEAU: État pour gérer l'affichage de l'attente du trading automatique
  const [tradingWaitingState, setTradingWaitingState] = useState({
    isWaiting: false,
    waitingUntil: null,
    message: ''
  });
  
  // État pour éviter l'écrasement des champs en cours de modification
  const [isEditingTradingConfig, setIsEditingTradingConfig] = useState(false);
  const editingTimeoutRef = useRef(null);
  
  // État local pour la valeur en cours de saisie du montant initial
  const [localInitialAmount, setLocalInitialAmount] = useState('');

  // Fonction pour récupérer le statut du système - stabilisée avec useCallback
  const fetchSystemStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/status`);
      const data = await response.json();
      setSystemStatus(data);
      
      // Mise à jour des états locaux SEULEMENT si on n'est pas en train de configurer
      if (!showSettings && !isConfiguring.current) {
        if (data.mode) setMode(data.mode);
        if (data.auto_timer_500) setTimer500(data.auto_timer_500);
        if (data.auto_timer_10) setTimer10(data.auto_timer_10);
        // Nouveaux paramètres d'horloges
        if (data.schedule_500_time) setSchedule500Time(data.schedule_500_time);
        if (data.schedule_10_time) setSchedule10Time(data.schedule_10_time);
        if (data.schedule_500_enabled !== undefined) setSchedule500Enabled(data.schedule_500_enabled);
        if (data.schedule_10_enabled !== undefined) setSchedule10Enabled(data.schedule_10_enabled);
      }
      
    } catch (error) {
      console.error('Erreur récupération statut:', error);
    }
  }, [showSettings]);

  // ===== NOUVELLES FONCTIONS POUR LE TRADING ALPACA =====
  const fetchTradingStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/trading/status`);
      const data = await response.json();
      
      if (data.success) {
        // MODIFIÉ: Forcer market_open à true pour tests 24h/24
        data.market_open = true;
        setTradingStatus(data);
        if (data.portfolio) {
          setPortfolio(data.portfolio);
        }
        // CORRECTION AMÉLIORÉE: Ne pas écraser la config si l'utilisateur est en train de l'éditer
        // ET vérifier si les valeurs ont réellement changé pour éviter les mises à jour inutiles
        if (data.config && !isEditingTradingConfig) {
          const hasConfigChanged = 
            data.config.take_profit_percent !== tradingConfig.take_profit_percent ||
            data.config.stop_loss_percent !== tradingConfig.stop_loss_percent ||
            data.config.investment_percent !== tradingConfig.investment_percent ||
            data.config.initial_amount !== tradingConfig.initial_amount;
          
          if (hasConfigChanged) {
            setTradingConfig(prev => ({ ...prev, ...data.config }));
          }
        }
      }
    } catch (error) {
      console.error('Erreur récupération statut trading:', error);
    }
  }, [isEditingTradingConfig, tradingConfig.take_profit_percent, tradingConfig.stop_loss_percent, tradingConfig.investment_percent, tradingConfig.initial_amount]);

  const fetchPortfolio = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/trading/portfolio`);
      const data = await response.json();
      
      if (data.success && data.portfolio) {
        setPortfolio(data.portfolio);
      }
    } catch (error) {
      console.error('Erreur récupération portefeuille:', error);
    }
  }, []);

  const configureTradingAPI = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/trading/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(tradingConfig)
      });
      
      const data = await response.json();
      if (data.success) {
        alert(`Configuration Alpaca réussie en mode ${tradingConfig.mode} !`);
        setShowTradingSettings(false);
        fetchTradingStatus();
        fetchPortfolio();
      } else {
        alert('Erreur configuration: ' + data.message);
      }
    } catch (error) {
      console.error('Erreur configuration trading:', error);
      alert('Erreur de connexion au serveur');
    }
  };

 // Fonction de sauvegarde automatique des paramètres de trading
const autoSaveTradingConfig = useCallback(async (configToSave) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/trading/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        take_profit_percent: configToSave.take_profit_percent,
        stop_loss_percent: configToSave.stop_loss_percent,
        investment_percent: configToSave.investment_percent,
        initial_amount: configToSave.initial_amount,
        currency: configToSave.currency,
        auto_buy_time: configToSave.auto_buy_time,
        auto_sell_time: configToSave.auto_sell_time
      } )
    });
    
    const data = await response.json();
    if (data.success) {
      console.log('Configuration sauvegardée automatiquement');
    }
  } catch (error) {
    console.error('Erreur sauvegarde automatique:', error);
  }
}, []);


  const updateTradingConfig = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/trading/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          take_profit_percent: tradingConfig.take_profit_percent,
          stop_loss_percent: tradingConfig.stop_loss_percent,
          auto_sell_time: tradingConfig.auto_sell_time,
          auto_buy_time: tradingConfig.auto_buy_time, // CORRECTION: Ajout du paramètre manquant
          investment_percent: tradingConfig.investment_percent,
          initial_amount: tradingConfig.initial_amount,
          currency: tradingConfig.currency
        })
      });
      
      const data = await response.json();
      if (data.success) {
        alert('Configuration de trading mise à jour !');
        fetchTradingStatus();
      } else {
        alert('Erreur: ' + data.message);
      }
    } catch (error) {
      console.error('Erreur mise à jour config trading:', error);
      alert('Erreur de connexion au serveur');
    }
  };

  const placeManualOrder = async (side) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/trading/order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: tradingSymbol,
          qty: tradingQty,
          side: side,
          order_type: 'market'
        })
      });
      
      const data = await response.json();
      if (data.success) {
        alert(`Ordre ${side} placé avec succès pour ${tradingQty} ${tradingSymbol} !`);
        fetchPortfolio();
      } else {
        alert('Erreur ordre: ' + data.message);
      }
    } catch (error) {
      console.error('Erreur placement ordre:', error);
      alert('Erreur de connexion au serveur');
    }
  };

  const startAutoTrading = useCallback(async () => {
    try {
      // AMÉLIORATION: Afficher l'état d'attente
      const currentTime = new Date().toLocaleTimeString('en-US', {
        timeZone: 'America/New_York',
        hour12: false,
        hour: '2-digit',
        minute: '2-digit'
      });
      
      const buyTime = tradingConfig.auto_buy_time;
      
      // Si l'heure d'achat n'est pas encore atteinte, afficher l'état d'attente
      if (currentTime < buyTime) {
        setTradingWaitingState({
          isWaiting: true,
          waitingUntil: buyTime,
          // message: `En attente de l'heure d'achat: ${buyTime} (ET)` // 
        });
      }
      
      const response = await fetch(`${API_BASE_URL}/api/trading/auto/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          symbol: tradingSymbol,
          use_recommendation: useRecommendation
        })
      });
      
      const data = await response.json();
      if (data.success) {
        const message = useRecommendation 
          ? `Trading automatique démarré en attente de recommandation (fallback: ${tradingSymbol})` 
          : `Trading automatique démarré pour ${tradingSymbol} !`;
        alert(message);
        fetchTradingStatus();
        
        // Si l'achat est immédiat, réinitialiser l'état d'attente
        if (currentTime >= buyTime) {
          setTradingWaitingState({
            isWaiting: false,
            waitingUntil: null,
            message: ''
          });
        }
      } else {
        alert('Erreur: ' + data.message);
        // Réinitialiser l'état d'attente en cas d'erreur
        setTradingWaitingState({
          isWaiting: false,
          waitingUntil: null,
          message: ''
        });
      }
    } catch (error) {
      console.error('Erreur démarrage trading auto:', error);
      alert('Erreur de connexion au serveur');
      // Réinitialiser l'état d'attente en cas d'erreur
      setTradingWaitingState({
        isWaiting: false,
        waitingUntil: null,
        message: ''
      });
    }
  }, [tradingSymbol, fetchTradingStatus, tradingConfig.auto_buy_time, useRecommendation]);

  const stopAutoTrading = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/trading/auto/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await response.json();
      if (data.success) {
        alert('Trading automatique arrêté !');
        fetchTradingStatus();
        // AMÉLIORATION: Réinitialiser l'état d'attente
        setTradingWaitingState({
          isWaiting: false,
          waitingUntil: null,
          message: ''
        });
      } else {
        alert('Erreur: ' + data.message);
      }
    } catch (error) {
      console.error('Erreur arrêt trading auto:', error);
      alert('Erreur de connexion au serveur');
    }
  };

  const formatCurrency = (amount, currency = 'USD') => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: currency
    }).format(amount);
  };

  // ===== FONCTION SIMPLIFIÉE POUR L'ENVOI AUTOMATIQUE =====
  const autoSendToTrading = useCallback(async (recommendation) => {
    if (!recommendation) {
      return;
    }

    // Vérifier si cette recommandation a déjà été traitée
    const recommendationId = `${recommendation.symbol}_${recommendation.analysis_timestamp || Date.now()}`;
    if (lastProcessedRecommendation === recommendationId) {
      return;
    }

    // Vérifier les conditions d'envoi (utiliser le seuil configuré)
    const score = recommendation.final_score || recommendation.score || 0;
    const recommendationType = recommendation.recommendation || '';
    
    // CORRECTION: Utiliser le seuil configuré au lieu d'un seuil fixe
    const configuredThreshold = autoThresholdConfig.target_score || 70;
    if (score < configuredThreshold) {
      console.log(`Score trop faible pour envoi automatique: ${score}% < ${configuredThreshold}%`);
      return;
    }

    const acceptedRecommendations = ['BUY', 'STRONG_BUY', 'WEAK_BUY'];
    if (!acceptedRecommendations.includes(recommendationType)) {
      console.log(`Type de recommandation non autorisé: ${recommendationType}`);
      return;
    }

    // Vérifier que l'API trading est connectée
    if (!tradingStatus.api_connected) {
      console.log('API trading non connectée, envoi automatique annulé');
      return;
    }

    try {
      console.log(`🚀 Envoi automatique vers trading: ${recommendation.symbol}`);
      
      const response = await fetch(`${API_BASE_URL}/api/trading/auto/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: recommendation.symbol })
      });
      
      const data = await response.json();
      
      const logEntry = {
        timestamp: new Date().toISOString(),
        symbol: recommendation.symbol,
        score: score,
        recommendation: recommendationType,
        success: data.success,
        message: data.message || (data.success ? 'Envoi réussi' : 'Envoi échoué')
      };

      setAutoSendLogs(prev => [logEntry, ...prev.slice(0, 9)]); // Garder les 10 derniers logs
      setLastProcessedRecommendation(recommendationId);

      if (data.success) {
        console.log(`✅ Envoi automatique réussi pour ${recommendation.symbol}`);
        setTradingSymbol(recommendation.symbol); // Met à jour le symbole dans l'interface
      } else {
        console.error(`❌ Envoi automatique échoué pour ${recommendation.symbol}: ${data.message}`);
      }
      
    } catch (error) {
      console.error('Erreur envoi automatique:', error);
      
      const logEntry = {
        timestamp: new Date().toISOString(),
        symbol: recommendation.symbol,
        score: score,
        recommendation: recommendationType,
        success: false,
        message: `Erreur: ${error.message}`
      };

      setAutoSendLogs(prev => [logEntry, ...prev.slice(0, 9)]);
    }
  }, [lastProcessedRecommendation, tradingStatus.api_connected, autoThresholdConfig.target_score]);

  // Fonction pour récupérer le Top 10 - stabilisée avec useCallback
  const fetchTop10 = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/get-top-10`);
      const data = await response.json();
      
      if (data.success) {
        setTop10Candidates(data.top_10);
      }
    } catch (error) {
      console.error('Erreur récupération Top 10:', error);
    }
  }, []);

  // Fonction pour récupérer la recommandation finale - stabilisée avec useCallback
  const fetchFinalRecommendation = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/get-final-recommendation`);
      const data = await response.json();
      
      if (data.success) {
        setFinalRecommendation(data.recommendation);
      }
    } catch (error) {
      console.error('Erreur récupération recommandation:', error);
    }
  }, []);

  // Fonction pour démarrer l'analyse des 500 tickers
  const startAnalysis500 = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/start-analysis-500`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await response.json();
      if (data.success) {
        alert('Analyse des 500 tickers démarrée !');
      } else {
        alert('Erreur: ' + data.message);
      }
    } catch (error) {
      console.error('Erreur démarrage analyse 500:', error);
      alert('Erreur de connexion au serveur');
    }
    setLoading(false);
  };

  // Fonction pour démarrer l'analyse des 10 finalistes
  const startAnalysis10 = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/start-analysis-10`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await response.json();
      if (data.success) {
        alert('Analyse des 10 finalistes démarrée !');
      } else {
        alert('Erreur: ' + data.message);
      }
    } catch (error) {
      console.error('Erreur démarrage analyse 10:', error);
      alert('Erreur de connexion au serveur');
    }
    setLoading(false);
  };

  // Fonction pour arrêter l'analyse
  const stopAnalysis = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/stop-analysis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await response.json();
      if (data.success) {
        alert('Analyse arrêtée !');
      }
    } catch (error) {
      console.error('Erreur arrêt analyse:', error);
    }
  };

  // ===== FONCTIONS POUR LE RAFRAÎCHISSEMENT DU CACHE =====
  
  // Fonction pour rafraîchir le cache
  const refreshCache = async () => {
    setRefreshing(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/refresh-cache`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await response.json();
      if (data.success) {
        // Réinitialiser les données locales
        setTop10Candidates([]);
        setFinalRecommendation(null);
        setShowTop10(false);
        setShowRecommendation(false);
        
        // Mettre à jour le statut système
        await fetchSystemStatus();
        
        alert('✅ Cache rafraîchi avec succès !');
      } else {
        alert('❌ Erreur lors du rafraîchissement: ' + data.message);
      }
    } catch (error) {
      console.error('Erreur rafraîchissement cache:', error);
      alert('❌ Erreur de connexion lors du rafraîchissement');
    }
    setRefreshing(false);
  };

  // Fonction pour obtenir les informations du cache
  const fetchCacheInfo = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/cache-info`);
      const data = await response.json();
      if (data.success) {
        setCacheInfo(data.cache_status);
      }
    } catch (error) {
      console.error('Erreur récupération info cache:', error);
    }
  };

  // Fonction pour configurer le mode et les timers
  const configureMode = async () => {
    isConfiguring.current = true;
    try {
      const response = await fetch(`${API_BASE_URL}/api/set-mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: mode,
          timer_500: timer500,
          timer_10: timer10,
          // Nouveaux paramètres d'horloges
          schedule_500_time: schedule500Time,
          schedule_10_time: schedule10Time,
          schedule_500_enabled: schedule500Enabled,
          schedule_10_enabled: schedule10Enabled
        })
      });
      
      const data = await response.json();
      if (data.success) {
        let message = `Mode ${mode} configuré avec succès !`;
        if (mode === 'auto') {
          if (schedule500Enabled && schedule500Time) {
            message += `\n📅 Analyse 500 tickers programmée à ${schedule500Time}`;
          }
          if (schedule10Enabled && schedule10Time) {
            message += `\n📅 Analyse 10 finalistes programmée à ${schedule10Time}`;
          }
        }
        alert(message);
        setShowSettings(false);
        isConfiguring.current = false;
        // Forcer une mise à jour du statut après configuration
        setTimeout(fetchSystemStatus, 500);
      } else {
        alert('Erreur: ' + data.message);
        isConfiguring.current = false;
      }
    } catch (error) {
      console.error('Erreur configuration mode:', error);
      alert('Erreur de connexion au serveur');
      isConfiguring.current = false;
    }
  };

  // Fonction pour ouvrir le panneau de configuration
  const openSettings = () => {
    isConfiguring.current = true;
    setShowSettings(true);
    // Fermer les autres panneaux pour éviter les conflits
    setShowAutoThresholdSettings(false);
  };

  // Fonction pour fermer le panneau de configuration
  const closeSettings = () => {
    setShowSettings(false);
    isConfiguring.current = false;
    // Restaurer les valeurs du serveur
    fetchSystemStatus();
  };

  // Fonction pour ouvrir le panneau de configuration du mode seuil
  const openAutoThresholdSettings = () => {
    // Fermer les autres panneaux pour éviter les conflits
    setShowSettings(false);
    isConfiguring.current = false;
    setShowAutoThresholdSettings(true);
  };

  // Fonction pour fermer le panneau de configuration du mode seuil
  const closeAutoThresholdSettings = () => {
    setShowAutoThresholdSettings(false);
    // NE PAS restaurer les valeurs du serveur pour préserver les paramètres locaux
    // fetchAutoThresholdStatus();
  };

  // ===== NOUVELLES FONCTIONS POUR LE MODE ANALYSE AUTOMATIQUE SEUIL 70% =====
  
  // Fonction pour récupérer le statut du mode analyse automatique seuil
  const fetchAutoThresholdStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/auto-threshold/status`);
      const data = await response.json();
      
      if (data.success) {
        setAutoThresholdConfig(data.config);
      }
    } catch (error) {
      console.error('Erreur récupération statut auto-threshold:', error);
    }
  }, []);

  // Fonction pour configurer le mode analyse automatique seuil
  const configureAutoThreshold = async () => {
    try {
      // CORRECTION: Utiliser le même endpoint et structure que PowerShell
      const body = {
        "mode": "auto",
        "auto_schedule": {
          "enabled": true,
          "threshold_time": autoThresholdConfig.schedule_time || "14:15",
          "timezone": "Europe/Paris",
          "weekdays_only": false,
          "auto_threshold_config": {
            "target_score": autoThresholdConfig.target_score,
            "max_cycles": autoThresholdConfig.max_cycles,
            "delay_between_cycles": autoThresholdConfig.delay_between_cycles
          }
        },
        "auto_threshold": {
          "enabled": autoThresholdConfig.enabled,
          "target_score": autoThresholdConfig.target_score,
          "max_cycles": autoThresholdConfig.max_cycles,
          "delay_between_cycles": autoThresholdConfig.delay_between_cycles
        }
      };

      const response = await fetch(`${API_BASE_URL}/api/set-mode-extended`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      
      const data = await response.json();
      if (data.success) {
        let message = 'Configuration analyse automatique seuil mise à jour !';
        if (autoThresholdConfig.schedule_enabled) {
          message += `\n⏰ Démarrage automatique programmé à ${autoThresholdConfig.schedule_time}`;
        }
        alert(message);
        // NE PAS fermer la fenêtre automatiquement pour permettre à l'utilisateur de voir les paramètres
        // setShowAutoThresholdSettings(false);
        // Mettre à jour le statut sans fermer la fenêtre
        fetchAutoThresholdStatus();
      } else {
        alert('Erreur: ' + data.message);
      }
    } catch (error) {
      console.error('Erreur configuration auto-threshold:', error);
      alert('Erreur de connexion au serveur');
    }
  };

  // Fonction pour démarrer le mode analyse automatique seuil
  const startAutoThreshold = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/auto-threshold/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await response.json();
      if (data.success) {
        alert('Mode analyse automatique seuil démarré !');
        fetchAutoThresholdStatus();
      } else {
        alert('Erreur: ' + data.message);
      }
    } catch (error) {
      console.error('Erreur démarrage auto-threshold:', error);
      alert('Erreur de connexion au serveur');
    }
  }, [fetchAutoThresholdStatus]);

  // Fonction pour arrêter le mode analyse automatique seuil
  const stopAutoThreshold = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/auto-threshold/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await response.json();
      if (data.success) {
        alert('Mode analyse automatique seuil arrêté !');
        fetchAutoThresholdStatus();
      } else {
        alert('Erreur: ' + data.message);
      }
    } catch (error) {
      console.error('Erreur arrêt auto-threshold:', error);
      alert('Erreur de connexion au serveur');
    }
  };

  // Fonction pour formater le temps
  const formatTime = (isoString) => {
    if (!isoString) return 'N/A';
    return new Date(isoString).toLocaleTimeString('fr-FR');
  };

  // Fonction pour obtenir la couleur du score - SUPPRIMÉE car non utilisée
  // const getScoreColor = (score) => {
  //   if (score >= 80) return '#4CAF50'; // Vert
  //   if (score >= 60) return '#FF9800'; // Orange
  //   return '#F44336'; // Rouge
  // };

  // Fonction pour obtenir la couleur de la recommandation
  const getRecommendationColor = (recommendation) => {
    if (!recommendation || typeof recommendation !== 'string') return '#FF9800'; // Orange par défaut
    if (recommendation.includes('BUY')) return '#4CAF50';
    if (recommendation.includes('SELL')) return '#F44336';
    return '#FF9800';
  };

  // Effet pour la mise à jour du statut du marché
  useEffect(() => {
    const updateMarketStatus = () => {
      setMarketOpen(isUSMarketOpen());
    };
    
    // Mise à jour immédiate
    updateMarketStatus();
    
    // Mise à jour toutes les minutes
    const interval = setInterval(updateMarketStatus, 60000);
    
    return () => clearInterval(interval);
  }, []);

  // Effet pour initialiser la valeur locale du montant initial
  useEffect(() => {
    setLocalInitialAmount(getInitialAmountFromStorage().toString());
  }, []);

  // Effet pour récupérer les informations du cache au démarrage
  useEffect(() => {
    fetchCacheInfo();
    const interval = setInterval(fetchCacheInfo, 30000); // Mise à jour toutes les 30 secondes
    return () => clearInterval(interval);
  }, []);

  // Effet pour les mises à jour automatiques - dépendances corrigées
  useEffect(() => {
    fetchSystemStatus();
    fetchTradingStatus(); // AJOUT: Récupération du statut trading
    
    // Initialisation supprimée car setLocalInitialAmount n'existe plus
    // setLocalInitialAmount(tradingConfig.initial_amount.toString());
    
    const interval = setInterval(() => {
      // Toujours permettre les mises à jour du statut système pour le progrès
      if (!isConfiguring.current) {
        fetchSystemStatus();
        // fetchTradingStatus et fetchPortfolio déplacés vers leur propre intervalle
        if (systemStatus.phase === 'completed_500' || systemStatus.phase === 'analyzing_10') {
          fetchTop10();
        }
        if (systemStatus.phase === 'completed_10') {
          fetchFinalRecommendation();
        }
      }
    }, 3000); // Mise à jour toutes les 3 secondes (statut système uniquement)

    // Intervalle séparé pour le statut trading (moins fréquent pour éviter les conflits)
    const tradingInterval = setInterval(() => {
      if (!isConfiguring.current && !isEditingTradingConfig && !showSettings && !showAutoThresholdSettings) {
        fetchTradingStatus();
        if (tradingStatus.api_connected) {
          fetchPortfolio();
        }
      }
    }, 10000); // Mise à jour toutes les 10 secondes pour le trading

    return () => {
      clearInterval(interval);
      clearInterval(tradingInterval);
    };
  }, [fetchSystemStatus, fetchTradingStatus, fetchPortfolio, fetchTop10, fetchFinalRecommendation, systemStatus.phase, tradingStatus.api_connected, isEditingTradingConfig, showSettings, showAutoThresholdSettings]);

  // ===== EFFET POUR LE MODE ANALYSE AUTOMATIQUE SEUIL 70% =====
  useEffect(() => {
    fetchAutoThresholdStatus();
    const interval = setInterval(() => {
      // Ne pas mettre à jour si la fenêtre de configuration est ouverte
      if (!showAutoThresholdSettings) {
        fetchAutoThresholdStatus();
      }
    }, 5000); // Mise à jour toutes les 5 secondes
    return () => clearInterval(interval);
  }, [fetchAutoThresholdStatus, showAutoThresholdSettings]);

  // Effet pour l'affichage automatique en mode auto - console.log supprimés
  useEffect(() => {
    if (systemStatus.mode === 'auto') {
      // Affichage automatique du Top 10 quand l'analyse des 500 est terminée
      if (systemStatus.phase === 'completed_500' && !showTop10) {
        setShowTop10(true);
        fetchTop10();
      }
      
      // Affichage automatique de la recommandation finale quand l'analyse des 10 est terminée
      if (systemStatus.phase === 'completed_10' && !showRecommendation) {
        setShowRecommendation(true);
        fetchFinalRecommendation();
      }
    }
  }, [systemStatus.phase, systemStatus.mode, showTop10, showRecommendation, fetchTop10, fetchFinalRecommendation]);

  // ===== EFFET POUR L'ENVOI AUTOMATIQUE (SIMPLIFIÉ) =====
  useEffect(() => {
    // Envoi automatique uniquement si :
    // 1. Mode automatique activé
    // 2. Analyse des 10 finalistes programmée et activée
    // 3. Recommandation finale disponible
    // 4. PAS en mode analyse automatique seuil (qui a sa propre logique)
    if (finalRecommendation && 
        systemStatus.mode === 'auto' && 
        systemStatus.phase === 'completed_10' &&
        schedule10Enabled &&
        !autoThresholdConfig.running) {  // ← CORRECTION: Exclure le mode seuil
      autoSendToTrading(finalRecommendation);
    }
  }, [finalRecommendation, systemStatus.mode, systemStatus.phase, schedule10Enabled, autoSendToTrading, autoThresholdConfig.running]);

  // ===== EFFET POUR LE DÉCLENCHEMENT AUTOMATIQUE DU MODE AUTO =====
  useEffect(() => {
    const checkAutoBuyTime = () => {
      const now = new Date();
      const currentTime = now.toTimeString().slice(0, 5); // Format HH:MM
      
      // Vérifier si l'heure actuelle correspond à l'heure d'achat programmée
      if (currentTime === tradingConfig.auto_buy_time && 
          !tradingStatus.auto_trading_enabled && 
          marketOpen) {
        console.log('Déclenchement automatique du mode auto à', currentTime);
        startAutoTrading();
      }
    };

    // Vérifier toutes les minutes
    const interval = setInterval(checkAutoBuyTime, 60000);
    
    // Vérification immédiate
    checkAutoBuyTime();
    
    return () => clearInterval(interval);
  }, [tradingConfig.auto_buy_time, tradingStatus.auto_trading_enabled, marketOpen, startAutoTrading]);

  // ===== EFFET POUR MISE À JOUR AUTOMATIQUE DU TRADING SYMBOL =====
  useEffect(() => {
    // Mettre à jour le trading symbol automatiquement quand une recommandation finale est disponible
    // CORRECTION: Seulement si le seuil est respecté ou si le mode seuil n'est pas actif
    if (finalRecommendation && finalRecommendation.symbol && finalRecommendation.symbol !== tradingSymbol) {
      
      // Vérifier si le mode seuil est actif
      if (autoThresholdConfig.enabled && autoThresholdConfig.running) {
        // Mode seuil actif : vérifier le score
        const score = finalRecommendation.final_score || finalRecommendation.score || 0;
        const targetScore = autoThresholdConfig.target_score || 70;
        
        if (score >= targetScore) {
          console.log(`Mise à jour automatique du trading symbol (seuil atteint): ${tradingSymbol} → ${finalRecommendation.symbol} (${score}% >= ${targetScore}%)`);
          setTradingSymbol(finalRecommendation.symbol);
          setSymbolAutoUpdated(true);
        } else {
          console.log(`Mise à jour automatique du trading symbol BLOQUÉE (seuil non atteint): ${finalRecommendation.symbol} (${score}% < ${targetScore}%)`);
        }
      } else {
        // Mode seuil inactif : mise à jour normale
        console.log(`Mise à jour automatique du trading symbol: ${tradingSymbol} → ${finalRecommendation.symbol}`);
        setTradingSymbol(finalRecommendation.symbol);
        setSymbolAutoUpdated(true);
      }
      
      // Réinitialiser l'indicateur après 10 secondes
      setTimeout(() => {
        setSymbolAutoUpdated(false);
      }, 10000);
    }
  }, [finalRecommendation, tradingSymbol, autoThresholdConfig.enabled, autoThresholdConfig.running, autoThresholdConfig.target_score]);

  // ===== EFFET POUR LE DÉCLENCHEMENT AUTOMATIQUE DU MODE SEUIL =====
  useEffect(() => {
    const checkAutoThresholdTime = () => {
      if (!autoThresholdConfig.schedule_enabled || autoThresholdConfig.running) {
        return; // Ne pas vérifier si la programmation n'est pas activée ou si déjà en cours
      }

      const now = new Date();
      const currentTime = now.toTimeString().slice(0, 5); // Format HH:MM
      
      // Vérifier si l'heure actuelle correspond à l'heure programmée
      if (currentTime === autoThresholdConfig.schedule_time) {
        console.log('Déclenchement automatique du mode seuil à', currentTime);
        startAutoThreshold();
      }
    };

    // Vérifier toutes les minutes
    const interval = setInterval(checkAutoThresholdTime, 60000);
    
    // Vérification immédiate
    checkAutoThresholdTime();
    
    return () => clearInterval(interval);
  }, [autoThresholdConfig.schedule_enabled, autoThresholdConfig.schedule_time, autoThresholdConfig.running, startAutoThreshold]);

  return (
    <div className="App">
      <header className="App-header">
        <h1>🚀 S&P 500 Day TradingBot</h1>
        <p>Système d'analyse intelligent avec modes manuel et automatique</p>
      </header>

      {/* Section Statut du Système */}
      <div className="status-section">
        <h2>📊 Statut du Système</h2>
        <div className="status-grid">
          <div className="status-card">
            <h3>Mode Actuel</h3>
            <span className={`mode-badge ${mode}`}>
              {mode === 'manual' ? '🔧 Manuel' : '⚡ Automatique'}
            </span>
          </div>
          
          <div className="status-card">
            <h3>Phase</h3>
            <span className="phase-badge">
              {systemStatus.phase === 'idle' && '⏸️ En attente'}
              {systemStatus.phase === 'analyzing_500' && '🔍 Analyse 500 tickers'}
              {systemStatus.phase === 'completed_500' && '✅ Top 10 sélectionné'}
              {systemStatus.phase === 'analyzing_10' && '⚡ Analyse 10 finalistes'}
              {systemStatus.phase === 'completed_10' && '🏆 Recommandation prête'}
              {systemStatus.phase === 'error' && '❌ Erreur'}
            </span>
          </div>
          
          <div className="status-card">
            <h3>Progrès</h3>
            <div className="progress-info">
              <span>{systemStatus.analyzed_stocks} / {systemStatus.total_stocks}</span>
              {systemStatus.total_stocks > 0 && (
                <div className="progress-bar">
                  <div 
                    className="progress-fill"
                    style={{ width: `${(systemStatus.analyzed_stocks / systemStatus.total_stocks) * 100}%` }}
                  ></div>
                </div>
              )}
            </div>
          </div>
          
          <div className="status-card">
            <h3>Dernière MAJ</h3>
            <span>{formatTime(systemStatus.last_update)}</span>
          </div>
        </div>
      </div>

      {/* ===== NOUVELLE SECTION TRADING ALPACA ===== */}
      <div className="trading-section">
        <h2>💰 Trading </h2>
        
        {/* Bouton pour afficher/masquer la section trading */}
        <div className="control-buttons">
          <button 
            className="config-btn"
            onClick={() => setShowTradingSection(!showTradingSection)}
          >
            {showTradingSection ? '🔽 Masquer Trading' : '🔼 Afficher Trading'}
          </button>
        </div>

        {showTradingSection && (
          <>
            {/* Statut de connexion */}
            <div className="trading-status">
              <div className="status-grid">
                <div className="status-card">
                  <h3>Connexion API</h3>
                  <span className={`connection-badge ${tradingStatus.api_connected ? 'connected' : 'disconnected'}`}>
                    {tradingStatus.api_connected ? '✅ Connecté' : '❌ Déconnecté'}
                  </span>
                </div>
                
                <div className="status-card">
                  <h3>Mode Trading</h3>
                  <span className={`mode-badge ${tradingStatus.mode}`}>
                    {tradingStatus.mode === 'paper' ? '📝 Paper' : '💰 Live'}
                  </span>
                </div>
                
                <div className="status-card">
                  <h3>Marché</h3>
                  <span className={`market-badge ${marketOpen ? 'open' : 'closed'}`}>
                    {marketOpen ? '🟢 Marché : Ouvert' : '🔴 Marché : Fermé'}
                  </span>
                </div>
                
                <div className="status-card">
                  <h3>Trading Auto</h3>
                  <span className={`auto-badge ${tradingStatus.auto_trading_enabled ? 'active' : 'inactive'}`}>
                    {tradingStatus.auto_trading_enabled ? '⚡ Actif' : '⏸️ Inactif'}
                  </span>
                  {/* AMÉLIORATION: Affichage de l'état d'attente */}
                  {tradingWaitingState.isWaiting && (
                    <div className="waiting-info" style={{marginTop: '5px', fontSize: '12px', color: '#666'}}>
                       {tradingWaitingState.message}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Configuration des clés API */}
            <div className="trading-config">
              <button 
                className="config-btn"
                onClick={() => setShowTradingSettings(!showTradingSettings)}
              >
                ⚙️ Configuration API Alpaca
              </button>

              {showTradingSettings && (
                <div className="settings-panel">
                  <h3>Configuration des Clés API Alpaca</h3>
                  
                  <div className="setting-group">
                    <label>Mode de trading :</label>
                    <select 
                      value={tradingConfig.mode} 
                      onChange={(e) => setTradingConfig(prev => ({ ...prev, mode: e.target.value }))}
                    >
                      <option value="paper">📝 Paper Trading</option>
                      <option value="live">💰 Live Trading</option>
                    </select>
                  </div>

                  <div className="setting-group">
                    <label>Clé API Paper :</label>
                    <input 
                      type="password" 
                      value={tradingConfig.paper_api_key} 
                      onChange={(e) => setTradingConfig(prev => ({ ...prev, paper_api_key: e.target.value }))}
                      placeholder="Votre clé API Paper Alpaca"
                    />
                  </div>

                  <div className="setting-group">
                    <label>Clé secrète Paper :</label>
                    <input 
                      type="password" 
                      value={tradingConfig.paper_secret_key} 
                      onChange={(e) => setTradingConfig(prev => ({ ...prev, paper_secret_key: e.target.value }))}
                      placeholder="Votre clé secrète Paper Alpaca"
                    />
                  </div>

                  <div className="setting-group">
                    <label>Clé API Live :</label>
                    <input 
                      type="password" 
                      value={tradingConfig.live_api_key} 
                      onChange={(e) => setTradingConfig(prev => ({ ...prev, live_api_key: e.target.value }))}
                      placeholder="Votre clé API Live Alpaca"
                    />
                  </div>

                  <div className="setting-group">
                    <label>Clé secrète Live :</label>
                    <input 
                      type="password" 
                      value={tradingConfig.live_secret_key} 
                      onChange={(e) => setTradingConfig(prev => ({ ...prev, live_secret_key: e.target.value }))}
                      placeholder="Votre clé secrète Live Alpaca"
                    />
                  </div>

                  <div className="setting-group">
                    <label>Montant initial du portefeuille :</label>
                    <input 
                      type="number" 
                      value={localInitialAmount}
                      onChange={(e) => {
                        const inputValue = e.target.value;
                        // Mettre à jour l'état local immédiatement pour une saisie fluide
                        setLocalInitialAmount(inputValue);
                        // Permettre la saisie vide
                        if (inputValue === '' || inputValue === null) {
                          saveInitialAmountToStorage(0);
                          setTradingConfig(prev => ({ ...prev, initial_amount: 0 }));
                          return;
                        }
                        // Traiter la valeur numérique
                        const value = parseFloat(inputValue.replace(',', '.'));
                        if (!isNaN(value) && value >= 0) {
                          saveInitialAmountToStorage(value);
                          setTradingConfig(prev => ({ ...prev, initial_amount: value }));
                        }
                      }}
                      onBlur={() => {
                        // Synchroniser avec la valeur sauvegardée en cas de valeur invalide
                        const savedValue = getInitialAmountFromStorage();
                        setLocalInitialAmount(savedValue.toString());
                      }}
                      onFocus={(e) => {
                        // Sélectionner tout le texte au focus pour faciliter la saisie
                        e.target.select();
                      }}
                      step="0.01"
                      placeholder="Saisissez le montant initial"
                    />
                    <small style={{ color: '#4CAF50' }}>💾 Sauvegarde automatique - Vous pouvez vider le champ</small>
                  </div>

                  <div className="setting-group">
                    <label>Devise :</label>
                    <select 
                      value={tradingConfig.currency} 
                      onChange={(e) => setTradingConfig(prev => ({ ...prev, currency: e.target.value }))}
                    >
                      <option value="USD">💵 USD</option>
                      <option value="EUR">💶 EUR</option>
                    </select>
                  </div>

                  <div className="setting-buttons">
                    <button className="apply-btn" onClick={configureTradingAPI}>
                      ✅ Connecter à Alpaca
                    </button>
                    <button className="cancel-btn" onClick={() => setShowTradingSettings(false)}>
                      ❌ Annuler
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Portefeuille */}
            {tradingStatus.api_connected && (
              <div className="portfolio-section">
                <h3>📊 Portefeuille</h3>
                <div className="portfolio-grid">
                  <div className="portfolio-card">
                    <h4>Pouvoir d'achat</h4>
                    <span className="amount">{formatCurrency(portfolio.buying_power, tradingConfig.currency)}</span>
                  </div>
                  
                  <div className="portfolio-card">
                    <h4>Valeur du portefeuille</h4>
                    <span className="amount">{formatCurrency(portfolio.portfolio_value, tradingConfig.currency)}</span>
                  </div>
                  
                  <div className="portfolio-card">
                    <h4>Montant initial</h4>
                    <span className="amount">{formatCurrency(getInitialAmountFromStorage(), tradingConfig.currency)}</span>
                  </div>
                  
                  <div className="portfolio-card">
                    <h4>Solde actualisé</h4>
                    <span className="amount">{formatCurrency(portfolio.updated_balance, tradingConfig.currency)}</span>
                  </div>
                  
                  <div className="portfolio-card">
                    <h4>P&L Total</h4>
                    <span className={`amount ${portfolio.total_pl >= 0 ? 'positive' : 'negative'}`}>
                      {formatCurrency(portfolio.portfolio_value - getInitialAmountFromStorage(), tradingConfig.currency)}
                    </span>
                  </div>
                </div>

                {/* Positions ouvertes */}
                {portfolio.positions && portfolio.positions.length > 0 && (
                  <div className="positions-section">
                    <h4>📈 Positions ouvertes</h4>
                    <div className="positions-list">
                      {portfolio.positions.map((position, index) => (
                        <div key={index} className="position-card">
                          <div className="position-header">
                            <span className="symbol">{position.symbol}</span>
                            <span className="qty">{position.qty} actions</span>
                          </div>
                          <div className="position-details">
                            <span>Prix moyen: {formatCurrency(position.avg_entry_price, tradingConfig.currency)}</span>
                            <span>Prix actuel: {formatCurrency(position.current_price, tradingConfig.currency)}</span>
                            <span>Valeur: {formatCurrency(position.market_value, tradingConfig.currency)}</span>
                            <span className={`pl ${position.unrealized_pl >= 0 ? 'positive' : 'negative'}`}>
                              P&L: {formatCurrency(position.unrealized_pl, tradingConfig.currency)} ({position.unrealized_plpc.toFixed(2)}%)
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Configuration de trading */}
            {tradingStatus.api_connected && (
              <div className="trading-controls">
                <h3>⚙️ Configuration de Trading</h3>
                
                <div className="config-grid">
                  <div className="setting-group">
                    <label>Take Profit (%) :</label>
                    <input 
                      type="range" 
                      min="0" 
                      max="5" 
                      step="0.1"
                      value={tradingConfig.take_profit_percent} 
                      onChange={(e) => {
                        const newValue = parseFloat(e.target.value);
                        setIsEditingTradingConfig(true);
                        setTradingConfig(prev => ({ ...prev, take_profit_percent: newValue }));
                        
                        // Annuler le timeout précédent
                        if (editingTimeoutRef.current) clearTimeout(editingTimeoutRef.current);
                        
                        // Programmer la sauvegarde automatique et la fin d'édition après 3 secondes
                        editingTimeoutRef.current = setTimeout(() => {
                          const updatedConfig = { ...tradingConfig, take_profit_percent: newValue };
                          autoSaveTradingConfig(updatedConfig);
                          setIsEditingTradingConfig(false);
                        }, 3000);
                      }}
                    />
                    <span>{tradingConfig.take_profit_percent}%</span>
                  </div>

                  <div className="setting-group">
                    <label>Stop Loss (%) :</label>
                    <input 
                      type="range" 
                      min="0" 
                      max="5" 
                      step="0.1"
                      value={tradingConfig.stop_loss_percent} 
                      onChange={(e) => {
                        const newValue = parseFloat(e.target.value);
                        setIsEditingTradingConfig(true);
                        setTradingConfig(prev => ({ ...prev, stop_loss_percent: newValue }));
                        
                        // Annuler le timeout précédent
                        if (editingTimeoutRef.current) clearTimeout(editingTimeoutRef.current);
                        
                        // Programmer la sauvegarde automatique et la fin d'édition après 3 secondes
                        editingTimeoutRef.current = setTimeout(() => {
                          const updatedConfig = { ...tradingConfig, stop_loss_percent: newValue };
                          autoSaveTradingConfig(updatedConfig);
                          setIsEditingTradingConfig(false);
                        }, 3000);
                      }}
                    />
                    <span>{tradingConfig.stop_loss_percent}%</span>
                  </div>

                  <div className="setting-group">
                    <label>% Portefeuille à investir :</label>
                    <input 
                      type="range" 
                      min="1" 
                      max="100" 
                      step="1"
                      value={tradingConfig.investment_percent} 
                      onChange={(e) => {
                        const newValue = parseFloat(e.target.value);
                        setIsEditingTradingConfig(true);
                        setTradingConfig(prev => ({ ...prev, investment_percent: newValue }));
                        
                        // Annuler le timeout précédent
                        if (editingTimeoutRef.current) clearTimeout(editingTimeoutRef.current);
                        
                        // Programmer la sauvegarde automatique et la fin d'édition après 3 secondes
                        editingTimeoutRef.current = setTimeout(() => {
                          const updatedConfig = { ...tradingConfig, investment_percent: newValue };
                          autoSaveTradingConfig(updatedConfig);
                          setIsEditingTradingConfig(false);
                        }, 3000);
                      }}
                    />
                    <span>{tradingConfig.investment_percent}%</span>
                  </div>

                  <div className="setting-group" style={{display: 'none'}}>
                    <label>Heure d'achat auto :</label>
                    <input 
                      type="time" 
                      value={tradingConfig.auto_buy_time} 
                      onChange={(e) => {
                        setIsEditingTradingConfig(true);
                        setTradingConfig(prev => ({ ...prev, auto_buy_time: e.target.value }));
                        if (editingTimeoutRef.current) clearTimeout(editingTimeoutRef.current);
                        editingTimeoutRef.current = setTimeout(() => setIsEditingTradingConfig(false), 2000);
                       }}
                     />
                </div>

                  <div className="setting-group">
                    <label>Heure de vente auto :</label>
                    <input 
                      type="time" 
                      value={tradingConfig.auto_sell_time} 
                      onChange={(e) => {
                        setIsEditingTradingConfig(true);
                        setTradingConfig(prev => ({ ...prev, auto_sell_time: e.target.value }));
                        if (editingTimeoutRef.current) clearTimeout(editingTimeoutRef.current);
                        editingTimeoutRef.current = setTimeout(() => setIsEditingTradingConfig(false), 2000);
                      }}
                    />
                  </div>
                </div>

                <button className="apply-btn" onClick={updateTradingConfig}>
                  ✅ Mettre à jour la configuration
                </button>
              </div>
            )}

            {/* Trading manuel */}
            {tradingStatus.api_connected && (
              <div className="manual-trading">
                <h3>🔧 Trading Manuel</h3>
                
                <div className="trading-form">
                  <div className="form-group">
                    <label>Symbole :</label>
                    <div className="symbol-input-container">
                      <input 
                        type="text" 
                        value={tradingSymbol} 
                        onChange={(e) => {
                          setTradingSymbol(e.target.value.toUpperCase());
                          setSymbolAutoUpdated(false); // Réinitialiser l'indicateur si l'utilisateur modifie manuellement
                        }}
                        placeholder="AAPL"
                        className={symbolAutoUpdated ? 'auto-updated' : ''}
                      />
                      {symbolAutoUpdated && (
                        <span className="auto-update-indicator">
                          ✨ Mis à jour automatiquement
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="form-group">
                    <label>Quantité :</label>
                    <input 
                      type="number" 
                      value={tradingQty} 
                      onChange={(e) => setTradingQty(parseInt(e.target.value))}
                      min="1"
                    />
                  </div>

                  <div className="trading-buttons">
                    <button 
                      className="buy-btn"
                      onClick={() => placeManualOrder('buy')}
                    >
                      📈 Acheter
                    </button>
                    
                    <button 
                      className="sell-btn"
                      onClick={() => placeManualOrder('sell')}
                    >
                      📉 Vendre
                    </button>

                    {!tradingStatus.auto_trading_enabled ? (
                      <>
                        <div className="recommendation-option">
                          <label>
                            <input
                              type="checkbox"
                              checked={useRecommendation}
                              onChange={(e) => setUseRecommendation(e.target.checked)}
                            />
                            Utiliser la recommandation finale
                          </label>
                        </div>
                        <button 
                          className="auto-btn"
                          onClick={startAutoTrading}
                        >
                          ⚡ Mode Auto
                        </button>
                      </>
                    ) : (
                      <button 
                        className="stop-auto-btn"
                        onClick={stopAutoTrading}
                      >
                        ⏹️ Arrêter Auto
                      </button>
                    )}
                  </div>


                </div>
              </div>
            )}
          </>
        )}
      </div>
      {/* ===== FIN NOUVELLE SECTION TRADING ALPACA ===== */}

      {/* Section Contrôles */}
      <div className="controls-section">
        <h2>🎮 Contrôles</h2>
        
        {/* Boutons de configuration */}
        <div className="control-buttons">
          <button 
            className="config-btn"
            onClick={openSettings}
          >
            ⚙️ Configuration Mode & Timers
          </button>
          
          <button 
            className={`config-btn ${autoThresholdConfig.enabled ? 'enabled' : ''}`}
            onClick={openAutoThresholdSettings}
          >
            🎯 Configuration Mode Analyse Automatique Seuil
          </button>
          
          <button 
            className={`refresh-btn ${refreshing ? 'refreshing' : ''}`}
            onClick={refreshCache}
            disabled={refreshing}
          >
            {refreshing ? '🔄 Rafraîchissement...' : '🧹 Rafraîchir Cache'}
          </button>
        </div>

        {/* ===== NOUVEAU PANNEAU CONFIGURATION MODE ANALYSE AUTOMATIQUE SEUIL 70% ===== */}
        {showAutoThresholdSettings && (
          <div className="settings-panel auto-threshold-panel">
            <h3>🎯 Configuration Mode Analyse Automatique Seuil</h3>
            
            <div className="setting-group">
              <label>
                <input 
                  type="checkbox" 
                  checked={autoThresholdConfig.enabled}
                  onChange={(e) => setAutoThresholdConfig(prev => ({ ...prev, enabled: e.target.checked }))}
                />
                Activer le mode analyse automatique seuil
              </label>
            </div>
            
            {autoThresholdConfig.enabled && (
              <>
                <div className="setting-group">
                  <label>Score cible à atteindre (%) :</label>
                  <input 
                    type="range" 
                    min="60" 
                    max="100" 
                    step="1"
                    value={autoThresholdConfig.target_score} 
                    onChange={(e) => setAutoThresholdConfig(prev => ({ ...prev, target_score: parseFloat(e.target.value) }))}
                  />
                  <span>{autoThresholdConfig.target_score}%</span>
                  <small>Score minimum requis pour envoyer la recommandation au trading</small>
                </div>

                <div className="setting-group">
                  <label>Nombre maximum de cycles :</label>
                  <input 
                    type="range" 
                    min="1" 
                    max="40" 
                    step="1"
                    value={autoThresholdConfig.max_cycles} 
                    onChange={(e) => setAutoThresholdConfig(prev => ({ ...prev, max_cycles: parseInt(e.target.value) }))}
                  />
                  <span>{autoThresholdConfig.max_cycles} cycles</span>
                  <small>Nombre maximum d'analyses à effectuer</small>
                </div>

                <div className="setting-group">
                  <label>Délai entre analyses (minutes) :</label>
                  <input 
                    type="range" 
                    min="1" 
                    max="60" 
                    step="1"
                    value={autoThresholdConfig.delay_between_cycles} 
                    onChange={(e) => setAutoThresholdConfig(prev => ({ ...prev, delay_between_cycles: parseInt(e.target.value) }))}
                  />
                  <span>{autoThresholdConfig.delay_between_cycles} min</span>
                  <small>Temps d'attente entre chaque cycle d'analyse</small>
                </div>

                {/* Nouvelle section pour l'horloge */}
                <div className="setting-group">
                  <label>
                    <input 
                      type="checkbox" 
                      checked={autoThresholdConfig.schedule_enabled}
                      onChange={(e) => setAutoThresholdConfig(prev => ({ ...prev, schedule_enabled: e.target.checked }))}
                    />
                    Activer programmation automatique
                  </label>
                </div>

                {autoThresholdConfig.schedule_enabled && (
                  <div className="setting-group">
                    <label>Heure de démarrage automatique :</label>
                    <input 
                      type="time" 
                      value={autoThresholdConfig.schedule_time} 
                      onChange={(e) => setAutoThresholdConfig(prev => ({ ...prev, schedule_time: e.target.value }))}
                      className="time-input"
                      step="60"
                      pattern="[0-9]{2}:[0-9]{2}"
                      title="Format 24h (HH:MM)"
                    />
                    <small>Heure à laquelle le mode seuil démarrera automatiquement (format 24h)</small>
                  </div>
                )}

                {/* Statut du mode analyse automatique seuil */}
                {autoThresholdConfig.running && (
                  <div className="auto-threshold-status">
                    <h4>📊 Statut Analyse Automatique Seuil</h4>
                    <div className="status-info">
                      <span>🔄 Cycle actuel: {autoThresholdConfig.current_cycle}/{autoThresholdConfig.max_cycles}</span>
                      <span>📊 Dernier score: {autoThresholdConfig.last_score}%</span>
                      <span>🎯 Score cible: {autoThresholdConfig.target_score}%</span>
                      {autoThresholdConfig.start_time && (
                        <span>⏰ Démarré: {new Date(autoThresholdConfig.start_time).toLocaleString('fr-FR')}</span>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}
            
            <div className="setting-buttons">
              <button className="apply-btn" onClick={configureAutoThreshold}>
                ✅ Appliquer Configuration
              </button>
              
              {autoThresholdConfig.enabled && !autoThresholdConfig.running && (
                <button className="start-btn" onClick={startAutoThreshold}>
                  🚀 Démarrer Mode Seuil
                </button>
              )}
              
              {autoThresholdConfig.running && (
                <button className="stop-btn" onClick={stopAutoThreshold}>
                  ⏹️ Arrêter Mode Seuil
                </button>
              )}
              
              <button className="cancel-btn" onClick={closeAutoThresholdSettings}>
                ❌ Fermer
              </button>
            </div>
          </div>
        )}

        {/* Informations du cache */}
        {cacheInfo && (
          <div className="cache-info">
            <h4>📊 État du Cache</h4>
            <div className="cache-status">
              <span className={`cache-indicator ${cacheInfo.potentially_stale ? 'stale' : 'fresh'}`}>
                {cacheInfo.potentially_stale ? '⚠️ Données potentiellement figées' : '✅ Données fraîches'}
              </span>
              <span>Top 10: {cacheInfo.top_10_count} | Opportunités: {cacheInfo.opportunities_count}</span>
              {cacheInfo.last_update && (
                <span>Dernière MAJ: {new Date(cacheInfo.last_update).toLocaleString('fr-FR')}</span>
              )}
            </div>
          </div>
        )}

        {/* Panneau de configuration */}
        {showSettings && (
          <div className="settings-panel">
            <h3>Configuration des Modes et Timers</h3>
            
            <div className="setting-group">
              <label>Mode d'opération :</label>
              <select 
                value={mode} 
                onChange={(e) => setMode(e.target.value)}
              >
                <option value="manual">🔧 Manuel</option>
                <option value="auto">⚡ Automatique</option>
              </select>
            </div>
            
            {mode === 'auto' && (
              <>
                <div className="setting-group">
                  <label>🕘 Heure analyse 500 tickers :</label>
                  <div className="schedule-controls">
                    <input 
                      type="checkbox" 
                      checked={schedule500Enabled}
                      onChange={(e) => setSchedule500Enabled(e.target.checked)}
                    />
                    <input 
                      type="time" 
                      value={schedule500Time} 
                      onChange={(e) => setSchedule500Time(e.target.value)}
                      disabled={!schedule500Enabled}
                    />
                  </div>
                  <small>Heure de démarrage automatique de l'analyse des 500 tickers (format 24h)</small>
                </div>
                
                <div className="setting-group">
                  <label>🕘 Heure analyse 10 finalistes :</label>
                  <div className="schedule-controls">
                    <input 
                      type="checkbox" 
                      checked={schedule10Enabled}
                      onChange={(e) => setSchedule10Enabled(e.target.checked)}
                    />
                    <input 
                      type="time" 
                      value={schedule10Time} 
                      onChange={(e) => setSchedule10Time(e.target.value)}
                      disabled={!schedule10Enabled}
                    />
                  </div>
                  <small>Heure de démarrage automatique de l'analyse des 10 finalistes (format 24h)</small>
                </div>
              </>
            )}
            
            <div className="setting-buttons">
              <button className="apply-btn" onClick={configureMode}>
                ✅ Appliquer Configuration
              </button>
              <button className="cancel-btn" onClick={closeSettings}>
                ❌ Annuler
              </button>
            </div>
          </div>
        )}

        {/* Boutons d'action */}
        <div className="action-buttons">
          <button 
            className="start-btn-500"
            onClick={startAnalysis500}
            disabled={loading || systemStatus.running}
          >
            {loading ? '⏳ Démarrage...' : '🚀 Analyser 500 Tickers'}
          </button>
          
          <button 
            className="start-btn-10"
            onClick={startAnalysis10}
            disabled={loading || systemStatus.running || !systemStatus.top_10_candidates?.length}
          >
            {loading ? '⏳ Démarrage...' : '⚡ Analyser 10 Finalistes'}
          </button>
          
          <button 
            className="stop-btn"
            onClick={stopAnalysis}
            disabled={!systemStatus.running}
          >
            🛑 Arrêter Analyse
          </button>
        </div>
      </div>

      {/* Section Résultats */}
      <div className="results-section">
        <h2>📈 Résultats</h2>
        
        {/* Boutons d'affichage des résultats */}
        <div className="result-buttons">
          <button 
            className="result-btn"
            onClick={() => {
              setShowTop10(!showTop10);
              if (!showTop10) fetchTop10();
            }}
            disabled={false}
          >
            🏆 Afficher Top 10 ({systemStatus.top_10_candidates?.length || 0})
          </button>
          
          <button 
            className="result-btn"
            onClick={() => {
              setShowRecommendation(!showRecommendation);
              if (!showRecommendation) fetchFinalRecommendation();
            }}
            disabled={systemStatus.phase !== 'completed_10'}
          >
            🎯 Recommandation Finale
          </button>
        </div>

        {/* Affichage du Top 10 */}
        {showTop10 && (
          <div className="top10-section">
            <h3>🏆 Top 10 des Candidats</h3>
            {top10Candidates.length > 0 ? (
              <div className="candidates-grid">
                {top10Candidates.map((candidate, index) => (
                  <div key={index} className="candidate-card">
                    <div className="candidate-header">
                      <h4>{candidate.symbol}</h4>
                      <span 
                        className="score-badge"
                        style={{ backgroundColor: getRecommendationColor(candidate.recommendation) }}
                      >
                        {candidate.recommendation}
                      </span>
                    </div>
                    <div className="candidate-details">
                      <p><strong>Prix:</strong> ${candidate.price}</p>
                      <p><strong>Volume:</strong> {candidate.volume?.toLocaleString()}</p>
                      <p><strong>Variation:</strong> {candidate.change}%</p>
                      <p><strong>Score:</strong> {candidate.score}%</p>
                      <p><strong>RSI:</strong> {candidate.rsi}</p>
                      <p><strong>Source:</strong> {candidate.source}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p>Aucun candidat disponible pour le moment.</p>
            )}
          </div>
        )}

        {/* Affichage de la recommandation finale */}
        {showRecommendation && finalRecommendation && (
          <div className="recommendation-section">
            <h3>🎯 Recommandation Finale</h3>
            <div className="recommendation-card">
              <div className="recommendation-header">
                <h4>{finalRecommendation.symbol}</h4>
                <span 
                  className="recommendation-badge"
                  style={{ backgroundColor: getRecommendationColor(finalRecommendation.recommendation) }}
                >
                  {finalRecommendation.recommendation}
                </span>
              </div>
              
              {/* Tableau des détails */}
              <div className="recommendation-table">
                <table>
                  <tbody>
                    <tr>
                      <td><strong>Prix actuel</strong></td>
                      <td>${finalRecommendation.price}</td>
                      <td><strong>Variation</strong></td>
                      <td>{finalRecommendation.change}%</td>
                    </tr>
                    <tr>
                      <td><strong>Score technique</strong></td>
                      <td>{finalRecommendation.score}%</td>
                      <td><strong>Score final</strong></td>
                      <td>{finalRecommendation.score}%</td>

                    </tr>
                    <tr>
                      <td><strong>RSI</strong></td>
                      <td>{finalRecommendation.rsi}</td>
                      <td><strong>MACD</strong></td>
                      <td>{finalRecommendation.macd}</td>
                    </tr>
                    <tr>
                      <td><strong>Volume</strong></td>
                      <td>{finalRecommendation.volume?.toLocaleString()}</td>
                      <td><strong>Source</strong></td>
                      <td>{finalRecommendation.source}</td>
                    </tr>
                    <tr>
                      <td><strong>Timestamp</strong></td>
                      <td colSpan="3">{new Date(finalRecommendation.timestamp).toLocaleString('fr-FR')}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ===== SECTION LOGS ENVOI AUTOMATIQUE (SIMPLIFIÉ) - MASQUÉE =====
        {autoSendLogs.length > 0 && (
          <div className="auto-send-logs-section">
            <h3>📋 Historique Envoi Automatique vers Trading</h3>
            <div className="logs-container">
              {autoSendLogs.map((log, index) => (
                <div key={index} className={`log-entry ${log.success ? 'success' : 'error'}`}>
                  <div className="log-header">
                    <span className="log-symbol">{log.symbol}</span>
                    <span className="log-timestamp">{new Date(log.timestamp).toLocaleTimeString('fr-FR')}</span>
                    <span className={`log-status ${log.success ? 'success' : 'error'}`}>
                      {log.success ? '✅' : '❌'}
                    </span>
                  </div>
                  <div className="log-details">
                    <span>Score: {log.score}% | {log.recommendation}</span>
                    <span className="log-message">{log.message}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        */}
      </div>

      {/* Footer */}
      <footer className="App-footer">
        <p>© 2024 S&P 500 DayTradingBot System</p>
      </footer>
    </div>
  );
}

export default App;




























































