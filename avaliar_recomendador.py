"""Avaliação reproduzível e análise do grafo. Uso: python avaliar_recomendador.py."""

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import time
from collections import Counter, defaultdict
from html import escape
from pathlib import Path

import networkx as nx

from recomendador_v2 import (
    carregar_livros, construir_grafo, contar_tipos, recomendar_ppr,
    simular_avaliacoes,
)


def ler_avaliacoes(arquivo, livros):
    """Rejeita dados ambíguos em vez de alterar silenciosamente o experimento."""
    avaliacoes, vistos = [], set()
    with open(arquivo, encoding="utf-8-sig", newline="") as f:
        for numero, linha in enumerate(csv.DictReader(f), 2):
            usuario, lid = linha["usuario"].strip(), linha["livro_id"]
            nota = int(linha["nota"])
            if not usuario or lid not in livros or not 1 <= nota <= 5:
                raise ValueError(f"Avaliação inválida na linha {numero}")
            if (usuario, lid) in vistos:
                raise ValueError(f"Avaliação repetida na linha {numero}")
            vistos.add((usuario, lid))
            avaliacoes.append((usuario, lid, nota))
    if not avaliacoes:
        raise ValueError("Nenhuma avaliação disponível")
    return avaliacoes


def separar_treino_teste(avaliacoes, semente, fracao=0.2):
    """Esconde 20% dos positivos (nota >= 4), preservando um positivo no treino."""
    positivos = defaultdict(list)
    for u, lid, nota in avaliacoes:
        if nota >= 4:
            positivos[u].append(lid)
    rnd, teste = random.Random(semente), {}
    for u in sorted(positivos):
        ids = sorted(positivos[u])
        if len(ids) >= 2:
            quantidade = min(len(ids) - 1, max(1, math.ceil(fracao * len(ids))))
            teste[u] = set(rnd.sample(ids, quantidade))
    treino = [(u, lid, nota) for u, lid, nota in avaliacoes
              if lid not in teste.get(u, set())]
    return treino, teste


def recomendar_caminhos(G, usuario, k=5):
    """Referência colaborativa: conta caminhos simples usuário–livro–usuário–livro.

    Usa todas as avaliações como leituras, sem pesos. Não reproduz uma v1 ausente.
    """
    lidos, pontos = set(G[usuario]), Counter()
    for livro in sorted(lidos):
        for vizinho in sorted(G[livro]):
            if vizinho == usuario or G.nodes[vizinho]["tipo"] != "usuario":
                continue
            for candidato in G[vizinho]:
                if candidato not in lidos:
                    pontos[candidato] += 1
    return sorted(pontos.items(), key=lambda par: (-par[1], par[0]))[:k]


def recomendar_jaccard(G, usuario, k=5):
    """Jaccard entre conjuntos de livros lidos; soma similaridades dos leitores.

    Para cada outro usuário v: |L(u) ∩ L(v)| / |L(u) ∪ L(v)|.
    Cada livro ainda não lido recebe a soma dos Jaccards de seus leitores.
    """
    lidos, pontos = set(G[usuario]), defaultdict(float)
    for v, dados in G.nodes(data=True):
        if v == usuario or dados["tipo"] != "usuario":
            continue
        outros = set(G[v])
        similaridade = len(lidos & outros) / len(lidos | outros)
        if similaridade:
            for lid in outros - lidos:
                pontos[lid] += similaridade
    return sorted(pontos.items(), key=lambda par: (-par[1], par[0]))[:k]


def metricas(recomendacoes, escondidos, livros, k=5):
    ids = [lid for lid, _ in recomendacoes]
    acertos = len(set(ids) & escondidos)
    return {
        "acertos": acertos,
        "precisao_5": acertos / k,
        "recall_5": acertos / len(escondidos),
        "hit_5": float(acertos > 0),
        "recomendacoes": len(ids),
        "autores_distintos": len({livros[lid]["autor"] for lid in ids}),
    }


def salvar_csv(arquivo, linhas):
    with open(arquivo, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)


def avaliar(livros, avaliacoes, sementes, pasta):
    resultados, particoes = [], []
    for semente in sementes:
        treino, teste = separar_treino_teste(avaliacoes, semente)
        if not teste:
            raise ValueError("Nenhum usuário tem dois positivos para avaliação")
        G = construir_grafo(livros, treino)
        for u, ids in sorted(teste.items()):
            for lid in sorted(ids):
                assert not G.has_edge(u, lid), "Vazamento do teste para o treino"
                particoes.append({"semente": semente, "usuario": u, "livro_id": lid})
        metodos = [
            ("Caminhos de tamanho 3", recomendar_caminhos, {}),
            ("Jaccard", recomendar_jaccard, {}),
            *[("PageRank", recomendar_ppr, {"alpha": a}) for a in (0.5, 0.7, 0.85, 0.95)],
        ]
        for nome, funcao, parametros in metodos:
            for u, ids in sorted(teste.items()):
                inicio = time.perf_counter()
                recs = funcao(G, u, **parametros)
                duracao = time.perf_counter() - inicio
                assert not set(lid for lid, _ in recs) & set(G[u])
                resultados.append({
                    "semente": semente, "usuario": u, "metodo": nome,
                    "alpha": parametros.get("alpha", ""), "escondidos": len(ids),
                    **metricas(recs, ids, livros), "tempo_ms": duracao * 1000,
                    "livros_recomendados": ";".join(lid for lid, _ in recs),
                })
        print(f"Semente {semente}: {len(teste)} usuários avaliados", flush=True)
    salvar_csv(pasta / "avaliacao_por_usuario.csv", resultados)
    salvar_csv(pasta / "particoes_teste.csv", particoes)
    grupos = defaultdict(list)
    for r in resultados:
        grupos[r["metodo"], r["alpha"]].append(r)
    resumo = []
    for (metodo, alpha), linhas in grupos.items():
        por_semente = defaultdict(list)
        for r in linhas:
            por_semente[r["semente"]].append(r["precisao_5"])
        medias = [statistics.mean(v) for v in por_semente.values()]
        resumo.append({
            "metodo": metodo, "alpha": alpha, "casos": len(linhas),
            **{campo: statistics.mean(r[campo] for r in linhas) for campo in (
                "precisao_5", "recall_5", "hit_5", "recomendacoes",
                "autores_distintos", "tempo_ms")},
            "desvio_precisao_entre_sementes": statistics.stdev(medias) if len(medias) > 1 else 0,
        })
    salvar_csv(pasta / "comparacao.csv", resumo)
    return resumo


def grafico_comparacao(resumo, arquivo):
    partes = ['<svg xmlns="http://www.w3.org/2000/svg" width="950" height="420" viewBox="0 0 950 420">',
              '<rect width="950" height="420" fill="white"/>',
              '<text x="25" y="30" font-size="20">Precisão@5 média — mesmas partições para todos os métodos</text>']
    for i, r in enumerate(resumo):
        y = 65 + i * 52
        nome = r["metodo"] + (f' α={r["alpha"]}' if r["alpha"] != "" else "")
        largura = 500 * r["precisao_5"]
        partes.extend([
            f'<text x="20" y="{y + 20}" font-size="16">{escape(nome)}</text>',
            f'<rect x="260" y="{y}" width="500" height="28" fill="#edf1f5"/>',
            f'<rect x="260" y="{y}" width="{largura}" height="28" fill="#3976b5"/>',
            f'<text x="775" y="{y + 20}" font-size="16">{r["precisao_5"]:.1%}</text>',
        ])
    partes.append('<text x="25" y="405" font-size="14">Escala de 0 a 100%. As barras não representam intervalos de confiança.</text></svg>')
    arquivo.write_text("\n".join(partes), encoding="utf-8")


def analisar_grafo(G, livros, pasta):
    comunidades = nx.community.louvain_communities(G, weight="peso", seed=42)
    comunidades.sort(key=lambda c: (-len(c), min(c)))
    grau = nx.degree_centrality(G)
    maiores = sorted((n for n in G if G.nodes[n]["tipo"] == "livro"),
                     key=lambda n: (-grau[n], n))[:10]
    componentes = sorted((len(c) for c in nx.connected_components(G)), reverse=True)
    principal = max(nx.connected_components(G), key=len)
    comunidades_principal = [c & principal for c in comunidades if c & principal]
    dados = {
        "vertices": len(G), "arestas": G.number_of_edges(), "tipos": contar_tipos(G),
        "grau_medio": sum(d for _, d in G.degree()) / len(G),
        "densidade": nx.density(G), "componentes_conexas": len(componentes),
        "tamanhos_componentes": componentes, "vertices_isolados": len(list(nx.isolates(G))),
        "comunidades": len(comunidades),
        "comunidades_no_componente_principal": len(comunidades_principal),
        "modularidade": nx.community.modularity(G, comunidades, weight="peso"),
        "livros_outros": sum(l["generos"] == ["Outros"] for l in livros.values()),
    }
    (pasta / "grafo.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    salvar_csv(pasta / "livros_centrais.csv", [
        {"livro_id": n, "titulo": livros[n]["titulo"], "grau": G.degree(n),
         "centralidade_grau": grau[n]} for n in maiores])
    linhas = []
    for i, comunidade in enumerate(comunidades, 1):
        for n in sorted(comunidade):
            linhas.append({"comunidade": i, "vertice": n, "tipo": G.nodes[n]["tipo"],
                           "titulo": livros[n]["titulo"] if n in livros else ""})
    salvar_csv(pasta / "comunidades.csv", linhas)
    desenhar_comunidades(G.subgraph(principal), comunidades_principal, pasta / "comunidades.svg")
    return dados, maiores


def desenhar_comunidades(G, comunidades, arquivo):
    """SVG vetorial com posições determinísticas; tooltip identifica cada vértice."""
    cores = [f"hsl({i * 137.508 % 360:.1f},65%,38%)" for i in range(len(comunidades))]
    pos, grupos = {}, {}
    rng = random.Random(42)
    altura = max(1030, 920 + math.ceil(len(comunidades) / 4) * 22)
    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{altura}" viewBox="0 0 1200 {altura}">',
              f'<rect width="1200" height="{altura}" fill="white"/>',
              f'<text x="20" y="30" font-size="22">Louvain — maior componente conexo ({len(G)} vértices)</text>',
              '<text x="20" y="55" font-size="14">Cores: comunidades. Passe o mouse nos vértices para identificar. Posições agrupadas por comunidade.</text>']
    raio_grupo = min(115, 550 / max(1, len(comunidades)))
    for i, comunidade in enumerate(comunidades):
        angulo = 2 * math.pi * i / len(comunidades)
        cx, cy = 600 + 320 * math.cos(angulo), 475 + 290 * math.sin(angulo)
        for n in sorted(comunidade):
            a, raio = rng.random() * 2 * math.pi, raio_grupo * math.sqrt(rng.random())
            pos[n] = (cx + raio * math.cos(a), cy + raio * math.sin(a))
            grupos[n] = i
    for a, b in G.edges:
        x1, y1 = pos[a]
        x2, y2 = pos[b]
        partes.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#aaa" stroke-opacity="0.16"/>')
    for n in G:
        x, y = pos[n]
        texto = G.nodes[n].get("titulo", n)
        raio = 5 if G.nodes[n]["tipo"] == "usuario" else 3
        partes.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{raio}" fill="{cores[grupos[n] % len(cores)]}"><title>{escape(str(texto))} ({G.nodes[n]["tipo"]}) — comunidade {grupos[n] + 1}</title></circle>')
    for i, comunidade in enumerate(comunidades):
        x, y = 20 + (i % 4) * 295, 890 + (i // 4) * 22
        partes.append(f'<text x="{x}" y="{y}" font-size="13" fill="{cores[i % len(cores)]}">Comunidade {i + 1}: {len(comunidade)} vértices</text>')
    partes.append('</svg>')
    arquivo.write_text("\n".join(partes), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--livros", type=Path, default=Path("livros.csv"))
    parser.add_argument("--avaliacoes", type=Path, default=Path("avaliacoes.csv"))
    parser.add_argument("--saida", type=Path, default=Path("resultados"))
    parser.add_argument("--sementes", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    args = parser.parse_args()
    livros = carregar_livros(args.livros)
    avaliacoes = ler_avaliacoes(args.avaliacoes, livros)
    args.saida.mkdir(parents=True, exist_ok=True)
    simuladas = sorted(avaliacoes) == sorted(simular_avaliacoes(livros))
    resumo = avaliar(livros, avaliacoes, args.sementes, args.saida)
    grafico_comparacao(resumo, args.saida / "comparacao.svg")
    G = construir_grafo(livros, avaliacoes)
    dados, maiores = analisar_grafo(G, livros, args.saida)
    usuarios = {u for u, _, _ in avaliacoes}
    melhor = max(resumo, key=lambda r: r["precisao_5"])
    linhas = [
        "# Resultados da avaliação do recomendador", "",
        f"Catálogo: {len(livros)} livros. Avaliações: {len(avaliacoes)} de {len(usuarios)} usuários.", "",
        ("As avaliações coincidem exatamente com a simulação padrão do projeto (semente 42)."
         if simuladas else "As avaliações não coincidem com a simulação padrão; isso não comprova origem real."), "",
        "## Protocolo", "",
        "Foram escondidos 20% dos livros com nota 4 ou 5 de cada usuário (arredondamento para cima, mínimo 1), preservando pelo menos um positivo no treino. Usuários com menos de dois positivos não entram nas métricas. As arestas escondidas são removidas antes de construir cada grafo de treino; os metadados dos livros permanecem disponíveis.", "",
        f"Sementes: {args.sementes}. Todos os métodos usam as mesmas partições. O top 5 exclui livros já avaliados no treino; empates são resolvidos pelo ID do livro. Não há preenchimento com candidatos de pontuação zero.", "",
        "Precisão@5 = acertos/5; recall@5 = acertos/positivos escondidos; hit@5 = proporção de casos com algum acerto. Médias por usuário e repetição. O desvio no CSV mede variação entre médias das sementes, sem representar intervalo de confiança; as repetições reutilizam usuários e não são independentes.", "",
        "Caminhos de tamanho 3 conta caminhos usuário–livro–usuário–livro. Jaccard soma similaridades entre conjuntos de leituras dos usuários. Ambos usam todas as notas como leituras, sem pesos. PageRank usa o grafo heterogêneo e os pesos da v2. Portanto, a comparação envolve método e representação, sem isolar o efeito de cada mudança. A v1 original está ausente: caminhos é uma referência implementada aqui, não uma reprodução comprovada da v1.", "",
        "## Comparação", "",
        "| Método | Alpha | Precisão@5 | Recall@5 | Hit@5 | Autores distintos (média) | Tempo médio (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in resumo:
        linhas.append(f'| {r["metodo"]} | {r["alpha"]} | {r["precisao_5"]:.2%} | {r["recall_5"]:.2%} | {r["hit_5"]:.2%} | {r["autores_distintos"]:.2f} | {r["tempo_ms"]:.2f} |')
    linhas.extend([
        "", f'Maior precisão observada: {melhor["metodo"]}, alpha={melhor["alpha"] or "não se aplica"}. Isso é um resultado exploratório; escolher alpha nestes testes requer uma nova avaliação independente antes de afirmar desempenho de generalização.', "",
        "Os tempos incluem o cálculo de cada recomendação, sem construção do grafo, e dependem deste ambiente. Mais autores distintos indica apenas diversidade por autor; alpha maior não garante mais diversidade.", "",
        "## Estrutura e comunidades", "",
        "A análise abaixo usa o grafo completo, separado dos experimentos de treino e teste.", "",
        f'- Vértices: {dados["vertices"]}; por tipo: {dados["tipos"]}.',
        f'- Arestas: {dados["arestas"]}; grau médio: {dados["grau_medio"]:.3f}; densidade: {dados["densidade"]:.5f}.',
        f'- Componentes conexas: {dados["componentes_conexas"]}; maior componente: {dados["tamanhos_componentes"][0]} vértices. Distribuição de tamanhos (tamanho: quantidade): {dict(sorted(Counter(dados["tamanhos_componentes"]).items(), reverse=True))}.',
        f'- Comunidades de Louvain: {dados["comunidades"]}; modularidade ponderada: {dados["modularidade"]:.4f} (semente 42, resolução padrão 1).',
        f'- Comunidades no componente principal: {dados["comunidades_no_componente_principal"]}. As demais pertencem a componentes desconectados; não devem ser interpretadas automaticamente como grupos de gosto.',
        f'- Livros classificados somente como Outros: {dados["livros_outros"]} ({dados["livros_outros"] / len(livros):.1%}).', "",
        "Livros com maior centralidade de grau (quantidade de relações, não qualidade literária):", "",
    ])
    linhas.extend(f'- {livros[n]["titulo"]}: grau {G.degree(n)}.' for n in maiores)
    linhas.extend([
        "", "Louvain encontra grupos estruturais; não comprova que sejam bolhas de gosto. Autores e gêneros também influenciam as comunidades. O SVG mostra somente o maior componente para facilitar a leitura; o CSV inclui todos os vértices. As cores identificam grupos e as posições do SVG foram organizadas por comunidade, sem significado de distância.", "",
        "## Limitações e próximos passos", "",
        "Os itens não avaliados têm relevância desconhecida e são tratados como não acertos. O número pequeno de positivos escondidos limita o máximo de precisão@5 em cada caso. Notas simuladas favorecem padrões de gênero usados na própria geração dos dados; resultados não comprovam qualidade para leitores reais. Coletar notas reais e reservar novos dados para validar a escolha de alpha são próximos passos. O experimento não mede escalabilidade com 300 e 3000 usuários.", "",
        "## Reprodução", "", "```bash", "python avaliar_recomendador.py", "python -m unittest discover -s tests -v", "```", "",
        "Os CSVs registram as partições, recomendações e métricas individuais. Os hashes e as versões estão em `execucao.json`. Os SVGs podem ser abertos no navegador.",
    ])
    (args.saida / "relatorio.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    import platform
    registro = {
        "python": platform.python_version(), "networkx": nx.__version__,
        "sementes": args.sementes, "avaliacoes_iguais_simulacao_padrao": simuladas,
        "sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (args.livros, args.avaliacoes)},
        "comando": "python avaliar_recomendador.py",
    }
    (args.saida / "execucao.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Relatório salvo em {args.saida / 'relatorio.md'}")


if __name__ == "__main__":
    main()
