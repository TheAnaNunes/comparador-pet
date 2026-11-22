# Comparador de preços para gatos (uso pessoal)

Dê dois cliques em `atualizar.bat`: ele busca os preços de novo e abre o catálogo no navegador.

- `coletar.py` busca os preços nas lojas que permitem consulta automática (Cobasi, Viva Verde, Catbio) e guarda em `dados/`.
- `gerar_site.py` monta `site/index.html` a partir de `modelo.html`.
- `config.json` define as lojas e as buscas. Para acompanhar outra marca, acrescente um termo em `buscas`.
- `dados/historico.csv` guarda todos os preços já vistos, para mostrar o menor preço da história.

Petz, Petlove, Mercado Livre e Cansei de Ser Gato bloqueiam consulta automática; elas aparecem como links de busca em cada produto.
