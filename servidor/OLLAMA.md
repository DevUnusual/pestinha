# Ollama no servidor da casa

O Pestinha fala com o Ollama pelo endpoint compatível com a OpenAI (`http://<servidor>:11434/v1`). Dois
ajustes no servidor fazem diferença.

## Aceitar conexões da rede

Por padrão o Ollama só atende o próprio computador. Para os outros PCs da casa usarem, ele precisa de
`OLLAMA_HOST=0.0.0.0`.

## Janela de contexto: `OLLAMA_CONTEXT_LENGTH`

A janela é quanto texto o modelo lê de uma vez, e **a resposta divide a janela com o pedido**. O Ollama
não avisa quando um pedido não cabe: ele corta o começo, que é onde ficam a persona e as regras do pet. Na
medição da auditoria, um pedido de ~8 mil tokens chegou com 4.099 e perdeu a instrução inicial.

Use **pelo menos 8192**. O Pestinha conta com isso:

- ele lê a janela do modelo carregado em `/api/ps` e monta cada pedido para caber nela, com espaço para a
  resposta (`pestinha/ia/orcamento.py`). Enquanto não consegue ler, ele supõe 8192;
- quando o servidor devolve bem menos tokens de entrada do que o pedido tinha, o log mostra
  `[ia] o Ollama cortou o pedido ...`, e o registro de uso marca `ENTRADA CORTADA`.

Com mais memória na placa, 16384 dá folga para o estudo de jogos e o resumo de vídeos longos. A janela
maior gasta mais memória de vídeo: com o `gemma4:e4b` numa placa de 8 GB, 8192 ocupa ~5 GB.

### No Linux com systemd (o serviço `ollama`)

```bash
sudo systemctl edit ollama
```

Acrescente e salve:

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
Environment="OLLAMA_CONTEXT_LENGTH=8192"
```

```bash
sudo systemctl restart ollama
```

### No Windows ou no macOS

Defina `OLLAMA_CONTEXT_LENGTH=8192` (e `OLLAMA_HOST=0.0.0.0`) nas variáveis de ambiente do usuário e
reabra o Ollama.

### Conferir

Com o modelo carregado (depois de uma olhada), `context_length` aparece em:

```bash
curl http://localhost:11434/api/ps
```

A avaliação da IA também mostra se há corte: `python ferramentas/avaliar_ia.py --casos C3 --escala 8`
monta uma conversa bem maior que a janela e confere se a instrução do começo sobrevive.
