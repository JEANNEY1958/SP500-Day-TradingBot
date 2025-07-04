#!/usr/bin/env python3
"""
Gestionnaire d'Horloge pour le Bot Trading SP500
Gère la planification automatique du mode seuil
"""

import schedule
import threading
import time
from datetime import datetime, timedelta
import pytz
import logging
from typing import Dict, Callable, Optional, List

class ScheduleManager:
    """Gestionnaire d'horaires pour le déclenchement automatique du mode seuil"""
    
    def __init__(self, timezone='Europe/Paris'):
        """
        Initialise le gestionnaire d'horaires
        
        Args:
            timezone (str): Fuseau horaire par défaut
        """
        self.timezone = timezone
        self.scheduled_jobs = {}
        self.running = False
        self.scheduler_thread = None
        self.stop_event = threading.Event()
        
        # Configuration du logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
    def add_schedule(self, time_str: str, callback: Callable, job_id: str, 
                    weekdays_only: bool = True, enabled: bool = True) -> bool:
        """
        Ajoute une tâche programmée
        
        Args:
            time_str (str): Heure au format "HH:MM"
            callback (Callable): Fonction à exécuter
            job_id (str): Identifiant unique de la tâche
            weekdays_only (bool): Exécuter seulement les jours de semaine
            enabled (bool): Tâche activée
            
        Returns:
            bool: True si la tâche a été ajoutée avec succès
        """
        try:
            # Validation du format d'heure
            if not self._validate_time_format(time_str):
                self.logger.error(f"Format d'heure invalide: {time_str}")
                return False
            
            # Supprimer la tâche existante si elle existe
            if job_id in self.scheduled_jobs:
                self.remove_schedule(job_id)
            
            # Créer la nouvelle tâche
            job_config = {
                'time_str': time_str,
                'callback': callback,
                'weekdays_only': weekdays_only,
                'enabled': enabled,
                'job': None,
                'last_run': None,
                'next_run': None
            }
            
            # Programmer la tâche
            if weekdays_only:
                job = schedule.every().monday.at(time_str).do(self._execute_job, job_id)
                schedule.every().tuesday.at(time_str).do(self._execute_job, job_id)
                schedule.every().wednesday.at(time_str).do(self._execute_job, job_id)
                schedule.every().thursday.at(time_str).do(self._execute_job, job_id)
                schedule.every().friday.at(time_str).do(self._execute_job, job_id)
            else:
                job = schedule.every().day.at(time_str).do(self._execute_job, job_id)
            
            job_config['job'] = job
            job_config['next_run'] = self._calculate_next_run(time_str, weekdays_only)
            
            self.scheduled_jobs[job_id] = job_config
            
            self.logger.info(f"Tâche programmée ajoutée: {job_id} à {time_str}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'ajout de la tâche {job_id}: {e}")
            return False
    
    def remove_schedule(self, job_id: str) -> bool:
        """
        Supprime une tâche programmée
        
        Args:
            job_id (str): Identifiant de la tâche
            
        Returns:
            bool: True si la tâche a été supprimée avec succès
        """
        try:
            if job_id in self.scheduled_jobs:
                job_config = self.scheduled_jobs[job_id]
                if job_config['job']:
                    schedule.cancel_job(job_config['job'])
                del self.scheduled_jobs[job_id]
                self.logger.info(f"Tâche supprimée: {job_id}")
                return True
            else:
                self.logger.warning(f"Tâche non trouvée: {job_id}")
                return False
        except Exception as e:
            self.logger.error(f"Erreur lors de la suppression de la tâche {job_id}: {e}")
            return False
    
    def enable_schedule(self, job_id: str) -> bool:
        """Active une tâche programmée"""
        if job_id in self.scheduled_jobs:
            self.scheduled_jobs[job_id]['enabled'] = True
            self.logger.info(f"Tâche activée: {job_id}")
            return True
        return False
    
    def disable_schedule(self, job_id: str) -> bool:
        """Désactive une tâche programmée"""
        if job_id in self.scheduled_jobs:
            self.scheduled_jobs[job_id]['enabled'] = False
            self.logger.info(f"Tâche désactivée: {job_id}")
            return True
        return False
    
    def start_scheduler(self) -> bool:
        """
        Démarre le gestionnaire d'horaires
        
        Returns:
            bool: True si le gestionnaire a été démarré avec succès
        """
        if self.running:
            self.logger.warning("Le gestionnaire d'horaires est déjà en cours d'exécution")
            return False
        
        try:
            self.running = True
            self.stop_event.clear()
            self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.scheduler_thread.start()
            self.logger.info("Gestionnaire d'horaires démarré")
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors du démarrage du gestionnaire: {e}")
            self.running = False
            return False
    
    def stop_scheduler(self) -> bool:
        """
        Arrête le gestionnaire d'horaires
        
        Returns:
            bool: True si le gestionnaire a été arrêté avec succès
        """
        if not self.running:
            self.logger.warning("Le gestionnaire d'horaires n'est pas en cours d'exécution")
            return False
        
        try:
            self.running = False
            self.stop_event.set()
            
            if self.scheduler_thread and self.scheduler_thread.is_alive():
                self.scheduler_thread.join(timeout=5)
            
            # Nettoyer toutes les tâches programmées
            schedule.clear()
            
            self.logger.info("Gestionnaire d'horaires arrêté")
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de l'arrêt du gestionnaire: {e}")
            return False
    
    def get_status(self) -> Dict:
        """
        Retourne le statut du gestionnaire d'horaires
        
        Returns:
            Dict: Statut complet du gestionnaire
        """
        status = {
            'running': self.running,
            'timezone': self.timezone,
            'jobs_count': len(self.scheduled_jobs),
            'jobs': {}
        }
        
        for job_id, job_config in self.scheduled_jobs.items():
            status['jobs'][job_id] = {
                'time': job_config['time_str'],
                'enabled': job_config['enabled'],
                'weekdays_only': job_config['weekdays_only'],
                'last_run': job_config['last_run'].isoformat() if job_config['last_run'] else None,
                'next_run': job_config['next_run'].isoformat() if job_config['next_run'] else None
            }
        
        return status
    
    def _execute_job(self, job_id: str):
        """Exécute une tâche programmée"""
        try:
            if job_id not in self.scheduled_jobs:
                self.logger.error(f"Tâche non trouvée: {job_id}")
                return
            
            job_config = self.scheduled_jobs[job_id]
            
            if not job_config['enabled']:
                self.logger.info(f"Tâche désactivée, ignorée: {job_id}")
                return
            
            self.logger.info(f"Exécution de la tâche programmée: {job_id}")
            
            # Mettre à jour l'heure de dernière exécution
            job_config['last_run'] = datetime.now()
            job_config['next_run'] = self._calculate_next_run(
                job_config['time_str'], 
                job_config['weekdays_only']
            )
            
            # Exécuter la fonction callback
            callback = job_config['callback']
            if callback:
                callback()
            
            self.logger.info(f"Tâche exécutée avec succès: {job_id}")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'exécution de la tâche {job_id}: {e}")
    
    def _run_scheduler(self):
        """Boucle principale du gestionnaire d'horaires"""
        self.logger.info("Boucle du gestionnaire d'horaires démarrée")
        
        while self.running and not self.stop_event.is_set():
            try:
                schedule.run_pending()
                time.sleep(1)  # Vérifier toutes les secondes
            except Exception as e:
                self.logger.error(f"Erreur dans la boucle du gestionnaire: {e}")
                time.sleep(5)  # Attendre avant de réessayer
        
        self.logger.info("Boucle du gestionnaire d'horaires arrêtée")
    
    def _validate_time_format(self, time_str: str) -> bool:
        """Valide le format d'heure HH:MM"""
        try:
            datetime.strptime(time_str, '%H:%M')
            return True
        except ValueError:
            return False
    
    def _calculate_next_run(self, time_str: str, weekdays_only: bool) -> Optional[datetime]:
        """Calcule la prochaine exécution d'une tâche"""
        try:
            now = datetime.now()
            time_parts = time_str.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            
            # Calculer la prochaine exécution aujourd'hui
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # Si l'heure est déjà passée aujourd'hui, passer au jour suivant
            if next_run <= now:
                next_run += timedelta(days=1)
            
            # Si on ne veut que les jours de semaine, ajuster si nécessaire
            if weekdays_only:
                while next_run.weekday() >= 5:  # 5 = samedi, 6 = dimanche
                    next_run += timedelta(days=1)
            
            return next_run
            
        except Exception as e:
            self.logger.error(f"Erreur lors du calcul de la prochaine exécution: {e}")
            return None

# Instance globale du gestionnaire d'horaires
schedule_manager = ScheduleManager()

