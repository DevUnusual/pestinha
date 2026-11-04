# `pestinha/ia/`

> Gerado por `ferramentas/gerar_readmes.py` a partir das docstrings. Não edite à mão: rode o script.

Visão e conversa por um modelo de IA (Claude, OpenAI, DeepSeek ou Ollama local): os clientes, os prompts e a leitura das respostas, e a voz para texto (pelo serviço de servidor/voz/). Sem Qt; as chamadas rodam em thread (ver mind/visao.py e mind/voz_ctl.py).

**Pode importar de:** core e módulos compartilhados (e dos módulos compartilhados). A regra é verificada por `tests/test_arquitetura.py`.

| Arquivo | O que faz |
|---|---|
| `chaves.py` | As chaves de API no arquivo .env da pasta do Pestinha. |
| `imagem.py` | Quando você pede no chat para ele pesquisar algo, ele acha uma imagem na Wikipédia para projetar. |
| `mente.py` | O que o pet pergunta ao modelo e como ele entende a resposta. |
| `musica.py` | Você pede um estilo no chat ("toca um lo-fi") e ele monta a fila no YouTube Music, aprendendo com o seu 👍 e 👎 (e com o que você deixa tocar até o fim ou pula). |
| `pesquisa.py` | O pet pesquisa na internet pelo Hermes (um agente com ferramentas), no formato da OpenAI. |
| `provedores.py` | Quem responde pelo pet: Claude, OpenAI, DeepSeek ou um modelo local no Ollama. |
| `voz.py` | A sua fala vira texto pelo serviço de voz (servidor/voz/), no formato da API de áudio da OpenAI. |
