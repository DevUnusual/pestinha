# Pacote `pestinha`

> Gerado por `ferramentas/gerar_readmes.py` a partir das docstrings. Não edite à mão: rode o script.

O código do pet, em camadas. Cada pasta tem o seu README com a lista de arquivos.

## Camadas

Cada camada só importa das que estão acima dela nesta tabela (verificado por `tests/test_arquitetura.py`):

```text
core  <  ia  <  sense  <  body  <  world  <  mind  <  ui  <  controle  <  app.py
```

| Pasta | Papel |
|---|---|
| `core/` | Cérebro e regras puras: rede neural, emoção, homeostase, memória, condicionamento, física e protesto. Sem Qt e sem API do sistema, para ser testável em qualquer lugar. |
| `ia/` | Visão e conversa por um modelo de IA (Claude, OpenAI, DeepSeek ou Ollama local): os clientes, os prompts e a leitura das respostas, e a voz para texto (pelo serviço de servidor/voz/). Sem Qt; as chamadas rodam em thread (ver mind/visao.py e mind/voz_ctl.py). |
| `plataforma/` | Tudo que depende do sistema operacional: programa em primeiro plano, tempo ocioso, janelas, tela cheia, foco e o atalho de pânico. Um módulo por sistema (Windows, macOS, Linux). Só nome de programa e geometria; o título da janela só com "Ver minha tela" ligado. |
| `sense/` | Sentidos: o que as leituras da plataforma significam (atividade, tela cheia, janela para pousar) e registro da rotina. Título de janela só para a visão da IA, se você ligar. |
| `body/` | O corpo do pet: a janela com o rosto, o estado que ele mostra, o comportamento (movimento) e a bolinha. |
| `world/` | Objetos que aparecem na tela: post-its, memes, cartazes, notebook, fogos, o balão de fala e a janela arrastável base. |
| `mind/` | Controladores de decisão: ligam o que a rede decide à cena (sono, mesa, protesto, travessuras, festa, revolução, cantinho do castigo, visão e conversa pela IA). |
| `ui/` | Janelas de interface: tela de permissões, bandeja, passo a passo, monitor neural, painel de protesto e o chat com o pet. |
| `controle/` | Mixins de `PestinhaApp`: sessão (permissões, visibilidade, pausa, pânico, salvar, sair, apagar) e interação (cutucar, arrastar, menus, notebook). |
| `app.py` | Composição: cria tudo, liga os relógios e roda os três ciclos (sentidos, pensamento e quadro). |

## Módulos compartilhados

Podem ser usados por qualquer camada.

| Arquivo | O que faz |
|---|---|
| `ajustes.py` | Todos os números que dão o jeito do pet, em um lugar só. |
| `config.py` | Caminhos, permissões da sessão, perfis de tempo e pets. |
| `paths.py` | Onde ficam as coisas. |
| `store.py` | A única forma de gravar e ler arquivos de estado. |
| `log.py` | Um lugar só para mensagens do app: terminal e arquivo em memory/logs/. |
| `mathutil.py` | Funções matemáticas pequenas, sem dependências. |
| `settings_store.py` | As permissões da sessão, em um lugar só. |

Ver [docs/ARQUITETURA.md](../docs/ARQUITETURA.md) para o fluxo completo.
