# Recomendação de livros com grafos

O projeto representa relações entre leitores e livros em um grafo e usa
PageRank personalizado para sugerir livros ainda não lidos por cada usuário.
É um protótipo acadêmico: os livros vêm de catálogos reais, mas as avaliações
são simuladas quando não existe um arquivo com notas reais.

## Abrir a interface gráfica no Windows

Execute `instalar_dependencias.bat` caso ainda não tenha instalado as dependências.
Depois, abra **`abrir_interface.bat` com dois cliques**. Uma janela local será
aberta, com três abas: **Um perfil**, **Meus gêneros** e **Minhas notas**.
Escolha o perfil, marque dois ou três gêneros ou busque livros para dar notas;
clique em **Encontrar minhas próximas leituras** para ver os cartões de sugestões.
As notas informadas na janela ficam somente na sessão e não alteram os CSVs.

Também é possível executar no terminal:

```powershell
.\.venv-windows\Scripts\python.exe interface_grafica.py
```

O iniciador funciona mesmo quando a pasta é aberta por outro diretório. A
interface usa Tkinter (Tcl/Tk, incluído normalmente no Python para Windows),
sem servidor ou dependência gráfica adicional via pip. Caso o Python instalado
não tenha Tcl/Tk, habilite esse componente na instalação do Python. Em Linux,
é necessário o pacote `python3-tk` compatível com o interpretador e uma sessão gráfica.

O arquivo `interface_recomendador.py` continua disponível como menu de terminal.
`servico_interface.py` conecta a janela ao mesmo algoritmo, com alpha=0,85 e
máximo de dois livros por autor. A busca aceita títulos e autores sem exigir acentos.
O cálculo ocorre em segundo plano para manter a janela responsiva.

Validação da janela: os fluxos do serviço foram testados automaticamente. A
renderização e a interação visual não foram validadas neste Linux, que está sem
Tkinter; precisam ser conferidas na máquina Windows do grupo.

## Os dois arquivos são necessários

- `buscar_livros.py`: coleta livros e gera `livros.csv`.
- `recomendador_v2.py`: lê esse catálogo, constrói o grafo, calcula as
  recomendações e salva imagens que ilustram algumas das relações.

O nome “v2” e os comentários indicam uma evolução de um recomendador anterior,
que não está nesta pasta. Ele não substitui o coletor `buscar_livros.py`.

O arquivo `avaliar_recomendador.py` executa os experimentos de qualidade e a
análise estrutural descritos ao final deste documento, sem precisar coletar
novamente o catálogo ou alterar as avaliações.

## Instalar e executar no Windows

É necessário ter Python 3 instalado e acesso à internet. Use uma versão recente,
como Python 3.12 ou superior.

1. Execute `instalar_dependencias.bat` com dois cliques. Ele cria o ambiente
   `.venv-windows`, instala os pacotes de `requirements.txt` e verifica os imports.
2. Abra um terminal nesta pasta e execute, nesta ordem:

```powershell
.\.venv-windows\Scripts\python.exe buscar_livros.py
.\.venv-windows\Scripts\python.exe recomendador_v2.py
```

Também é possível instalar manualmente:

```powershell
py -3 -m venv .venv-windows
.\.venv-windows\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-windows\Scripts\python.exe -m pip check
```

Não é necessário ativar o ambiente: os comandos usam diretamente seu Python.

## Instalar e executar no WSL/Linux

No Ubuntu/WSL, instale primeiro o suporte a ambientes virtuais, caso esteja ausente:

```bash
sudo apt update
sudo apt install python3-venv
```

Se a mensagem do Python pedir um pacote específico, como `python3.14-venv`,
instale o pacote indicado correspondente à versão do interpretador.

Depois, no terminal desta pasta:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python buscar_livros.py
.venv/bin/python recomendador_v2.py
```

Windows e WSL usam ambientes separados; não compartilhe um ambiente virtual
entre os dois sistemas.

## Dependências

| Pacote | Função |
| --- | --- |
| NetworkX | Construir o grafo, calcular PageRank e organizar os vértices no desenho. |
| Matplotlib | Salvar as imagens das recomendações. |
| NumPy e SciPy | Dependências numéricas mantidas no ambiente; o PageRank atual usa iteração em Python. |

O coletor usa apenas a biblioteca padrão do Python. O `pip` instala também
as dependências transitivas dos pacotes listados. As versões não estão fixadas.
A avaliação foi executada com Python 3.14.4 e NetworkX 3.7; seus SVGs são
gerados sem Matplotlib, NumPy ou SciPy.

## Como funciona o trabalho

### 1. Coletar o catálogo

O coletor procura até 80 resultados por editora: Galera, DarkSide, Planeta,
Arqueiro e Rocco. A fonte padrão é a Open Library, sem chave de API. Se a
variável de ambiente `GOOGLE_BOOKS_API_KEY` estiver definida, usa Google Books.

Ele solicita livros em português, remove duplicatas pelo título e grava
`id`, `titulo`, `autores`, `editora`, `categorias`, `ano` e `fonte` em `livros.csv`.
O total depende do catálogo e da disponibilidade da API. O ano da Open Library
é o da primeira publicação da obra. Os metadados podem agregar várias edições;
o filtro de idioma não garante que todos os títulos retornados estejam em português.

### 2. Preparar gêneros e avaliações

O recomendador identifica palavras nas categorias e as agrupa em gêneros,
como Fantasia, Terror, Romance e Ficção científica. Quando não encontra
correspondência, marca o livro como `Outros`.

Se `avaliacoes.csv` existir, lê suas notas e ignora registros de livros que
não estão no catálogo. Caso contrário, simula 30 usuários, atribui gêneros
favoritos e gera notas de 1 a 5. A semente aleatória é 42. O arquivo gerado
inclui `usuario,livro_id,titulo,nota`; a coluna `titulo` serve apenas para consulta.
Para usar avaliações reais, mantenha ao menos `usuario,livro_id,nota`, com
IDs presentes em `livros.csv` e notas inteiras de 1 a 5.

### 3. Construir o grafo

É um grafo **não direcionado, ponderado e heterogêneo**:

- **Vértices:** usuários, livros, autores e gêneros.
- **Arestas usuário–livro:** representam avaliações, com peso `nota / 5`.
  Uma nota 5 gera peso 1; uma nota 1 gera peso 0,2.
- **Arestas livro–autor e livro–gênero:** têm peso 1.

O código usa somente o primeiro autor de cada livro. `Outros` não vira um
vértice de gênero. Editoras e anos não participam do cálculo de recomendação.

Um caminho possível é:

```text
Usuario01 → livro que avaliou → Fantasia → livro ainda não lido
```

Outro é:

```text
Usuario01 → livro que avaliou → Usuario02 → outro livro
```

Assim, a recomendação combina informações do conteúdo e relações entre leitores.

### 4. Calcular PageRank personalizado

Imagine um passeio pelo grafo que começa no usuário escolhido. A cada passo:

- Com probabilidade de 85%, segue uma aresta, respeitando seu peso relativo
  às outras arestas do vértice atual.
- Com probabilidade de 15%, reinicia no usuário escolhido.

O código calcula numericamente a distribuição de visitas desse passeio,
por iteração de potência em Python, com erro L1 entre iterações menor que
`1e-10` e limite de 2000 iterações. A implementação foi comparada com a
referência em Python do NetworkX nos quatro valores de alpha avaliados.
Livros com pontuação maior têm maior probabilidade de visita
nesse modelo. A pontuação não é uma nota prevista nem uma porcentagem de
certeza de que a pessoa vai gostar.

O código remove os livros que o usuário já avaliou e devolve até cinco
candidatos, ordenados pela pontuação. Na execução padrão, mostra resultados
para os três primeiros usuários em ordem alfabética.

### 5. Explicar e desenhar

Para cada sugestão, procura autores, gêneros ou outros leitores em comum
com livros aos quais o usuário deu nota 4 ou 5. Salva até três motivos em
texto e uma imagem `recomendacao_UsuarioXX.png` para cada usuário exibido.
As figuras representam algumas ligações locais; não mostram o grafo completo
nem todos os caminhos considerados pelo PageRank. O Matplotlib salva os PNGs
sem abrir uma janela.

## Limitações importantes para a apresentação

- As avaliações simuladas permitem demonstrar o algoritmo, mas não comprovam
  sua qualidade com leitores reais. O script de avaliação separa treino e
  teste e mede a recuperação de livros positivos escondidos.
- A personalização concentra o passeio no componente conectado ao usuário.
  Livros de componentes desconectados têm pontuação zero e são excluídos;
  não há garantia de cinco sugestões para todos os usuários.
- Notas baixas reduzem o peso da relação, mas não expressam rejeição explícita.
- A classificação de gêneros é uma heurística por palavras; pode errar ou
  deixar livros sem gênero identificado.
- A simulação também funciona com catálogos pequenos, mas eles não garantem
  usuários com positivos suficientes para avaliação ou cinco recomendações.
- Execute os scripts a partir desta pasta: os caminhos dos CSVs e PNGs são
  relativos ao diretório do terminal. Sem `livros.csv`, o recomendador falha.
- Uma nova coleta pode alterar os IDs disponíveis; revise as avaliações
  existentes antes de reutilizá-las com um catálogo diferente.

Uma descrição possível do objetivo acadêmico é: **“Modelar relações entre
leitores, livros, autores e gêneros em um grafo heterogêneo e aplicar PageRank
personalizado para recomendar obras ainda não lidas, apresentando relações
que ajudam a explicar as sugestões.”**

## Avaliação, comparação e comunidades

Com as dependências instaladas, execute na pasta do projeto:

```powershell
.\.venv-windows\Scripts\python.exe avaliar_recomendador.py
.\.venv-windows\Scripts\python.exe -m unittest discover -s tests -v
```

No Linux, use `.venv/bin/python` nos mesmos comandos. Para repetir a execução
feita nesta sessão, que aproveitou somente o código Python do NetworkX já
instalado no ambiente Windows, o comando foi:

```bash
PYTHONPATH=.venv-windows/Lib/site-packages python3 avaliar_recomendador.py
PYTHONPATH=.venv-windows/Lib/site-packages python3 -m unittest discover -s tests -v
```

Esse aproveitamento foi específico do ambiente disponível: os pacotes binários
Windows não funcionam no Linux. A geração dos PNGs originais continua exigindo
uma instalação compatível de Matplotlib e não foi executada nesta sessão.

A avaliação esconde 20% dos positivos de cada usuário (notas 4 ou 5), mantém
pelo menos um positivo no treino e repete com cinco sementes. Compara uma
referência de caminhos de tamanho 3, Jaccard entre leitores e PageRank nos
alphas 0,5; 0,7; 0,85 e 0,95. A v1 original não está disponível para comparação
direta. As definições e limitações estão no relatório gerado.

Saídas em `resultados/`:

- `relatorio.md`: protocolo, resultados e interpretação.
- `comparacao.csv` e `comparacao.svg`: métricas agregadas e gráfico.
- `avaliacao_por_usuario.csv` e `particoes_teste.csv`: recomendações, métricas
  individuais e livros escondidos em cada repetição.
- `grafo.json` e `livros_centrais.csv`: métricas estruturais e centralidade de grau.
- `comunidades.csv`: comunidade de todos os vértices, calculada por Louvain.
- `comunidades.svg`: comunidades do maior componente conexo, com identificação
  dos vértices ao passar o mouse.
- `execucao.json`: versões, sementes e hashes dos dados de entrada.

O catálogo original tem 338 livros e 286 avaliações de 30 usuários. As notas
coincidem exatamente com a simulação padrão. A avaliação completa foi executada;
isso não valida recomendações para leitores reais.

## Implementações adicionais das sugestões do Cláudio

O estado de cada uma das 15 sugestões está em `STATUS_TRABALHO.md`.
Foram adicionados pesos por tipo de aresta, penalização de hubs, normalização
das notas e limite por autor. As opções são configuráveis e a base continua
sendo o padrão: as mudanças não garantiram melhor precisão neste experimento.
Os 22 testes automatizados passaram, incluindo as novas opções, o importador,
a integração do serviço da interface gráfica e a preservação dos dados originais
e de planilhas já preenchidas.

### Demonstração no terminal

```powershell
.\.venv-windows\Scripts\python.exe interface_recomendador.py
```

O menu permite escolher um usuário, iniciar por 2 ou 3 gêneros favoritos ou
marcar livros com notas somente para a sessão. Mostra até cinco recomendações
com limite de dois livros por autor. Notas da sessão não são gravadas nos CSVs.
Use `--melhorado` para experimentar pesos, hubs e normalização juntos;
essa configuração não foi a melhor na avaliação.

### Preparar os dados e o formulário

```powershell
.\.venv-windows\Scripts\python.exe preparar_dados.py preparar
```

A saída `dados_preparados/` contém uma cópia do catálogo e das notas, com
IDs de edições equivalentes remapeados e regras de gêneros ampliadas.
Os CSVs originais são preservados. A fusão compara título e autores normalizados;
não tenta adivinhar equivalências por títulos muito diferentes nem remove
números de volumes. Notas do mesmo usuário para edições fundidas são reunidas
pela média, arredondando .5 para cima, e registradas em `notas_consolidadas.csv`.

O arquivo `generos_para_revisar.csv` lista os livros ainda em Outros, ordenados
por número de leituras. Preencha a coluna `generos` com nomes separados por
ponto e vírgula. Aceitam-se os gêneros definidos em `GENEROS_AMPLIADOS`, no
recomendador. Para reaplicar a revisão:

```powershell
.\.venv-windows\Scripts\python.exe preparar_dados.py preparar --generos dados_preparados/generos_para_revisar.csv
```

O modelo de revisão existente é preservado para não apagar o preenchimento.
As classificações automáticas são heurísticas, sem verificação manual de obras.
Na execução atual foram agrupadas duas entradas de "O diário de um mago";
o catálogo preparado tem 337 livros, sendo 164 em Outros (antes eram 196).
Essa cobertura maior não elevou a precisão observada: PageRank com alpha=0,85
teve 8,13% no catálogo preparado, contra 9,07% no original. Ambos são mantidos
para comparação; a configuração e o catálogo originais continuam como referência.

`dados_preparados/roteiro_formulario.md` orienta a criação de um Google Forms
com 30 livros. `respostas_modelo.csv` permite coletar as notas diretamente em
planilha. Nenhum formulário foi publicado e nenhuma nota real foi inventada.
Para importar as respostas e avaliar:

```powershell
.\.venv-windows\Scripts\python.exe preparar_dados.py importar respostas.csv --livros dados_preparados/livros.csv --destino avaliacoes_reais.csv
.\.venv-windows\Scripts\python.exe avaliar_recomendador.py --livros dados_preparados/livros.csv --avaliacoes avaliacoes_reais.csv --saida resultados_reais
```

O CSV deve ter uma coluna `usuario` e perguntas no formato `[livro_id] Título`.
Respostas em branco ou "Não li" são ignoradas. Notas inválidas e duplicatas
geram erro; o importador não sobrescreve um destino existente.

### Avaliar as opções e medir escalabilidade

```powershell
.\.venv-windows\Scripts\python.exe experimentar_melhorias.py
.\.venv-windows\Scripts\python.exe avaliar_recomendador.py --livros dados_preparados/livros.csv --avaliacoes dados_preparados/avaliacoes.csv --saida resultados_dados_preparados
```

`resultados_melhorias/relatorio.md` compara cada opção isolada e a configuração
combinada usando os dados originais e cinco partições. Inclui tempos medidos
com 30, 300 e 3000 usuários simulados e a análise de complexidade. O relatório
`resultados_dados_preparados/relatorio.md` avalia separadamente o catálogo
consolidado e os gêneros ampliados. Alterar o catálogo pode alterar as partições,
portanto as comparações entre esses dois catálogos não isolam uma única causa.

Para demonstrar com os dados preparados, use:

```powershell
.\.venv-windows\Scripts\python.exe interface_recomendador.py --livros dados_preparados/livros.csv --avaliacoes dados_preparados/avaliacoes.csv
```

O ambiente Linux desta sessão executou os mesmos scripts com o prefixo
`PYTHONPATH=.venv-windows/Lib/site-packages python3`, como explicado acima.

## PARET VISUAL 

<img width="1600" height="862" alt="WhatsApp Image 2026-11-17 at 13 32 51" src="https://github.com/user-attachments/assets/c307043f-4c8f-4093-b905-4c4a1ca7d1b1" />

<img width="406" height="1033" alt="WhatsApp Image 2026-11-17 at 13 32 51 (1)" src="https://github.com/user-attachments/assets/fed9cd4d-959f-419d-bcb2-1109c046f783" />

<img width="413" height="1026" alt="WhatsApp Image 2026-11-17 at 13 32 51 (2)" src="https://github.com/user-attachments/assets/ea59cfb8-6439-4166-b295-1776d3c0bbfb" />

