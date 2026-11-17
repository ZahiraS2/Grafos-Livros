"""Janela local do recomendador. Execute: python interface_grafica.py."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def abrir_interface(tk, ttk, messagebox, servico):
    class Aplicacao(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Entre livros • Recomendador com grafos")
            self.geometry("1180x780")
            self.minsize(960, 680)
            self.configure(bg="#f4f1eb")
            self.executor = ThreadPoolExecutor(max_workers=1)
            self.futuro = None
            self.notas = {}
            self.protocol("WM_DELETE_WINDOW", self.fechar)
            estilo = ttk.Style(self)
            estilo.theme_use("clam")
            estilo.configure("TFrame", background="#f4f1eb")
            estilo.configure("TLabel", background="#f4f1eb", foreground="#253b38", font=("Segoe UI", 10))
            estilo.configure("TButton", font=("Segoe UI", 10), padding=8)
            estilo.configure("Acao.TButton", background="#236457", foreground="white", font=("Segoe UI", 11, "bold"), padding=13)
            estilo.map("Acao.TButton", background=[("active", "#194d42"), ("disabled", "#859e97")])
            estilo.configure("TNotebook", background="#f4f1eb", borderwidth=0)
            estilo.configure("TNotebook.Tab", padding=(10, 10), font=("Segoe UI", 10))
            estilo.configure("Treeview", font=("Segoe UI", 10), rowheight=29)
            estilo.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
            estilo.configure("TCheckbutton", background="#f4f1eb", font=("Segoe UI", 11), padding=4)
            self.montar()

        def texto(self, pai, texto, tamanho=10, cor="#253b38", negrito=False, **kwargs):
            return tk.Label(pai, text=texto, bg=pai.cget("bg"), fg=cor,
                            font=("Segoe UI", tamanho, "bold" if negrito else "normal"), **kwargs)

        def montar(self):
            cabecalho = tk.Frame(self, bg="#173e36", padx=28, pady=22)
            cabecalho.pack(fill="x")
            self.texto(cabecalho, "ENTRE LIVROS", 11, "#b9d6c6", True).pack(anchor="w")
            self.texto(cabecalho, "Sua próxima leitura começa aqui.", 25, "white", True).pack(anchor="w", pady=(6, 4))
            self.texto(cabecalho, f"{len(servico.livros)} livros  •  {len(servico.usuarios)} perfis  •  Recomendações com grafos", 10, "#d4e2db").pack(anchor="w")
            corpo = tk.Frame(self, bg="#f4f1eb", padx=22, pady=22)
            corpo.pack(fill="both", expand=True)
            corpo.columnconfigure(0, weight=0, minsize=385)
            corpo.columnconfigure(1, weight=1)
            corpo.rowconfigure(0, weight=1)
            esquerda = tk.Frame(corpo, bg="#f4f1eb", width=385)
            esquerda.grid(row=0, column=0, sticky="nsew", padx=(0, 22))
            esquerda.grid_propagate(False)
            self.texto(esquerda, "Como você quer descobrir livros?", 14, negrito=True).pack(anchor="w", pady=(0, 12))
            self.abas = ttk.Notebook(esquerda)
            self.abas.pack(fill="both", expand=True)
            perfil, generos, notas = (ttk.Frame(self.abas, padding=12) for _ in range(3))
            self.abas.add(perfil, text="Um perfil")
            self.abas.add(generos, text="Meus gêneros")
            self.abas.add(notas, text="Minhas notas")
            self.montar_perfil(perfil)
            self.montar_generos(generos)
            self.montar_notas(notas)
            self.botao = ttk.Button(esquerda, text="Encontrar minhas próximas leituras →", style="Acao.TButton", command=self.recomendar)
            self.botao.pack(fill="x", pady=(16, 7))
            self.progresso = ttk.Progressbar(esquerda, mode="indeterminate")
            self.progresso.pack(fill="x")
            self.status = tk.StringVar(value="Escolha uma aba e descubra até cinco livros.")
            ttk.Label(esquerda, textvariable=self.status, wraplength=365).pack(anchor="w", pady=(8, 0))
            direita = tk.Frame(corpo, bg="#f4f1eb")
            direita.grid(row=0, column=1, sticky="nsew")
            self.texto(direita, "Escolhidos para você", 19, negrito=True).pack(anchor="w")
            self.contexto = tk.StringVar(value="Até cinco sugestões, com no máximo dois livros por autor.")
            ttk.Label(direita, textvariable=self.contexto, wraplength=560).pack(anchor="w", pady=(4, 14))
            area = tk.Frame(direita, bg="#f4f1eb")
            area.pack(fill="both", expand=True)
            self.canvas = tk.Canvas(area, bg="#f4f1eb", highlightthickness=0)
            barra = ttk.Scrollbar(area, orient="vertical", command=self.canvas.yview)
            self.canvas.configure(yscrollcommand=barra.set)
            barra.pack(side="right", fill="y")
            self.canvas.pack(side="left", fill="both", expand=True)
            self.cartoes = tk.Frame(self.canvas, bg="#f4f1eb")
            self.janela_cartoes = self.canvas.create_window((0, 0), window=self.cartoes, anchor="nw")
            self.cartoes.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
            self.canvas.bind("<Configure>", self.redimensionar)
            self.bind_all("<MouseWheel>", self.rolar, add="+")
            self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-3, "units"))
            self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(3, "units"))
            vazio = tk.Frame(self.cartoes, bg="#e7ece5", padx=24, pady=32)
            vazio.pack(fill="x", pady=(10, 0))
            self.texto(vazio, "Um livro pode levar a outro.", 18, negrito=True).pack(anchor="w")
            self.texto(vazio, "Escolha um perfil, conte seus gêneros favoritos ou dê notas aos livros que já leu. Depois, clique no botão para ver as sugestões.", 11, wraplength=450, justify="left").pack(anchor="w", pady=(12, 0))

        def montar_perfil(self, pai):
            ttk.Label(pai, text="Explore as recomendações de um perfil.", wraplength=330).pack(anchor="w", pady=(0, 12))
            self.usuario = tk.StringVar(value=servico.usuarios[0])
            combo = ttk.Combobox(pai, textvariable=self.usuario, values=servico.usuarios, state="readonly")
            combo.pack(fill="x")
            combo.bind("<<ComboboxSelected>>", lambda e: self.atualizar_historico())
            ttk.Label(pai, text="Livros já avaliados", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(16, 6))
            self.historico = self.tabela(pai, ("titulo", "nota"), ("Livro", "Nota"), height=8)
            self.atualizar_historico()

        def tabela(self, pai, colunas, titulos, height=5):
            moldura = ttk.Frame(pai)
            moldura.pack(fill="both", expand=True)
            tabela = ttk.Treeview(moldura, columns=colunas, show="headings", selectmode="browse", height=height)
            for c, titulo in zip(colunas, titulos):
                tabela.heading(c, text=titulo)
                tabela.column(c, width=235 if c == "titulo" else 48, minwidth=40,
                               stretch=c == "titulo")
            barra = ttk.Scrollbar(moldura, orient="vertical", command=tabela.yview)
            tabela.configure(yscrollcommand=barra.set)
            barra.pack(side="right", fill="y")
            tabela.pack(side="left", fill="both", expand=True)
            return tabela

        def atualizar_historico(self):
            self.historico.delete(*self.historico.get_children())
            for lid, nota in sorted(servico.historico(self.usuario.get()), key=lambda x: -x[1]):
                self.historico.insert("", "end", values=(servico.livros[lid]["titulo"], f"{nota}/5"))

        def montar_generos(self, pai):
            ttk.Label(pai, text="Ainda não avaliou livros? Escolha dois ou três gêneros de que gosta.", wraplength=330).pack(anchor="w", pady=(0, 12))
            area = ttk.Frame(pai)
            area.pack(fill="both", expand=True)
            canvas = tk.Canvas(area, bg="#f4f1eb", highlightthickness=0, width=280)
            barra = ttk.Scrollbar(area, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=barra.set)
            barra.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            lista = ttk.Frame(canvas)
            janela = canvas.create_window((0, 0), window=lista, anchor="nw")
            lista.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.bind("<Configure>", lambda e: canvas.itemconfigure(janela, width=e.width))
            self.generos = {}
            for genero in servico.generos:
                valor = tk.BooleanVar()
                self.generos[genero] = valor
                ttk.Checkbutton(lista, text=genero, variable=valor).pack(anchor="w")

        def montar_notas(self, pai):
            ttk.Label(pai, text="Busque um livro e conte o que achou dele. As notas ficam apenas nesta sessão.", wraplength=330).pack(anchor="w", pady=(0, 10))
            self.busca = tk.StringVar()
            entrada = ttk.Entry(pai, textvariable=self.busca)
            entrada.pack(fill="x", pady=(0, 6))
            self.busca.trace_add("write", lambda *_: self.filtrar())
            self.catalogo = self.tabela(pai, ("titulo",), ("Título · autor",), height=4)
            linha = ttk.Frame(pai)
            linha.pack(fill="x", pady=8)
            ttk.Label(linha, text="Minha nota:").pack(side="left")
            self.nota = tk.StringVar(value="5")
            ttk.Combobox(linha, textvariable=self.nota, values=[1, 2, 3, 4, 5], state="readonly", width=3).pack(side="left", padx=8)
            ttk.Button(linha, text="Adicionar", command=self.adicionar_nota).pack(side="right")
            self.avaliados = self.tabela(pai, ("titulo", "nota"), ("Minhas avaliações", "Nota"), height=3)
            ttk.Button(pai, text="Remover avaliação selecionada", command=self.remover_nota).pack(fill="x", pady=(6, 0))
            self.filtrar()

        def filtrar(self):
            self.catalogo.delete(*self.catalogo.get_children())
            for lid in servico.buscar_livros(self.busca.get()):
                livro = servico.livros[lid]
                self.catalogo.insert("", "end", iid=lid, values=(f'{livro["titulo"]} · {livro["autor"]}',))

        def adicionar_nota(self):
            selecao = self.catalogo.selection()
            if not selecao:
                messagebox.showinfo("Escolha um livro", "Selecione um livro na lista de busca.", parent=self)
                return
            lid = selecao[0]
            self.notas[lid] = int(self.nota.get())
            if self.avaliados.exists(lid):
                self.avaliados.delete(lid)
            self.avaliados.insert("", "end", iid=lid, values=(servico.livros[lid]["titulo"], f"{self.notas[lid]}/5"))

        def remover_nota(self):
            for lid in self.avaliados.selection():
                del self.notas[lid]
                self.avaliados.delete(lid)

        def recomendar(self):
            if self.futuro is not None:
                return
            aba = self.abas.index(self.abas.select())
            modo = ("usuario", "generos", "notas")[aba]
            generos = [g for g, valor in self.generos.items() if valor.get()]
            if modo == "generos" and len(generos) not in (2, 3):
                messagebox.showinfo("Escolha seus gêneros", "Marque dois ou três gêneros favoritos.", parent=self)
                return
            if modo == "notas" and not self.notas:
                messagebox.showinfo("Conte suas leituras", "Adicione pelo menos um livro com sua nota.", parent=self)
                return
            self.destino = {"usuario": f"Sugestões para {self.usuario.get()}",
                            "generos": "Seu ponto de partida: " + ", ".join(generos),
                            "notas": f"Sugestões a partir dos seus {len(self.notas)} livros avaliados"}[modo]
            self.botao.state(["disabled"])
            self.status.set("Procurando conexões entre os livros…")
            self.progresso.start(12)
            self.futuro = self.executor.submit(servico.recomendar, modo, self.usuario.get(), generos, dict(self.notas))
            self.after(80, self.verificar_resultado)

        def verificar_resultado(self):
            if not self.futuro.done():
                self.after(80, self.verificar_resultado)
                return
            futuro, self.futuro = self.futuro, None
            self.progresso.stop()
            self.botao.state(["!disabled"])
            try:
                resultados = futuro.result()
            except Exception as erro:
                self.status.set("Não foi possível gerar as recomendações.")
                messagebox.showerror("Não foi possível recomendar", str(erro), parent=self)
                return
            for filho in self.cartoes.winfo_children():
                filho.destroy()
            self.contexto.set(self.destino)
            for indice, livro in enumerate(resultados, 1):
                cartao = tk.Frame(self.cartoes, bg="white", padx=20, pady=17,
                                  highlightbackground="#dddcd3", highlightthickness=1)
                cartao.pack(fill="x", pady=(0, 12), padx=(0, 4))
                self.texto(cartao, f"LEITURA {indice:02d}", 9, "#397568", True).pack(anchor="w")
                self.texto(cartao, livro["titulo"], 16, negrito=True, wraplength=470, justify="left").pack(anchor="w", pady=(5, 3))
                self.texto(cartao, livro["autor"], 11, "#616b64", wraplength=470, justify="left").pack(anchor="w")
                self.texto(cartao, " · ".join(livro["generos"]), 9, "#397568", wraplength=470).pack(anchor="w", pady=(8, 0))
                motivo = "\n".join("• " + m[:1].upper() + m[1:] for m in livro["motivos"][:2])
                if not motivo:
                    motivo = "Sugerido pelas conexões do grafo entre leitores e livros."
                self.texto(cartao, motivo, 10, "#616b64", wraplength=470, justify="left").pack(anchor="w", pady=(10, 0))
            if not resultados:
                self.texto(self.cartoes, "Nenhuma sugestão disponível. Experimente outros gêneros ou avalie mais livros.", 12, wraplength=470, justify="left").pack(anchor="w", pady=30)
            self.status.set(f"{len(resultados)} sugestões encontradas. Máximo de dois livros por autor.")
            self.canvas.yview_moveto(0)
            self.after_idle(lambda: self.redimensionar(None))

        def redimensionar(self, evento):
            largura = max(250, self.canvas.winfo_width())
            self.canvas.itemconfigure(self.janela_cartoes, width=largura)
            for cartao in self.cartoes.winfo_children():
                for filho in cartao.winfo_children():
                    if isinstance(filho, tk.Label):
                        filho.configure(wraplength=max(180, largura - 50))

        def rolar(self, evento):
            widget = self.winfo_containing(evento.x_root, evento.y_root)
            while widget is not None:
                if widget == self.canvas or widget == self.cartoes:
                    self.canvas.yview_scroll(-1 if evento.delta > 0 else 1, "units")
                    return "break"
                widget = getattr(widget, "master", None)

        def fechar(self):
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.destroy()

    Aplicacao().mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    pasta = Path(__file__).resolve().parent
    parser.add_argument("--livros", type=Path, default=pasta / "livros.csv")
    parser.add_argument("--avaliacoes", type=Path, default=pasta / "avaliacoes.csv")
    args = parser.parse_args()
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        parser.exit(1, "Tkinter não está disponível neste Python. No Windows, habilite Tcl/Tk na instalação do Python; no Linux, instale o pacote python3-tk compatível.\n")
    try:
        from servico_interface import ServicoRecomendacoes
        servico = ServicoRecomendacoes(args.livros, args.avaliacoes)
    except (ImportError, OSError, ValueError, KeyError) as erro:
        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror("Não foi possível abrir o projeto", f"{erro}\n\nConfira os CSVs e execute instalar_dependencias.bat.", parent=raiz)
        raiz.destroy()
        return 1
    abrir_interface(tk, ttk, messagebox, servico)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
