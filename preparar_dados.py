"""Prepara cópias do catálogo, revisão de gêneros e coleta de notas reais."""

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from recomendador_v2 import GENEROS_AMPLIADOS, carregar_livros, generos_do_livro, sem_acento


def escrever_csv(caminho, campos, linhas):
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas)


def chave_obra(titulo, autores):
    """Somente diferenças de caixa, acentos, pontuação e indicação de edição.

    Não elimina números de volume nem subtítulos. Autor vazio não permite fusão.
    """
    titulo = sem_acento(titulo)
    titulo = re.sub(r"\b\d+\s*[aªº]?\s*(?:edicao|edition)\b", "", titulo)
    titulo = " ".join(re.findall(r"\w+", titulo))
    autores = " ".join(re.findall(r"\w+", sem_acento(autores)))
    return titulo, autores


def consolidar(linhas):
    vistos, mapa, saida = {}, {}, []
    for linha in linhas:
        chave = chave_obra(linha["titulo"], linha["autores"])
        if not linha["id"] or linha["id"] in mapa:
            raise ValueError("IDs vazios ou repetidos no catálogo")
        if chave[0] and chave[1] and chave[1] != "desconhecido" and chave in vistos:
            canonico = vistos[chave]
            mapa[linha["id"]] = canonico["id"]
            categorias = dict.fromkeys((canonico["categorias"] + ";" + linha["categorias"]).split(";"))
            canonico["categorias"] = "; ".join(c.strip() for c in categorias if c.strip())
        else:
            copia = dict(linha)
            vistos[chave] = copia
            mapa[linha["id"]] = linha["id"]
            saida.append(copia)
    return saida, mapa


def importar_respostas(arquivo, livros):
    """Importa CSV largo: usuario e colunas '[livro_id] Título'. Não li = vazio."""
    respostas, vistos = [], set()
    with open(arquivo, encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f)
        if not leitor.fieldnames or "usuario" not in leitor.fieldnames:
            raise ValueError("O CSV deve conter a coluna usuario")
        colunas = {}
        for nome in leitor.fieldnames:
            match = re.match(r"^\[([^]]+)\]", nome)
            if match:
                lid = match.group(1)
                if lid not in livros or lid in colunas.values():
                    raise ValueError("ID desconhecido ou repetido nas perguntas")
                colunas[nome] = lid
        if not colunas:
            raise ValueError("Nenhuma pergunta no padrão [livro_id] Título")
        for numero, linha in enumerate(leitor, 2):
            usuario = (linha.get("usuario") or "").strip()
            if not usuario:
                raise ValueError(f"Usuário vazio na linha {numero}")
            for coluna, lid in colunas.items():
                valor = (linha.get(coluna) or "").strip()
                if sem_acento(valor) in ("", "nao li", "nao conheco"):
                    continue
                nota = int(valor)
                if not 1 <= nota <= 5 or (usuario, lid) in vistos:
                    raise ValueError(f"Nota inválida ou avaliação duplicada na linha {numero}")
                vistos.add((usuario, lid))
                respostas.append({"usuario": usuario, "livro_id": lid, "titulo": livros[lid]["titulo"], "nota": nota})
    if not respostas:
        raise ValueError("Nenhuma nota preenchida; o modelo vazio não contém avaliações reais")
    return respostas


def preparar(args):
    pasta = args.saida
    pasta.mkdir(parents=True, exist_ok=True)
    with open(args.livros, encoding="utf-8-sig", newline="") as f:
        originais = list(csv.DictReader(f))
    if not originais:
        raise ValueError("Catálogo vazio")
    consolidados, mapa = consolidar(originais)
    revisoes = {}
    if args.generos:
        with open(args.generos, encoding="utf-8-sig", newline="") as f:
            for linha in csv.DictReader(f):
                generos = [g.strip() for g in linha["generos"].split(";") if g.strip()]
                if linha["livro_id"] not in mapa or any(g not in GENEROS_AMPLIADOS for g in generos):
                    raise ValueError("Revisão contém ID ou gênero inválido")
                if generos:
                    lid = mapa[linha["livro_id"]]
                    if lid in revisoes and revisoes[lid] != generos:
                        raise ValueError("Revisões conflitantes de edições da mesma obra")
                    revisoes[lid] = generos
    for linha in consolidados:
        linha["generos_revisados"] = "; ".join(revisoes.get(linha["id"], generos_do_livro(linha["categorias"], ampliado=True)))
        linha["origem_generos"] = "revisao_manual" if linha["id"] in revisoes else "heuristica_ampliada"
    campos = list(consolidados[0])
    escrever_csv(pasta / "livros.csv", campos, consolidados)
    escrever_csv(pasta / "mapa_edicoes.csv", ["id_original", "id_canonico"],
                 [{"id_original": a, "id_canonico": b} for a, b in mapa.items()])
    notas = defaultdict(list)
    with open(args.avaliacoes, encoding="utf-8-sig", newline="") as f:
        for linha in csv.DictReader(f):
            nota = int(linha["nota"])
            if linha["livro_id"] not in mapa or not 1 <= nota <= 5 or not linha["usuario"].strip():
                raise ValueError("Avaliação inválida")
            notas[linha["usuario"], mapa[linha["livro_id"]]].append(nota)
    # Uma obra pode ter sido avaliada em várias edições. Média, arredondada para cima em .5.
    titulos = {l["id"]: l["titulo"] for l in consolidados}
    escrever_csv(pasta / "avaliacoes.csv", ["usuario", "livro_id", "titulo", "nota"], [
        {"usuario": u, "livro_id": lid, "titulo": titulos[lid], "nota": int(sum(ns) / len(ns) + 0.5)}
        for (u, lid), ns in sorted(notas.items())])
    escrever_csv(pasta / "notas_consolidadas.csv", ["usuario", "livro_id", "notas_originais"], [
        {"usuario": u, "livro_id": lid, "notas_originais": ";".join(map(str, ns))}
        for (u, lid), ns in sorted(notas.items()) if len(ns) > 1])
    livros = carregar_livros(pasta / "livros.csv")
    leituras = defaultdict(int)
    for _, lid in notas:
        leituras[lid] += 1
    revisar = sorted((lid for lid, l in livros.items() if l["generos"] == ["Outros"]),
                     key=lambda lid: (-leituras[lid], lid))
    modelo = pasta / "generos_para_revisar.csv"
    # Não sobrescreve um modelo que o grupo já pode estar preenchendo.
    if not modelo.exists():
        escrever_csv(modelo, ["livro_id", "titulo", "leituras", "generos"], [
            {"livro_id": lid, "titulo": livros[lid]["titulo"], "leituras": leituras[lid], "generos": ""}
            for lid in revisar])
    selecionados = sorted(livros, key=lambda lid: (-leituras[lid], lid))[:30]
    perguntas = [f'[{lid}] {livros[lid]["titulo"]}' for lid in selecionados]
    if not (pasta / "respostas_modelo.csv").exists():
        escrever_csv(pasta / "respostas_modelo.csv", ["usuario", *perguntas], [])
    (pasta / "generos_disponiveis.txt").write_text("\n".join(sorted(GENEROS_AMPLIADOS)) + "\n", encoding="utf-8")
    roteiro = ["# Coleta de avaliações reais", "",
               "Crie um Google Forms com uma pergunta de resposta curta chamada exatamente `usuario` (apelido único).",
               "Para cada livro abaixo, crie uma pergunta opcional de múltipla escolha com as opções: 1, 2, 3, 4, 5, Não li.",
               "Copie o título completo da pergunta, incluindo o ID entre colchetes. Não peça notas de livros não lidos.", "",
               *[f"- {p}" for p in perguntas], "",
               "Exporte as respostas da planilha em CSV. O importador ignora colunas adicionais como data/hora.",
               "Também é possível preencher respostas_modelo.csv diretamente, com uma linha por pessoa.", "",
               "Importar: `python preparar_dados.py importar respostas.csv --livros dados_preparados/livros.csv --destino avaliacoes_reais.csv`.",
               "Depois: `python avaliar_recomendador.py --livros dados_preparados/livros.csv --avaliacoes avaliacoes_reais.csv --saida resultados_reais`."]
    (pasta / "roteiro_formulario.md").write_text("\n".join(roteiro) + "\n", encoding="utf-8")
    resumo = {"livros_originais": len(originais), "livros_consolidados": len(consolidados),
              "edicoes_agrupadas": len(originais) - len(consolidados), "livros_outros": len(revisar),
              "revisoes_aplicadas": len(revisoes), "perguntas_formulario": len(perguntas)}
    (pasta / "preparacao.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="acao", required=True)
    prep = subs.add_parser("preparar")
    prep.add_argument("--livros", type=Path, default=Path("livros.csv"))
    prep.add_argument("--avaliacoes", type=Path, default=Path("avaliacoes.csv"))
    prep.add_argument("--generos", type=Path)
    prep.add_argument("--saida", type=Path, default=Path("dados_preparados"))
    imp = subs.add_parser("importar")
    imp.add_argument("arquivo", type=Path)
    imp.add_argument("--livros", type=Path, default=Path("livros.csv"))
    imp.add_argument("--destino", type=Path, default=Path("avaliacoes_reais.csv"))
    args = parser.parse_args()
    if args.acao == "preparar":
        if args.saida.resolve() == args.livros.resolve().parent or args.saida.resolve() == args.avaliacoes.resolve().parent:
            raise ValueError("Use uma pasta de saída diferente dos dados de entrada")
        preparar(args)
    else:
        if args.destino.exists():
            raise ValueError("O destino já existe; escolha outro nome para preservar as avaliações")
        livros = carregar_livros(args.livros)
        respostas = importar_respostas(args.arquivo, livros)
        escrever_csv(args.destino, ["usuario", "livro_id", "titulo", "nota"], respostas)
        print(f"{len(respostas)} notas importadas em {args.destino}")


if __name__ == "__main__":
    main()
