# Privacidade do Pestinha

O Pestinha roda só no seu computador. Sem a IA ligada, ele não envia nada para a internet.

## O que ele lê

- O **nome** do programa em primeiro plano (por exemplo `code.exe`). Nunca o título nem o conteúdo da janela.
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
- **O que fica gravado:** nada, a não ser que você ligue **Lembrar o que viu**. O print, o título, o
  comentário e a conversa ficam só na memória enquanto o app está aberto (o botão **Esquecer** do chat
  apaga a conversa na hora). Não vão para `memory/` nem para o log. O que fica é o efeito na rede neural,
  como qualquer outro estímulo.
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

## Pesquisar na internet pelo Hermes (desligado por padrão)

Só vale com **Usar IA**, **Ver minha tela** e **Pesquisar na internet (Hermes)** ligados.

- **O que vai para o Hermes:** o termo da pesquisa (até 80 caracteres, escolhido pelo modelo que olhou a
  tela, que é instruído a não pôr nomes, e-mails, senhas, números nem dados pessoais), o resumo curto da
  última olhada, o estado da rede e, com **Lembrar o que viu**, as lembranças dos seus computadores (os
  mesmos resumos curtos do serviço de memória). **Nunca** o print nem o título da janela. Com o Hermes em
  outro computador da rede, isso passa sem criptografia (http), a não ser que você use um endereço https.
- **Para onde vai depois:** o Hermes manda o termo para o motor de busca configurado nele e manda o
  pedido para o modelo de IA dele (no teste, DeepSeek). O Hermes guarda as sessões no histórico dele
  (`hermes sessions`); o Pestinha não grava nada disso em `memory/` nem no log.
- **Quantas vezes:** no máximo uma pesquisa a cada 10 minutos.
- Deixe a API do Hermes só com a ferramenta de pesquisa (veja o README): assim, nada que apareça na tela
  consegue fazer ele rodar comandos ou mexer em arquivos.
- O pânico, a pausa ou desligar a pesquisa descartam a dica que ainda estava a caminho.

## Memória em outro computador (desligado por padrão)

Com **Compartilhar a memória dele** e o endereço do **Servidor da memória** (ver `servidor/memoria/`), os
arquivos do pet em `memory/pets/<pet>/` (a tabela abaixo, as lembranças de cada computador e o
`.sync.json`, que só anota o que já foi sincronizado) e a definição dele (`pets/<pet>.json`) também ficam
nesse servidor, para todos os seus computadores usarem o mesmo pet. O servidor guarda o nome de cada
computador e o sistema (Windows, macOS, Linux) de quem gravou. Permissões, painéis, rotina e log não vão.
Na rede local tudo passa sem criptografia (http), a não ser que você use um endereço https; sem
`PESTINHA_MEMORIA_TOKEN`, qualquer um da sua rede pode ler o servidor. **Apagar todos os dados** apaga só
este computador: no servidor, apague a pasta do pet em `~/pestinha-memoria/dados/`.

## O que ele grava (tudo em `memory/`)

Do app e seu, direto em `memory/`:

| Arquivo | Conteúdo |
|---|---|
| `permissions.json` | As opções que você escolheu |
| `timeline.csv` | Uma linha por minuto: hora, categoria de programa, trocas de janela, ocioso. Só com "Aprender minha rotina" ligado |
| `panels.json` | Posição dos painéis, do notebook e da placa |
| `logs/pestinha.log` | Mensagens do programa (sem conteúdo de janelas) |

De cada personagem, em `memory/pets/<pet>/` (um personagem não lê a memória do outro):

| Arquivo | Conteúdo |
|---|---|
| `nervous.json` | Estado da rede neural (habituação e aprendizado) |
| `episodes.jsonl`, `preferences.json` | Resultado de cada travessura e preferências aprendidas |
| `conditioning.json` | O que ele aprendeu a antecipar |
| `drives.json` | Energia, estimulação e carência |
| `protest.json`, `sad_protest.json` | Insatisfação e tristeza |
| `castigo.json` | Fugas do cantinho, rancor e receio |
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
- **Apagar todos os dados do Pestinha** apaga a pasta `memory/` inteira, com a memória de todos os personagens (pede confirmação e fecha o programa).
- Você também pode apagar a pasta `memory/` manualmente, com o programa fechado.

## Controle

- Cada permissão pode ser desligada na tela de configurações; desligar uma permissão também recolhe o que
  já estava na tela.
- O atalho **Ctrl + Alt + Shift + B** desliga tudo na hora, e ele continua desligado até você religar.
