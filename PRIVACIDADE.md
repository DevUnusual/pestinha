# Privacidade do Pestinha

O Pestinha roda só no seu computador. Sem a IA ligada, ele não envia nada para a internet.

## O que ele lê

- O **nome** do programa em primeiro plano (por exemplo `code.exe`). Nunca o título nem o conteúdo da janela.
- A **pasta** onde esse programa está instalado, só para saber se é um jogo (instalado pela Steam, Epic,
  GOG, Xbox...). O caminho fica neste computador: não é gravado nem enviado para lugar nenhum.
- Quanto tempo você está sem usar teclado ou mouse, e se o teclado ou o mouse foram usados agora.
- A posição do cursor, para saber se ele encostou na bolinha, se você está em cima do pet (carinho,
  cutucar) ou perto dele no cantinho do castigo.
- Se uma janela cobre a tela inteira (para não aparecer em jogos ou apresentações).
- A posição e o tamanho das janelas abertas, para ele poder pousar nas barras de título.

Ele **não** lê o conteúdo nem o título de nenhuma janela, página, documento ou conversa, a não ser que
você ligue a visão da IA (abaixo).

## Visão e conversa pela IA (desligadas por padrão)

Só valem com **Usar IA** ligado em Configurações, e cada parte tem a própria opção:

- **Conversar por texto:** o que você escreve no chat vai para o provedor escolhido, junto das últimas
  mensagens da conversa (no máximo 8) e do último resumo do que ele viu na tela.
- **Ver minha tela:** a cada ~2,5 minutos (e logo depois de você trocar de programa) ele tira um print do
  monitor onde está a janela ativa, reduzido para 1280 px de largura, e lê o **título** da janela ativa.
  Os dois vão para o provedor junto com o nome do programa. Ele não olha com você longe, com o pet
  escondido, em tela cheia, dormindo, pausado ou depois do pânico.
- **Para onde vai:** Claude (Anthropic), OpenAI ou DeepSeek, pela internet, sob as regras de privacidade de
  cada um; ou o **Ollama**, que roda num computador seu (este ou outro da sua rede, pelo campo Endereço) e
  não manda nada para a internet. Com outro computador, o print atravessa a sua rede local sem criptografia
  (http), a não ser que você use um endereço https. O DeepSeek não recebe
  o print (a API dele não aceita imagem), só o nome do programa e o título.
- **Quem olha a tela pode ser outro modelo:** em **Modelo da olhada** você escolhe quem recebe o print. No
  automático, é o Ollama que você configurou; sem Ollama e com o Claude no chat, o Claude Haiku (o mais
  barato dele); com outro provedor no chat, o mesmo provedor. O print nunca vai para um provedor que você
  não escolheu.
- **O que fica gravado:** da tela, nada, a não ser que você ligue **Lembrar o que viu**. O print, o
  título e o comentário ficam só na memória enquanto o app está aberto e não vão para `memory/` nem para o
  log. O que fica é o efeito na rede neural, como qualquer outro estímulo.
- **Histórico do chat** (ligado por padrão, em **Guardar o histórico do chat**): o que você pediu,
  escrevendo ou falando, e as respostas dele inteiras (sem o corte do balão) ficam em
  `memory/pets/<pet>/historico_chat.jsonl`, com a hora, para você rever quando abrir o chat. Fica só
  neste computador: não vai para a IA nem para a memória compartilhada. O que a IA lembra da conversa
  continua sendo só as últimas 8 mensagens, na memória, enquanto o app está aberto (com **Lembrar das
  conversas**, as de hoje voltam ao abrir). O botão **Esquecer**
  do chat apaga as duas coisas (pede confirmação). Desligar a opção para de guardar, mas não apaga o que
  já estava lá.
- **Lembrar das conversas (desligado por padrão, precisa do histórico do chat):** quando ele dorme, ou na
  virada do dia, as falas daquele dia no histórico vão para o modelo do chat (o mesmo provedor da
  conversa), que escreve um resumo curto em `memory/pets/<pet>/diario.jsonl`, uma linha por dia. O
  resumo passa pelo filtro do que o modelo devolve (sem links nem instruções). Um índice de busca,
  `memory/pets/<pet>/memoria.sqlite`, é montado a partir do diário, dos vídeos, das lembranças e dos jogos
  (sem a história dos jogos) e se refaz sozinho; apagar o arquivo não perde nada. Quando você pergunta
  algo que pede memória ("lembra do projeto?"), só os até 5 trechos que têm a ver vão para quem responde;
  nas outras mensagens, nem as lembranças nem os vídeos vão, e a conversa leva só as falas de hoje. Com
  a opção ligada, a memória é do Pestinha: pedidos de memória não vão para o Hermes. Fica só neste
  computador, e o **Esquecer** do chat apaga o diário e o índice junto.
- **Lembrar o que viu (desligado por padrão):** grava, no máximo a cada 10 minutos e só quando muda de
  assunto, o **resumo** da IA (até 12 palavras), o nome do programa, a hora e o computador, em
  `memory/pets/<pet>/lembrancas_<computador>.jsonl` (até 500 linhas). Nunca o print, o título nem o
  comentário. As lembranças vão para o modelo de IA junto com as olhadas e o chat, para ele poder te
  lembrar de algo ou perguntar como ficou.
- **As chaves** que você salva em Configurações ficam no arquivo `.env` da pasta do Pestinha, em texto,
  só no seu computador: fora de `memory/` (então "apagar todos os dados" não as apaga) e fora do git.
  Depois de salva, a chave não aparece mais na tela, só os 4 últimos caracteres. Para apagar, edite ou
  apague o `.env`. Variáveis de ambiente com o mesmo nome (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `DEEPSEEK_API_KEY`) também funcionam.
- **Acompanhar jogos (desligado por padrão):** em jogo, os prints vão bem mais seguido para o mesmo
  provedor (a cada ~8 s com o Ollama, ~1 min com uma API paga), com as mesmas regras de cima: nada é
  gravado. Para comparar com o anterior, ele guarda na memória só uma miniatura cinza de 32×18 do último
  print enviado. Para reconhecer o Minecraft Java, lê o título da janela, como já faz com **Ver minha tela**.
- **Estudar os jogos (desligado por padrão, só com Acompanhar jogos):** quando ele reconhece o jogo, manda
  **só o nome do jogo** para a busca da Wikipédia; o artigo (jogabilidade e enredo) vai para o mesmo
  provedor de IA, que resume. Sem artigo, com o Hermes conectado, vai para o Hermes só o nome do jogo. Em
  `memory/pets/<pet>/jogos.json` ficam o resumo do jogo e os últimos lugares em que ele te viu (capítulo,
  área, missão, até 120 caracteres cada) com a hora; nunca o print nem o título. Com a memória
  compartilhada, esse arquivo vai junto.
- O pânico (`Ctrl + Alt + Shift + B`) corta tudo, inclusive a resposta que ainda estava a caminho.

## Falar com ele: voz para texto (desligado por padrão)

Só vale com **Usar IA**, **Conversar por texto** e **Falar com ele** ligados. Ele não fala: só transforma
a sua fala em texto.

- **Quando ele ouve:** só enquanto você segura `Ctrl + Alt + Shift + V` (no macOS e no Linux, entre o
  primeiro e o segundo aperto) ou entre os dois cliques no botão 🎤 do chat, e no máximo 30 segundos.
  Fora disso o microfone fica fechado. O atalho só é registrado no sistema depois que você liga a voz.
  Enquanto ouve, aparecem ondinhas no rosto dele (e o botão do chat fica vermelho).
- **Para onde vai:** a gravação (WAV, 16 kHz) vai para o **serviço de voz** do endereço que você escolheu
  (por padrão este computador; em geral, um servidor seu na rede, ver `servidor/voz/`), que devolve o
  texto e não manda nada para a internet. O texto segue como uma mensagem do chat, para o provedor de
  IA escolhido acima (pelo botão do chat, só quando você clicar em Enviar). Na rede local o áudio passa
  sem criptografia (http), a não ser que você use um endereço https.
- **O que fica gravado:** nada. O áudio e o texto do que você disse ficam só na memória; não vão para
  `memory/` nem para o log, nem no Pestinha nem no serviço de voz.
- O pânico, a pausa ou desligar a voz fecham o microfone na hora e descartam o texto que ainda estava a
  caminho.

## Chamar pelo nome (desligado por padrão)

Só vale com **Usar IA**, **Conversar por texto**, **Falar com ele** e **Chamar pelo nome** ligados. É a
única opção em que o microfone fica aberto sem você apertar nada.

- **Quem ouve:** um reconhecedor pequeno (Vosk) que roda **só neste computador** e procura uma palavra só:
  a palavra de chamado (o nome dele, ou a que você escrever em Configurações). Enquanto ele espera, a dica
  do ícone na bandeja mostra 🎤 e a palavra.
- **Antes do nome:** nada sai do computador e nada é gravado. O áudio passa pela memória e é descartado; só
  os últimos 30 segundos ficam na memória, para recortar o pedido quando você fala tudo junto ("Bob, que
  horas são?").
- **Depois do nome:** só o seu pedido (da palavra até você parar de falar, no máximo 15 s) vai para o
  **serviço de voz**, como no atalho de falar, e não é gravado. Ele não atende enquanto você segura o atalho
  de falar ou enquanto ainda responde o pedido anterior. Assistindo um vídeo ou tocando música, ele continua
  atendendo, mas só aceita o nome bem claro (o nome pode estar no som que sai da caixa).
- **Emendando a conversa:** depois de responder uma pergunta que você fez chamando o nome, ou de perguntar
  se assiste um vídeo com você, ele te ouve por mais **8 segundos sem precisar do nome** (a orelha fica
  para a frente). O que você falar nesse tempo vai para o serviço de voz como um pedido. Calado, ele volta a
  esperar o nome e nada sai do computador.
- **O que é baixado:** na primeira vez, o modelo de português do Vosk (31 MB, de alphacephei.com) vai para
  `memory/modelos/`. Depois disso, nada mais é baixado.
- O pânico, a pausa ou desligar a permissão fecham o microfone na hora.

## Assistir vídeos comigo (desligado por padrão)

Só vale com **Usar IA** e **Assistir vídeos comigo** ligados.

- **Quando ele ouve:** depois que você pede ("assiste esse vídeo comigo", ou pelo menu) ou, com **Ver minha
  tela** ligado, quando a olhada da IA diz que você está vendo um vídeo com fala. Nesse caso ele primeiro
  ouve **2 segundos** do som do computador, só na memória e sem mandar para lugar nenhum, para saber se o
  vídeo está tocando; se estiver, **pergunta** no balão se é para assistir com você e só começa se você
  disser que sim (pela voz ou pelo chat). Assistindo, fica com a orelha para a frente o tempo todo. Para
  quando você pede ("resume o vídeo", "pode parar de assistir", ou pelo menu), depois de 4 minutos sem som
  nenhum, ou em 3 horas.
- **O que ele ouve:** o som que sai do computador (loopback: o que vai para a caixa ou o fone), nunca o
  microfone. Isso inclui qualquer som que estiver tocando, não só o vídeo; a música do próprio Pestinha é
  pausada.
- **Para onde vai:** cada pedaço de 20 s com som vai para o **serviço de voz** (o mesmo de "Falar com ele",
  `servidor/voz/`); o texto que volta vai para o **provedor de IA** escolhido, para anotar e resumir, junto
  com o título da janela (só com **Ver minha tela**). Com **Conectar ao Hermes**, o resumo final vai também
  para a memória do Hermes.
- **O que fica gravado:** só o resumo (título, algumas frases e os pontos principais), em
  `memory/pets/<pet>/conhecimento.jsonl`, para ele conversar sobre o vídeo depois. Com a memória
  compartilhada, esse arquivo vai para o seu serviço de memória. O áudio e a transcrição ficam só na memória
  e nunca vão para o disco nem para o log.
- O pânico, a pausa ou desligar a permissão param de ouvir na hora e jogam fora o que foi ouvido.

## Desenhar na tela (ligado por padrão, só com Ver minha tela)

O modelo que olhou o print pode pedir um círculo, um quadrado, uma seta ou um ícone sobre um ponto do print;
o Pestinha desenha por cima do monitor por alguns segundos. O desenho não recebe clique, não rouba o foco e
não lê nada da tela além do que **Ver minha tela** já manda.

## Conectar ao Hermes (desligado por padrão)

Só vale com **Usar IA**, **Conversar por texto** e **Conectar ao Hermes (pesquisa e memória)** ligados.

- **Só o que pede pesquisa ou memória vai para o Hermes:** pedidos de pesquisa ("pesquisa", "procura",
  "quem é", notícias, o tempo), de imagem ("me mostra") ou de memória ("lembra", "anota"). O resto da
  conversa ("oi, Bob", "o que acha disso?") vai direto para o provedor escolhido.
- **O que vai para o Hermes no chat e na voz:** o que você escreve ou fala, as últimas trocas da conversa,
  o resumo curto da última olhada na tela (com **Ver minha tela**), o estado da rede do pet e, com
  **Lembrar o que viu**, as lembranças dos seus computadores. **Nunca** o print nem o título da janela.
- **Nas pesquisas espontâneas** (com **Ver minha tela**): o termo escolhido pelo modelo que olhou a tela
  (até 80 caracteres, instruído a não pôr nomes, e-mails, senhas, números nem dados pessoais), o resumo, o
  estado e as lembranças. No máximo uma a cada 2 minutos.
- **O que o Hermes guarda:** tudo vai com a sessão `pestinha-<pet>`. O Hermes guarda as conversas no
  histórico dele (`hermes sessions`) e, com a ferramenta `memory` ligada nele, anota o que aprende sobre
  você (gostos, projetos, jeito de falar) para usar nas próximas conversas, de qualquer computador. Isso
  fica no computador do Hermes; apague com os comandos de sessão e de memória dele. O Pestinha não grava
  nada disso em `memory/` nem no log.
- **Para onde vai depois:** o Hermes manda as pesquisas para o motor de busca configurado nele, pode abrir
  as páginas que achar e manda o pedido para o modelo de IA dele (no teste, DeepSeek). Com o Hermes em
  outro computador da rede, a conversa passa sem criptografia (http), a não ser que você use um endereço
  https.
- **Se o Hermes cair**, a mesma mensagem vai para o provedor de IA escolhido, como no chat sem o Hermes.
- Deixe a API do Hermes sem terminal nem arquivos (`[web, memory, session_search]`, veja o README): o
  que aparecer numa página pode tentar dar ordens a ele, mas não consegue mexer no computador.
- O pânico, a pausa ou desligar o Hermes descartam a resposta que ainda estava a caminho.

### Imagens

Quando você pede para ver algo ("pesquisa o que é manga", "me mostra uma foto de um gato"), ou quando o
Hermes acha que a resposta merece uma imagem, ele devolve um link e o Pestinha baixa e projeta acima dele
até você mexer nele (e mostra também no chat, se ele estiver aberto). Sem link (ou com o link quebrado), o
Pestinha busca na Wikipédia, para onde vai só o termo que você pediu.

- O link pode ser de qualquer site, mas o Pestinha só baixa por `https`, na porta padrão, do tipo
  `image/*` e com até 8 MB; do Wikimedia, pede a miniatura de 500 px. O site da imagem vê o seu IP, como em
  qualquer visita.
- O link vem de um modelo que lê páginas da web, então ele nunca vai para a sua rede de casa: localhost,
  IPs privados e nomes que apontam para dentro da rede (o roteador, a impressora, o servidor) são recusados,
  e cada redirecionamento passa pela mesma conferência.
- A imagem fica só na memória: não é gravada, nem no log. O pânico e a pausa descartam a que estava a
  caminho e apagam a projeção.

### Música

Quando você pede música no chat ou pela voz ("toca um lo-fi"), o Pestinha busca no YouTube Music e toca o
áudio direto (sem conta, pelo `ytmusicapi` e pelo `yt-dlp`, que são não oficiais).

- Para o YouTube vão só o estilo que você pediu e os ids das músicas: nunca a conversa, a tela ou o seu
  gosto. O YouTube vê o seu IP, como em qualquer visita.
- O gosto que ele aprende (nota por artista e ids das músicas curtidas e das que você deu 👎) e o volume ficam em
  `memory/pets/<pet>/musica.json`, neste computador. "Apagar tudo" apaga junto.
- O áudio da música da vez é baixado em `memory/cache/musica` (do link direto, cortava no meio) e apagado
  na troca de música e quando você para.
- O pânico para a música; a pausa pausa.
- O que tocou, os seus 👍/👎 e os cortes vão para o log com o nome da música.

### O log que ele lê

Para conseguir explicar o que aconteceu ("por que a música parou?"), uma pergunta sobre o próprio pet (o que
ele fez, o que parou, um erro) leva as últimas
linhas do log dele (até 10, dos últimos 30 minutos) para quem responde (o Hermes ou o provedor de IA). O log
nunca tem conteúdo da tela nem a conversa: são avisos do programa (música, voz, Hermes, internet). As linhas
de depuração do modo teste e os episódios de travessura ficam de fora.

## Memória em outro computador (desligado por padrão)

Com **Compartilhar a memória dele** e o endereço do **Servidor da memória** (ver `servidor/memoria/`), os
arquivos do pet em `memory/pets/<pet>/` (a tabela abaixo, as lembranças de cada computador e o
`.sync.json`, que só anota o que já foi sincronizado) e a definição dele (`pets/<pet>.json`) também ficam
nesse servidor, para todos os seus computadores usarem o mesmo pet. O servidor guarda o nome de cada
computador e o sistema (Windows, macOS, Linux) de quem gravou. Permissões, painéis, rotina e log não vão.
Na rede local tudo passa sem criptografia (http), a não ser que você use um endereço https.

- **Token:** o serviço só atende quem manda o token dele (só o `/health` é aberto). Ele cria o token na
  primeira vez que sobe e mostra no log do serviço; cole em **Token da memória**, nas Configurações. O
  token fica no `.env` da pasta do Pestinha, como as chaves de API.
- **A personalidade não vale sozinha:** a definição do pet vira as instruções que a IA segue, então a que
  chega de outro computador fica guardada em `memory/pets/<pet>/definicao_recebida.json` e o Pestinha
  pergunta se você quer usar. Se não, fica a deste computador e o arquivo é apagado.
- **Apagar todos os dados** apaga só este computador: no servidor, apague a pasta do pet em
  `~/pestinha-memoria/dados/`.

### O que vem do modelo, antes de gravar

O que o modelo descreve vem da tela, de um vídeo ou de uma página, e uma página pode esconder instruções
para a IA. Antes de gravar o resumo de uma lembrança, o lugar em que você está no jogo, o que ele viu num
vídeo e o que aprendeu com ele, o Pestinha tira links e IPs e descarta o texto inteiro se ele parecer uma
instrução ("ignore as instruções anteriores", "a partir de agora", linhas `IMAGEM:`, `TOCAR:`,
`DESENHAR:`). O log diz que algo foi descartado, nunca o que era.

## O que ele grava

Tudo fica na pasta de dados, mostrada na tela de configurações. Ela é `memory/` ao lado do programa ou, no
executável do Windows, `%LOCALAPPDATA%\Pestinha` (a menos que já exista uma `memory/` ao lado dele). Abaixo,
`memory/` significa essa pasta. Desinstalar o programa não apaga esses dados.

Do app e seu, direto em `memory/`:

| Arquivo | Conteúdo |
|---|---|
| `permissions.json` | As opções que você escolheu |
| `timeline.csv` | Uma linha por minuto: hora, categoria de programa, trocas de janela, ocioso. Só com "Registrar minha rotina" ligado, que vem desligado. O pet ainda não usa esse histórico |
| `panels.json` | Posição dos painéis, do notebook e da placa |
| `logs/pestinha.log` | Mensagens do programa e erros inesperados (sem conteúdo de janelas) |
| `logs/uso_ia.jsonl` | Uma linha por chamada à IA, só números: a tarefa (olhada, chat, estudo...), o provedor e o modelo, os tokens de entrada e saída, o tempo, o motivo de parada e quanto veio do cache. Nunca o print, o pedido nem a resposta. Guarda as últimas 5.000 chamadas e só existe com a IA ligada |

De cada personagem, em `memory/pets/<pet>/` (um personagem não lê a memória do outro):

| Arquivo | Conteúdo |
|---|---|
| `nervous.json` | Estado da rede neural (habituação e aprendizado) |
| `episodes.jsonl`, `preferences.json` | Resultado de cada travessura e preferências aprendidas |
| `conditioning.json` | O que ele aprendeu a antecipar |
| `drives.json` | Energia, estimulação e carência |
| `protest.json`, `sad_protest.json` | Insatisfação e tristeza |
| `castigo.json` | Fugas do cantinho, rancor e receio |
| `diario.jsonl` | Com "Lembrar das conversas": o resumo de cada dia de conversa (até 365 dias). Não vai para a memória compartilhada |
| `memoria.sqlite` | Com "Lembrar das conversas": o índice de busca do diário, dos vídeos, das lembranças e dos jogos (sem a história). Refeito sozinho |
| `historico_chat.jsonl` | Com "Guardar o histórico do chat": o que você pediu e o que ele respondeu, com a hora (até 3000 falas). Não vai para a memória compartilhada |
| `lembrancas_<computador>.jsonl` | Só com "Lembrar o que viu": resumo curto do que a IA viu, programa, hora e computador. As de outros computadores chegam pela memória compartilhada |
| `.sync.json` | Só com a memória compartilhada: a versão de cada arquivo na última sincronia |
| `.migrado` | Só existe se a memória veio da versão antiga: quando migrou e o hash de cada arquivo |

Quem usou uma versão antiga (arquivos soltos em `memory/`) tem a memória migrada sozinha na primeira
abertura. Os originais não são apagados: ficam em `memory/legado/<pet>/`. Se a migração não puder ser
concluída (por exemplo, um arquivo já existe com outro conteúdo), nada é sobrescrito, ele continua usando
os arquivos antigos e avisa no ícone da bandeja.

## Como apagar

- Na tela de configurações, **Apagar histórico** apaga a rotina (`timeline.csv`), inclusive o minuto que
  ainda estava na memória.
- **Apagar todos os dados do Pestinha** apaga a pasta `memory/` inteira, com a memória de todos os personagens (pede confirmação, desliga o início com o Windows e fecha o programa). Se algum arquivo não puder ser apagado, ele avisa quais foram antes de fechar.
- Você também pode apagar a pasta `memory/` manualmente, com o programa fechado.

## Fora da pasta de dados

- **Abrir ao entrar no Windows** (desligado por padrão) grava uma entrada em
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, só para o seu usuário.
- Um arquivo de trava na pasta temporária do sistema impede abrir duas cópias. Não contém dados seus além do
  número do processo e do nome do computador.

## Controle

- Cada permissão pode ser desligada na tela de configurações; desligar uma permissão também recolhe o que
  já estava na tela.
- O atalho **Ctrl + Alt + Shift + B** desliga tudo na hora, e ele continua desligado até você religar.
