#!/bin/bash

echo "🚀 Démarrage du système SP500 Trading Bot en mode développement"

# Vérification des prérequis
if ! command -v python3.11 &> /dev/null; then
    echo "❌ Python 3.11 requis. Installez-le depuis python.org"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ Node.js et npm requis. Installez-les depuis nodejs.org"
    exit 1
fi

# Installation des dépendances Python
echo "📦 Installation des dépendances Python..."
pip install -r requirements.txt

# Démarrage du backend
echo "🐍 Démarrage du backend Flask..."
cd sp500-api
python3.11 src/main.py &
BACKEND_PID=$!
cd ..

# Attente du démarrage du backend
sleep 5

# Installation des dépendances Node.js
echo "📦 Installation des dépendances Node.js..."
cd sp500-dashboard
npm install

# Démarrage du frontend
echo "⚛️ Démarrage du frontend React..."
REACT_APP_API_URL=http://localhost:5000 npm start &
FRONTEND_PID=$!
cd ..

echo "✅ Système démarré avec succès !"
echo "🌐 Frontend: http://localhost:3000"
echo "🔧 Backend: http://localhost:5000"
echo ""
echo "Pour arrêter : kill $BACKEND_PID $FRONTEND_PID"

# Attendre l'arrêt
wait
