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
- **O que fica gravado:** nada. O print, o título, o resumo e a conversa ficam só na memória enquanto o app
  está aberto (o botão **Esquecer** do chat apaga a conversa na hora). Não vão para `memory/` nem para o
  log. O que fica é o efeito na rede neural, como qualquer outro estímulo.
- **As chaves** que você salva em Configurações ficam no arquivo `.env` da pasta do Pestinha, em texto,
  só no seu computador: fora de `memory/` (então "apagar todos os dados" não as apaga) e fora do git.
  Depois de salva, a chave não aparece mais na tela, só os 4 últimos caracteres. Para apagar, edite ou
  apague o `.env`. Variáveis de ambiente com o mesmo nome (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `DEEPSEEK_API_KEY`) também funcionam.
- O pânico (`Ctrl + Alt + Shift + B`) corta tudo, inclusive a resposta que ainda estava a caminho.

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
