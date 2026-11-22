@echo off
cd /d "%~dp0"
python coletar.py
python gerar_site.py
start "" "site\index.html"
