@echo off
cd /d "%~dp0"
python coletar.py
python gerar_site.py
git add -A
git commit -q -m "Atualiza precos"
git push -q
start "" "site\index.html"
