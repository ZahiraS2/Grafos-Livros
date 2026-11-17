# Estado das 15 sugestões do Cláudio

| Nº | Sugestão | Estado e evidência |
|---:|---|---|
| 1 | Avaliação com precisão@k | Implementada e executada: precisão@5, recall@5 e hit@5, cinco partições sem notas de teste no treino. `resultados/`. |
| 2 | Comparação das versões | PageRank, Jaccard e referência de caminhos de tamanho 3 comparados. A v1 original não foi fornecida; não é possível afirmar que a referência a reproduz exatamente. |
| 3 | Testar alpha | Implementado e executado para 0,5; 0,7; 0,85 e 0,95. `resultados/comparacao.csv`. |
| 4 | Avaliações reais | Roteiro de Google Forms com 30 livros, modelo de respostas e importador implementados. A criação/publicação do formulário e as notas dos colegas ainda dependem do grupo. `dados_preparados/roteiro_formulario.md`. |
| 5 | Gêneros melhores | Regras ampliadas, origem da classificação registrada, CSV para revisão manual e importação de correções implementados. Outros caiu de 196 para 164 livros. Os 164 restantes ainda precisam de metadados ou revisão humana; não foi consultada a Google Books nesta etapa. |
| 6 | Juntar edições | Consolidação conservadora por título e autores normalizados, mapa de IDs e remapeamento de avaliações implementados. Uma duplicata foi agrupada. Equivalências de títulos muito diferentes ainda exigem revisão. |
| 7 | Penalizar hubs | Parâmetro `penalizacao_hubs`, aplicado aos pesos pelo grau dos extremos da aresta. Testado e avaliado separadamente. |
| 8 | Pesos por tipo de aresta | `peso_autor` e `peso_genero` configuráveis. Experimento autor=2 e gênero=0,5 executado; não é uma busca exaustiva de pesos. |
| 9 | Normalizar notas | Z-score por usuário transformado por logística para manter pesos positivos, usando somente o treino; desvio zero tratado. Testado e avaliado. |
| 10 | Usuário novo | PageRank iniciado pelos gêneros favoritos, sem exigir notas. Menu solicita 2 ou 3 gêneros; vetor de personalização validado. |
| 11 | Louvain | Implementado e executado, CSV de todos os vértices e SVG do maior componente. Componentes desconectados não são apresentados como evidência de gosto. |
| 12 | Análise do grafo | Grau médio, densidade, componentes, centralidade de grau e modularidade calculados. |
| 13 | Complexidade e tempo | Análise teórica e medições com 30, 300 e 3000 usuários simulados executadas. `resultados_melhorias/`. |
| 14 | Interface | Janela gráfica com perfis, gêneros, busca de livros, notas na sessão e cartões de recomendações. Abra `abrir_interface.bat` ou execute `interface_grafica.py`. O menu `interface_recomendador.py` também está disponível. A aparência da janela ainda precisa ser conferida no Windows: o Linux desta sessão não tem Tkinter. |
| 15 | Diversidade | Limite configurável por autor, sem incluir candidatos de pontuação zero. Menu usa máximo 2 por autor. Testado e comparado com a base. |

## O que os resultados permitem concluir

As opções funcionam e podem ser reproduzidas. Implementar uma ideia não garante
melhor precisão: nos dados originais, a base manteve a maior precisão observada.
O limite por autor aumentou a diversidade média com uma pequena redução nos acertos.
A configuração combinada ficou disponível como experimento, sem substituir a base.

Os dados originais são simulados. A origem real não é comprovada apenas porque
um CSV difere da simulação padrão: o catálogo preparado muda gêneros e IDs, mas
suas notas continuam derivadas da mesma simulação. O grupo ainda precisa coletar
notas reais e reservar novos dados para validar os parâmetros escolhidos.

## Validação e entrega

Foram executados 22 testes automatizados, cobrindo partição, métricas, PageRank
contra a referência NetworkX, personalização por múltiplos gêneros, diversidade,
pesos, normalização, hubs, edições, revisão de gêneros, importação de respostas
e o serviço utilizado pela janela gráfica (busca, perfis, gêneros e notas temporárias).
Os experimentos de qualidade e desempenho também foram executados. Os fluxos
do menu foram conferidos com usuário existente, início por gêneros e notas na
sessão, além das opções de configuração experimental e catálogo preparado.

O catálogo preparado reduziu Outros de 196 para 164, mas a precisão@5 do
PageRank com alpha=0,85 ficou em 8,13%, contra 9,07% no catálogo original.
Isso reforça a necessidade de avaliar cada mudança em vez de presumir melhora.

Envie o código Python, `requirements.txt`, `instalar_dependencias.bat`, `README.md`,
este documento, os CSVs de entrada e as pastas `tests`, `resultados`,
`resultados_melhorias`, `dados_preparados` e `resultados_dados_preparados`.
Inclua também `abrir_interface.bat` para abrir a janela com dois cliques.
Ambientes virtuais e arquivos internos do editor não fazem parte da entrega.
