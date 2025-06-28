"""
Module de trading Alpaca CORRIGÉ - Version avec Achat Immédiat Robuste
CORRECTIONS PRINCIPALES:
1. Unifie la logique de surveillance des positions pour tous les modes
2. Assure que stop loss, take profit et vente programmée fonctionnent correctement
3. Corrige la gestion des threads de surveillance
4. SUPPRIME l'heure d'achat - ACHAT IMMÉDIAT dès réception de recommandation
5. Améliore la robustesse du système
6. NOUVEAU: Attente de recommandation robuste avec timeout et gestion d'erreurs
7. NOUVEAU: Fallback sur symbole par défaut si pas de recommandation
8. NOUVEAU: Logs détaillés pour debugging et surveillance
9. CORRECTION DOUBLE ORDRE: Désactive le thread auto trading pour éviter duplication
"""

import alpaca_trade_api as tradeapi
from datetime import datetime, timedelta, time
import pytz
import threading
import time as time_module
import json
import os
from typing import Dict, List, Optional, Tuple
import logging
import schedule

# ===== CORRECTION DOUBLE ORDRE: VARIABLE DE CONTRÔLE =====
# Désactive le thread auto trading pour éviter les doubles ordres
DISABLE_AUTO_TRADING_THREAD = True
print(f"🔧 Thread auto trading: {'DÉSACTIVÉ' if DISABLE_AUTO_TRADING_THREAD else 'ACTIVÉ'}")

# ===== SYSTÈME DE VERROUILLAGE GLOBAL =====
# Empêche les achats simultanés
import threading as thread_module
_auto_buy_lock = thread_module.Lock()
_auto_buy_in_progress = False

def is_auto_buy_in_progress():
    """Vérifie si un achat automatique est en cours"""
    global _auto_buy_in_progress
    return _auto_buy_in_progress

def set_auto_buy_in_progress(status: bool):
    """Définit l'état d'achat automatique en cours"""
    global _auto_buy_in_progress
    _auto_buy_in_progress = status

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AlpacaTradingAgent:
    def __init__(self):
        self.api = None
        self.config = {
            'paper_api_key': '',
            'paper_secret_key': '',
            'live_api_key': '',
            'live_secret_key': '',
            'mode': 'paper',  # 'paper' ou 'live'
            'initial_amount': 10000.0,
            'currency': 'USD',
            'auto_trading_enabled': False,
            'take_profit_percent': 2.0,  # 0-5% - Valeur par défaut réaliste de 2%
            'stop_loss_percent': 2.0,    # 0-5% - Valeur par défaut réaliste de 2%

            'auto_sell_time': '15:50',   # Heure de vente automatique
            'investment_percent': 10.0,  # Pourcentage du portefeuille à investir
        }
        self.portfolio = {
            'buying_power': 0.0,
            'portfolio_value': 0.0,
            'positions': [],
            'day_trade_count': 0,
            'initial_amount': 10000.0,
            'updated_balance': 0.0,
            'total_pl': 0.0
        }
        self.active_orders = {}
        self.auto_trading_thread = None
        self.stop_auto_trading = False
        self.market_hours = {
            'NYSE': {'open': time(9, 30), 'close': time(16, 0), 'timezone': 'US/Eastern'},
            'NASDAQ': {'open': time(9, 30), 'close': time(16, 0), 'timezone': 'US/Eastern'}
        }
        
        # CORRECTION: Dictionnaire pour suivre les threads de surveillance actifs
        self.monitoring_threads = {}
        
        # Définir le chemin du fichier de configuration
        self.config_file = os.path.join(os.path.dirname(__file__), 'config.json')
        
        # Charger la configuration au démarrage
        self._load_config()
    
    def _load_config(self):
        """Charge la configuration depuis un fichier JSON."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                # Mettre à jour seulement les clés existantes pour éviter d'ajouter des champs inconnus
                for key, value in loaded_config.items():
                    if key in self.config:
                        self.config[key] = value
                logger.info(f"Configuration chargée depuis {self.config_file}")
                
                # Si des clés API sont présentes, initialiser automatiquement l'API
                if (self.config['paper_api_key'] and self.config['paper_secret_key']) or \
                   (self.config['live_api_key'] and self.config['live_secret_key']):
                    logger.info("Clés API détectées, initialisation automatique...")
                    self._initialize_api()
                    
            except json.JSONDecodeError as e:
                logger.error(f"Erreur de décodage JSON dans {self.config_file}: {e}. Utilisation de la configuration par défaut.")
            except Exception as e:
                logger.error(f"Erreur lors du chargement de la configuration depuis {self.config_file}: {e}. Utilisation de la configuration par défaut.")
        else:
            logger.info(f"Fichier de configuration {self.config_file} non trouvé. Création avec la configuration par défaut.")
            self._save_config()  # Sauvegarder la configuration par défaut si le fichier n'existe pas

    def _save_config(self):
        """Sauvegarde la configuration actuelle dans un fichier JSON."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Configuration sauvegardée dans {self.config_file}")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de la configuration dans {self.config_file}: {e}")
        
    def configure_api_keys(self, paper_key: str, paper_secret: str, 
                          live_key: str = '', live_secret: str = '', 
                          mode: str = 'paper') -> Dict:
        """Configure les clés API Alpaca et sauvegarde la configuration"""
        try:
            self.config['paper_api_key'] = paper_key
            self.config['paper_secret_key'] = paper_secret
            self.config['live_api_key'] = live_key
            self.config['live_secret_key'] = live_secret
            self.config['mode'] = mode
            
            # Sauvegarder la configuration après mise à jour
            self._save_config()
            
            # Initialiser la connexion API
            return self._initialize_api()
            
        except Exception as e:
            logger.error(f"Erreur configuration clés API: {e}")
            return {'success': False, 'message': str(e)}
    
    def _initialize_api(self) -> Dict:
        """Initialise la connexion API Alpaca"""
        try:
            if self.config['mode'] == 'paper':
                api_key = self.config['paper_api_key']
                secret_key = self.config['paper_secret_key']
                base_url = 'https://paper-api.alpaca.markets'
            else:
                api_key = self.config['live_api_key']
                secret_key = self.config['live_secret_key']
                base_url = 'https://api.alpaca.markets'
            
            if not api_key or not secret_key:
                return {'success': False, 'message': 'Clés API manquantes'}
            
            self.api = tradeapi.REST(
                api_key,
                secret_key,
                base_url,
                api_version='v2'
            )
            
            # Test de connexion
            account = self.api.get_account()
            logger.info(f"Connexion Alpaca réussie - Mode: {self.config['mode']}")
            
            # Mise à jour du portefeuille
            self._update_portfolio()
            
            return {
                'success': True, 
                'message': f'Connexion réussie en mode {self.config["mode"]}',
                'account_status': account.status
            }
            
        except Exception as e:
            logger.error(f"Erreur initialisation API: {e}")
            return {'success': False, 'message': str(e)}
    
    def _update_portfolio(self) -> None:
        """Met à jour les informations du portefeuille"""
        try:
            if not self.api:
                # Si pas d'API connectée, utiliser les valeurs par défaut
                self.portfolio.update({
                    'buying_power': self.config['initial_amount'],
                    'portfolio_value': self.config['initial_amount'],
                    'updated_balance': self.config['initial_amount'],
                    'total_pl': 0.0
                })
                return
            
            account = self.api.get_account()
            positions = self.api.list_positions()
            
            # Gestion sécurisée des attributs qui peuvent ne pas exister
            day_trade_count = 0
            try:
                day_trade_count = int(account.day_trade_count)
            except AttributeError:
                day_trade_count = 0
            
            unrealized_pl = 0.0
            realized_pl = 0.0
            try:
                unrealized_pl = float(account.unrealized_pl or 0)
                realized_pl = float(account.realized_pl or 0)
            except AttributeError:
                unrealized_pl = 0.0
                realized_pl = 0.0
            
            self.portfolio.update({
                'buying_power': float(account.buying_power),
                'portfolio_value': float(account.portfolio_value),
                'day_trade_count': day_trade_count,
                'total_pl': unrealized_pl + realized_pl
            })
            
            # Calcul du solde actualisé basé sur la valeur réelle du portefeuille
            self.portfolio['updated_balance'] = float(account.portfolio_value)
            
            # Mise à jour des positions avec données en temps réel
            self.portfolio['positions'] = []
            for position in positions:
                # Récupérer le prix actuel en temps réel
                try:
                    latest_trade = self.api.get_latest_trade(position.symbol)
                    current_price = float(latest_trade.price)
                except:
                    # Fallback sur le prix de la position si l'API échoue
                    current_price = float(position.current_price)
                
                # Calculer la valeur de marché avec le prix actuel
                qty = float(position.qty)
                market_value = qty * current_price
                avg_entry_price = float(position.avg_entry_price)
                
                # Calculer le P&L avec précision
                unrealized_pl = market_value - (qty * avg_entry_price)
                unrealized_plpc = (unrealized_pl / (qty * avg_entry_price)) * 100 if qty * avg_entry_price != 0 else 0
                
                self.portfolio['positions'].append({
                    'symbol': position.symbol,
                    'qty': qty,
                    'market_value': market_value,
                    'unrealized_pl': unrealized_pl,
                    'unrealized_plpc': unrealized_plpc,
                    'avg_entry_price': avg_entry_price,
                    'current_price': current_price
                })
            
            logger.info(f"Portefeuille mis à jour - Valeur: ${self.portfolio['portfolio_value']:.2f}, Positions: {len(self.portfolio['positions'])}")
            
        except Exception as e:
            logger.error(f"Erreur mise à jour portefeuille: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def get_portfolio_status(self) -> Dict:
        """Retourne le statut actuel du portefeuille"""
        self._update_portfolio()
        return {
            'success': True,
            'portfolio': self.portfolio,
            'config': {
                'mode': self.config['mode'],
                'auto_trading_enabled': self.config['auto_trading_enabled'],
                'take_profit_percent': self.config['take_profit_percent'],
                'stop_loss_percent': self.config['stop_loss_percent'],
                'investment_percent': self.config['investment_percent']
            }
        }
    
    def is_market_open(self, symbol: str = 'AAPL') -> bool:
        """Retourne toujours True pour permettre les tests 24h/24"""
        return True
    
    def place_manual_order(self, symbol: str, qty: int, side: str, 
                          order_type: str = 'market') -> Dict:
        """Place un ordre manuel"""
        try:
            if not self.api:
                return {'success': False, 'message': 'API non initialisée - Veuillez configurer vos clés Alpaca'}
            
            # Validation des paramètres
            if side not in ['buy', 'sell']:
                return {'success': False, 'message': 'Side invalide (buy/sell)'}
            
            if qty <= 0:
                return {'success': False, 'message': 'Quantité invalide'}
            
            # Placer l'ordre
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type=order_type,
                time_in_force='day'
            )
            
            logger.info(f"Ordre placé: {side} {qty} {symbol}")
            
            # Mise à jour du portefeuille
            self._update_portfolio()
            
            return {
                'success': True,
                'message': f'Ordre {side} placé avec succès',
                'order_id': order.id,
                'symbol': symbol,
                'qty': qty,
                'side': side
            }
            
        except Exception as e:
            logger.error(f"Erreur placement ordre: {e}")
            return {'success': False, 'message': str(e)}
    
    def calculate_investment_amount(self, symbol: str) -> Tuple[int, float]:
        """Calcule le montant et la quantité à investir"""
        try:
            if not self.api:
                return 0, 0.0
                
            # CORRECTION: Utiliser portfolio_value au lieu de buying_power
            # pour éviter les problèmes de marge qui peuvent doubler/tripler le montant
            portfolio_value = self.portfolio['portfolio_value']
            investment_amount = portfolio_value * (self.config['investment_percent'] / 100)
            
            # Log pour debugging
            logger.info(f"💰 CALCUL INVESTISSEMENT:")
            logger.info(f"   - Valeur portefeuille: ${portfolio_value:.2f}")
            logger.info(f"   - Pourcentage configuré: {self.config['investment_percent']}%")
            logger.info(f"   - Montant à investir: ${investment_amount:.2f}")
            
            # Obtenir le prix actuel
            latest_trade = self.api.get_latest_trade(symbol)
            current_price = float(latest_trade.price)
            
            # Calculer la quantité (arrondie à l'entier inférieur)
            qty = int(investment_amount / current_price)
            actual_amount = qty * current_price
            
            logger.info(f"   - Prix actuel {symbol}: ${current_price:.2f}")
            logger.info(f"   - Quantité calculée: {qty}")
            logger.info(f"   - Montant réel: ${actual_amount:.2f}")
            
            return qty, actual_amount
            
        except Exception as e:
            logger.error(f"Erreur calcul investissement: {e}")
            return 0, 0.0

    # ===== CORRECTION PRINCIPALE: NOUVELLE FONCTION POUR ACHAT IMMÉDIAT EN MODE AUTO =====

    def execute_immediate_auto_buy(self, symbol: str) -> Dict:
        """
        CORRECTION: Exécute un achat immédiat en mode auto trading avec surveillance unifiée + VERROUILLAGE
        """
        global _auto_buy_lock, _auto_buy_in_progress
        
        # PROTECTION DOUBLE ORDRE: Vérifier si un achat est déjà en cours
        with _auto_buy_lock:
            if _auto_buy_in_progress:
                logger.warning(f"🔒 PROTECTION DOUBLE ORDRE: Achat déjà en cours pour un autre symbole")
                return {'success': False, 'message': 'Achat automatique déjà en cours - verrouillage actif'}
            
            # Marquer qu'un achat est en cours
            set_auto_buy_in_progress(True)
            logger.info(f"🔒 VERROUILLAGE ACHAT ACTIVÉ pour {symbol}")
        
        try:
            if not self.api:
                return {'success': False, 'message': 'API non initialisée - Veuillez configurer vos clés Alpaca'}
            
            if not self.config['auto_trading_enabled']:
                return {'success': False, 'message': 'Mode auto trading non activé'}
            
            # PROTECTION: Vérifier s'il y a déjà une position ouverte pour ce symbole
            existing_positions = [pos for pos in self.portfolio['positions'] if pos['symbol'] == symbol]
            if existing_positions:
                logger.warning(f"⚠️ PROTECTION DOUBLE ACHAT: Position déjà ouverte pour {symbol}")
                return {'success': False, 'message': f'Position déjà ouverte pour {symbol} - achat bloqué'}
            
            # Vérifier si le marché est ouvert
            if not self._is_market_open():
                logger.warning("Marché fermé - achat automatique annulé")
                return {'success': False, 'message': 'Marché fermé - achat automatique annulé'}
            
            # Mettre à jour le portefeuille avant calcul
            self._update_portfolio()
            
            # Calculer le montant d'investissement
            qty, amount = self.calculate_investment_amount(symbol)
            if qty <= 0:
                logger.warning("Montant d'investissement insuffisant pour l'achat automatique")
                return {'success': False, 'message': 'Montant d\'investissement insuffisant'}
            
            # Log de sécurité avant achat
            logger.info(f"🛡️ SÉCURITÉ ACHAT AUTO:")
            logger.info(f"   - Symbole: {symbol}")
            logger.info(f"   - Quantité: {qty}")
            logger.info(f"   - Montant: ${amount:.2f}")
            logger.info(f"   - Positions existantes: {len(existing_positions)}")
            
            # Exécuter l'achat immédiatement
            buy_result = self.place_manual_order(symbol, qty, 'buy')
            if not buy_result['success']:
                logger.error(f"Échec achat automatique immédiat: {buy_result['message']}")
                return buy_result
            
            entry_price = amount / qty
            logger.info(f"💰 ACHAT AUTOMATIQUE IMMÉDIAT EXÉCUTÉ: {qty} {symbol} à ${entry_price:.2f}")
            
            # CORRECTION: Utiliser la surveillance unifiée
            self._start_unified_position_monitoring(symbol, qty, entry_price)
            
            return {
                'success': True,
                'message': f'Achat automatique immédiat exécuté: {qty} {symbol} à ${entry_price:.2f}',
                'symbol': symbol,
                'qty': qty,
                'entry_price': entry_price,
                'amount': amount
            }
            
        except Exception as e:
            logger.error(f"Erreur achat automatique immédiat: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            # TOUJOURS libérer le verrouillage
            with _auto_buy_lock:
                set_auto_buy_in_progress(False)
                logger.info(f"🔓 VERROUILLAGE ACHAT LIBÉRÉ pour {symbol}")
    
    def start_auto_trading(self, symbol: str) -> Dict:
        """Démarre le trading automatique"""
        try:
            if not self.api:
                return {'success': False, 'message': 'API non initialisée - Veuillez configurer vos clés Alpaca'}
            
            if self.config['auto_trading_enabled']:
                return {'success': False, 'message': 'Trading automatique déjà actif'}
            
            self.config['auto_trading_enabled'] = True
            self.stop_auto_trading = False
            
            # Sauvegarder la configuration pour persister l'état
            self._save_config()
            
            # CORRECTION: Utiliser la méthode existante au lieu de _auto_trading_loop manquante
            self.auto_trading_thread = threading.Thread(
                target=self._auto_trading_with_immediate_buy,
                args=(symbol,)
            )
            self.auto_trading_thread.daemon = True
            self.auto_trading_thread.start()
            
            logger.info(f"Trading automatique démarré pour {symbol}")
            
            return {
                'success': True,
                'message': f'Trading automatique démarré pour {symbol}',
                'symbol': symbol
            }
            
        except Exception as e:
            logger.error(f"Erreur démarrage trading auto: {e}")
            return {'success': False, 'message': str(e)}
    
    def stop_auto_trading_mode(self) -> Dict:
        """Arrête le trading automatique"""
        try:
            self.config['auto_trading_enabled'] = False
            self.stop_auto_trading = True
            
            # CORRECTION: Arrêter tous les threads de surveillance
            for symbol, thread in self.monitoring_threads.items():
                if thread and thread.is_alive():
                    logger.info(f"Arrêt surveillance position {symbol}")
                    # Le thread se terminera automatiquement car stop_auto_trading = True
            
            if self.auto_trading_thread and self.auto_trading_thread.is_alive():
                self.auto_trading_thread.join(timeout=5)
            
            # Sauvegarder la configuration pour persister l'arrêt
            self._save_config()
            
            logger.info("Trading automatique arrêté")
            
            return {'success': True, 'message': 'Trading automatique arrêté'}
            
        except Exception as e:
            logger.error(f"Erreur arrêt trading auto: {e}")
            return {'success': False, 'message': str(e)}
    
    def get_auto_trading_status(self) -> Dict:
        """Retourne le statut du trading automatique"""
        return {
            'success': True,
            'auto_trading_enabled': self.config['auto_trading_enabled'],
            'config': self.config
        }
    
    def update_config(self, config_updates: Dict) -> Dict:
        """Met à jour la configuration de trading et sauvegarde"""
        try:
            # Valider et mettre à jour les paramètres
            if 'take_profit_percent' in config_updates:
                value = float(config_updates['take_profit_percent'])
                if 0.0 <= value <= 5.0:
                    self.config['take_profit_percent'] = value
                else:
                    return {'success': False, 'message': 'Take profit doit être entre 0 et 5%'}
            
            if 'stop_loss_percent' in config_updates:
                value = float(config_updates['stop_loss_percent'])
                if 0.0 <= value <= 5.0:
                    self.config['stop_loss_percent'] = value
                else:
                    return {'success': False, 'message': 'Stop loss doit être entre 0 et 5%'}
            
            if 'investment_percent' in config_updates:
                value = float(config_updates['investment_percent'])
                if 1.0 <= value <= 100.0:
                    self.config['investment_percent'] = value
                else:
                    return {'success': False, 'message': 'Pourcentage d\'investissement doit être entre 1 et 100%'}
            

            
            if 'auto_sell_time' in config_updates:
                # Valider le format HH:MM
                try:
                    datetime.strptime(config_updates['auto_sell_time'], '%H:%M')
                    self.config['auto_sell_time'] = config_updates['auto_sell_time']
                except ValueError:
                    return {'success': False, 'message': 'Format d\'heure invalide (utilisez HH:MM)'}
            
            # Sauvegarder la configuration après mise à jour
            self._save_config()
            
            logger.info("Configuration mise à jour et sauvegardée")
            
            return {'success': True, 'message': 'Configuration mise à jour avec succès'}
            
        except Exception as e:
            logger.error(f"Erreur mise à jour config: {e}")
            return {'success': False, 'message': str(e)}
    
    def _is_market_open(self) -> bool:
        """Vérifie si le marché est ouvert"""
        try:
            # Pour les tests, toujours retourner True
            logger.info("Vérification marché: Mode test - marché considéré comme ouvert")
            return True
            
        except Exception as e:
            logger.error(f"Erreur vérification ouverture marché: {e}")
            return False

    # ===== CORRECTION PRINCIPALE: SURVEILLANCE UNIFIÉE DES POSITIONS =====
    
    def _start_unified_position_monitoring(self, symbol: str, qty: int, entry_price: float) -> None:
        """
        CORRECTION: Démarre la surveillance unifiée d'une position
        Cette fonction assure que la surveillance fonctionne de la même manière pour tous les modes
        """
        try:
            logger.info(f"🔍 DÉMARRAGE SURVEILLANCE UNIFIÉE pour {symbol}")
            logger.info(f"   - Quantité: {qty}")
            logger.info(f"   - Prix d'entrée: ${entry_price:.2f}")
            logger.info(f"   - Take Profit: {self.config['take_profit_percent']}%")
            logger.info(f"   - Stop Loss: {self.config['stop_loss_percent']}%")
            
            # Créer et démarrer le thread de surveillance
            monitor_thread = threading.Thread(
                target=self._unified_monitor_position,
                args=(symbol, qty, entry_price),
                daemon=True
            )
            
            # Enregistrer le thread pour pouvoir l'arrêter plus tard
            self.monitoring_threads[symbol] = monitor_thread
            monitor_thread.start()
            
            logger.info(f"✅ Thread de surveillance démarré pour {symbol}")
            
        except Exception as e:
            logger.error(f"Erreur démarrage surveillance unifiée {symbol}: {e}")
    
    def _unified_monitor_position(self, symbol: str, qty: int, entry_price: float) -> None:
        """
        CORRECTION: Surveillance unifiée d'une position avec stop loss, take profit et vente programmée
        Cette fonction fonctionne de la même manière pour tous les modes
        """
        try:
            logger.info(f"🎯 SURVEILLANCE ACTIVE pour {symbol} - Entry: ${entry_price:.2f}")
            
            # Calculer les prix de déclenchement
            take_profit_price = entry_price * (1 + self.config['take_profit_percent'] / 100)
            stop_loss_price = entry_price * (1 - self.config['stop_loss_percent'] / 100)
            
            logger.info(f"📊 Seuils configurés pour {symbol}:")
            logger.info(f"   - Take Profit: ${take_profit_price:.2f} (+{self.config['take_profit_percent']}%)")
            logger.info(f"   - Stop Loss: ${stop_loss_price:.2f} (-{self.config['stop_loss_percent']}%)")
            
            position_sold = False
            
            while not self.stop_auto_trading and not position_sold and self.config['auto_trading_enabled']:
                try:
                    # Récupérer le prix actuel
                    latest_trade = self.api.get_latest_trade(symbol)
                    current_price = float(latest_trade.price)
                    
                    # Calculer le P&L actuel
                    pl_percent = ((current_price - entry_price) / entry_price) * 100
                    
                    # Afficher le statut toutes les 30 secondes
                    logger.info(f"💹 {symbol}: ${current_price:.2f} | P&L: {pl_percent:+.2f}%")
                    
                    # Vérifier Take Profit
                    if current_price >= take_profit_price:
                        logger.info(f"🎯 TAKE PROFIT DÉCLENCHÉ pour {symbol}: ${current_price:.2f} >= ${take_profit_price:.2f}")
                        self._execute_unified_sell(symbol, qty, "Take Profit", current_price, entry_price)
                        position_sold = True
                        break
                    
                    # Vérifier Stop Loss
                    if current_price <= stop_loss_price:
                        logger.info(f"🛑 STOP LOSS DÉCLENCHÉ pour {symbol}: ${current_price:.2f} <= ${stop_loss_price:.2f}")
                        self._execute_unified_sell(symbol, qty, "Stop Loss", current_price, entry_price)
                        position_sold = True
                        break
                    
                    # Vérifier l'heure de vente automatique
                    if self._should_auto_sell():
                        logger.info(f"⏰ VENTE PROGRAMMÉE DÉCLENCHÉE pour {symbol}")
                        self._execute_unified_sell(symbol, qty, "Vente Programmée", current_price, entry_price)
                        position_sold = True
                        break
                    
                    # Attendre 30 secondes avant la prochaine vérification
                    time_module.sleep(30)
                    
                except Exception as e:
                    logger.error(f"Erreur surveillance {symbol}: {e}")
                    time_module.sleep(10)  # Attendre un peu avant de réessayer
            
            # Nettoyer le thread du dictionnaire
            if symbol in self.monitoring_threads:
                del self.monitoring_threads[symbol]
                logger.info(f"🧹 Thread de surveillance nettoyé pour {symbol}")
            
            if not position_sold:
                logger.info(f"⏹️ SURVEILLANCE ARRÊTÉE pour {symbol} - Trading automatique désactivé")
            
        except Exception as e:
            logger.error(f"Erreur surveillance unifiée {symbol}: {e}")
            # Nettoyer le thread en cas d'erreur
            if symbol in self.monitoring_threads:
                del self.monitoring_threads[symbol]
    
    def _execute_unified_sell(self, symbol: str, qty: int, reason: str, current_price: float, entry_price: float) -> None:
        """
        CORRECTION: Exécute une vente unifiée avec logging détaillé
        """
        try:
            # Calculer le P&L avant la vente
            pl_percent = ((current_price - entry_price) / entry_price) * 100
            pl_amount = (current_price - entry_price) * qty
            
            logger.info(f"💰 EXÉCUTION VENTE {symbol}:")
            logger.info(f"   - Raison: {reason}")
            logger.info(f"   - Quantité: {qty}")
            logger.info(f"   - Prix d'entrée: ${entry_price:.2f}")
            logger.info(f"   - Prix de vente: ${current_price:.2f}")
            logger.info(f"   - P&L: {pl_percent:+.2f}% (${pl_amount:+.2f})")
            
            sell_result = self.place_manual_order(symbol, qty, 'sell')
            if sell_result['success']:
                logger.info(f"✅ VENTE RÉUSSIE: {qty} {symbol} - {reason}")
                logger.info(f"   - Gain/Perte réalisé: {pl_percent:+.2f}% (${pl_amount:+.2f})")
            else:
                logger.error(f"❌ ÉCHEC VENTE {symbol}: {sell_result['message']}")
                
        except Exception as e:
            logger.error(f"Erreur exécution vente unifiée {symbol}: {e}")
    
    def _should_auto_sell(self) -> bool:
        """
        CORRECTION: Vérifie s'il faut vendre automatiquement selon l'heure
        """
        try:
            auto_sell_time = self.config.get('auto_sell_time', '15:50')
            
            # Parser l'heure de vente automatique
            sell_time = datetime.strptime(auto_sell_time, '%H:%M').time()
            
            # Utiliser l'heure locale
            current_time = datetime.now().time()
            
            # Vendre si l'heure de vente automatique est atteinte
            if current_time >= sell_time:
                logger.info(f"⏰ Heure de vente automatique atteinte: {current_time.strftime('%H:%M')} >= {auto_sell_time}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur vérification auto sell: {e}")
            return False

    # ===== CORRECTION: NOUVELLE LOGIQUE POUR ATTENDRE LA RECOMMANDATION =====
    
    def wait_for_recommendation(self, use_recommendation: bool = True, max_wait_time: int = None) -> Optional[str]:
        """
        CORRECTION ROBUSTE: Attend la recommandation finale avec timeout optionnel
        Si max_wait_time est None, attente infinie jusqu'à réception de la recommandation
        """
        try:
            if not use_recommendation:
                logger.info("Option 'utiliser la recommandation finale' désactivée - pas d'attente")
                return None
                
            import requests
            
            if max_wait_time is None:
                logger.info("🔍 ATTENTE RECOMMANDATION FINALE (SANS TIMEOUT - attente infinie)")
            else:
                logger.info(f"🔍 ATTENTE RECOMMANDATION FINALE (timeout: {max_wait_time}s)")
                
            start_time = time_module.time()
            consecutive_errors = 0
            max_consecutive_errors = 10  # Plus tolérant aux erreurs
            
            while True:
                # Vérifier le timeout global SEULEMENT si max_wait_time est défini
                if max_wait_time is not None:
                    elapsed_time = time_module.time() - start_time
                    if elapsed_time > max_wait_time:
                        logger.warning(f"⏰ Timeout atteint ({max_wait_time}s) - Abandon de l'attente")
                        return None
                        
                # Vérifier l'arrêt demandé par l'utilisateur
                if self.stop_auto_trading:
                    logger.info("Attente de recommandation interrompue par l'utilisateur")
                    return None
                    
                try:
                    # Interroger l'API pour la recommandation finale
                    response = requests.get('http://localhost:5000/api/get-final-recommendation', timeout=15)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('success') and data.get('recommendation'):
                            symbol = data['recommendation'].get('symbol')
                            if symbol:
                                elapsed_time = time_module.time() - start_time
                                logger.info(f"✅ RECOMMANDATION FINALE REÇUE: {symbol} (après {elapsed_time:.1f}s)")
                                return symbol
                    
                    # Réinitialiser le compteur d'erreurs en cas de succès
                    consecutive_errors = 0
                    
                    # Afficher le statut de l'analyse pour information
                    try:
                        status_response = requests.get('http://localhost:5000/api/status', timeout=5)
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            phase = status_data.get('phase', 'unknown')
                            analyzed = status_data.get('analyzed_stocks', 0)
                            total = status_data.get('total_stocks', 0)
                            elapsed_time = time_module.time() - start_time
                            logger.info(f"📊 Statut analyse: {phase} ({analyzed}/{total}) - Attente: {elapsed_time:.0f}s")
                    except:
                        pass  # Ignorer les erreurs de statut
                    
                except requests.exceptions.RequestException as e:
                    consecutive_errors += 1
                    logger.warning(f"Erreur communication API ({consecutive_errors}/{max_consecutive_errors}): {e}")
                    
                    # Si trop d'erreurs consécutives, abandonner
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"Trop d'erreurs consécutives ({max_consecutive_errors}) - Abandon de l'attente")
                        return None
                
                # Attendre avant de réessayer (intervalle adaptatif)
                wait_time = min(15, 5 + consecutive_errors)  # 5-15 secondes selon les erreurs
                time_module.sleep(wait_time)
                
        except Exception as e:
            logger.error(f"Erreur attente recommandation: {e}")
            return None
    
    def _auto_trading_with_immediate_buy(self, symbol: str) -> None:
        """
        CORRECTION ROBUSTE: Mode auto trading avec achat immédiat dès réception de la recommandation
        """
        try:
            logger.info("=" * 60)
            logger.info(f"🚀 MODE AUTO TRADING AVEC RECOMMANDATION pour {symbol}")
            logger.info(f"   - Configuration:")
            logger.info(f"     * Take Profit: {self.config['take_profit_percent']}%")
            logger.info(f"     * Stop Loss: {self.config['stop_loss_percent']}%")
            logger.info(f"     * Heure de vente: {self.config['auto_sell_time']}")
            logger.info(f"     * % Portefeuille: {self.config['investment_percent']}%")
            logger.info("=" * 60)
            
            # Attendre la recommandation finale SANS TIMEOUT (attente infinie)
            symbol_to_trade = self.wait_for_recommendation(use_recommendation=True, max_wait_time=None)
            # Si aucune recommandation, utiliser le symbole par défaut
            if not symbol_to_trade:
                logger.info(f"⚠️ Aucune recommandation reçue dans les délais")
                logger.info(f"🔄 Utilisation du symbole par défaut: {symbol}")
                symbol_to_trade = symbol
            
            # Vérifier que le trading automatique est toujours activé
            if not self.config['auto_trading_enabled']:
                logger.info("Trading automatique désactivé pendant l'attente - Arrêt")
                return
            
            # ACHAT IMMÉDIAT dès réception de la recommandation ou après timeout
            logger.info(f"🎯 ACHAT IMMÉDIAT pour {symbol_to_trade}")
            buy_result = self.execute_immediate_auto_buy(symbol_to_trade)
            
            if not buy_result['success']:
                logger.error(f"Échec achat immédiat: {buy_result['message']}")
                logger.error("⚠️ ATTENTION: Le trading automatique reste activé")
                # NE PAS désactiver auto_trading_enabled ici
                return
            
            # La surveillance de la position est déjà démarrée dans execute_immediate_auto_buy
            logger.info(f"✅ ACHAT IMMÉDIAT TERMINÉ - Surveillance active pour {symbol_to_trade}")
            logger.info(f"   - Quantité achetée: {buy_result.get('qty', 'N/A')}")
            logger.info(f"   - Prix d'entrée: ${buy_result.get('entry_price', 0):.2f}")
            logger.info(f"   - Montant investi: ${buy_result.get('amount', 0):.2f}")
            
        except Exception as e:
            logger.error(f"Erreur mode auto trading avec achat immédiat: {e}")
            logger.error("⚠️ Le trading automatique reste activé malgré l'erreur")

# ===== INSTANCE GLOBALE =====

# Créer une instance globale pour l'utilisation par l'API
trading_agent = AlpacaTradingAgent()

# ===== FONCTIONS D'API =====

def configure_api_keys(paper_api_key: str, paper_secret_key: str, live_api_key: str = '', live_secret_key: str = '') -> Dict:
    """Configure les clés API Alpaca"""
    try:
        trading_agent.config['paper_api_key'] = paper_api_key
        trading_agent.config['paper_secret_key'] = paper_secret_key
        
        if live_api_key and live_secret_key:
            trading_agent.config['live_api_key'] = live_api_key
            trading_agent.config['live_secret_key'] = live_secret_key
        
        # Sauvegarder la configuration
        trading_agent._save_config()
        
        # Réinitialiser l'API
        trading_agent._initialize_api()
        
        if trading_agent.api:
            return {'success': True, 'message': 'Clés API configurées avec succès'}
        else:
            return {'success': False, 'message': 'Erreur lors de l\'initialisation de l\'API'}
            
    except Exception as e:
        return {'success': False, 'message': str(e)}

def get_portfolio_info() -> Dict:
    """Retourne les informations du portefeuille"""
    try:
        if not trading_agent.api:
            return {'success': False, 'message': 'API non initialisée'}
        
        trading_agent._update_portfolio()
        return {'success': True, 'portfolio': trading_agent.portfolio}
        
    except Exception as e:
        return {'success': False, 'message': str(e)}

def place_order(symbol: str, qty: int, side: str) -> Dict:
    """Place un ordre"""
    return trading_agent.place_manual_order(symbol, qty, side)

def start_auto_trading_mode(symbol: str) -> Dict:
    """Démarre le mode de trading automatique"""
    return trading_agent.start_auto_trading(symbol)

def stop_auto_trading_mode() -> Dict:
    """Arrête le mode de trading automatique"""
    return trading_agent.stop_auto_trading_mode()

def get_auto_trading_status() -> Dict:
    """Retourne le statut du trading automatique"""
    return trading_agent.get_auto_trading_status()

def update_trading_config(config_updates: Dict) -> Dict:
    """Met à jour la configuration de trading"""
    return trading_agent.update_config(config_updates)

def calculate_investment_amount(symbol: str) -> Dict:
    """Calcule le montant d'investissement pour un symbole donné"""
    try:
        qty, amount = trading_agent.calculate_investment_amount(symbol)
        return {
            'success': True,
            'symbol': symbol,
            'qty': qty,
            'amount': amount,
            'investment_percent': trading_agent.config['investment_percent']
        }
    except Exception as e:
        return {'success': False, 'message': str(e)}

def get_market_status() -> Dict:
    """Retourne le statut du marché"""
    try:
        is_open = trading_agent._is_market_open()
        return {
            'success': True,
            'market_open': is_open,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        return {'success': False, 'message': str(e)}

def get_position_info(symbol: str) -> Dict:
    """Retourne les informations sur une position spécifique"""
    try:
        if not trading_agent.api:
            return {'success': False, 'message': 'API non initialisée'}
        
        positions = trading_agent.api.list_positions()
        for position in positions:
            if position.symbol == symbol:
                return {
                    'success': True,
                    'position': {
                        'symbol': position.symbol,
                        'qty': float(position.qty),
                        'market_value': float(position.market_value),
                        'unrealized_pl': float(position.unrealized_pl),
                        'unrealized_plpc': float(position.unrealized_plpc),
                        'avg_entry_price': float(position.avg_entry_price),
                        'current_price': float(position.current_price)
                    }
                }
        
        return {'success': False, 'message': f'Aucune position trouvée pour {symbol}'}
        
    except Exception as e:
        logger.error(f"Erreur récupération position {symbol}: {e}")
        return {'success': False, 'message': str(e)}

def close_position(symbol: str) -> Dict:
    """Ferme une position spécifique"""
    try:
        if not trading_agent.api:
            return {'success': False, 'message': 'API non initialisée'}
        
        # Récupérer la position actuelle
        positions = trading_agent.api.list_positions()
        position_qty = 0
        
        for position in positions:
            if position.symbol == symbol:
                position_qty = abs(float(position.qty))
                break
        
        if position_qty == 0:
            return {'success': False, 'message': f'Aucune position ouverte pour {symbol}'}
        
        # Fermer la position
        result = trading_agent.place_manual_order(symbol, int(position_qty), 'sell')
        
        if result['success']:
            logger.info(f"Position fermée: {symbol} - {position_qty} actions vendues")
            return {
                'success': True,
                'message': f'Position {symbol} fermée avec succès',
                'qty_sold': position_qty
            }
        else:
            return result
            
    except Exception as e:
        logger.error(f"Erreur fermeture position {symbol}: {e}")
        return {'success': False, 'message': str(e)}

def get_account_info() -> Dict:
    """Retourne les informations détaillées du compte"""
    try:
        if not trading_agent.api:
            return {'success': False, 'message': 'API non initialisée'}
        
        account = trading_agent.api.get_account()
        
        return {
            'success': True,
            'account': {
                'id': account.id,
                'status': account.status,
                'currency': account.currency,
                'buying_power': float(account.buying_power),
                'portfolio_value': float(account.portfolio_value),
                'cash': float(account.cash),
                'equity': float(account.equity),
                'last_equity': float(account.last_equity),
                'multiplier': int(account.multiplier),
                'day_trade_count': getattr(account, 'day_trade_count', 0),
                'daytrade_buying_power': float(getattr(account, 'daytrade_buying_power', 0)),
                'regt_buying_power': float(getattr(account, 'regt_buying_power', 0))
            }
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération info compte: {e}")
        return {'success': False, 'message': str(e)}

def get_orders_history(limit: int = 50) -> Dict:
    """Retourne l'historique des ordres"""
    try:
        if not trading_agent.api:
            return {'success': False, 'message': 'API non initialisée'}
        
        orders = trading_agent.api.list_orders(
            status='all',
            limit=limit,
            direction='desc'
        )
        
        orders_list = []
        for order in orders:
            orders_list.append({
                'id': order.id,
                'symbol': order.symbol,
                'qty': float(order.qty),
                'side': order.side,
                'order_type': order.order_type,
                'status': order.status,
                'filled_qty': float(order.filled_qty or 0),
                'filled_avg_price': float(order.filled_avg_price or 0),
                'created_at': order.created_at.isoformat() if order.created_at else None,
                'updated_at': order.updated_at.isoformat() if order.updated_at else None
            })
        
        return {
            'success': True,
            'orders': orders_list,
            'count': len(orders_list)
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération historique ordres: {e}")
        return {'success': False, 'message': str(e)}

def cancel_all_orders() -> Dict:
    """Annule tous les ordres en attente"""
    try:
        if not trading_agent.api:
            return {'success': False, 'message': 'API non initialisée'}
        
        cancelled_orders = trading_agent.api.cancel_all_orders()
        
        return {
            'success': True,
            'message': f'{len(cancelled_orders)} ordres annulés',
            'cancelled_count': len(cancelled_orders)
        }
        
    except Exception as e:
        logger.error(f"Erreur annulation ordres: {e}")
        return {'success': False, 'message': str(e)}

def get_current_price(symbol: str) -> Dict:
    """Retourne le prix actuel d'un symbole"""
    try:
        if not trading_agent.api:
            return {'success': False, 'message': 'API non initialisée'}
        
        latest_trade = trading_agent.api.get_latest_trade(symbol)
        
        return {
            'success': True,
            'symbol': symbol,
            'price': float(latest_trade.price),
            'timestamp': latest_trade.timestamp.isoformat() if latest_trade.timestamp else None
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération prix {symbol}: {e}")
        return {'success': False, 'message': str(e)}

# ===== FONCTIONS DE VALIDATION =====

def validate_symbol(symbol: str) -> bool:
    """Valide qu'un symbole est correct"""
    try:
        if not symbol or len(symbol) < 1 or len(symbol) > 5:
            return False
        
        # Vérifier que le symbole ne contient que des lettres
        return symbol.isalpha() and symbol.isupper()
        
    except Exception:
        return False

def validate_trading_config(config: Dict) -> Dict:
    """Valide une configuration de trading"""
    errors = []
    
    try:
        # Validation take_profit_percent
        if 'take_profit_percent' in config:
            value = float(config['take_profit_percent'])
            if not (0.0 <= value <= 5.0):
                errors.append('Take profit doit être entre 0 et 5%')
        
        # Validation stop_loss_percent
        if 'stop_loss_percent' in config:
            value = float(config['stop_loss_percent'])
            if not (0.0 <= value <= 5.0):
                errors.append('Stop loss doit être entre 0 et 5%')
        
        # Validation investment_percent
        if 'investment_percent' in config:
            value = float(config['investment_percent'])
            if not (1.0 <= value <= 100.0):
                errors.append('Pourcentage d\'investissement doit être entre 1 et 100%')
        
        # Validation auto_sell_time
        if 'auto_sell_time' in config:
            try:
                datetime.strptime(config['auto_sell_time'], '%H:%M')
            except ValueError:
                errors.append('Format d\'heure de vente invalide (utilisez HH:MM)')
        
        if errors:
            return {'success': False, 'errors': errors}
        else:
            return {'success': True, 'message': 'Configuration valide'}
            
    except Exception as e:
        return {'success': False, 'errors': [f'Erreur de validation: {str(e)}']}

# ===== FONCTIONS DE MONITORING =====

def get_trading_performance() -> Dict:
    """Retourne les statistiques de performance du trading"""
    try:
        if not trading_agent.api:
            return {'success': False, 'message': 'API non initialisée'}
        
        account = trading_agent.api.get_account()
        portfolio_history = trading_agent.api.get_portfolio_history(
            period='1D',
            timeframe='1Min'
        )
        
        # Calculer les métriques de performance
        initial_value = trading_agent.config.get('initial_amount', 10000.0)
        current_value = float(account.portfolio_value)
        total_return = current_value - initial_value
        total_return_pct = (total_return / initial_value) * 100 if initial_value > 0 else 0
        
        return {
            'success': True,
            'performance': {
                'initial_value': initial_value,
                'current_value': current_value,
                'total_return': total_return,
                'total_return_pct': total_return_pct,
                'unrealized_pl': float(getattr(account, 'unrealized_pl', 0)),
                'realized_pl': float(getattr(account, 'realized_pl', 0)),
                'day_trade_count': getattr(account, 'day_trade_count', 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération performance: {e}")
        return {'success': False, 'message': str(e)}

# ===== LOGGING ET DEBUG =====

def get_trading_logs() -> Dict:
    """Retourne les logs récents du trading"""
    try:
        # Cette fonction pourrait être étendue pour lire les logs depuis un fichier
        return {
            'success': True,
            'logs': [
                'Module de trading Alpaca initialisé - VERSION SANS HEURE D\'ACHAT',
                f'Configuration actuelle: {trading_agent.config}',
                f'Statut API: {"Connecté" if trading_agent.api else "Déconnecté"}',
                f'Trading automatique: {"Actif" if trading_agent.config["auto_trading_enabled"] else "Inactif"}',
                '🚀 ACHAT IMMÉDIAT activé - Plus d\'attente d\'heure d\'achat'
            ]
        }
    except Exception as e:
        return {'success': False, 'message': str(e)}

def debug_trading_status() -> Dict:
    """Retourne des informations de debug détaillées"""
    try:
        return {
            'success': True,
            'debug_info': {
                'api_connected': trading_agent.api is not None,
                'config': trading_agent.config,
                'portfolio': trading_agent.portfolio,
                'auto_trading_thread_alive': trading_agent.auto_trading_thread.is_alive() if trading_agent.auto_trading_thread else False,
                'stop_auto_trading_flag': trading_agent.stop_auto_trading,
                'market_open': trading_agent.is_market_open(),
                'config_file_exists': os.path.exists(trading_agent.config_file),
                'monitoring_threads': list(trading_agent.monitoring_threads.keys()),
                'immediate_buy_mode': True  # Nouveau flag pour indiquer le mode achat immédiat
            }
        }
    except Exception as e:
        return {'success': False, 'message': str(e)}

# ===== NOUVELLE FONCTION POUR L'ACHAT IMMÉDIAT =====

def execute_immediate_buy_from_recommendation(symbol: str) -> Dict:
    """
    NOUVELLE FONCTION: Exécute un achat immédiat dès réception d'une recommandation
    Cette fonction est appelée par l'API principale quand une recommandation finale est disponible
    """
    return trading_agent.execute_immediate_auto_buy(symbol)

# ===== POINT D'ENTRÉE POUR TESTS =====

if __name__ == "__main__":
    print("🚀 Module de trading Alpaca SANS heure d'achat - ACHAT IMMÉDIAT")
    print("=" * 60)
    
    # Test de base
    agent = AlpacaTradingAgent()
    print(f"✅ Agent créé - Config: {agent.config['mode']}")
    print(f"🎯 Achat immédiat: ACTIVÉ")
    print(f"⏰ Heure d'achat: SUPPRIMÉE")
    
    print("✅ Module de trading corrigé fonctionnel - ACHAT IMMÉDIAT !")


# ===== FONCTIONS MANQUANTES RESTAURÉES =====

def get_trading_status() -> Dict:
    """Retourne le statut du trading automatique"""
    return {
        'success': True,
        'api_connected': trading_agent.api is not None,
        'mode': trading_agent.config['mode'],
        'auto_trading_enabled': trading_agent.config['auto_trading_enabled'],
        'market_open': trading_agent._is_market_open(),
        'config': trading_agent.config,
        'portfolio': trading_agent.portfolio
    }

def configure_trading(config_data: Dict) -> Dict:
    """Configure les paramètres de trading"""
    return trading_agent.update_config(config_data)

def start_trading(symbol: str, use_recommendation: bool = False) -> Dict:
    """Démarre le trading automatique pour un symbole avec option de recommandation"""
    return trading_agent.start_auto_trading_with_recommendation(use_recommendation, symbol)

def stop_trading() -> Dict:
    """Arrête le trading automatique"""
    return trading_agent.stop_auto_trading_mode()

def get_portfolio() -> Dict:
    """Retourne les informations du portefeuille"""
    return trading_agent.get_portfolio_status()

def setup_api_keys(paper_key: str, paper_secret: str, live_key: str = '', live_secret: str = '', mode: str = 'paper') -> Dict:
    """Configure les clés API Alpaca"""
    return trading_agent.configure_api_keys(paper_key, paper_secret, live_key, live_secret, mode)

# ===== MÉTHODES MANQUANTES DE LA CLASSE =====

# Ajouter les méthodes manquantes à la classe AlpacaTradingAgent
def _add_missing_methods():
    """Ajoute les méthodes manquantes à la classe AlpacaTradingAgent"""
    
    def configure_api_keys(self, paper_key: str, paper_secret: str, live_key: str = '', live_secret: str = '', mode: str = 'paper') -> Dict:
        """Configure les clés API Alpaca"""
        try:
            self.config['paper_api_key'] = paper_key
            self.config['paper_secret_key'] = paper_secret
            
            if live_key and live_secret:
                self.config['live_api_key'] = live_key
                self.config['live_secret_key'] = live_secret
            
            self.config['mode'] = mode
            
            # Sauvegarder la configuration
            self._save_config()
            
            # Réinitialiser l'API
            self._initialize_api()
            
            if self.api:
                return {'success': True, 'message': 'Clés API configurées avec succès'}
            else:
                return {'success': False, 'message': 'Erreur lors de l\'initialisation de l\'API'}
                
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def get_portfolio_status(self) -> Dict:
        """Retourne le statut détaillé du portefeuille"""
        try:
            if not self.api:
                return {'success': False, 'message': 'API non initialisée'}
            
            self._update_portfolio()
            return {'success': True, 'portfolio': self.portfolio}
            
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def start_auto_trading_with_recommendation(self, use_recommendation: bool, symbol: str) -> Dict:
        """Démarre le trading automatique avec ou sans recommandation - CORRIGÉ DOUBLE ORDRE"""
        try:
            if not self.api:
                return {'success': False, 'message': 'API non initialisée - Veuillez configurer vos clés Alpaca'}
            
            if self.config['auto_trading_enabled']:
                return {'success': False, 'message': 'Trading automatique déjà actif'}
            
            # Activer le trading automatique
            self.config['auto_trading_enabled'] = True
            self.stop_auto_trading = False
            
            # Sauvegarder la configuration
            self._save_config()
            
            if use_recommendation:
                # CORRECTION DOUBLE ORDRE: Vérifier si le thread doit être désactivé
                if DISABLE_AUTO_TRADING_THREAD:
                    logger.info(f"🎯 TRADING AUTOMATIQUE AVEC RECOMMANDATION pour {symbol} - THREAD DÉSACTIVÉ")
                    logger.info("🔧 Le thread auto trading est désactivé pour éviter les doubles ordres")
                    logger.info("📡 L'achat sera déclenché par trigger_immediate_auto_buy_on_recommendation()")
                    
                    return {
                        'success': True,
                        'message': f'Trading automatique avec recommandation configuré pour {symbol} (thread désactivé)',
                        'symbol': symbol,
                        'use_recommendation': True,
                        'thread_disabled': True
                    }
                else:
                    # Mode avec recommandation finale - achat immédiat dès réception (ANCIEN COMPORTEMENT)
                    logger.info(f"🎯 TRADING AUTOMATIQUE AVEC RECOMMANDATION pour {symbol} - THREAD ACTIVÉ")
                    self.auto_trading_thread = threading.Thread(
                        target=self._auto_trading_with_immediate_buy,
                        args=(symbol,),
                        daemon=True
                    )
                    self.auto_trading_thread.start()
                    
                    return {
                        'success': True,
                        'message': f'Trading automatique avec recommandation démarré pour {symbol}',
                        'symbol': symbol,
                        'use_recommendation': True,
                        'thread_disabled': False
                    }
            else:
                # Mode sans recommandation - achat immédiat
                logger.info(f"🚀 TRADING AUTOMATIQUE SANS RECOMMANDATION pour {symbol}")
                result = self.execute_immediate_auto_buy(symbol)
                return result
                
        except Exception as e:
            logger.error(f"Erreur démarrage trading auto: {e}")
            return {'success': False, 'message': str(e)}
    
    def is_market_open(self) -> bool:
        """Vérifie si le marché est ouvert (méthode publique)"""
        return self._is_market_open()
    
    # Ajouter les méthodes à la classe
    AlpacaTradingAgent.configure_api_keys = configure_api_keys
    AlpacaTradingAgent.get_portfolio_status = get_portfolio_status
    AlpacaTradingAgent.start_auto_trading_with_recommendation = start_auto_trading_with_recommendation
    AlpacaTradingAgent.is_market_open = is_market_open

# Appliquer les méthodes manquantes
_add_missing_methods()

# ===== FONCTIONS D'API SUPPLÉMENTAIRES =====

def start_auto_trading_mode(symbol: str) -> Dict:
    """Démarre le mode de trading automatique"""
    return trading_agent.start_auto_trading(symbol)

def stop_auto_trading_mode() -> Dict:
    """Arrête le mode de trading automatique"""
    return trading_agent.stop_auto_trading_mode()

def update_trading_config(config_updates: Dict) -> Dict:
    """Met à jour la configuration de trading"""
    return trading_agent.update_config(config_updates)

def configure_api_keys(paper_api_key: str, paper_secret_key: str, live_api_key: str = '', live_secret_key: str = '') -> Dict:
    """Configure les clés API Alpaca"""
    try:
        trading_agent.config['paper_api_key'] = paper_api_key
        trading_agent.config['paper_secret_key'] = paper_secret_key
        
        if live_api_key and live_secret_key:
            trading_agent.config['live_api_key'] = live_api_key
            trading_agent.config['live_secret_key'] = live_secret_key
        
        # Sauvegarder la configuration
        trading_agent._save_config()
        
        # Réinitialiser l'API
        trading_agent._initialize_api()
        
        if trading_agent.api:
            return {'success': True, 'message': 'Clés API configurées avec succès'}
        else:
            return {'success': False, 'message': 'Erreur lors de l\'initialisation de l\'API'}
            
    except Exception as e:
        return {'success': False, 'message': str(e)}

def get_portfolio_info() -> Dict:
    """Retourne les informations du portefeuille"""
    try:
        if not trading_agent.api:
            return {'success': False, 'message': 'API non initialisée'}
        
        trading_agent._update_portfolio()
        return {'success': True, 'portfolio': trading_agent.portfolio}
        
    except Exception as e:
        return {'success': False, 'message': str(e)}

def place_order(symbol: str, qty: int, side: str) -> Dict:
    """Place un ordre"""
    return trading_agent.place_manual_order(symbol, qty, side)

















































