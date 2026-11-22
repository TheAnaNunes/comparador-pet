"""Gera site/index.html (uma página só, funciona offline) a partir de dados/catalogo.json."""
import csv, json, re, unicodedata
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).parent
MINHAS_MARCAS = ["formula natural", "royal canin", "cansei de ser gato", "viva verde", "catbio", "sheba"]


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()


def chave_produto(i):
    if i["ean"]:
        return "ean:" + i["ean"].lstrip("0")
    return "nome:" + re.sub(r"[^a-z0-9]+", " ", sem_acento(i["nome"])).strip()


def main():
    cat = json.loads((RAIZ / "dados" / "catalogo.json").read_text(encoding="utf-8"))

    menor_visto = {}
    hist = RAIZ / "dados" / "historico.csv"
    if hist.exists():
        with hist.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                k = chave_produto({"ean": r["ean"], "nome": r["nome"]})
                p = float(r["preco"])
                if k not in menor_visto or p < menor_visto[k][0]:
                    menor_visto[k] = (p, r["data"][:10])

    grupos = defaultdict(list)
    for i in cat["itens"]:
        grupos[chave_produto(i)].append(i)

    produtos = []
    for k, ofertas in grupos.items():
        ofertas.sort(key=lambda o: (not o["disponivel"], o["preco"]))
        base = max(ofertas, key=lambda o: (bool(o["imagem"]), len(o["nome"])))
        marca = base["marca"]
        txt = sem_acento(marca + " " + base["nome"])
        minha = any(m in txt for m in MINHAS_MARCAS) or (base["categoria"] == "Areia" and "biodegrad" in txt)
        mv = menor_visto.get(k)
        produtos.append({
            "n": base["nome"], "m": marca, "c": base["categoria"], "kg": base["peso_kg"],
            "img": base["imagem"], "minha": minha,
            "mv": mv[0] if mv else None, "mvd": mv[1] if mv else None,
            "o": [{"l": o["loja"], "p": o["preco"], "de": o["preco_de"], "d": o["disponivel"], "u": o["link"]} for o in ofertas],
        })

    html = (RAIZ / "modelo.html").read_text(encoding="utf-8")
    html = html.replace("/*DADOS*/null", json.dumps(
        {"atualizado": cat["atualizado_em"], "produtos": produtos, "busca": cat["links_busca"]},
        ensure_ascii=False, separators=(",", ":")))
    for pasta in ("site", "docs"):  # docs/ é o que o GitHub Pages publica
        (RAIZ / pasta).mkdir(exist_ok=True)
        (RAIZ / pasta / "index.html").write_text(html, encoding="utf-8")
    print(f"site/index.html gerado com {len(produtos)} produtos")


if __name__ == "__main__":
    main()
