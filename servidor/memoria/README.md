# `servidor/memoria/` — serviço de memória do Pestinha

Um serviço pequeno que roda **num computador seu que fica ligado** (o mesmo do Ollama e da voz serve) e
guarda a memória e a personalidade dos pets, para o **mesmo bichinho** viver em todos os seus computadores
(Windows, Mac e, no futuro, iPhone): a rede neural, o humor, o que ele aprendeu, a definição
(`pets/<pet>.json`) e as lembranças de cada computador.

| Rota | O que faz |
|---|---|
| `GET /health` | está vivo? |
| `GET /v1/pets` | os pets guardados |
| `GET /v1/pets/<pet>` | os documentos do pet (versão, quando, de qual computador e sistema) e quem está com ele aberto |
| `GET /v1/pets/<pet>/<doc>` | um documento |
| `PUT /v1/pets/<pet>/<doc>` | grava, com a versão que você tinha (`base`); se alguém gravou depois, `409` |
| `POST /v1/pets/<pet>/ativo` | "estou com ele aberto" (vale por 2 min) |

Só a biblioteca padrão do Python (3.10+): **nada para instalar**. Os arquivos ficam como estão, um por
documento, em `~/pestinha-memoria/dados/<pet>/`, com um `.meta` ao lado (versão, horário, computador,
sistema, hash). Só aceita JSON (ou JSON por linha, nos `.jsonl`) e nomes que o Pestinha usa.

**Cada computador tem as próprias lembranças** (`lembrancas_<computador>.jsonl`): só ele grava a dele, e
todos leem as dos outros. É assim que, no Mac, ele sabe que você estava fazendo algo no Windows.

Sem senha por padrão, como o serviço de voz: deixe a porta aberta só para a sua rede de casa. Para pedir
um token, defina `PESTINHA_MEMORIA_TOKEN` no serviço **e** no computador do pet (variável de ambiente ou
`.env`).

## Instalar (Linux, sem sudo)

```bash
mkdir -p ~/pestinha-memoria && cp pestinha_memoria.py ~/pestinha-memoria/
mkdir -p ~/.config/systemd/user && cp pestinha-memoria.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now pestinha-memoria
curl -s localhost:11600/health
```

No Pestinha de cada computador: Configurações, **Memória em outro computador**, marque **Compartilhar a
memória dele**, **Servidor da memória** = o IP desse computador, **Testar memória**, e reabra.

## Como a sincronia funciona

- **Ao abrir**, o Pestinha baixa o que outro computador gravou depois da última vez. Se os dois mudaram, vale
  o mais recente.
- **Com ele aberto**, a cada minuto (e ao fechar) ele manda o que mudou. Se outro computador gravou no meio,
  vale o daqui, porque é o pet que está vivo aqui (o log avisa).
- Sem rede ou com o serviço desligado, ele usa a memória do computador e sincroniza quando der.
- Deixe o pet aberto em **um computador por vez**: se abrir em dois, ele avisa na bandeja.

## Ajustes (variáveis de ambiente do serviço)

| Variável | Padrão | |
|---|---|---|
| `PESTINHA_MEMORIA_PORTA` | `11600` | porta |
| `PESTINHA_MEMORIA_DADOS` | `~/pestinha-memoria/dados` | onde ficam os arquivos |
| `PESTINHA_MEMORIA_TOKEN` | (vazio) | se definido, todo pedido menos `/health` precisa de `Authorization: Bearer <token>` |

Backup: copie a pasta `dados/`. Para apagar um pet do servidor, apague a pasta dele.
