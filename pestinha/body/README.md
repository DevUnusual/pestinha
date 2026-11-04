# `pestinha/body/`

> Gerado por `ferramentas/gerar_readmes.py` a partir das docstrings. Não edite à mão: rode o script.

O corpo do pet: a janela com o rosto, o estado que ele mostra, o comportamento (movimento) e a bolinha.

**Pode importar de:** core, sense (e dos módulos compartilhados). A regra é verificada por `tests/test_arquitetura.py`.

| Arquivo | O que faz |
|---|---|
| `animacoes.py` | Como o corpo mostra o que a mente (IA, voz) está fazendo: só tempo e curvas, sem Qt. |
| `behavior.py` | Como a rede e a emoção viram movimento. |
| `bolinha.py` | A janela da bolinha: desenho e mouse. |
| `brincadeira.py` | Como o pet brinca: chuta a bolinha, arremessa no cursor, cola post-its. |
| `desenho_fantasias.py` | O que ele veste conforme o que a mente está fazendo (o tempo vem de animacoes.py). |
| `desenho_rosto.py` | Só o que se desenha do pet: moldura, olhos, brilho, acessórios, os Zzz e o que a mente está fazendo na telinha (linha de leitura, reflexo do jogo; o tempo vem de animacoes.py). |
| `pet.py` | A telinha com olhinhos: janela transparente, desenho e mouse. |
| `pet_state.py` | O que o pet está sentindo e mostrando, num lugar só. |
| `toy.py` | A bolinha dele. |
