# `tests/` — testes automáticos

> Gerado por `ferramentas/gerar_readmes.py` a partir das docstrings. Não edite à mão: rode o script.

Rodam sem abrir janelas (o `conftest.py` da raiz liga o Qt em modo offscreen) e sempre numa pasta
temporária: nada aqui toca na `memory/` de verdade.

```bash
python -m pytest -q
```

O `python -m pytest` na raiz roda `tests/` (ver `pyproject.toml`). Testes que montam o
app inteiro usam um relógio virtual: avançam o tempo sem esperar.

| Arquivo | O que faz |
|---|---|
| `test_30_bugs.py` | Regressão dos 30 bugs encontrados na rodada de fuzzing e revisão (docs/auditorias/BUGS_30_RODADA.md). |
| `test_animacoes.py` | Animações da mente: o corpo mostra o que a IA e a voz estão fazendo (olhando, pensando, pesquisando, ouvindo, jogo) e dá o pop quando o balão aparece. |
| `test_aparencia.py` | Etapa 5 do multipet: cores e acessórios por pet, numa camada por cima do rosto. |
| `test_app.py` | Testes de integração do app, com Qt em modo offscreen e tudo numa pasta temporária. |
| `test_arquitetura.py` | Regra de camadas do pacote `pestinha`: cada camada só importa das que estão abaixo dela. |
| `test_assistir.py` | Assistindo você jogar: com "Acompanhar jogos" e um jogo na tela, ele vai para o monitor ao lado (o mais à direita que não é o do jogo), fica parado olhando para a partida e comenta, sem passear nem aprontar. |
| `test_atividade.py` | Programas de trabalho: VS Code, Claude e Codex contam como programação. |
| `test_auditoria_30.py` | Contratos dos 30 bugs da auditoria (docs/auditorias/AUDITORIA_30_BUGS.md). |
| `test_bolinha.py` | Testes da bolinha e da tristeza (abandono). |
| `test_brincadeira.py` | Bolinha: colisão com post-its e estilos de brincadeira por pet. |
| `test_cantinho_cenarios.py` | 100 cenários explícitos do cantinho. |
| `test_cantinho_rede.py` | As 10 funções do cantinho que mexem na rede neural: entrada, aprendizado e efeito nos motores. |
| `test_carinho.py` | Carinho: olhinhos fechados de felicidade enquanto ele recebe carinho, e voltam ao normal depois. |
| `test_castigo.py` | Cantinho do castigo: soltar o Bryan na frente da placa prende ele, e a fuga bem-sucedida fica salva. |
| `test_castigo_bugs_rede.py` | Reproduções diagnósticas: asserções descrevem o comportamento esperado. |
| `test_castigo_integracao.py` | Cantinho do castigo dentro do app: o castigo vence a mesa e as travessuras, e o pânico encerra a fuga. |
| `test_castigo_real.py` | Cantinho no app inteiro, com relógio virtual: soltar no ar, pousar, ficar preso e reagir pela rede. |
| `test_chamado.py` | Chamar pelo nome ("Bob!"): as grafias que o modelo ouve, a leitura do resultado do Vosk, o recorte do pedido, a escuta depois do nome, a conversa que emenda depois da resposta, o nome exigente com vídeo tocando, o download do modelo (de um zip local) e o controlador dentro do app de verdade (Qt offscreen, detector e serviço de voz falsos). |
| `test_chaves.py` | Chaves de API no .env: gravar pela tela de Configurações, carregar ao abrir, nunca aceitar uma chave no campo de modelo. |
| `test_condicionamento.py` | Testes do condicionamento: aprender a reagir antes, extinguir, e persistir. |
| `test_conteudo.py` | Etapa 2 do multipet: conteúdo por pet (frases, cartazes, memes, imagens). |
| `test_escolha_pet.py` | Etapa 3 do multipet: escolha do personagem nas configurações e o nome certo em cada texto. |
| `test_festa.py` | Fogos de artifício ligados à rede e brincadeira mais animada quando feliz. |
| `test_hermes_conectado.py` | Pet e Hermes conectados: o chat passa pelo Hermes (persona do pet, pesquisa, memória por sessão), a IA vilã aparece só enquanto ele usa uma ferramenta, o link de imagem da resposta vira holograma e, se o Hermes cair, o provedor escolhido responde no lugar sem a conversa quebrar. |
| `test_historico_chat.py` | Histórico do chat: o arquivo (guardar, ler, linha estragada, limite), a resposta inteira no chat e curta no balão, e no app de verdade as falas escritas e pela voz guardadas e de volta ao abrir, a opção desligada e o Esquecer. |
| `test_holograma.py` | Imagem pedida no chat: "pesquisa o que é manga" acha o link de uma imagem na Wikipédia, baixa e o pet projeta como holograma. |
| `test_homeostase.py` | Homeostase: trabalhar é estímulo, então o tédio não sobe enquanto ele programa. |
| `test_ia.py` | Visão e conversa pela IA: o texto do modelo, os clientes (com SDK falsa, sem rede) e o controlador dentro do app de verdade (Qt offscreen, pasta temporária). |
| `test_jogo.py` | Acompanhar jogos (#4): o Ollama sem "pensar", o reconhecimento do jogo, o pedido de jogo, o print repetido que não é mandado e o freio da fala, com o controlador dentro do app de verdade (Qt offscreen, modelo falso). |
| `test_jorge.py` | Etapa 4 do multipet: o Jorge, segundo personagem, feito só de configuração e conteúdo. |
| `test_memoria.py` | Memória compartilhada: o serviço de servidor/memoria/ de verdade (numa porta livre, pasta temporária) e dois "computadores" (duas pastas) sincronizando por ele. |
| `test_mesa.py` | Notebook: sentar e levantar pelo disparo do neurônio SENTAR. |
| `test_migracao.py` | Etapa 1 do multipet: memória por pet (memory/pets/<pet>/) e a migração da versão antiga. |
| `test_musica.py` | Música pelo chat: "toca um lo-fi" monta a fila no YouTube Music, 👍/👎/pulo/ouvir até o fim ensinam o gosto e a fila se renova pelo rádio. |
| `test_nucleo.py` | Testes dos módulos puros: nada de Qt, nada de Windows. |
| `test_paineis.py` | Painéis do menu (monitor neural e painel de protesto): abrir à mão deve manter o painel na tela. |
| `test_pedido.py` | Pedir para trabalhar: o neurônio SENTAR decide. |
| `test_pesquisa.py` | Pesquisa na internet pelo Hermes: o prompt, o cliente (com um servidor HTTP falso nesta máquina) e o controlador dentro do app de verdade (Qt offscreen, Hermes falso). |
| `test_plataforma.py` | Plataforma: cada sistema expõe as mesmas funções, e as leituras de texto (wmctrl, xdotool, ioreg, janelas do Quartz) são testadas com saídas de exemplo, em qualquer sistema. |
| `test_robustez.py` | Robustez: arquivo corrompido, assets faltando, log em arquivo. |
| `test_robustez_v2.py` | Falhas do relatório técnico (docs/auditorias/ANALISE_TECNICA.md): cada caso tem um teste que reproduz o problema. |
| `test_conversa_atencao.py` | Falar ou escrever com o pet é atenção: carência e tristeza caem e a rede recebe recompensa na hora, mesmo sem resposta da IA; pausado, não conta. |
| `test_tocando_disco.py` | O cartão de música mostra o tempo: a borda acende do meio de cima e dá a volta (sentido horário) até o fim da música, o número '1:23 / 3:45' acompanha e um disquinho gira no canto, com a capa da música como selo (que dá para tirar pelo 🖼). |
| `test_video_desenho.py` | Assistir vídeos (conferir o som e perguntar antes, ouvir, olhar a tela, anotar, resumir e guardar) e desenhar na tela: o texto do modelo, o conhecimento em disco, a janela do desenho e os controladores dentro do app de verdade (Qt offscreen, pasta temporária, som e modelo falsos). |
| `test_voz.py` | Voz: o áudio e o cliente do serviço de transcrição (com um servidor HTTP falso nesta máquina) e o controlador dentro do app de verdade (Qt offscreen, microfone falso). |
