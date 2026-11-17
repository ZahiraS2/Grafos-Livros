"""Menu de demonstração. Uso: python interface_recomendador.py [--melhorado]."""

import argparse

from avaliar_recomendador import ler_avaliacoes
from recomendador_v2 import (
    carregar_livros, construir_grafo, recomendar_ppr, recomendar_por_generos,
    explicar, sem_acento,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--livros", default="livros.csv")
    parser.add_argument("--avaliacoes", default="avaliacoes.csv")
    parser.add_argument("--generos", help="CSV de gêneros revisados, opcional")
    parser.add_argument("--melhorado", action="store_true", help="Ativa configuração experimental")
    args = parser.parse_args()
    livros = carregar_livros(args.livros, args.generos)
    avaliacoes = ler_avaliacoes(args.avaliacoes, livros)
    config = dict(peso_autor=2, peso_genero=0.5, penalizacao_hubs=0.5,
                  normalizar_notas=True) if args.melhorado else {}
    G = construir_grafo(livros, avaliacoes, **config)
    usuarios = sorted({u for u, _, _ in avaliacoes})
    while True:
        print("\n1 — Escolher usuário\n2 — Sou novo: escolher gêneros\n3 — Marcar livros e notas nesta sessão\n0 — Sair")
        try:
            opcao = input("Opção: ").strip()
            if opcao == "0":
                break
            usuario, grafo = None, G
            if opcao == "1":
                for i, u in enumerate(usuarios, 1):
                    print(f"{i}: {u}")
                indice = int(input("Número do usuário: "))
                if not 1 <= indice <= len(usuarios):
                    raise ValueError("Usuário inválido")
                usuario = usuarios[indice - 1]
                recs = recomendar_ppr(G, usuario, max_por_autor=2)
            elif opcao == "2":
                generos = sorted(n[7:] for n in G if G.nodes[n]["tipo"] == "genero" and G.degree(n))
                for i, genero in enumerate(generos, 1):
                    print(f"{i}: {genero}")
                indices = [int(n.strip()) for n in input("Escolha 2 ou 3 números separados por vírgula: ").split(",")]
                if len(set(indices)) not in (2, 3) or any(i < 1 or i > len(generos) for i in indices):
                    raise ValueError("Escolha 2 ou 3 gêneros diferentes da lista")
                recs = recomendar_por_generos(G, [generos[i - 1] for i in indices])
            elif opcao == "3":
                termo = sem_acento(input("Buscar título/autor (Enter lista todos): "))
                for lid, livro in livros.items():
                    if termo in sem_acento(livro["titulo"] + " " + livro["autor"]):
                        print(f'{lid}: {livro["titulo"]} — {livro["autor"]}')
                entrada = input("Digite ID=nota;ID=nota (notas inteiras de 1 a 5): ")
                marcados = {}
                for item in entrada.split(";"):
                    lid, nota = item.strip().rsplit("=", 1)
                    lid, nota = lid.strip(), int(nota)
                    if lid not in livros or not 1 <= nota <= 5:
                        raise ValueError("Livro ou nota inválidos")
                    marcados[lid] = nota
                usuario = "usuario:sessao"
                while usuario in G:
                    usuario += ":novo"
                grafo = construir_grafo(livros, avaliacoes + [(usuario, lid, n) for lid, n in marcados.items()], **config)
                recs = recomendar_ppr(grafo, usuario, max_por_autor=2)
            else:
                print("Escolha uma opção da lista.")
                continue
            print("\nRecomendações (máximo de dois livros por autor):")
            for lid, score in recs:
                print(f'{livros[lid]["titulo"]} — {livros[lid]["autor"]} ({score:.5f})')
                if usuario:
                    for motivo in explicar(grafo, usuario, lid):
                        print("  Motivo:", motivo)
            if len(recs) < 5:
                print(f"Foram encontrados {len(recs)} candidatos com pontuação positiva dentro do limite por autor.")
        except (ValueError, IndexError) as e:
            print("Entrada inválida:", e)
        except (EOFError, KeyboardInterrupt):
            print("\nMenu encerrado.")
            break


if __name__ == "__main__":
    main()
