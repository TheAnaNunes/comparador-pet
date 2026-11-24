"""Coleta preços de produtos para gatos nas lojas que permitem consulta automática.

Uso:  python coletar.py
Gera: dados/catalogo.json (última coleta) e acrescenta em dados/historico.csv
"""
import csv, datetime as dt, json, re, time, unicodedata, urllib.error, urllib.parse, urllib.request
from pathlib import Path

RAIZ = Path(__file__).parent
DADOS = RAIZ / "dados"
UA = "Mozilla/5.0 (compatible; comparador-pet-pessoal/0.1; uso pessoal)"
PAUSA = 1.0  # segundos entre pedidos, para não sobrecarregar as lojas


def baixar_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError) as e:
            if tentativa == 2:
                print(f"  falhou: {url} ({e})")
                return None
            time.sleep(3)


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()


def peso_em_kg(texto):
    """'10,1 kg' -> 10.1 ; '85g' -> 0.085 ; '12 x 85g' -> 1.02"""
    t = sem_acento(texto).replace(",", ".")
    m = re.search(r"(\d+)\s*(?:x|un\.? de|unidades de)\s*(\d+(?:\.\d+)?)\s*(kg|g)\b", t)
    if m:
        q, v, u = int(m.group(1)), float(m.group(2)), m.group(3)
        return round(q * (v if u == "kg" else v / 1000), 3)
    m = re.findall(r"(\d+(?:\.\d+)?)\s*(kg|g)\b", t)
    if m:
        v, u = m[0]
        v = float(v)
        return round(v if u == "kg" else v / 1000, 3)
    return None


def categoria(nome, cats=""):
    t = sem_acento(nome + " " + cats)
    if re.search(r"\b(areia|granulado|substrato)\b", t):
        return "Areia"
    if re.search(r"\b(petisco|snack|bifinho|stick|creme|cremoso|treat|biscoito)\b", t):
        return "Petisco"
    if re.search(r"\b(sache|umida|lata|pate|patê|wet|mousse)\b", t):
        return "Ração úmida"
    if re.search(r"\b(racao|alimento)\b", t):
        return "Ração seca"
    return "Outros"


def eh_de_gato(nome, cats):
    t = sem_acento(nome + " " + cats)
    if "/caes/" in t or re.search(r"\b(caes|cao|cachorro|dog)\b", sem_acento(nome)):
        return False
    return "gato" in t or "felin" in t or "cat" in sem_acento(nome)


def coletar_vtex(chave, fonte):
    itens = {}
    for termo in fonte["buscas"]:
        for inicio in range(0, 150, 50):
            q = f"ft={urllib.parse.quote(termo)}&" if termo else ""
            url = f"{fonte['url']}/api/catalog_system/pub/products/search?{q}_from={inicio}&_to={inicio + 49}"
            dados = baixar_json(url)
            time.sleep(PAUSA)
            if not dados:
                break
            for p in dados:
                cats = " ".join(p.get("categories") or [])
                for sku in p.get("items", []):
                    nome = sku.get("nameComplete") or f"{p['productName']} {sku.get('name','')}"
                    if fonte.get("so_gatos", True) and not eh_de_gato(nome, cats):
                        continue
                    oferta = (sku.get("sellers") or [{}])[0].get("commertialOffer", {})
                    preco = oferta.get("Price") or 0
                    if not preco:
                        continue
                    imgs = sku.get("images") or [{}]
                    itens[f"{chave}:{sku['itemId']}"] = {
                        "fonte": chave,
                        "loja": fonte["nome"],
                        "nome": nome.strip(),
                        "marca": p.get("brand", ""),
                        "ean": (sku.get("ean") or "").strip(),
                        "categoria": categoria(nome, cats + " " + fonte.get("categoria_padrao", "")),
                        "peso_kg": peso_em_kg(nome) or peso_em_kg(sku.get("name", "")),
                        "preco": round(preco, 2),
                        "preco_de": round(oferta.get("ListPrice") or preco, 2),
                        "disponivel": bool(oferta.get("IsAvailable")),
                        "link": p.get("link") or f"{fonte['url']}/{p.get('linkText')}/p",
                        "imagem": imgs[0].get("imageUrl", ""),
                    }
            if len(dados) < 50:
                break
    return list(itens.values())


def coletar_shopify(chave, fonte):
    itens = []
    for pagina in range(1, 6):
        dados = baixar_json(f"{fonte['url']}/products.json?limit=250&page={pagina}")
        time.sleep(PAUSA)
        if not dados or not dados.get("products"):
            break
        for p in dados["products"]:
            img = (p.get("images") or [{}])[0].get("src", "")
            for v in p.get("variants", []):
                nome = p["title"] if v.get("title") in (None, "", "Default Title") else f"{p['title']} {v['title']}"
                preco = float(v.get("price") or 0)
                if not preco:
                    continue
                gramas = v.get("grams") or 0
                itens.append({
                    "fonte": chave,
                    "loja": fonte["nome"],
                    "nome": nome.strip(),
                    "marca": p.get("vendor", ""),
                    "ean": (v.get("barcode") or "").strip(),
                    "categoria": categoria(nome, p.get("product_type", "")),
                    "peso_kg": peso_em_kg(nome) or (round(gramas / 1000, 3) if gramas else None),
                    "preco": round(preco, 2),
                    "preco_de": round(float(v.get("compare_at_price") or preco), 2),
                    "disponivel": bool(v.get("available", True)),
                    "link": f"{fonte['url']}/products/{p['handle']}?variant={v['id']}",
                    "imagem": img,
                })
    return itens


def carregar_segredos():
    """Lê segredos.env (NUNCA vai para o GitHub: está no .gitignore)."""
    seg = {}
    arq = RAIZ / "segredos.env"
    if arq.exists():
        for linha in arq.read_text(encoding="utf-8").splitlines():
            if "=" in linha and not linha.strip().startswith("#"):
                k, v = linha.split("=", 1)
                seg[k.strip()] = v.strip()
    return seg


def token_mercadolivre(seg):
    cid, sec = seg.get("ML_CLIENT_ID"), seg.get("ML_CLIENT_SECRET")
    if not cid or not sec or "cole" in cid.lower():
        return None
    dados = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": cid, "client_secret": sec}).encode()
    req = urllib.request.Request("https://api.mercadolibre.com/oauth/token", data=dados,
                                 headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)["access_token"]
    except urllib.error.HTTPError as e:
        print(f"  Mercado Livre recusou o login do app ({e.code}): {e.read()[:200]!r}")
        return None


def coletar_mercadolivre(chave, fonte):
    token = token_mercadolivre(carregar_segredos())
    if not token:
        print("  sem chave do Mercado Livre em segredos.env; pulando")
        return []
    itens = []
    for termo in fonte["buscas"]:
        url = "https://api.mercadolibre.com/sites/MLB/search?" + urllib.parse.urlencode({"q": termo, "limit": 50})
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                dados = json.load(r)
        except urllib.error.HTTPError as e:
            print(f"  busca '{termo}' falhou ({e.code}): {e.read()[:200]!r}")
            continue
        time.sleep(PAUSA)
        for p in dados.get("results", []):
            nome = p.get("title", "")
            if not eh_de_gato(nome, ""):
                continue
            attrs = {a.get("id"): a.get("value_name") for a in p.get("attributes", [])}
            preco = p.get("price") or 0
            if not preco:
                continue
            frete = " · frete grátis" if (p.get("shipping") or {}).get("free_shipping") else ""
            itens.append({
                "fonte": chave,
                "loja": fonte["nome"] + frete,
                "nome": nome,
                "marca": attrs.get("BRAND") or "",
                "ean": (attrs.get("GTIN") or "").split(",")[0].strip(),
                "categoria": categoria(nome),
                "peso_kg": peso_em_kg(nome),
                "preco": round(preco, 2),
                "preco_de": round(p.get("original_price") or preco, 2),
                "disponivel": True,
                "link": p.get("permalink", ""),
                "imagem": (p.get("thumbnail") or "").replace("http://", "https://"),
            })
    return itens


def main():
    cfg = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
    DADOS.mkdir(exist_ok=True)
    agora = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    todos = []
    for chave, fonte in cfg["fontes"].items():
        print(f"Coletando {fonte['nome']}...")
        f = {"vtex": coletar_vtex, "shopify": coletar_shopify, "mercadolivre": coletar_mercadolivre}[fonte["tipo"]]
        itens = f(chave, fonte)
        print(f"  {len(itens)} itens")
        todos += itens

    hist = DADOS / "historico.csv"
    novo = not hist.exists()
    with hist.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if novo:
            w.writerow(["data", "fonte", "ean", "nome", "preco", "preco_de"])
        for i in todos:
            w.writerow([agora, i["fonte"], i["ean"], i["nome"], i["preco"], i["preco_de"]])

    (DADOS / "catalogo.json").write_text(
        json.dumps({"atualizado_em": agora, "itens": todos, "links_busca": cfg["links_busca"]}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"Pronto: {len(todos)} ofertas salvas em dados/catalogo.json")


if __name__ == "__main__":
    main()
