"""
Recomendação de livros com grafos — versão 2
=============================================

Novidades em relação à versão 1:
  1. Livros reais (livros.csv, gerado por buscar_livros.py)
  2. Grafo HETEROGÊNEO: usuário, livro, autor e gênero
        usuário —(nota)— livro —— autor
                              └── gênero
  3. Recomendação por PageRank PERSONALIZADO (passeio aleatório com
     reinício): explora caminhos de qualquer tamanho dentro do componente
     conectado às sementes. Não alcança componentes desconectados.

Avaliações:
  Se existir avaliacoes.csv (colunas usuario,livro_id,nota), ele é usado.
  Senão, o script SIMULA usuários com gêneros favoritos e salva o
  avaliacoes.csv — depois dá pra trocar por notas reais de colegas.

Uso: python recomendador_v2.py
"""

import csv
import os
import random
import unicodedata
import math
from collections import defaultdict

import networkx as nx

ARQ_LIVROS = "livros.csv"
ARQ_AVALIACOES = "avaliacoes.csv"

# ---------------------------------------------------------------------------
# 1. Normalização de gêneros
#    As categorias da Open Library são bagunçadas ("Fiction, fantasy, general",
#    "Ficção brasileira", "Horror tales"...). Aqui viram poucos gêneros.
# ---------------------------------------------------------------------------
GENEROS = {
    "Fantasia":           ["fantas", "magic", "magia", "dragon", "drag"],
    "Terror":             ["horror", "terror", "ghost", "vampir", "zombi", "macabr"],
    "Suspense/Policial":  ["thriller", "suspens", "mystery", "misterio", "detective",
                           "policial", "crime"],
    "Ficção científica":  ["science fiction", "ficcao cientifica", "dystopi",
                           "distopi", "space", "robot"],
    "Romance":            ["romance", "love", "amor", "romantic"],
    "Jovem adulto":       ["young adult", "juvenil", "juvenile", "teen", "adolesc"],
    "Biografia/História": ["biograph", "biografi", "memoir", "history", "historia"],
    "Autoajuda":          ["self-help", "autoajuda", "success", "motivat", "conduct of life"],
}

# Regras adicionais são opcionais: a configuração base continua reproduzível.
GENEROS_AMPLIADOS = {
    **GENEROS,
    "Fantasia": GENEROS["Fantasia"] + ["fairies", "fairy tales", "mythology", "wizard", "witchcraft"],
    "Ficção científica": GENEROS["Ficção científica"] + ["interplanetary", "star wars"],
    "Autoajuda": GENEROS["Autoajuda"] + ["habit breaking", "time management", "self-actualization", "vocational guidance"],
    "Quadrinhos": ["graphic novel", "comic books", "comic strip", "manga", "cartoons and comics"],
    "Poesia": ["poetry", "poesia", "poem"],
    "Filosofia": ["philosophy", "filosof", "philosoph"],
    "Negócios/Finanças": ["business", "negocios", "accounting", "personal finance", "financas"],
    "Infantil": ["children's fiction", "children's literature", "literatura infantil"],
}


def sem_acento(texto):
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def generos_do_livro(categorias, ampliado=False):
    """Devolve a lista de gêneros (normalizados) de um livro."""
    texto = sem_acento(categorias)
    regras = GENEROS_AMPLIADOS if ampliado else GENEROS
    achados = [g for g, chaves in regras.items()
               if any(ch in texto for ch in chaves)]
    return achados or ["Outros"]


# ---------------------------------------------------------------------------
# 2. Leitura dos dados
# ---------------------------------------------------------------------------
def carregar_livros(arquivo=ARQ_LIVROS, arquivo_generos=None):
    livros = {}
    with open(arquivo, encoding="utf-8-sig") as f:
        for linha in csv.DictReader(f):
            autores = [a.strip() for a in linha["autores"].split(";") if a.strip()]
            livros[linha["id"]] = {
                "titulo": linha["titulo"],
                "autor": autores[0] if autores else "Desconhecido",
                "editora": linha["editora"],
                "generos": ([g.strip() for g in linha.get("generos_revisados", "").split(";") if g.strip()]
                            or generos_do_livro(linha["categorias"])),
            }
    if arquivo_generos:
        with open(arquivo_generos, encoding="utf-8-sig", newline="") as f:
            for linha in csv.DictReader(f):
                generos = [g.strip() for g in linha["generos"].split(";") if g.strip()]
                if linha["livro_id"] not in livros or any(g not in GENEROS_AMPLIADOS for g in generos):
                    raise ValueError("ID ou gênero inválido na revisão de gêneros")
                if generos:
                    livros[linha["livro_id"]]["generos"] = generos
    return livros


def simular_avaliacoes(livros, n_usuarios=30, semente=42):
    """
    Cria usuários fictícios. Cada um tem 1 ou 2 gêneros favoritos:
    lê vários livros desses gêneros (nota alta) e alguns aleatórios
    (nota variada). Isso imita gostos reais e dá estrutura ao grafo.
    """
    rnd = random.Random(semente)
    por_genero = {}
    for lid, l in livros.items():
        for g in l["generos"]:
            por_genero.setdefault(g, []).append(lid)
    generos = [g for g in por_genero if g != "Outros" and len(por_genero[g]) >= 3]

    avaliacoes = []
    for i in range(1, n_usuarios + 1):
        usuario = f"Usuario{i:02d}"
        favoritos = rnd.sample(generos, k=min(len(generos), rnd.choice([1, 2])))
        lidos = set()
        for g in favoritos:
            for lid in rnd.sample(por_genero[g], k=min(len(por_genero[g]), rnd.randint(3, 6))):
                if lid not in lidos:
                    lidos.add(lid)
                    avaliacoes.append((usuario, lid, rnd.choice([4, 5, 5])))
        for lid in rnd.sample(list(livros), k=min(3, len(livros))):
            if lid not in lidos:
                lidos.add(lid)
                avaliacoes.append((usuario, lid, rnd.choice([1, 2, 3, 4])))
    return avaliacoes


def carregar_ou_simular_avaliacoes(livros, arquivo=ARQ_AVALIACOES):
    if os.path.exists(arquivo):
        with open(arquivo, encoding="utf-8") as f:
            return [(l["usuario"], l["livro_id"], int(l["nota"]))
                    for l in csv.DictReader(f) if l["livro_id"] in livros]
    avaliacoes = simular_avaliacoes(livros)
    with open(arquivo, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["usuario", "livro_id", "titulo", "nota"])
        for u, lid, nota in avaliacoes:
            w.writerow([u, lid, livros[lid]["titulo"], nota])
    print(f"(avaliações simuladas salvas em {arquivo})")
    return avaliacoes


# ---------------------------------------------------------------------------
# 3. Grafo heterogêneo
# ---------------------------------------------------------------------------
def construir_grafo(livros, avaliacoes, peso_autor=1.0, peso_genero=1.0,
                    penalizacao_hubs=0.0, normalizar_notas=False):
    if peso_autor < 0 or peso_genero < 0 or not 0 <= penalizacao_hubs <= 1:
        raise ValueError("Pesos devem ser não negativos e penalização deve estar entre 0 e 1")
    avaliacoes = list(avaliacoes)
    por_usuario = defaultdict(list)
    for usuario, lid, nota in avaliacoes:
        if lid not in livros or not 1 <= nota <= 5:
            raise ValueError("Livro ou nota inválidos")
        por_usuario[usuario].append(nota)
    estatisticas = {}
    for u, notas in por_usuario.items():
        media = sum(notas) / len(notas)
        desvio = math.sqrt(sum((n - media) ** 2 for n in notas) / len(notas))
        estatisticas[u] = (media, desvio)
    G = nx.Graph()
    for lid, l in livros.items():
        G.add_node(lid, tipo="livro", titulo=l["titulo"], autor=l["autor"])
        autor = "autor:" + l["autor"]
        G.add_node(autor, tipo="autor")
        if peso_autor > 0:
            G.add_edge(lid, autor, peso=peso_autor, tipo="autor")
        for g in l["generos"]:
            if g == "Outros":           # "Outros" não diz nada sobre o gosto
                continue
            genero = "genero:" + g
            G.add_node(genero, tipo="genero")
            if peso_genero > 0:
                G.add_edge(lid, genero, peso=peso_genero, tipo="genero")

    for usuario, lid, nota in avaliacoes:
        G.add_node(usuario, tipo="usuario")
        # nota baixa ainda indica que leu, mas pesa pouco no passeio
        peso = nota / 5
        if normalizar_notas:
            media, desvio = estatisticas[usuario]
            z = (nota - media) / desvio if desvio else 0
            peso = 1 / (1 + math.exp(-z))
        G.add_edge(usuario, lid, peso=peso, nota=nota, tipo="avaliacao")
    if penalizacao_hubs:
        graus = dict(G.degree())
        for a, b, dados in G.edges(data=True):
            dados["peso"] /= (graus[a] * graus[b]) ** (penalizacao_hubs / 2)
    return G


def contar_tipos(G):
    contagem = {}
    for _, d in G.nodes(data=True):
        contagem[d["tipo"]] = contagem.get(d["tipo"], 0) + 1
    return contagem


# ---------------------------------------------------------------------------
# 4. Recomendação: PageRank personalizado
# ---------------------------------------------------------------------------
def pontuacoes_ppr(G, usuario=None, alpha=0.85, tol=1e-10, max_iter=2000,
                   personalizacao=None, detalhes=None):
    """PageRank por iteração de potência, sem depender de NumPy/SciPy.

    O erro L1 entre iterações deve ser menor que tol. A personalização
    e a redistribuição de vértices sem saída seguem o usuário ou o vetor
    explícito de sementes (usado no início por gêneros).
    """
    if personalizacao is None and usuario not in G:
        raise ValueError(f"Usuário ausente no grafo: {usuario}")
    if not 0 < alpha < 1:
        raise ValueError("alpha deve estar entre 0 e 1")
    personalizacao = {usuario: 1.0} if personalizacao is None else personalizacao
    if (not personalizacao or any(n not in G or not math.isfinite(p) or p < 0
                                  for n, p in personalizacao.items())
            or sum(personalizacao.values()) <= 0):
        raise ValueError("Personalização inválida")
    total = sum(personalizacao.values())
    reinicio = {n: p / total for n, p in personalizacao.items() if p > 0}
    transicoes = {}
    for n in G:
        soma = sum(d.get("peso", 1.0) for d in G[n].values())
        transicoes[n] = [(v, d.get("peso", 1.0) / soma)
                         for v, d in G[n].items()] if soma else []
    pr = dict.fromkeys(G, 0.0)
    pr.update(reinicio)
    for iteracao in range(1, max_iter + 1):
        novo = dict.fromkeys(G, 0.0)
        for n, probabilidade in reinicio.items():
            novo[n] = (1 - alpha) * probabilidade
        sem_saida = 0.0
        for n, vizinhos in transicoes.items():
            massa = alpha * pr[n]
            if not vizinhos:
                sem_saida += massa
            for v, probabilidade in vizinhos:
                novo[v] += massa * probabilidade
        for n, probabilidade in reinicio.items():
            novo[n] += sem_saida * probabilidade
        erro = sum(abs(novo[n] - pr[n]) for n in G)
        pr = novo
        if erro < tol:
            if detalhes is not None:
                detalhes.update(iteracoes=iteracao, erro_l1=erro)
            return pr
    raise nx.PowerIterationFailedConvergence(max_iter)


def selecionar_recomendacoes(G, pontos, lidos=(), k=5, max_por_autor=None):
    if k < 1 or (max_por_autor is not None and max_por_autor < 1):
        raise ValueError("k e limite de autor devem ser positivos")
    lidos = set(lidos)
    candidatos = [(n, s) for n, s in pontos.items()
                  if G.nodes[n]["tipo"] == "livro" and n not in lidos and s > 0]
    candidatos.sort(key=lambda x: (-x[1], x[0]))
    escolhidos, autores = [], defaultdict(int)
    for lid, score in candidatos:
        autor = G.nodes[lid].get("autor", lid)
        if autor == "Desconhecido":
            autor = lid
        if max_por_autor is not None and autores[autor] >= max_por_autor:
            continue
        escolhidos.append((lid, score))
        autores[autor] += 1
        if len(escolhidos) == k:
            break
    return escolhidos


def recomendar_por_generos(G, generos, k=5, alpha=0.85, max_por_autor=2):
    sementes = {"genero:" + g: 1.0 for g in generos}
    if not sementes or any(n not in G for n in sementes):
        raise ValueError("Escolha gêneros presentes no catálogo")
    pontos = pontuacoes_ppr(G, alpha=alpha, personalizacao=sementes)
    return selecionar_recomendacoes(G, pontos, k=k, max_por_autor=max_por_autor)


def recomendar_ppr(G, usuario, k=5, alpha=0.85, max_por_autor=None):
    """
    Passeio aleatório que começa no usuário. A cada passo:
      - com prob. alpha segue uma aresta (proporcional ao peso);
      - com prob. 1-alpha volta para o usuário (reinício).
    Livros muito visitados = "perto" do gosto do usuário.
    Removemos os já lidos e devolvemos os k maiores.
    """
    pr = pontuacoes_ppr(G, usuario, alpha=alpha)
    return selecionar_recomendacoes(G, pr, G.neighbors(usuario), k, max_por_autor)


def explicar(G, usuario, livro):
    """Mostra o que liga o usuário ao livro recomendado."""
    gostou = [l for l in G.neighbors(usuario) if G[usuario][l]["nota"] >= 4]
    vizinhos_livro = set(G.neighbors(livro))
    motivos = []
    for l in gostou:
        comum = vizinhos_livro & set(G.neighbors(l))
        for c in comum:
            tipo = G.nodes[c]["tipo"]
            if tipo == "autor":
                motivos.append(f"mesmo autor de '{G.nodes[l]['titulo']}'")
            elif tipo == "genero":
                motivos.append(f"mesmo gênero ({c[7:]}) de '{G.nodes[l]['titulo']}'")
            elif tipo == "usuario":
                motivos.append(f"{c} leu '{G.nodes[l]['titulo']}' e este")
    return sorted(set(motivos))[:3]


# ---------------------------------------------------------------------------
# 5. Desenho: só o "caminho" entre o usuário e as recomendações
#    Colunas:  usuário | livros que gostou | ligações | recomendados
# ---------------------------------------------------------------------------
CORES = {"usuario": "#4C78A8", "livro": "#F58518", "autor": "#54A24B",
         "genero": "#B279A2", "recomendado": "#E45756"}


def curto(texto, n=28):
    return texto if len(texto) <= n else texto[:n - 1] + "…"


def rotulo(G, n):
    d = G.nodes[n]
    if d["tipo"] == "livro":
        return curto(d["titulo"])
    if d["tipo"] in ("autor", "genero"):
        return curto(n.split(":", 1)[1])
    return n


def desenhar_recomendacao(G, usuario, recomendacoes, arquivo):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    recs = [l for l, _ in recomendacoes]
    gostou = [l for l in G.neighbors(usuario) if G[usuario][l]["nota"] >= 4]

    H = nx.Graph()
    camada = {usuario: 0}
    for l in gostou:
        H.add_edge(usuario, l)
        camada[l] = 1
    for r in recs:
        camada[r] = 3
        H.add_node(r)
        for l in gostou:
            for c in set(G.neighbors(r)) & set(G.neighbors(l)):
                if c == usuario:
                    continue
                camada.setdefault(c, 2)
                H.add_edge(l, c)
                H.add_edge(c, r)
    # livros que gostou mas não ajudaram em nenhuma recomendação: tira
    for l in gostou:
        if H.degree(l) == 1:
            H.remove_node(l)
    nx.set_node_attributes(H, {n: camada[n] for n in H}, "camada")

    pos = nx.multipartite_layout(H, subset_key="camada", align="vertical")
    # espaça as colunas e coloca os rótulos ao lado
    pos = {n: (x * 4, y) for n, (x, y) in pos.items()}

    plt.figure(figsize=(14, max(6, 0.45 * len(H))))
    nomes = {"usuario": "Usuário", "livro": "Livro", "autor": "Autor",
             "genero": "Gênero"}
    for tipo in ("usuario", "livro", "autor", "genero"):
        nos = [n for n in H if G.nodes[n]["tipo"] == tipo and n not in recs]
        nx.draw_networkx_nodes(H, pos, nodelist=nos, node_color=CORES[tipo],
                               node_size=500, label=nomes[tipo])
    nx.draw_networkx_nodes(H, pos, nodelist=recs, node_color=CORES["recomendado"],
                           node_shape="s", node_size=600, label="Recomendado")
    nx.draw_networkx_edges(H, pos, edge_color="#AAAAAA", width=1)
    pos_txt = {n: (x + 0.15, y) for n, (x, y) in pos.items()}
    nx.draw_networkx_labels(H, pos_txt, labels={n: rotulo(G, n) for n in H},
                            font_size=8, horizontalalignment="left")

    for x, titulo in zip([0, 1, 2, 3],
                         ["Usuário", "Gostou de", "Ligação\n(autor/gênero/leitor)",
                          "Recomendado"]):
        xs = [pos[n][0] for n in H if camada[n] == x]
        if xs:
            plt.text(xs[0], max(y for _, y in pos.values()) + 0.12, titulo,
                     ha="center", fontsize=10, fontweight="bold")

    plt.title(f"Por que estes livros foram recomendados para {usuario}", pad=25)
    plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=5,
               frameon=False, markerscale=0.6)
    plt.axis("off")
    plt.margins(x=0.25)
    plt.tight_layout()
    plt.savefig(arquivo, dpi=150, bbox_inches="tight")
    plt.close()


# ---------------------------------------------------------------------------
# 6. Execução
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    livros = carregar_livros()
    avaliacoes = carregar_ou_simular_avaliacoes(livros)
    G = construir_grafo(livros, avaliacoes)

    print(f"Vértices: {G.number_of_nodes()}  {contar_tipos(G)}")
    print(f"Arestas:  {G.number_of_edges()}\n")

    usuarios = sorted(n for n, d in G.nodes(data=True) if d["tipo"] == "usuario")
    for u in usuarios[:3]:                       # mostra 3 usuários de exemplo
        print(f"=== {u} gostou de:")
        for l in G.neighbors(u):
            if G[u][l]["nota"] >= 4:
                print(f"    {G.nodes[l]['titulo']}  {livros[l]['generos']}")
        print("  Recomendações:")
        recs = recomendar_ppr(G, u)
        arquivo = f"recomendacao_{u}.png"
        desenhar_recomendacao(G, u, recs, arquivo)
        print(f"  (desenho salvo em {arquivo})")
        for livro, score in recs:
            print(f"    {G.nodes[livro]['titulo']:<45} {score:.4f}")
            for m in explicar(G, u, livro):
                print(f"        porque: {m}")
        print()
