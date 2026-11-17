"""Operações da interface gráfica, independentes de Tkinter."""

from pathlib import Path

from avaliar_recomendador import ler_avaliacoes
from recomendador_v2 import (
    carregar_livros, construir_grafo, explicar, recomendar_por_generos,
    recomendar_ppr, sem_acento,
)


class ServicoRecomendacoes:
    def __init__(self, arquivo_livros=None, arquivo_avaliacoes=None):
        pasta = Path(__file__).resolve().parent
        self.livros = carregar_livros(arquivo_livros or pasta / "livros.csv")
        self.avaliacoes = ler_avaliacoes(arquivo_avaliacoes or pasta / "avaliacoes.csv", self.livros)
        self.grafo = construir_grafo(self.livros, self.avaliacoes)
        self.usuarios = sorted({u for u, _, _ in self.avaliacoes})
        self.generos = sorted(n[7:] for n, d in self.grafo.nodes(data=True)
                              if d["tipo"] == "genero" and self.grafo.degree(n))

    def buscar_livros(self, termo=""):
        termo = sem_acento(termo.strip())
        return sorted((lid for lid, livro in self.livros.items()
                       if termo in sem_acento(livro["titulo"] + " " + livro["autor"])),
                      key=lambda lid: (sem_acento(self.livros[lid]["titulo"]), lid))

    def historico(self, usuario):
        return [(lid, nota) for u, lid, nota in self.avaliacoes if u == usuario]

    def recomendar(self, modo, usuario=None, generos=(), notas=None):
        grafo = self.grafo
        if modo == "usuario":
            if usuario not in self.usuarios:
                raise ValueError("Escolha um usuário da lista.")
            recs = recomendar_ppr(grafo, usuario, max_por_autor=2)
        elif modo == "generos":
            generos = list(dict.fromkeys(generos))
            if len(generos) not in (2, 3) or any(g not in self.generos for g in generos):
                raise ValueError("Escolha dois ou três gêneros da lista.")
            usuario = None
            recs = recomendar_por_generos(grafo, generos, max_por_autor=2)
        elif modo == "notas":
            notas = dict(notas or {})
            if not notas:
                raise ValueError("Adicione pelo menos um livro com sua nota.")
            if any(lid not in self.livros or type(nota) is not int or not 1 <= nota <= 5
                   for lid, nota in notas.items()):
                raise ValueError("Escolha livros do catálogo e notas inteiras de 1 a 5.")
            usuario = "usuario:janela"
            while usuario in grafo:
                usuario += ":novo"
            grafo = construir_grafo(self.livros, self.avaliacoes +
                                     [(usuario, lid, nota) for lid, nota in notas.items()])
            recs = recomendar_ppr(grafo, usuario, max_por_autor=2)
        else:
            raise ValueError("Escolha uma das formas de recomendar.")
        resultados = []
        for lid, score in recs:
            livro = self.livros[lid]
            motivos = explicar(grafo, usuario, lid) if usuario else []
            if not usuario:
                comuns = sorted(set(generos) & set(livro["generos"]))
                motivos = ["Combina com os gêneros escolhidos: " + ", ".join(comuns)] if comuns else []
            resultados.append({"id": lid, **livro, "score": score, "motivos": motivos})
        return resultados
