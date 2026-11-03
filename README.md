# Pestinha

Pets de tela para Windows, macOS e Linux, cada um com o próprio cérebro. São dois personagens por enquanto:

- **Bryan**, o original: uma telinha com dois olhos que mora no seu monitor principal. Cai, quica, pousa nas
  barras de título das janelas, brinca com uma bolinha, trabalha num notebook quando você programa, apronta
  com memes e post-its, protesta contra o cursor quando fica bravo e aprende com o seu carinho.
- **Jorge**, um personagem de sátira: um "coach" de finanças e IA que vive tentando vender mentorias para
  quem está na frente do computador. **Jorge não é uma referência a nenhum coach, empresa ou pessoa real.**
  É um personagem inventado para fazer piada com a cultura de promessas de enriquecimento rápido. Não vende,
  cobra nem pede nada de ninguém.

Os dois têm a mesma rede neural, mas cada um tem seu temperamento, seu conteúdo e sua memória, separados.
Quem decide o que o pet sente e faz é uma **rede neural pulsada** de 500 neurônios (integração e disparo com
vazamento), alimentada pelo que acontece no seu computador e pelo que você faz com ele. Algumas regras
do programa (limiares, o que pode ou não acontecer) são escritas à mão; a seção
[Como a decisão funciona](docs/ARQUITETURA.md#como-a-decisão-funciona) explica o que é aprendido e o que é regra.

> Projeto em desenvolvimento. Algumas coisas podem não funcionar direito e o comportamento pode
> mudar entre versões.

## Personagens

Cada personagem é um `pets/<pet>.json` (quem ele é) mais uma pasta `pets/<pet>/` (as frases, cartazes e
memes dele). Todos usam a mesma rede neural, mas cada um tem a própria memória: o que um aprende não
passa para o outro. Você escolhe o personagem em **Configurações**; a troca vale na próxima vez que abrir.
Para criar um, veja [pets/README.md](pets/README.md).

| Personagem | Quem é |
|---|---|
| **Bryan** | Revoltado contra o cursor, o Alt+F4 e o Gerenciador de Tarefas. Protesta, faz greve e revolução. |
| **Jorge** | Personagem de sátira. Não é referência a nenhum coach, empresa ou pessoa real. Os mesmos estágios viram prospecção, marketing agressivo, "assinatura premium" (só no cartaz) e colapso financeiro; ele atira panfletos de mentoria. É sátira: não vende, cobra nem bloqueia nada. Tem cinco memes felizes, contentes, curiosos e bravos próprios; as outras emoções ainda não têm. |

## O que o pet faz

| | |
|---|---|
| **Corpo** | Gravidade, quique, giro, pouso nas barras de título. Você arrasta, joga e gira com a rodinha. |
| **Emoções** | Saem dos motores da rede: feliz, contente, curioso, observando, bravo, triste, assustado, dramático, dormindo. |
| **Carinho** | Passe o mouse de um lado para o outro em cima dele: fecha os olhinhos de felicidade e aprende com isso. |
| **Bolinha** | Ele chuta e arremessa uma bolinha de tênis; você pode pegar, levar embora (ele reage) ou guardar. |
| **Notebook** | Quando você trabalha (VS Code, Visual Studio, PyCharm, Claude, Codex), ele pode sentar atrás do notebook e trabalhar junto. Você também pode pedir; ele decide se quer. |
| **Travessuras** | Traz memes, fotos e post-its para a tela. Com que frequência é decidido pela rede (tédio, curiosidade). |
| **Protesto** | Bravo por muito tempo: reclamação, manifestação, greve e revolução contra o cursor, com cartazes e bolinhas de papel. |
| **Tristeza** | Sozinho ou ignorado, fica triste, vai para o cantinho e cola bilhetes tristes. |
| **Cantinho do castigo** | Uma placa que você arrasta para onde quiser. Solte ele na frente dela e ele fica de castigo: olha para você, vira de costas, xinga em cartazes e, se a frustração durar, foge. Carinho faz ele perdoar. |
| **Sono e fogos** | Dorme quando a energia acaba. Muito feliz, solta fogos de artifício. |
| **Visão (IA, opcional)** | Com "Ver minha tela" ligado, de tempos em tempos ele olha um print da tela e entende o que você está fazendo: um erro na tela deixa ele alerta, um meme deixa ele brincalhão, você concentrado deixa ele quieto. Às vezes comenta num balãozinho. |
| **Conversa (IA, opcional)** | Botão direito nele, **Conversar**: você escreve e ele responde com a personalidade dele, sabendo o que está na sua tela. |

Tudo o que ele aprende (carinho, condicionamento, o que deu certo nas travessuras, fugas do castigo)
fica salvo localmente e muda o jeito dele com o tempo.

## Requisitos

- Windows 10 ou 11, macOS (Quartz/pyobjc) ou Linux com X11.
- Python 3.11 ou mais novo.
- No Linux, para as janelas e o tempo ocioso: `xdotool`, `wmctrl` e `xprintidle`. Sem eles, o pet continua
  andando, mas não enxerga as janelas.
- Cerca de 70 MB de RAM com ele rodando.

## Instalação e uso

```bash
pip install -r requirements.txt
```
```bash
python main.py
```

Na primeira vez, um passo a passo explica o que ele vê e não vê, e depois abre a tela de permissões.
Para pular a tela e usar as opções salvas:

```bash
python main.py --direto
```

### Como interagir

| Gesto | Efeito |
|---|---|
| Clique rápido | Cutucada |
| Passar o mouse de um lado para o outro em cima dele | Carinho |
| Segurar e arrastar / soltar rápido | Leva junto / arremessa |
| Rodinha do mouse | Gira |
| Botão direito | Menu: cutucar, carinho, bolinha, dormir, travessura, trabalhar, notebook, cantinho do castigo, painéis, configurações, esconder, fechar |

### Visão e conversa (IA)

Desligadas por padrão. Para ligar: **Configurações**, grupo **Visão e conversa (IA)**, marque **Usar IA**,
escolha o provedor, cole a chave no campo **Chave** e clique em **Salvar chave** (aparece um aviso verde
e a chave some da tela). **Ver minha tela** é separado: sem ele, ele conversa mas não vê nada.

| Provedor | Vê a tela? | Como configurar |
|---|---|---|
| **Claude** (padrão) | Sim | Chave da Anthropic (`ANTHROPIC_API_KEY`). Modelo padrão `claude-opus-5-5`; `claude-haiku-5-5` sai bem mais barato. |
| **OpenAI** | Sim | Chave da OpenAI (`OPENAI_API_KEY`). Modelo padrão `gpt-5-mini`. |
| **DeepSeek** | Não (só o nome do programa e o título da janela) | Chave do DeepSeek (`DEEPSEEK_API_KEY`). A API do DeepSeek não aceita imagem. |
| **Ollama** (local) | Sim, com modelo de visão | Sem chave e sem internet. Instale o [Ollama](https://ollama.com) neste ou em outro computador da rede e baixe um modelo de visão. **Recomendado: `ollama pull gemma4:e4b`** (testado numa RTX 3070 de 8 GB: ~5 s por olhada, ~3 s no chat). Para usar outro PC, ponha o endereço dele em **Endereço** (ex.: `192.168.0.10`) e clique em **Testar conexão**; lá, o Ollama precisa de `OLLAMA_HOST=0.0.0.0`. |

A chave é gravada no arquivo `.env` da pasta do Pestinha, que fica fora do git e da pasta `memory/`, e
vale na hora. Também dá para usar uma variável de ambiente com o mesmo nome; se as duas existirem, vale a
do `.env`. O campo **Modelo** recusa texto com cara de chave. Cada olhada (a cada ~2,5 min, e logo depois de trocar de programa) e
cada mensagem custam um pouco na conta do provedor; com o Ollama, nada sai do computador.

### Falar com ele (voz para texto)

Desligado por padrão, e só funciona com **Usar IA** e **Conversar por texto** ligados. A sua fala vira
texto e ele responde por escrito, como no chat (ele não fala). Dois jeitos:

- **Atalho:** segure `Ctrl + Alt + Shift + V`, fale e solte; o texto vai direto para ele e a resposta
  aparece no balão. No macOS e no Linux: aperta para começar e aperta de novo para parar.
- **Microfone do chat:** na janela Conversar, clique no 🎤, fale e clique de novo; o texto cai no campo
  para você conferir e mandar.

Ele só ouve enquanto você aperta (no máximo 30 s), com ondinhas no canto do rosto. A transcrição roda
num **serviço de voz** seu, não na internet: [`servidor/voz/`](servidor/voz/README.md) tem o serviço
(faster-whisper `large-v3-turbo`) e como instalar num computador com placa de vídeo, sem sudo. Em
Configurações, ponha o endereço dele em **Servidor da voz** (ex.: `192.168.0.10`, porta 11500) e clique em
**Testar voz**. Testado numa RTX 3070 de 8 GB junto com o `gemma4:e4b`: ~0,2 s para transcrever uma frase
e cerca de 6 GB de VRAM somando os dois.

### Pesquisar na internet (Hermes)

Desligado por padrão, e só funciona com **Usar IA** e **Ver minha tela** ligados. Quando algo na tela chama
a atenção dele, ele pede ao [Hermes](https://github.com/NousResearch/hermes-agent) (um agente com
ferramentas, rodando num computador seu) para pesquisar e te dá uma dica no balão. Quem olha a tela
continua sendo o provedor de IA escolhido; o Hermes recebe só o termo, o resumo e (com **Lembrar o que
viu**) as lembranças dos seus computadores. Rode o Hermes no mesmo servidor da memória e da voz: todos os
computadores usam o mesmo Hermes, com a memória dele.

No Hermes, uma vez:

1. No `.env` dele, `API_SERVER_KEY=<uma senha longa>` (a API fica só em `127.0.0.1:8642`; para outro
   computador da rede, `API_SERVER_HOST=0.0.0.0`).
2. No `config.yaml` dele, a plataforma da API **só com a pesquisa** (o texto da tela pode tentar dar
   ordens a ele; assim ele não tem terminal, arquivos nem controle do computador):

   ```yaml
   platform_toolsets:
     api_server:
       - search
   ```

3. `hermes gateway run` (ou `hermes gateway install` para ficar sempre ligado).

No Pestinha: Configurações, marque **Pesquisar na internet (Hermes)**, cole a mesma senha em **Chave do
Hermes**, **Salvar chave** e **Testar Hermes**.

### O mesmo pet em todos os computadores

Com **Compartilhar a memória dele** (desligado por padrão), a rede, o humor, o que ele aprendeu e a
personalidade ficam também num **serviço de memória** seu ([`servidor/memoria/`](servidor/memoria/README.md),
só Python, nada para instalar). Abra no Windows ou no Mac e é o mesmo bichinho. Com **Lembrar o que viu**,
cada computador guarda as próprias lembranças (o resumo curto do que a IA viu, com hora e sistema), e ele
pode, no Mac, te lembrar de algo que viu no Windows.

### Pânico

`Ctrl + Alt + Shift + B` desliga tudo na hora (inclusive o microfone), e ele continua desligado
até você religar em Configurações.

### Modo teste

Desligado por padrão. Ligado, os tempos ficam curtos (emoções, travessuras e protesto acontecem em
segundos), os painéis de desenvolvimento ficam na tela (monitor neural e painel de protesto) e o
terminal mostra as decisões.

## Privacidade

Sem a IA ligada, ele roda só no seu computador e não envia nada para a internet. Lê o **nome** do
programa em primeiro plano, o tempo sem usar teclado e mouse, a posição do cursor e a geometria das
janelas, e não lê conteúdo nem título de janela. Com **Usar IA** e **Ver minha tela** ligados, ele manda
um print da tela e o título da janela ativa para o provedor escolhido (ou para o Ollama, no seu
computador); o print e o que o modelo respondeu não são gravados. Com **Falar com ele**, ele só
ouve enquanto você aperta a tecla ou o microfone, e o áudio vai para o seu serviço de voz sem ser gravado. Tudo o que ele grava fica em `memory/` e pode ser apagado pela tela de
configurações. Detalhes em [PRIVACIDADE.md](PRIVACIDADE.md).

## Personalizar

- **Memes, recadinhos e cartazes do Bryan:** pasta `pets/bryan/`, explicada em [pets/README.md](pets/README.md).
  Pode editar com ele aberto.
- **Bolinhas, notebook e suas fotos:** `assets/comum/`, valem para qualquer personagem
  ([assets/LEIA-ME.txt](assets/LEIA-ME.txt)).
- **Personalidade:** `pets/bryan.json` (semente da rede, temperamento, pesos de brincadeira, reação ao notebook).
- **Números do comportamento:** `pestinha/ajustes.py`, todos validados ao abrir.

## Estrutura

| Pasta | O que tem |
|---|---|
| `pestinha/` | O código, em camadas ([pestinha/README.md](pestinha/README.md)) |
| `assets/comum/` | Imagens da bolinha e do notebook, e suas fotos: valem para qualquer pet |
| `pets/` | Cada pet: `<pet>.json` (quem ele é) e `<pet>/` (frases, cartazes e memes dele) |
| `tests/` | Testes automáticos |
| `ferramentas/fuzz_pestinha.py` | Fuzzer: roda ações aleatórias e checa invariantes |
| `ferramentas/` | Geradores de documentação |
| `docs/` | Arquitetura, rede neural e relatórios ([docs/README.md](docs/README.md)) |
| `memory/` | Gerada em uso, com o que ele aprende. Não vai para o repositório |

## Documentação

- [docs/ARQUITETURA.md](docs/ARQUITETURA.md): como as partes conversam.
- [docs/REDE_NEURAL.md](docs/REDE_NEURAL.md): canais, interneurônios, motores e decisões da rede.
- [pestinha/README.md](pestinha/README.md) e o README de cada pasta: o que cada arquivo faz.
- [CONTRIBUTING.md](CONTRIBUTING.md): como rodar os testes e contribuir.
- [CHANGELOG.md](CHANGELOG.md): o que mudou.

## Desenvolvimento

```bash
pip install -r requirements-dev.txt
```
```bash
python -m pytest -q
```

Os testes rodam sem abrir janelas (Qt em modo offscreen). Mais detalhes em [CONTRIBUTING.md](CONTRIBUTING.md).

### Gerar o executável

Há duas formas: gerar no seu computador (só o sistema em que você está) ou deixar o GitHub gerar os três.
O PyInstaller só gera o executável do sistema onde roda, por isso um Windows não gera o de Mac.

#### Opção 1: no seu computador

1. Instale as dependências de desenvolvimento (inclui o PyInstaller):

   ```bash
   pip install -r requirements-dev.txt
   ```

2. Gere o executável, no Windows:

   ```bash
   python -m PyInstaller --noconfirm --onefile --windowed --name Pestinha --distpath build/onefile --workpath build/work --specpath build --hidden-import win32timezone main.py
   ```

   No macOS e no Linux, use o mesmo comando sem `--windowed` e sem `--hidden-import win32timezone`.

3. O resultado fica em `build/onefile/` (`Pestinha.exe` no Windows, `Pestinha` nos outros).

4. Monte a pasta de entrega: copie o executável e as pastas `assets/` e `pets/` para uma mesma pasta.
   O programa lê o conteúdo dessas pastas ao lado do executável. A `memory/` é criada sozinha na primeira execução,
   então não copie a sua.

#### Opção 2: pelo GitHub (os três sistemas de uma vez)

O workflow `.github/workflows/executaveis.yml` gera Windows, macOS e Linux em máquinas do próprio GitHub.

1. Suba o repositório para o GitHub (`git push`).
2. Para gerar sem criar versão: na aba **Actions**, escolha **executáveis**, clique em **Run workflow**.
3. Para gerar e publicar uma versão: crie uma tag e envie. Por exemplo:

   ```bash
   git tag v0.8.0
   git push origin v0.8.0
   ```

4. Ao terminar (alguns minutos), a execução tem três artefatos, um por sistema, com a pasta pronta
   (executável + `assets/` + `pets/`). Baixe pela própria página da execução, na seção **Artifacts**.

Para distribuir para quem não é do projeto, publique esses artefatos na aba **Releases** (use "Draft a new release"
na tag criada), e não dentro do repositório: cada executável tem cerca de 60 MB.

#### Depois de gerar

- Teste o executável numa pasta separada da sua, para não gravar na sua `memory/`.
- O executável não é assinado: o Windows e o macOS avisam na primeira execução. No macOS, a permissão de
  Acessibilidade é necessária para o atalho Ctrl+Alt+Shift+B; no Linux, o atalho e as janelas precisam de
  `xdotool`, `wmctrl` e `xprintidle`.

## Licença

O código do Pestinha é software livre, sob a [GNU General Public License v3.0 ou posterior](LICENSE)
(GPL-3.0-or-later). Você pode usar, estudar, modificar e redistribuir, mas toda versão distribuída,
modificada ou não, precisa continuar aberta e sob a mesma licença.

As imagens e os textos de `assets/` não estão cobertos por esta licença

## Limitações conhecidas

- macOS e Linux ainda não foram testados numa máquina real: a parte de leitura das janelas e do teclado foi
  escrita e testada só nas partes de texto (ver `tests/test_plataforma.py`).
- No macOS, o pet precisa da permissão de Acessibilidade para o atalho Ctrl+Alt+Shift+B funcionar.
- No Linux com Wayland, o pet não enxerga janelas nem o tempo ocioso, e o atalho global não funciona.
- Pouco testado com escala de tela acima de 100% e com vários monitores.
- A visão olha só o monitor da janela ativa. No macOS ela precisa da permissão de Gravação de Tela, e o
  título da janela não é lido.
- Jogos em janela sem borda podem não ser detectados como tela cheia.
- O executável não é assinado; o Windows pode avisar na primeira execução.
