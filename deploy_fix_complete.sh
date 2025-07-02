#!/bin/bash
# Script de Correction Complète du Fuseau Horaire
# Version Robuste pour Render

echo "🚀 CORRECTION COMPLÈTE DU FUSEAU HORAIRE"
echo "========================================"

# Vérifier qu'on est dans le bon répertoire
if [ ! -d "sp500-api" ]; then
    echo "❌ Erreur: Exécuter depuis la racine du projet SP500-Day-TradingBot"
    exit 1
fi

echo "📁 Répertoire de travail: $(pwd)"

# 1. NETTOYER LE CACHE PYTHON
echo "🧹 Nettoyage du cache Python..."
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
echo "✅ Cache Python nettoyé"

# 2. COPIER LE PATCH GLOBAL
echo "📋 Installation du patch global..."
if [ -f "/home/ubuntu/timezone_patch.py" ]; then
    cp /home/ubuntu/timezone_patch.py sp500-api/src/timezone_patch.py
    echo "✅ timezone_patch.py copié"
else
    echo "❌ Erreur: timezone_patch.py non trouvé"
    exit 1
fi

# 3. SAUVEGARDER LES FICHIERS ORIGINAUX
echo "💾 Sauvegarde des fichiers originaux..."
cp sp500-api/src/main.py sp500-api/src/main.py.backup.$(date +%Y%m%d_%H%M%S)
cp sp500-api/src/alpaca_trading.py sp500-api/src/alpaca_trading.py.backup.$(date +%Y%m%d_%H%M%S)
cp sp500-api/src/schedule_manager.py sp500-api/src/schedule_manager.py.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ Sauvegardes créées"

# 4. MODIFIER MAIN.PY - AJOUTER L'IMPORT DU PATCH EN PREMIÈRE LIGNE
echo "🔧 Modification de main.py..."

# Vérifier si l'import n'existe pas déjà
if ! grep -q "import timezone_patch" sp500-api/src/main.py; then
    # Ajouter l'import en première ligne après le shebang
    sed -i '2i import timezone_patch  # PATCH FUSEAU HORAIRE - DOIT ÊTRE EN PREMIER' sp500-api/src/main.py
    echo "✅ Import timezone_patch ajouté à main.py"
else
    echo "ℹ️ Import timezone_patch déjà présent dans main.py"
fi

# 5. CORRIGER ALPACA_TRADING.PY
echo "🔧 Correction de alpaca_trading.py..."

# Ajouter l'import pytz si nécessaire
if ! grep -q "import pytz" sp500-api/src/alpaca_trading.py; then
    sed -i '/^import time as time_module$/a import pytz' sp500-api/src/alpaca_trading.py
    echo "✅ Import pytz ajouté à alpaca_trading.py"
fi

# Corriger la ligne problématique
sed -i 's/current_time = datetime\.now()\.time()/current_time = datetime.now(pytz.timezone("Europe\/Brussels")).time()/g' sp500-api/src/alpaca_trading.py

# Vérifier si la correction a été appliquée
if grep -q 'current_time = datetime.now(pytz.timezone("Europe/Brussels")).time()' sp500-api/src/alpaca_trading.py; then
    echo "✅ Correction appliquée dans alpaca_trading.py"
else
    echo "⚠️ Correction alpaca_trading.py à vérifier manuellement"
fi

# 6. STANDARDISER SCHEDULE_MANAGER.PY
echo "🔧 Standardisation de schedule_manager.py..."
sed -i 's/Europe\/Paris/Europe\/Brussels/g' sp500-api/src/schedule_manager.py
echo "✅ Fuseau horaire standardisé sur Europe/Brussels"

# 7. CORRIGER TOUS LES AUTRES FICHIERS PYTHON
echo "🔧 Correction des autres fichiers Python..."

# Corriger individual_agent_v2.py
if [ -f "sp500-api/src/individual_agent_v2.py" ]; then
    sed -i 's/datetime\.now()/datetime.now(pytz.timezone("Europe\/Brussels"))/g' sp500-api/src/individual_agent_v2.py
    echo "✅ individual_agent_v2.py corrigé"
fi

# Corriger central_orchestrator.py
if [ -f "sp500-api/src/central_orchestrator.py" ]; then
    sed -i 's/datetime\.now()/datetime.now(pytz.timezone("Europe\/Brussels"))/g' sp500-api/src/central_orchestrator.py
    echo "✅ central_orchestrator.py corrigé"
fi

# 8. VÉRIFICATION DES CORRECTIONS
echo "🔍 Vérification des corrections..."

echo "📊 Statistiques des corrections:"
echo "   - main.py: $(grep -c 'timezone_patch' sp500-api/src/main.py) import(s) du patch"
echo "   - alpaca_trading.py: $(grep -c 'Europe/Brussels' sp500-api/src/alpaca_trading.py) référence(s) Belgium"
echo "   - schedule_manager.py: $(grep -c 'Europe/Brussels' sp500-api/src/schedule_manager.py) référence(s) Belgium"

# Vérifier s'il reste des datetime.now() problématiques
remaining_issues=$(grep -r "datetime\.now()" sp500-api/src/ --include="*.py" | grep -v "timezone_patch" | grep -v "Europe/Brussels" | wc -l)
echo "   - Appels datetime.now() restants: $remaining_issues"

if [ $remaining_issues -gt 0 ]; then
    echo "⚠️ Appels datetime.now() restants à vérifier:"
    grep -r "datetime\.now()" sp500-api/src/ --include="*.py" | grep -v "timezone_patch" | grep -v "Europe/Brussels" | head -5
fi

# 9. CRÉER UN FICHIER DE VALIDATION
echo "📝 Création du fichier de validation..."
cat > sp500-api/src/validate_timezone.py << 'EOF'
#!/usr/bin/env python3
"""
Script de validation du fuseau horaire
À exécuter après déploiement pour vérifier que les corrections fonctionnent
"""

import timezone_patch  # Importer le patch
import datetime
import pytz

def validate_timezone():
    print("🔍 VALIDATION DU FUSEAU HORAIRE")
    print("=" * 40)
    
    # Test 1: datetime.now() patchée
    current_time = datetime.datetime.now()
    print(f"datetime.now(): {current_time}")
    print(f"Fuseau horaire: {current_time.tzinfo}")
    
    # Test 2: Comparaison avec UTC
    utc_time = datetime.datetime.now(pytz.utc)
    print(f"UTC: {utc_time}")
    
    # Test 3: Différence
    if current_time.tzinfo and utc_time.tzinfo:
        diff = (current_time - utc_time).total_seconds() / 3600
        print(f"Différence: {diff:.1f} heures")
        
        if 1 <= diff <= 2:
            print("✅ FUSEAU HORAIRE CORRECT")
            return True
        else:
            print("❌ FUSEAU HORAIRE INCORRECT")
            return False
    else:
        print("⚠️ Impossible de valider")
        return False

if __name__ == "__main__":
    validate_timezone()
EOF

echo "✅ Script de validation créé: sp500-api/src/validate_timezone.py"

# 10. INSTRUCTIONS FINALES
echo ""
echo "🎯 CORRECTIONS APPLIQUÉES AVEC SUCCÈS!"
echo "======================================"
echo ""
echo "📋 PROCHAINES ÉTAPES:"
echo "1. 🌐 Ajouter la variable d'environnement sur Render:"
echo "   TZ=Europe/Brussels"
echo ""
echo "2. 🚀 Déployer le code modifié sur Render"
echo ""
echo "3. 🔄 Redémarrer complètement l'application"
echo ""
echo "4. ✅ Tester avec le script de validation:"
echo "   python sp500-api/src/validate_timezone.py"
echo ""
echo "5. 🕐 Vérifier que les logs affichent l'heure belge (10h35)"
echo ""
echo "💡 IMPORTANT:"
echo "- Nettoyer le cache de build sur Render si nécessaire"
echo "- Vérifier que tous les logs affichent maintenant l'heure belge"
echo "- La vente automatique doit se déclencher à l'heure belge"
echo ""
echo "🔄 Pour restaurer en cas de problème:"
echo "   cp sp500-api/src/*.backup.* (nom_original)"

exit 0

