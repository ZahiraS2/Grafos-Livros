"""Compara melhorias isoladas e mede tempo com 30, 300 e 3000 usuários."""

import argparse
import json
import platform
import statistics
import time
from collections import defaultdict
from pathlib import Path

import networkx as nx

from avaliar_recomendador import (
    ler_avaliacoes, metricas, recomendar_caminhos, recomendar_jaccard,
    salvar_csv, separar_treino_teste,
)
from recomendador_v2 import (
    carregar_livros, construir_grafo, pontuacoes_ppr, recomendar_ppr,
    selecionar_recomendacoes, simular_avaliacoes,
)


CONFIGURACOES = [
    ("Base", {}, {}),
    ("Penalização de hubs", {"penalizacao_hubs": 0.5}, {}),
    ("Pesos autor=2 gênero=0.5", {"peso_autor": 2, "peso_genero": 0.5}, {}),
    ("Notas normalizadas", {"normalizar_notas": True}, {}),
    ("Máximo 2 por autor", {}, {"max_por_autor": 2}),
    ("Combinada", {"peso_autor": 2, "peso_genero": 0.5,
                   "normalizar_notas": True, "penalizacao_hubs": 0.5}, {"max_por_autor": 2}),
]


def comparar(livros, avaliacoes, pasta, sementes):
    resultados = []
    particoes = []
    for semente in sementes:
        treino, teste = separar_treino_teste(avaliacoes, semente)
        if not teste:
            raise ValueError("É necessário pelo menos um usuário com dois positivos")
        for u, ids in sorted(teste.items()):
            particoes.extend({"semente": semente, "usuario": u, "livro_id": lid} for lid in sorted(ids))
        for nome, parametros, selecao in CONFIGURACOES:
            G = construir_grafo(livros, treino, **parametros)
            for u, escondidos in sorted(teste.items()):
                if any(G.has_edge(u, lid) for lid in escondidos):
                    raise AssertionError("Vazamento de treino/teste")
                inicio = time.perf_counter()
                recs = recomendar_ppr(G, u, **selecao)
                duracao = time.perf_counter() - inicio
                resultados.append({
                    "semente": semente, "usuario": u, "configuracao": nome,
                    **metricas(recs, escondidos, livros), "tempo_ms": duracao * 1000,
                    "escondidos": len(escondidos),
                    "livros_recomendados": ";".join(lid for lid, _ in recs),
                })
        print(f"Melhorias: semente {semente} concluída", flush=True)
    salvar_csv(pasta / "melhorias_por_usuario.csv", resultados)
    salvar_csv(pasta / "particoes_teste.csv", particoes)
    resumo = []
    for nome, parametros, selecao in CONFIGURACOES:
        linhas = [r for r in resultados if r["configuracao"] == nome]
        medias_sementes = [statistics.mean(r["precisao_5"] for r in linhas if r["semente"] == s)
                           for s in sementes]
        resumo.append({"configuracao": nome, "casos": len(linhas),
                       **{campo: statistics.mean(r[campo] for r in linhas) for campo in (
                           "precisao_5", "recall_5", "hit_5", "autores_distintos", "recomendacoes", "tempo_ms")},
                       "desvio_entre_sementes": statistics.stdev(medias_sementes) if len(sementes) > 1 else 0})
    salvar_csv(pasta / "melhorias.csv", resumo)
    return resumo


def medir_escalabilidade(livros, pasta, tamanhos=(30, 300, 3000), repeticoes=3):
    linhas = []
    for quantidade in tamanhos:
        notas = simular_avaliacoes(livros, n_usuarios=quantidade, semente=42)
        inicio = time.perf_counter()
        G = construir_grafo(livros, notas)
        construcao = (time.perf_counter() - inicio) * 1000
        usuarios = sorted({u for u, _, _ in notas})[:3]
        metodos = [("Caminhos de tamanho 3", recomendar_caminhos), ("Jaccard", recomendar_jaccard),
                   ("PageRank", None)]
        for nome, funcao in metodos:
            for repeticao in range(repeticoes):
                for u in usuarios:
                    detalhes = {}
                    inicio = time.perf_counter()
                    if funcao:
                        recs = funcao(G, u)
                    else:
                        pontos = pontuacoes_ppr(G, u, detalhes=detalhes)
                        recs = selecionar_recomendacoes(G, pontos, G[u])
                    tempo = (time.perf_counter() - inicio) * 1000
                    linhas.append({"usuarios": quantidade, "vertices": len(G), "arestas": G.number_of_edges(),
                                   "avaliacoes": len(notas), "metodo": nome, "usuario": u,
                                   "repeticao": repeticao + 1, "tempo_ms": tempo,
                                   "iteracoes": detalhes.get("iteracoes", ""),
                                   "construcao_grafo_ms": construcao, "recomendacoes": len(recs)})
            print(f"Desempenho: {quantidade} usuários, {nome} concluído", flush=True)
    salvar_csv(pasta / "tempos_individuais.csv", linhas)
    grupos = defaultdict(list)
    for linha in linhas:
        grupos[linha["usuarios"], linha["metodo"]].append(linha)
    resumo = []
    for (usuarios, metodo), grupo in grupos.items():
        tempos = [l["tempo_ms"] for l in grupo]
        resumo.append({"usuarios": usuarios, "metodo": metodo, "vertices": grupo[0]["vertices"],
                       "arestas": grupo[0]["arestas"], "medicoes": len(grupo),
                       "mediana_ms": statistics.median(tempos), "min_ms": min(tempos), "max_ms": max(tempos),
                       "iteracoes_media": statistics.mean(l["iteracoes"] for l in grupo) if metodo == "PageRank" else ""})
    salvar_csv(pasta / "escalabilidade.csv", resumo)
    return resumo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--livros", type=Path, default=Path("livros.csv"))
    parser.add_argument("--avaliacoes", type=Path, default=Path("avaliacoes.csv"))
    parser.add_argument("--generos", type=Path)
    parser.add_argument("--saida", type=Path, default=Path("resultados_melhorias"))
    parser.add_argument("--sementes", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    parser.add_argument("--repeticoes", type=int, default=3)
    args = parser.parse_args()
    if args.repeticoes < 1:
        parser.error("repeticoes deve ser positivo")
    args.saida.mkdir(parents=True, exist_ok=True)
    livros = carregar_livros(args.livros, args.generos)
    avaliacoes = ler_avaliacoes(args.avaliacoes, livros)
    resumo = comparar(livros, avaliacoes, args.saida, args.sementes)
    tempos = medir_escalabilidade(livros, args.saida, repeticoes=args.repeticoes)
    melhor = max(resumo, key=lambda r: r["precisao_5"])
    linhas = ["# Experimentos com as melhorias", "",
              "Todos os métodos abaixo usam PageRank com alpha=0,85 e as mesmas partições. O grafo de cada configuração é reconstruído somente com notas de treino. Estatísticas para normalização e graus para penalização são calculados no treino, sem acessar as notas escondidas.", "",
              f"Sementes: {args.sementes}. A base preserva os pesos anteriores. Cada linha isolada muda uma opção; a combinada ativa todas as opções.", "",
              "| Configuração | Precisão@5 | Recall@5 | Hit@5 | Autores distintos | Recomendações |",
              "|---|---:|---:|---:|---:|---:|"]
    for r in resumo:
        linhas.append(f'| {r["configuracao"]} | {r["precisao_5"]:.2%} | {r["recall_5"]:.2%} | {r["hit_5"]:.2%} | {r["autores_distintos"]:.2f} | {r["recomendacoes"]:.2f} |')
    linhas += ["", f'Maior precisão observada: {melhor["configuracao"]}. Não é prova de superioridade estatística nem validação com leitores reais. A configuração combinada é experimental e não substitui automaticamente a base.', "",
               "## Definições", "",
               "- Hubs: peso de cada aresta dividido por `(grau(a) × grau(b))^(beta/2)`, com beta=0,5. O grau é estrutural, sem peso, calculado antes da transformação.",
               "- Tipos de aresta: usuário–livro mantém seu peso; livro–autor=2 e livro–gênero=0,5 no experimento de pesos.",
               "- Normalização: z=(nota−média do usuário)/desvio populacional; peso=1/(1+exp(−z)). Desvio zero resulta em peso 0,5. Nenhum peso fica negativo; a nota original permanece armazenada.",
               "- Diversidade: percorre a classificação e aceita no máximo dois livros por autor. Não preenche com livros de pontuação zero nem relaxa o limite; pode devolver menos de cinco.", "",
               "## Escalabilidade", "",
               "As medições abaixo usam dados simulados, catálogo fixo, configuração base, alpha=0,85 e os três primeiros usuários em ordem alfabética, repetidos três vezes por padrão. Tempos incluem uma recomendação completa, sem construir o grafo. A construção é registrada separadamente no CSV. Não são avaliações de qualidade nem testes de todos os usuários; não há aquecimento separado.", "",
               "| Usuários | Método | Vértices | Arestas | Tempo mediano (ms) | Iterações médias |",
               "|---:|---|---:|---:|---:|---:|"]
    for r in tempos:
        linhas.append(f'| {r["usuarios"]} | {r["metodo"]} | {r["vertices"]} | {r["arestas"]} | {r["mediana_ms"]:.2f} | {r["iteracoes_media"]} |')
    linhas += ["", "## Complexidade", "",
               "Considere V vértices, E arestas, T iterações, U usuários, L(u) livros lidos e C candidatos.", "",
               "- Construção do grafo e transformação dos pesos: O(V+E) em tempo e memória.",
               "- PageRank: O(T(V+E)) para as iterações e O(V+E) de memória. Ordenar candidatos custa O(C log C), seguido de O(C) para a diversidade.",
               "- Caminhos de tamanho 3: visita, para cada livro de L(u), cada outro leitor e os livros desse leitor. O custo da contagem é proporcional à soma desses graus; repetir leitores em vários livros repete trabalho. O pior caso é O(|L(u)| × U × número de livros), além da ordenação de candidatos.",
               "- Jaccard: constrói os conjuntos de leituras e suas interseções/uniões para cada outro usuário. Nesta implementação, O(U × |L(u)| + soma_v |L(v)|), além da ordenação; memória auxiliar proporcional às leituras e aos candidatos.", "",
               "O pior caso não determina sozinho o método mais rápido neste catálogo. Os tempos dependem do grau, do tamanho do grafo, da convergência e do ambiente. Aumentar alpha pode aumentar o número de iterações.", "",
               "Os CSVs contêm todos os casos, partições, configurações agregadas e tempos individuais. Use novas avaliações para validar qualquer configuração escolhida nestes resultados."]
    (args.saida / "relatorio.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    import hashlib
    arquivos = [args.livros, args.avaliacoes] + ([args.generos] if args.generos else [])
    registro = {"python": platform.python_version(), "networkx": nx.__version__, "sementes": args.sementes,
                "repeticoes": args.repeticoes, "configuracoes": CONFIGURACOES,
                "sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in arquivos}}
    (args.saida / "execucao.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Experimentos concluídos: {args.saida / 'relatorio.md'}", flush=True)


if __name__ == "__main__":
    main()
