"""
Busca o catálogo de livros de algumas editoras e salva em livros.csv
(título, autores, editora, categorias/gêneros, ano).

Fontes:
  - Open Library (padrão, não precisa de chave)
  - Google Books (só se você definir a variável GOOGLE_BOOKS_API_KEY)

Uso:
  python buscar_livros.py
  GOOGLE_BOOKS_API_KEY=suachave python buscar_livros.py   # opcional
"""

import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

EDITORAS = ["Galera", "DarkSide", "Planeta", "Arqueiro", "Rocco"]
LIVROS_POR_EDITORA = 80
CABECALHO = {"User-Agent": "TrabalhoAlgoritmosGrafos/1.0 (projeto academico)"}
CAMPOS = ["id", "titulo", "autores", "editora", "categorias", "ano", "fonte"]


# ---------------------------------------------------------------------------
# Requisição com nova tentativa (espera cada vez mais quando dá 429)
# ---------------------------------------------------------------------------
def get_json(url, tentativas=5):
    espera = 2
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=CABECALHO)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and i < tentativas - 1:
                print(f"  HTTP {e.code}, tentando de novo em {espera}s...")
                time.sleep(espera)
                espera *= 2
            else:
                raise


# ---------------------------------------------------------------------------
# Open Library
# ---------------------------------------------------------------------------
def buscar_openlibrary(editora, limite=LIVROS_POR_EDITORA):
    params = urllib.parse.urlencode({
        "publisher": editora,
        "language": "por",
        "fields": "key,title,author_name,publisher,subject,first_publish_year",
        "limit": limite,
    })
    dados = get_json(f"https://openlibrary.org/search.json?{params}")
    livros = []
    for d in dados.get("docs", []):
        # pega o nome de editora que contém o termo buscado
        editoras = [p for p in d.get("publisher", [])
                    if editora.lower() in p.lower()]
        livros.append({
            "id": d.get("key", ""),
            "titulo": d.get("title", ""),
            "autores": "; ".join(d.get("author_name", [])),
            "editora": editoras[0] if editoras else editora,
            "categorias": "; ".join(d.get("subject", [])[:5]),
            "ano": d.get("first_publish_year", ""),
            "fonte": "openlibrary",
        })
    return livros


# ---------------------------------------------------------------------------
# Google Books (precisa de chave para não tomar 429)
# ---------------------------------------------------------------------------
def buscar_google(editora, chave, limite=LIVROS_POR_EDITORA):
    livros, inicio = [], 0
    while inicio < limite:
        params = urllib.parse.urlencode({
            "q": f"inpublisher:{editora}",
            "langRestrict": "pt",
            "printType": "books",
            "maxResults": 40,
            "startIndex": inicio,
            "key": chave,
        })
        dados = get_json(f"https://www.googleapis.com/books/v1/volumes?{params}")
        itens = dados.get("items", [])
        if not itens:
            break
        for item in itens:
            info = item.get("volumeInfo", {})
            livros.append({
                "id": item["id"],
                "titulo": info.get("title", ""),
                "autores": "; ".join(info.get("authors", [])),
                "editora": info.get("publisher", editora),
                "categorias": "; ".join(info.get("categories", [])),
                "ano": info.get("publishedDate", "")[:4],
                "fonte": "google",
            })
        inicio += 40
        time.sleep(1)
    return livros


# ---------------------------------------------------------------------------
def main():
    chave = os.environ.get("GOOGLE_BOOKS_API_KEY")
    print("Fonte:", "Google Books" if chave else "Open Library")

    todos, vistos = [], set()
    for editora in EDITORAS:
        print(f"Buscando {editora}...")
        try:
            if chave:
                livros = buscar_google(editora, chave)
            else:
                livros = buscar_openlibrary(editora)
        except Exception as e:
            print(f"  erro em {editora}: {e}")
            continue

        novos = 0
        for livro in livros:
            k = livro["titulo"].lower().strip()
            if k and k not in vistos:      # remove edições repetidas
                vistos.add(k)
                todos.append(livro)
                novos += 1
        print(f"  {novos} livros")
        time.sleep(1)  # pausa entre editoras

    if not todos:
        print("Nenhum livro encontrado. Verifique a internet ou tente mais tarde.")
        return

    with open("livros.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(todos)
    print(f"\n{len(todos)} livros salvos em livros.csv")


if __name__ == "__main__":
    main()
