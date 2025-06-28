@echo off
echo Lancement du TradingBot S&P 500...

echo.
echo 0. Nettoyage des processus Python existants...
taskkill /f /im python.exe 2>nul
taskkill /f /im python3.exe 2>nul
timeout /t 2 /nobreak >nul
echo Nettoyage terminé.

echo.
echo 1. Démarrage du serveur Flask...
start "Flask Server" cmd /k "cd /d C:\Users\Jean-Jacques\Desktop\SP500-Day-TradingBot\sp500-api\src && python main.py"

echo.
echo 2. Attente de 5 secondes pour le serveur...
timeout /t 5 /nobreak >nul

echo.
echo 3. Création du fichier .env pour désactiver l'ouverture automatique...
echo BROWSER=none > "C:\Users\Jean-Jacques\Desktop\SP500-Day-TradingBot\sp500-dashboard\.env"
echo REACT_APP_BROWSER=none >> "C:\Users\Jean-Jacques\Desktop\SP500-Day-TradingBot\sp500-dashboard\.env"

echo.
echo 4. Démarrage du frontend React...
start "React Frontend" cmd /k "cd /d C:\Users\Jean-Jacques\Desktop\SP500-Day-TradingBot\sp500-dashboard && npm start"

echo.
echo 5. Attente de 12 secondes pour React...
timeout /t 12 /nobreak >nul

echo.
echo 6. Ouverture du navigateur...
start "" "http://localhost:3001"

echo.
echo Lancement terminé. Tu peux utiliser le TradingBot via le navigateur !
pause

