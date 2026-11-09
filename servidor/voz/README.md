# `servidor/voz/` — serviço de voz para texto do Pestinha

Um serviço pequeno que roda **num computador seu com placa de vídeo** (não no computador do pet) e
transforma a sua fala em texto, no formato da API de áudio da OpenAI:

| Rota | O que faz |
|---|---|
| `POST /v1/audio/transcriptions` | fala → texto (faster-whisper `large-v3-turbo`, na placa de vídeo) |
| `GET /health` | está vivo? (e se o Whisper está carregado) |

Feito para dividir a máquina com outras coisas (um servidor de jogo, o Ollama): um pedido por vez,
poucos threads de CPU, `nice 10`, e o Whisper só entra na placa no primeiro pedido e sai depois de 10 min
sem uso. Nada é gravado em disco. Não tem senha: deixe a porta aberta só para a sua rede local.

Medido numa RTX 3070 de 8 GB (Ryzen 7 5700X3D): ~0,2 s para uma frase de 7 s já carregado (~3 s no
primeiro pedido, que carrega o modelo). `int8_float16` usa ~1,2 GB de VRAM; junto com o `gemma4:e4b` do
Ollama ficam ~6,1 GB de 8. O processo do Minecraft no mesmo servidor não mostrou "Can't keep up" novo
durante os testes.

## Instalar (Linux, sem sudo)

```bash
curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh
mkdir -p ~/pestinha-voz && cd ~/pestinha-voz      # copie os arquivos desta pasta para cá
~/.local/bin/uv venv --python 3.12 .venv
~/.local/bin/uv pip install --python .venv -r requirements.txt
mkdir -p modelos/whisper-large-v3-turbo && cd modelos/whisper-large-v3-turbo
W=https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo/resolve/main
for f in config.json preprocessor_config.json tokenizer.json vocabulary.json model.bin; do
  curl -fsSL -o $f $W/$f; done
```

Serviço de usuário (sobe sozinho depois de reiniciar, se `loginctl show-user $USER -p Linger` disser
`yes`):

```bash
chmod +x ~/pestinha-voz/iniciar.sh
mkdir -p ~/.config/systemd/user && cp pestinha-voz.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now pestinha-voz
curl -s localhost:11500/health
```

No Pestinha: Configurações, **Falar com ele**, **Servidor da voz** = o IP desse computador, e **Testar voz**.

## Ajustes (variáveis de ambiente do serviço)

| Variável | Padrão | |
|---|---|---|
| `PESTINHA_VOZ_PORTA` | `11500` | porta |
| `PESTINHA_VOZ_OCIOSO` | `600` | s sem uso até tirar o Whisper da placa |
| `PESTINHA_VOZ_WHISPER_TIPO` | `int8_float16` | `float16` usa ~2,2 GB de VRAM sem ganho perceptível |
