# Histórico de versões

## Acompanhar jogos

- **Visão ~10× mais rápida no Ollama:** o Pestinha pede para o modelo responder sem "pensar" antes
  (`reasoning_effort: none`). No `gemma4:e4b` (RTX 3070), a olhada caiu de ~5,9 s para ~0,6 s, com o
  mesmo JSON; o tamanho do print quase não pesava (1280 → 512 px: ~0,1 s).
- **Acompanhar jogos** (desligado por padrão, precisa de Usar IA e Ver minha tela): em jogo, olha a cada
  ~8 s com o Ollama (~1 min com API paga; 4 s e 20 s no modo teste) e o pedido vira "acompanhe a partida":
  itens, conquistas, mortes, jogadas boas. Não manda o print se a tela quase não mudou (miniatura 32×18)
  e fala no máximo a cada 45 s (12 s no modo teste).
- Mais jogos reconhecidos (Minecraft Bedrock, Roblox, Fortnite, LoL, Dota 2, Apex...) e o Minecraft Java
  (`javaw`) pelo título da janela.

## Pesquisa na internet pelo Hermes

- **Pesquisar na internet (Hermes)** (desligado por padrão, precisa de Usar IA e Ver minha tela): quando
  algo na tela chama a atenção dele (um jogo, um item, um erro), a olhada devolve um termo em
  `"pesquisar"`; o [Hermes](https://github.com/NousResearch/hermes-agent) pesquisa e a dica aparece no balão.
  Vai para o Hermes só o termo e o resumo da olhada, nunca o print nem o título. No máximo uma pesquisa a
  cada 10 min (1 min no modo teste); pânico e pausa descartam a que estiver a caminho.
- **Endereço do Hermes**, **Chave do Hermes** (a `API_SERVER_KEY` dele, guardada como `HERMES_API_KEY` no
  `.env`) e **Testar Hermes** nas Configurações. Novo `pestinha/ia/pesquisa.py`.
- Com **Lembrar o que viu**, as lembranças dos seus computadores vão junto: rodando o Hermes no mesmo
  servidor da memória, todos os computadores falam com o mesmo Hermes (e a memória dele).
- Testado com o Hermes 0.22.2 (DeepSeek) no servidor da casa, com o api_server só com a ferramenta
  `search`: ~10 s por dica; pedido para rodar um comando, ele recusa (não tem a ferramenta).

## O mesmo pet em todos os computadores

- **Serviço de memória** em `servidor/memoria/` (só Python, nada para instalar): guarda a rede, a memória,
  o humor e a personalidade (`pets/<pet>.json`) de cada pet, com versão por documento. Serviço de usuário
  (`systemctl --user`), porta 11600, token opcional (`PESTINHA_MEMORIA_TOKEN`).
- **Compartilhar a memória dele** (desligado por padrão) e **Servidor da memória** + **Testar memória** nas
  Configurações. Ao abrir, baixa o que outro computador gravou (vale o mais novo); aberto, manda o que
  mudou a cada minuto e ao fechar (vale o daqui). Sem rede, segue com a memória local. Avisa se o pet já
  está aberto em outro computador. Novo `pestinha/memoria_remota.py`.
- **Lembrar o que viu** (desligado por padrão): o resumo curto da IA, o programa, a hora, o sistema e o
  computador vão para `lembrancas_<computador>.jsonl`, só quando muda de assunto e no máximo a cada 10 min.
  Cada computador grava as próprias e lê as dos outros: no Mac, ele pode lembrar do que você fazia no
  Windows e perguntar como ficou. Novo `pestinha/mind/lembrancas.py`.

## Rede e IA em sincronia

- **Rede -> IA:** cada olhada e cada mensagem do chat levam o estado da rede naquele instante (emoção,
  o que os motores querem, energia, tédio, carência, protesto e o motivo, castigo, o que ele já enjoou).
  O temperamento de `pets/<pet>.json` vira texto no prompt do sistema. Perguntado por que está bravo ou
  como é o temperamento dele, responde pela rede, não com algo genérico. Novo `pestinha/mind/sincronia.py`.
- **IA -> rede:** como antes, pelos canais `VISAO_*` e `CONVERSA`.
- O protesto anota o motivo de cada salto da insatisfação (notebook arrancado, cartaz fechado à força), e
  as mudanças de estágio vão sempre para o log, não só na depuração.
- `pets/<pet>.json` aceita `exemplos` (falas que dão o tom) e `evitar` (frases batidas proibidas). Ele não
  repete os últimos comentários.
- Bryan novo: curioso e marrento. Pergunta sobre o que aparece de novo na tela; a rede dele também ficou
  mais curiosa com novidade vista (`VISAO_NOVO->CURIOUS`).
- A visão só marca "erro" para erro de verdade (código normal não conta).
- Monitor neural: os canais se ajustam à altura (2 ou 3 colunas) e a janela cabe na tela.
- Dois cliques no pet abrem o chat.
- `rotulos.py` passou de `ui/` para `core/`.

## Falar com ele (voz para texto)

- Opcional e desligado por padrão (**Falar com ele**, no grupo de IA): a sua fala vira texto e ele
  responde por escrito. Segure `Ctrl + Alt + Shift + V` e fale (o texto vai direto para ele), ou use o
  botão 🎤 da janela Conversar (o texto cai no campo para conferir). No macOS e no Linux o atalho é
  aperta-e-aperta. Ele nunca ouve sem você apertar e para sozinho depois de 30 s.
- Ondinhas no rosto mostram que ele está ouvindo.
- **Serviço de voz** em `servidor/voz/` (compatível com `/v1/audio/transcriptions` da OpenAI):
  faster-whisper `large-v3-turbo` na placa de vídeo, como serviço de usuário (`systemctl --user`), com
  nice 10, sem sudo. Configurações: **Servidor da voz** e **Testar voz**.
- O pânico, a pausa e desligar a voz fecham o microfone na hora.
- Novos `pestinha/ia/voz.py` (sem Qt) e `pestinha/mind/voz_ctl.py`; atalho de falar em `plataforma/`.

## Visão e conversa pela IA

- Opcional e desligado por padrão: o grupo **Visão e conversa (IA)** nas Configurações liga a IA, a visão
  da tela, os comentários e o chat, e escolhe o provedor (Claude, OpenAI, DeepSeek ou Ollama local) e o
  modelo. A chave é colada no campo **Chave** e gravada no `.env` (fora do git) pelo botão **Salvar
  chave**, que avisa em verde e apaga o campo; vale sem reabrir. O campo **Modelo** recusa chaves.
- **Visão:** de tempos em tempos (e logo depois de trocar de programa) ele manda um print e o título da
  janela ativa para o modelo, que devolve um resumo, talvez um comentário, e quatro sinais (graça, erro,
  foco, novidade).
- **Rede:** cinco canais sensoriais novos (`VISAO_GRACA`, `VISAO_ERRO`, `VISAO_FOCO`, `VISAO_NOVO`,
  `CONVERSA`), agora 500 neurônios. A IA descreve a tela; a rede decide o que ele sente. Ver você focado
  inibe travessuras.
- **Ollama em outro computador:** campo **Endereço** (aceita só o IP, completa `http://` e a porta) e botão
  **Testar conexão**, que diz se o Ollama respondeu e se o modelo está instalado. `gemma4:e4b` é o modelo
  recomendado para o Ollama.
- **Balão de fala** em cima do pet para os comentários e as respostas.
- **Chat por texto** pelo menu do pet (Conversar), e "O que você está vendo?" para pedir uma olhada agora.
- Cada personagem tem uma `persona` em `pets/<pet>.json`. O Jorge continua sátira: nunca vende nem pede nada.
- Nada da IA é gravado em disco; pânico, pausa ou desligar a IA descartam a resposta a caminho.
- Nova camada `pestinha/ia/` (sem Qt), entre `core` e `sense`.

## Suporte a macOS e Linux

- Toda a leitura do sistema (programa em primeiro plano, tempo ocioso, janelas, tela cheia, foco e o atalho
  de pânico) passa para `pestinha/plataforma/`, com um módulo por sistema. O resto do código não sabe
  qual sistema está rodando.
- O Windows continua com o mesmo comportamento: o código foi movido, não reescrito.
- macOS: Quartz e AppKit (pyobjc), tempo ocioso pelo `ioreg` se não houver pyobjc. Atalho via pynput.
- Linux (X11): xdotool, wmctrl e xprintidle; atalho via pynput. Em Wayland, o pet não enxerga janelas
  nem o tempo ocioso, e o atalho não funciona.
- A checagem de atividade reconhece os nomes de programa dos três sistemas (com ou sem `.exe`).

## Renomeação para Pestinha

- O programa e o pacote Python passam a se chamar `pestinha/` (antes `bryan/`); a classe principal é
  `PestinhaApp`; o executável, o log e a documentação usam Pestinha.
- Bryan continua sendo o nome do primeiro personagem: `pets/bryan.json`, `pets/bryan/`, a memória
  `memory/pets/bryan/` e os arquivos de conteúdo dele não mudaram.
- Os comentários e textos que falavam do pet em geral passam a dizer "o pet".

## 0.7.0 — primeira versão pública (em preparação)

### O que ele faz
- Pet de tela com corpo físico: gravidade, quique, giro, pouso nas barras de título, arraste e arremesso.
- Rede neural pulsada de 470 neurônios LIF, com 30 canais sensoriais, 10 populações de interneurônios
  e 15 motores (8 de expressão e 7 de decisão).
- Emoções vindas dos motores; carinho com olhinhos fechados de felicidade.
- Bolinha de tênis, notebook de trabalho (VS Code, Visual Studio, PyCharm, Claude, Codex) e pedido de
  trabalho que ele pode recusar.
- Travessuras com memes, fotos, post-its e bilhetes tristes, com frequência decidida pela rede.
- Protesto em estágios até a revolução contra o cursor, com cartazes e bolinhas de papel.
- Cantinho do castigo: placa arrastável, perdão por carinho, fuga por vontade acumulada, rancor, receio,
  medo condicionado da placa e cartazes de xingamento.
- Aprendizado: habituação, regra de três fatores, condicionamento Rescorla–Wagner, memória episódica.
- Pânico (`Ctrl + Alt + Shift + B`), pausa, modo teste, monitor neural e painel de protesto.

### Memória por personagem
- Cada personagem tem a sua memória em `memory/pets/<pet>/` (rede e os sete arquivos de memória); o que
  é do app (permissões, rotina, painéis, log) continua em `memory/`.
- Migração automática da versão antiga: copia, confere, guarda os originais em `memory/legado/<pet>/` e
  só então marca como migrado. Conflito ou falta de permissão não sobrescrevem nada: ele segue com os
  arquivos antigos e avisa na bandeja.

### Conteúdo por personagem
- Frases, cartazes e memes de cada personagem ficam em `pets/<pet>/`; imagens neutras (bolinhas, notebook)
  e suas fotos em `assets/comum/`. Um personagem nunca usa o conteúdo de outro: sem conteúdo próprio, usa
  frases neutras ou não faz aquela travessura.
- Os cartazes do cantinho do castigo saíram do código para as seções `[castigo]` e `[xingamento]` do
  `cartazes.txt` do pet.

### Escolha do personagem
- O programa passa a se chamar **Pestinha**; o Bryan é o primeiro personagem.
- O personagem é escolhido em Configurações (vale ao reabrir). Só `pets/<pet>.json` vira opção.
- Os textos usam o nome do personagem onde é ele que fala (apresentação, "Estou aqui", notebook, monitor
  neural, painel de protesto) e o nome do programa no resto (configurações, bandeja, pânico).
- O log passa a ser `memory/logs/pestinha.log`; o executável, `Pestinha.exe`.

### Jorge
- Segundo personagem: coach de finanças e IA, trambiqueiro. Mesma rede e mesmos estágios do Bryan, com
  outra semente, outro temperamento e conteúdo próprio (recadinhos, bilhetes tristes, cartazes de todos os
  estágios e do cantinho, e um panfleto de mentoria no lugar da bolinha de papel). Cinco memes para cada uma de felizes, contentes, curiosos e bravos, em `pets/jorge/memes/`.
- `ferramentas/medir_cartazes.py` confere, com as fontes de verdade, se cada cartaz cabe na placa.
- `ferramentas/gerar_panfleto.py` desenha o panfleto do Jorge.

### Cores e acessórios
- Cada pet pode ter as próprias cores (moldura, tela, olhos) e acessórios (óculos, gravata) no campo
  `aparencia` do `.json`. Os acessórios são uma camada por cima do rosto; olhos e expressões não mudam.
- O Jorge tem moldura e olhos dourados e gravata vermelha. O Bryan continua igual.

### Licença
- Código sob GPL-3.0-or-later (`LICENSE`).

### Qualidade
- Arquitetura em camadas verificada por teste; `app.py` dividido em composição e mixins de sessão e
  interação.
- Persistência validada: escrita atômica, recusa de `NaN`, carga tudo-ou-nada.
- Cinco rodadas de auditoria, com cada bug corrigido coberto por teste, registradas em `docs/auditorias/`.
- Suíte de testes, bateria de 100 cenários do cantinho e fuzzer com invariantes.
