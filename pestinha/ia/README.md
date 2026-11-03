# `pestinha/ia/`

> Gerado por `ferramentas/gerar_readmes.py` a partir das docstrings. Não edite à mão: rode o script.

Visão e conversa por um modelo de IA (Claude, OpenAI, DeepSeek ou Ollama local): os clientes, os prompts e a leitura das respostas. Sem Qt; as chamadas rodam em thread (ver mind/visao.py).

**Pode importar de:** core e módulos compartilhados (e dos módulos compartilhados). A regra é verificada por `tests/test_arquitetura.py`.

| Arquivo | O que faz |
|---|---|
| `mente.py` | O que o pet pergunta ao modelo e como ele entende a resposta. |
| `provedores.py` | Quem responde pelo pet: Claude, OpenAI, DeepSeek ou um modelo local no Ollama. |
