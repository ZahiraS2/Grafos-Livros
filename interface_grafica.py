"""Janela local do recomendador. Execute: python interface_grafica.py."""

import argparse
import csv
import random
import struct
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# ── Paleta (a mesma de antes) ────────────────────────────────────────────────
ROXO_ESCURO = "#4b267f"
ROXO_MEDIO = "#603994"
ROXO_VIVO = "#7542b8"
ROXO_CLARO = "#a77add"
LILAS = "#e4d5ff"
LILAS_SUAVE = "#eee6f8"
FUNDO = "#f5f1fb"
TEXTO = "#302442"
TEXTO_SUAVE = "#74677f"
SERIFA = "Georgia"


# ── Cursor de coração ────────────────────────────────────────────────────────
def _dentro_do_coracao(x, y):
    return (x * x + y * y - 1) ** 3 - x * x * y ** 3 <= 0


def _gerar_cur(caminho):
    """Escreve um cursor .cur 32x32 (coração roxo com contorno escuro) para o Windows."""
    n, sub = 32, 4
    contorno, recheio = (0x4B, 0x26, 0x7F), (0xA7, 0x7A, 0xDD)  # RGB
    linhas = []
    for py in range(n):
        linha = bytearray()
        for px in range(n):
            fora = dentro = 0
            for sy in range(sub):
                for sx in range(sub):
                    x = (px + (sx + .5) / sub - 16) / 13.2
                    y = (16 - (py + (sy + .5) / sub)) / 13.2 + 0.1
                    if _dentro_do_coracao(x, y):
                        fora += 1
                        if _dentro_do_coracao(x / 0.78, (y - 0.1) / 0.78 + 0.1):
                            dentro += 1
            total = sub * sub
            if not fora:
                linha += b"\x00\x00\x00\x00"
                continue
            t = dentro / fora
            r, g, b = (round(contorno[i] * (1 - t) + recheio[i] * t) for i in range(3))
            linha += bytes((b, g, r, round(255 * fora / total)))
        linhas.append(bytes(linha))
    pixels = b"".join(reversed(linhas))  # BMP é guardado de baixo para cima
    mascara = bytes(4 * n)
    cabecalho_bmp = struct.pack("<IiiHHIIiiII", 40, n, n * 2, 1, 32, 0,
                                len(pixels) + len(mascara), 0, 0, 0, 0)
    tamanho = len(cabecalho_bmp) + len(pixels) + len(mascara)
    entrada = struct.pack("<BBBBHHII", n, n, 0, 0, 16, 16, tamanho, 22)
    caminho.write_bytes(struct.pack("<HHH", 0, 2, 1) + entrada + cabecalho_bmp + pixels + mascara)


def candidatos_de_cursor():
    """Lista de cursores de coração, do melhor para o pior, conforme o sistema."""
    if sys.platform.startswith("win"):
        try:
            pasta = Path(tempfile.gettempdir()) / "entre_livros_cursor"
            pasta.mkdir(exist_ok=True)
            arquivo = pasta / "coracao.cur"
            _gerar_cur(arquivo)
            caminho = arquivo.as_posix()
            return [f"@{caminho}", f"@{{{caminho}}}", "heart", "hand2"]
        except OSError:
            return ["heart", "hand2"]
    if sys.platform == "darwin":  # o Tk do macOS não aceita cursores personalizados
        return ["pointinghand", "heart", "hand2"]
    return ["heart", "hand2"]  # no Linux o Tk traz um coração nativo


def escolher_cursor(widget):
    for nome in candidatos_de_cursor():
        try:
            widget.configure(cursor=nome)
            return nome
        except Exception:
            continue
    return ""


# ── Interface ────────────────────────────────────────────────────────────────
def abrir_interface(tk, ttk, messagebox, servico):
    from tkinter import font as tkfont

    def retangulo_arredondado(canvas, x1, y1, x2, y2, r=12, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return canvas.create_polygon(pts, smooth=True, **kw)

    def misturar(c1, c2, t):
        a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
        return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))

    class Aplicacao(tk.Tk):
        def __init__(self):
            super().__init__()
            self.cursor = escolher_cursor(self)
            self.title("Entre livros • Recomendador com grafos")
            self.geometry("1240x860")
            self.minsize(1000, 740)
            self.configure(bg=FUNDO)
            self.executor = ThreadPoolExecutor(max_workers=1)
            self.futuro = None
            self.notas = {}
            self.brilhos = []
            self.fase = 0
            self.piscar_id = None
            self.protocol("WM_DELETE_WINDOW", self.fechar)
            self.estilizar()
            self.montar()
            self.aplicar_cursor_em_tudo(self)
            self.piscar_id = self.after(900, self.piscar)

        # ── estilos ──
        def estilizar(self):
            estilo = ttk.Style(self)
            estilo.theme_use("clam")
            estilo.configure("TFrame", background=FUNDO)
            estilo.configure("TLabel", background=FUNDO, foreground=TEXTO, font=("Segoe UI", 10))
            estilo.configure("TButton", font=("Segoe UI", 10), padding=9,
                             background=LILAS_SUAVE, foreground=ROXO_ESCURO, borderwidth=1,
                             bordercolor="#d3bff0", focuscolor=LILAS_SUAVE)
            estilo.map("TButton", background=[("active", "#e2d2f5")])
            estilo.configure("Acao.TButton", background=ROXO_VIVO, foreground="white",
                             font=("Segoe UI", 11, "bold"), padding=14, borderwidth=0,
                             focuscolor=ROXO_VIVO)
            estilo.map("Acao.TButton", background=[("active", "#5b2f98"), ("disabled", "#b9a2d5")],
                       foreground=[("disabled", FUNDO)])
            estilo.configure("Suave.TButton", background=ROXO_VIVO, foreground="white",
                             font=("Segoe UI", 10, "bold"), padding=9, borderwidth=0,
                             focuscolor=ROXO_VIVO)
            estilo.map("Suave.TButton", background=[("active", "#5b2f98")])
            estilo.configure("TNotebook", background=FUNDO, borderwidth=0, tabmargins=(0, 5, 0, 0))
            estilo.configure("TNotebook.Tab", padding=(13, 11), font=("Segoe UI", 10, "bold"),
                             background="#eae1f4", foreground="#6d5b7e", bordercolor="#d3bff0")
            estilo.map("TNotebook.Tab", background=[("selected", "#ffffff"), ("active", "#dfd0f0")],
                       foreground=[("selected", "#5b2f98")])
            estilo.configure("Treeview", font=("Segoe UI", 10), rowheight=32,
                             background="#ffffff", fieldbackground="#ffffff", foreground=TEXTO,
                             borderwidth=0)
            estilo.map("Treeview", background=[("selected", "#e6d8f7")],
                       foreground=[("selected", ROXO_ESCURO)])
            estilo.configure("Treeview.Heading", font=(SERIFA, 10, "bold", "italic"),
                             background=LILAS_SUAVE, foreground=ROXO_ESCURO, padding=8,
                             borderwidth=0, relief="flat")
            estilo.configure("TCheckbutton", background=FUNDO, foreground=TEXTO,
                             font=("Segoe UI", 10), padding=6)
            estilo.map("TCheckbutton", background=[("active", FUNDO)],
                       indicatorcolor=[("selected", ROXO_VIVO)])
            estilo.configure("Horizontal.TProgressbar", troughcolor="#e8def2",
                             background=ROXO_CLARO, bordercolor="#e8def2", lightcolor=ROXO_CLARO,
                             darkcolor=ROXO_CLARO)
            for orient in ("Vertical", "Horizontal"):
                estilo.configure(f"{orient}.TScrollbar", background="#cdb6ec", troughcolor="#efe7f8",
                                 bordercolor="#efe7f8", arrowcolor=ROXO_ESCURO, relief="flat",
                                 gripcount=0, lightcolor="#cdb6ec", darkcolor="#cdb6ec")
                estilo.map(f"{orient}.TScrollbar", background=[("active", ROXO_CLARO)])
            estilo.configure("TEntry", fieldbackground="white", foreground=TEXTO,
                             bordercolor="#cdb6ec", lightcolor="#cdb6ec", darkcolor="#cdb6ec",
                             padding=6)
            estilo.map("TEntry", bordercolor=[("focus", ROXO_VIVO)], lightcolor=[("focus", ROXO_VIVO)])
            estilo.configure("TCombobox", fieldbackground="white", background=LILAS_SUAVE,
                             foreground=TEXTO, arrowcolor=ROXO_ESCURO, bordercolor="#cdb6ec",
                             padding=5)
            estilo.map("TCombobox", fieldbackground=[("readonly", "white")],
                       bordercolor=[("focus", ROXO_VIVO)])

        def texto(self, pai, texto, tamanho=10, cor=TEXTO, negrito=False, serifa=False, **kwargs):
            if serifa:
                fonte = (SERIFA, tamanho, "bold", "italic") if negrito else (SERIFA, tamanho, "italic")
            else:
                fonte = ("Segoe UI", tamanho, "bold" if negrito else "normal")
            return tk.Label(pai, text=texto, bg=pai.cget("bg"), fg=cor, font=fonte, **kwargs)

        def aplicar_cursor_em_tudo(self, widget):
            if not self.cursor:
                return
            try:
                widget.configure(cursor=self.cursor)
            except tk.TclError:
                pass
            for filho in widget.winfo_children():
                self.aplicar_cursor_em_tudo(filho)

        # ── cabeçalho de fantasia ──
        def desenhar_cabecalho(self, evento):
            c = self.cab
            c.delete("all")
            self.brilhos = []
            w, h = max(evento.width, 700), 200
            for y in range(0, h, 2):
                c.create_rectangle(0, y, w, y + 2, outline="", fill=misturar(ROXO_ESCURO, ROXO_MEDIO, y / h))
            rng = random.Random(7)
            for _ in range(46):
                x, y = rng.randint(8, w - 8), rng.randint(8, h - 8)
                if x < 700 and 18 < y < 140:  # não atrapalha o texto
                    continue
                glifo = rng.choice("✦✧⋆✦✧·")
                cores = rng.choice([(LILAS, ROXO_CLARO), (ROXO_CLARO, "#ffffff"), ("#ffffff", LILAS)])
                item = c.create_text(x, y, text=glifo, fill=cores[0], font=("Segoe UI Symbol", rng.randint(8, 16)))
                self.brilhos.append((item, cores))
            c.create_text(w - 90, 70, text="☾", fill=LILAS, font=("Segoe UI Symbol", 58))
            c.create_text(w - 150, 40, text="✦", fill="#ffffff", font=("Segoe UI Symbol", 14))
            c.create_text(w - 44, 126, text="✧", fill=LILAS, font=("Segoe UI Symbol", 16))
            c.create_text(30, 28, anchor="w", fill=LILAS, text="✦  ENTRE LIVROS  ·  RECOMENDADOR INTELIGENTE  ✦",
                          font=("Segoe UI", 10, "bold"))
            c.create_text(30, 70, anchor="w", fill="white", text="Sua próxima leitura começa aqui.",
                          font=(SERIFA, 28, "bold", "italic"))
            c.create_text(30, 112, anchor="w", fill="#eee7fa", text="Descubra histórias que combinam com você  ⋆｡°✩",
                          font=(SERIFA, 12, "italic"))
            x = 30
            f_num, f_leg = tkfont.Font(font=("Segoe UI", 12, "bold")), tkfont.Font(font=("Segoe UI", 8, "bold"))
            for numero, legenda in ((len(servico.livros), "LIVROS NO CATÁLOGO"),
                                    (len(servico.usuarios), "PERFIS DE LEITORES"),
                                    ("IA + GRAFOS", "RECOMENDAÇÕES")):
                numero = str(numero)
                largura = max(f_num.measure(numero), f_leg.measure(legenda)) + 30
                retangulo_arredondado(c, x, 144, x + largura, 188, 14, fill=ROXO_MEDIO, outline=ROXO_CLARO)
                c.create_text(x + 15, 158, anchor="w", text=numero, fill="white", font=("Segoe UI", 12, "bold"))
                c.create_text(x + 15, 177, anchor="w", text=legenda, fill=LILAS, font=("Segoe UI", 8, "bold"))
                x += largura + 10

        def piscar(self):
            self.fase = 1 - self.fase
            try:
                for i, (item, cores) in enumerate(self.brilhos):
                    self.cab.itemconfigure(item, fill=cores[(i + self.fase) % 2])
            except tk.TclError:
                pass
            self.piscar_id = self.after(900, self.piscar)

        def montar(self):
            self.cab = tk.Canvas(self, height=200, bg=ROXO_ESCURO, highlightthickness=0)
            self.cab.pack(fill="x")
            self.cab.bind("<Configure>", self.desenhar_cabecalho)
            tk.Frame(self, bg=ROXO_CLARO, height=4).pack(fill="x")

            corpo = tk.Frame(self, bg=FUNDO, padx=22, pady=20)
            corpo.pack(fill="both", expand=True)
            corpo.columnconfigure(0, weight=0, minsize=400)
            corpo.columnconfigure(1, weight=1)
            corpo.rowconfigure(0, weight=1)
            esquerda = tk.Frame(corpo, bg=FUNDO, width=400)
            esquerda.grid(row=0, column=0, sticky="nsew", padx=(0, 22))
            esquerda.grid_propagate(False)
            esquerda.pack_propagate(False)  # mantém o painel com largura fixa; nada o empurra
            self.texto(esquerda, "✧  PERSONALIZE SUA DESCOBERTA  ✧", 10, ROXO_VIVO, True).pack(anchor="w", pady=(0, 3))
            self.texto(esquerda, "Como você quer descobrir livros?", 16, negrito=True, serifa=True).pack(anchor="w", pady=(0, 10))
            self.abas = ttk.Notebook(esquerda)
            self.abas.pack(fill="both", expand=True)
            perfil, generos, notas = (ttk.Frame(self.abas, padding=12) for _ in range(3))
            self.abas.add(perfil, text="Um perfil")
            self.abas.add(generos, text="Meus gêneros")
            self.abas.add(notas, text="Minhas notas")
            self.montar_perfil(perfil)
            self.montar_generos(generos)
            self.montar_notas(notas)
            self.status = tk.StringVar(value="Escolha uma aba e descubra até cinco livros.")
            ttk.Label(esquerda, textvariable=self.status, wraplength=380).pack(side="bottom", anchor="w", pady=(8, 0), before=self.abas)
            self.progresso = ttk.Progressbar(esquerda, mode="indeterminate")
            self.progresso.pack(side="bottom", fill="x", before=self.abas)
            self.botao = ttk.Button(esquerda, text="✦  Encontrar minhas próximas leituras  ✦", style="Acao.TButton", command=self.recomendar)
            self.botao.pack(side="bottom", fill="x", pady=(14, 7), before=self.abas)

            direita = tk.Frame(corpo, bg=FUNDO)
            direita.grid(row=0, column=1, sticky="nsew")
            self.texto(direita, "✦  Escolhidos para você  ✦", 22, ROXO_ESCURO, True, serifa=True).pack(anchor="w")
            self.contexto = tk.StringVar(value="Até cinco sugestões, com no máximo dois livros por autor.")
            ttk.Label(direita, textvariable=self.contexto, wraplength=560).pack(anchor="w", pady=(4, 14))
            area = tk.Frame(direita, bg=FUNDO)
            area.pack(fill="both", expand=True)
            self.canvas = tk.Canvas(area, bg=FUNDO, highlightthickness=0)
            barra = ttk.Scrollbar(area, orient="vertical", command=self.canvas.yview)
            self.canvas.configure(yscrollcommand=barra.set)
            barra.pack(side="right", fill="y")
            self.canvas.pack(side="left", fill="both", expand=True)
            self.cartoes = tk.Frame(self.canvas, bg=FUNDO)
            self.janela_cartoes = self.canvas.create_window((0, 0), window=self.cartoes, anchor="nw")
            self.cartoes.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
            self.canvas.bind("<Configure>", self.redimensionar)
            self.bind_all("<MouseWheel>", self.rolar, add="+")
            if self.tk.call("tk", "windowingsystem") == "x11":
                self.bind_all("<Button-4>", self.rolar, add="+")
                self.bind_all("<Button-5>", self.rolar, add="+")
            vazio = tk.Frame(self.cartoes, bg=LILAS_SUAVE, padx=26, pady=34,
                             highlightbackground="#d3bff0", highlightthickness=2)
            vazio.pack(fill="x", pady=(10, 0))
            self.texto(vazio, "⋆ ✧ ⋆", 16, ROXO_CLARO, True).pack(anchor="w")
            self.texto(vazio, "Seu próximo favorito está por aqui.", 20, ROXO_ESCURO, True, serifa=True).pack(anchor="w", pady=(4, 0))
            self.texto(vazio, "Escolha um perfil, selecione seus gêneros favoritos ou avalie livros que já leu. Vamos cruzar essas pistas para encontrar novas histórias.", 11, TEXTO_SUAVE, wraplength=450, justify="left").pack(anchor="w", pady=(12, 0))

        # ── aba: um perfil ──
        def montar_perfil(self, pai):
            ttk.Label(pai, text="Explore as recomendações de um perfil.", wraplength=350).pack(anchor="w", pady=(0, 12))
            self.usuario = tk.StringVar(value=servico.usuarios[0] if servico.usuarios else "")
            combo = ttk.Combobox(pai, textvariable=self.usuario, values=servico.usuarios, state="readonly")
            combo.pack(fill="x")
            combo.bind("<<ComboboxSelected>>", lambda e: self.atualizar_historico())
            ttk.Label(pai, text="Livros já avaliados", font=(SERIFA, 11, "bold", "italic")).pack(anchor="w", pady=(16, 6))
            moldura = ttk.Frame(pai)
            moldura.pack(fill="both", expand=True)
            self.historico = self.tabela(moldura, ("titulo", "nota"), ("Livro", "Nota"), height=8)
            self.atualizar_historico()

        def tabela(self, pai, colunas, titulos, height=5, larg_nota=60):
            """Cria a tabela dentro de `pai`. A coluna do título se ajusta sozinha à largura
            disponível, para a coluna de notas nunca ficar cortada."""
            tabela = ttk.Treeview(pai, columns=colunas, show="headings", selectmode="browse", height=height)
            for c, titulo in zip(colunas, titulos):
                if c == "titulo":
                    tabela.column(c, width=120, minwidth=80, stretch=True, anchor="w")
                else:
                    tabela.column(c, width=larg_nota, minwidth=larg_nota, stretch=False, anchor="center")
                tabela.heading(c, text=titulo)
            barra = ttk.Scrollbar(pai, orient="vertical", command=tabela.yview)
            tabela.configure(yscrollcommand=barra.set)
            barra.pack(side="right", fill="y")
            tabela.pack(side="left", fill="both", expand=True)

            def ajustar(evento, t=tabela):
                fixas = sum(int(t.column(c, "width")) for c in colunas if c != "titulo")
                t.column("titulo", width=max(80, evento.width - fixas - 2))
            tabela.bind("<Configure>", ajustar)
            return tabela

        def atualizar_historico(self):
            self.historico.delete(*self.historico.get_children())
            for lid, nota in sorted(servico.historico(self.usuario.get()), key=lambda x: -x[1]):
                self.historico.insert("", "end", values=(servico.livros[lid]["titulo"], f"{nota}/5"))

        # ── aba: meus gêneros ──
        def montar_generos(self, pai):
            ttk.Label(pai, text="Ainda não avaliou livros? Escolha dois ou três gêneros de que gosta.", wraplength=350).pack(anchor="w", pady=(0, 12))
            area = ttk.Frame(pai)
            area.pack(fill="both", expand=True)
            canvas = tk.Canvas(area, bg=FUNDO, highlightthickness=0, width=280)
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

        # ── aba: minhas notas ──
        def montar_notas(self, pai):
            """Layout em grade: busca · lista (cresce) · corações · botões · contador.
            Tudo cabe na aba, então a nota e o botão Adicionar sempre aparecem."""
            pai.columnconfigure(0, weight=1)
            pai.rowconfigure(2, weight=1)
            self.ids = {}
            self.busca = tk.StringVar()
            self.nota = tk.IntVar(value=5)
            self.resumo_var = tk.StringVar()

            ttk.Label(pai, text="Busque um livro, escolha sua nota em corações e clique em Adicionar. Vale só nesta sessão.",
                      wraplength=350).grid(row=0, column=0, sticky="w", pady=(0, 8))
            ttk.Entry(pai, textvariable=self.busca).grid(row=1, column=0, sticky="ew", pady=(0, 8))
            self.busca.trace_add("write", lambda *_: self.filtrar())

            moldura = ttk.Frame(pai)
            moldura.grid(row=2, column=0, sticky="nsew")
            self.catalogo = self.tabela(moldura, ("titulo", "nota"), ("Livro · autor", "Minha nota"),
                                        height=5, larg_nota=96)
            self.catalogo.bind("<<TreeviewSelect>>", self.carregar_nota)
            self.catalogo.bind("<Double-1>", self.duplo_clique)

            linha = tk.Frame(pai, bg=FUNDO)
            linha.grid(row=3, column=0, sticky="ew", pady=(10, 0))
            self.texto(linha, "Minha nota:", 10, TEXTO, True).pack(side="left", padx=(0, 8))
            self.coracoes = []
            for i in range(1, 6):
                rotulo = tk.Label(linha, text="♥", bg=FUNDO, font=("Segoe UI Symbol", 20))
                rotulo.pack(side="left")
                rotulo.bind("<Button-1>", lambda e, i=i: self.definir_nota(i))
                rotulo.bind("<Enter>", lambda e, i=i: self.pintar_coracoes(i))
                rotulo.bind("<Leave>", lambda e: self.pintar_coracoes(self.nota.get()))
                self.coracoes.append(rotulo)
            self.rotulo_nota = self.texto(linha, "", 10, ROXO_VIVO, True)
            self.rotulo_nota.pack(side="left", padx=(8, 0))
            self.pintar_coracoes(5)

            botoes = ttk.Frame(pai)
            botoes.grid(row=4, column=0, sticky="ew", pady=(8, 0))
            botoes.columnconfigure(0, weight=3)
            botoes.columnconfigure(1, weight=2)
            ttk.Button(botoes, text="♥  Adicionar nota", style="Suave.TButton",
                       command=self.adicionar_nota).grid(row=0, column=0, sticky="ew", padx=(0, 6))
            ttk.Button(botoes, text="Remover", command=self.remover_nota).grid(row=0, column=1, sticky="ew")

            ttk.Label(pai, textvariable=self.resumo_var, foreground=ROXO_VIVO,
                      font=("Segoe UI", 10, "bold")).grid(row=5, column=0, sticky="w", pady=(8, 0))
            self.filtrar()

        def definir_nota(self, valor):
            self.nota.set(valor)
            self.pintar_coracoes(valor)

        def pintar_coracoes(self, ate):
            for indice, rotulo in enumerate(self.coracoes, 1):
                rotulo.configure(fg=ROXO_VIVO if indice <= ate else "#d8c9ea")
            self.rotulo_nota.configure(text=f"{ate}/5")

        def coracoes_texto(self, nota):
            return "♥" * nota + "♡" * (5 - nota)

        def resumo_notas(self):
            total = len(self.notas)
            if not total:
                return "Nenhum livro avaliado ainda."
            return f"{total} livro avaliado." if total == 1 else f"{total} livros avaliados."

        def filtrar(self, manter=None):
            self.catalogo.delete(*self.catalogo.get_children())
            encontrados = list(servico.buscar_livros(self.busca.get()))
            encontrados.sort(key=lambda lid: lid not in self.notas)  # avaliados primeiro
            for lid in encontrados:
                livro = servico.livros[lid]
                self.ids[str(lid)] = lid
                nota = self.notas.get(lid)
                self.catalogo.insert("", "end", iid=str(lid), values=(
                    f'{livro["titulo"]} · {livro["autor"]}', self.coracoes_texto(nota) if nota else "—"))
            if manter is not None and self.catalogo.exists(str(manter)):
                self.catalogo.selection_set(str(manter))
                self.catalogo.see(str(manter))
            self.resumo_var.set("♥  " + self.resumo_notas())

        def carregar_nota(self, _evento=None):
            selecao = self.catalogo.selection()
            if selecao:
                lid = self.ids.get(selecao[0])
                if lid in self.notas:
                    self.definir_nota(self.notas[lid])

        def duplo_clique(self, evento):
            if self.catalogo.identify_region(evento.x, evento.y) == "cell":
                self.adicionar_nota()

        def adicionar_nota(self):
            selecao = self.catalogo.selection()
            if not selecao:
                messagebox.showinfo("Escolha um livro", "Selecione um livro na lista antes de dar a nota.", parent=self)
                return
            nota = self.nota.get()
            if not 1 <= nota <= 5:
                messagebox.showinfo("Escolha uma nota", "Escolha uma nota de 1 a 5 corações.", parent=self)
                return
            lid = self.ids[selecao[0]]
            self.notas[lid] = nota
            self.filtrar(manter=lid)
            self.status.set(f"♥ Nota {nota}/5 para “{servico.livros[lid]['titulo']}”. {self.resumo_notas()}")

        def remover_nota(self):
            selecao = self.catalogo.selection()
            if not selecao:
                messagebox.showinfo("Escolha um livro", "Selecione o livro cuja nota você quer remover.", parent=self)
                return
            lid = self.ids[selecao[0]]
            if lid not in self.notas:
                messagebox.showinfo("Sem nota", "Este livro ainda não tem nota.", parent=self)
                return
            del self.notas[lid]
            self.filtrar(manter=lid)
            self.status.set(f"Nota removida. {self.resumo_notas()}")

        # ── recomendações ──
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

        def dentro_de(self, pai, x, y):
            try:
                widget = self.winfo_containing(x, y)
            except (KeyError, tk.TclError):
                return False
            while widget is not None:
                if widget == pai:
                    return True
                widget = getattr(widget, "master", None)
            return False

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
                cartao = tk.Frame(self.cartoes, bg="white", highlightbackground="#e5d9f2", highlightthickness=2)
                cartao.pack(fill="x", pady=(0, 14), padx=(0, 4))
                tk.Frame(cartao, bg=ROXO_CLARO, width=7).pack(side="left", fill="y")
                conteudo = tk.Frame(cartao, bg="white", padx=20, pady=17)
                conteudo.pack(side="left", fill="both", expand=True)

                def entrar(e, c=cartao):
                    c.configure(highlightbackground=ROXO_CLARO)

                def sair(e, c=cartao):
                    if not self.dentro_de(c, e.x_root, e.y_root):
                        c.configure(highlightbackground="#e5d9f2")
                cartao.bind("<Enter>", entrar)
                cartao.bind("<Leave>", sair)
                self.texto(conteudo, f"✦  LEITURA {indice:02d}  ✦", 9, ROXO_VIVO, True).pack(anchor="w")
                self.texto(conteudo, livro["titulo"], 17, ROXO_ESCURO, True, serifa=True, wraplength=470, justify="left").pack(anchor="w", pady=(5, 3))
                self.texto(conteudo, livro["autor"], 11, TEXTO_SUAVE, wraplength=470, justify="left").pack(anchor="w")
                self.texto(conteudo, "⋆ · ✧ · ⋆", 9, ROXO_CLARO).pack(anchor="w", pady=(7, 0))
                self.texto(conteudo, " · ".join(livro["generos"]), 9, ROXO_VIVO, True, wraplength=470).pack(anchor="w", pady=(2, 0))
                motivo = "\n".join("♥ " + m[:1].upper() + m[1:] for m in livro["motivos"][:2])
                if not motivo:
                    motivo = "♥ Sugerido pelas conexões do grafo entre leitores e livros."
                self.texto(conteudo, motivo, 10, TEXTO_SUAVE, wraplength=470, justify="left").pack(anchor="w", pady=(10, 0))
            if not resultados:
                self.texto(self.cartoes, "Nenhuma sugestão disponível. Experimente outros gêneros ou avalie mais livros.", 12, wraplength=470, justify="left").pack(anchor="w", pady=30)
            total = len(resultados)
            if total:
                self.status.set(f"{total} {'sugestão encontrada' if total == 1 else 'sugestões encontradas'}. Máximo de dois livros por autor.")
            else:
                self.status.set("Nenhuma sugestão encontrada.")
            self.aplicar_cursor_em_tudo(self.cartoes)
            self.canvas.yview_moveto(0)
            self.after_idle(lambda: self.redimensionar(None))

        def ajustar_quebra(self, widget, largura):
            for filho in widget.winfo_children():
                if isinstance(filho, tk.Label):
                    filho.configure(wraplength=largura)
                else:
                    self.ajustar_quebra(filho, largura)

        def redimensionar(self, evento):
            largura = max(250, self.canvas.winfo_width())
            self.canvas.itemconfigure(self.janela_cartoes, width=largura)
            self.ajustar_quebra(self.cartoes, max(180, largura - 80))

        def rolar(self, evento):
            try:
                widget = self.winfo_containing(evento.x_root, evento.y_root)
            except (KeyError, tk.TclError):  # popdown do Combobox não está no mapa de widgets
                return None
            while widget is not None:
                if widget == self.canvas or widget == self.cartoes:
                    if evento.num == 4:
                        passo = -1
                    elif evento.num == 5:
                        passo = 1
                    else:
                        passo = -1 if evento.delta > 0 else 1
                    self.canvas.yview_scroll(passo, "units")
                    return "break"
                widget = getattr(widget, "master", None)
            return None

        def fechar(self):
            if self.piscar_id:
                self.after_cancel(self.piscar_id)
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
    except (ImportError, OSError, ValueError, KeyError, IndexError, csv.Error) as erro:
        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror("Não foi possível abrir o projeto", f"{erro}\n\nConfira os CSVs e execute instalar_dependencias.bat.", parent=raiz)
        raiz.destroy()
        return 1
    abrir_interface(tk, ttk, messagebox, servico)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
