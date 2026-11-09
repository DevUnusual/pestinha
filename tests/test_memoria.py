"""
Memória compartilhada: o serviço de servidor/memoria/ de verdade (numa porta livre, pasta temporária) e
dois "computadores" (duas pastas) sincronizando por ele. Também as lembranças de cada computador.
"""

import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from pestinha import config, memoria_remota  # noqa: E402
from pestinha.memoria_remota import ErroMemoria, Sincronia  # noqa: E402
from pestinha.mind.lembrancas import ANOTA_A_CADA, Lembrancas, mesmo_assunto  # noqa: E402
from pestinha.paths import Paths  # noqa: E402

_spec = importlib.util.spec_from_file_location("pestinha_memoria", ROOT / "servidor" / "memoria" / "pestinha_memoria.py")
servico = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(servico)


@pytest.fixture
def servidor(tmp_path):
    srv = servico.servir(porta=0, pasta=tmp_path / "servidor", token="teste", host="127.0.0.1")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", srv
    srv.shutdown()
    srv.server_close()


def computador(tmp_path, base, nome, sistema="windows", token="teste"):
    """Um 'computador': a pasta do pet e a definição dele, sincronizando com o serviço."""
    pasta = tmp_path / nome / "pets" / "bryan"
    pasta.mkdir(parents=True)
    arquivos = {"drives.json": pasta / "drives.json", "definicao.json": tmp_path / nome / "bryan.json"}
    return Sincronia(base, "bryan", arquivos, pasta, maquina=nome, sistema=sistema, token=token)


def escrever(caminho, dados, quando=None):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    if quando is not None:
        os.utime(caminho, (quando, quando))


def ler(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


# ---------------- dois computadores, um pet ----------------

def test_o_que_um_grava_o_outro_recebe(tmp_path, servidor):
    base, _ = servidor
    win, mac = computador(tmp_path, base, "win"), computador(tmp_path, base, "mac", "macos")
    escrever(win.arquivos["drives.json"], {"energy": 0.3})
    escrever(win.arquivos["definicao.json"], {"nome": "Bryan", "persona": "marrento"})
    assert win.enviar() == 2
    assert win.enviar() == 0                                    # nada mudou: nada sobe
    assert mac.baixar() == "win"                                # o Windows estava com ele aberto
    assert ler(mac.arquivos["drives.json"]) == {"energy": 0.3}
    assert ler(mac.arquivos["definicao.json"])["persona"] == "marrento"


def test_volta_e_meia_ida_e_volta(tmp_path, servidor):
    base, _ = servidor
    win, mac = computador(tmp_path, base, "win"), computador(tmp_path, base, "mac", "macos")
    escrever(win.arquivos["drives.json"], {"energy": 0.3})
    win.enviar()
    mac.baixar()
    escrever(mac.arquivos["drives.json"], {"energy": 0.9})
    assert mac.enviar() == 1
    win.baixar()
    assert ler(win.arquivos["drives.json"]) == {"energy": 0.9}


def test_ao_abrir_vale_o_mais_novo(tmp_path, servidor):
    base, _ = servidor
    win, mac = computador(tmp_path, base, "win"), computador(tmp_path, base, "mac", "macos")
    escrever(win.arquivos["drives.json"], {"energy": 0.1})
    win.enviar()
    mac.baixar()
    escrever(mac.arquivos["drives.json"], {"energy": 0.5}, quando=time.time() + 60)   # mudou aqui depois
    escrever(win.arquivos["drives.json"], {"energy": 0.2})
    win.enviar()
    mac.baixar()
    assert ler(mac.arquivos["drives.json"]) == {"energy": 0.5}                         # ficou o daqui
    mac.enviar()
    win.baixar()
    assert ler(win.arquivos["drives.json"]) == {"energy": 0.5}


def test_com_o_pet_aberto_vale_o_daqui(tmp_path, servidor):
    base, _ = servidor
    win, mac = computador(tmp_path, base, "win"), computador(tmp_path, base, "mac", "macos")
    escrever(win.arquivos["drives.json"], {"energy": 0.1})
    escrever(mac.arquivos["drives.json"], {"energy": 0.7})
    win.enviar()
    assert mac.enviar() == 1                                    # 409 por baixo; regrava sobre a versão nova
    win.baixar()
    assert ler(win.arquivos["drives.json"]) == {"energy": 0.7}


def test_sem_servidor_vira_erro_explicado(tmp_path):
    sync = computador(tmp_path, "http://127.0.0.1:9", "win")
    with pytest.raises(ErroMemoria, match="não respondeu"):
        sync.baixar()


def test_token(tmp_path):
    srv = servico.servir(porta=0, pasta=tmp_path / "s", token="segredo", host="127.0.0.1")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with pytest.raises(ErroMemoria, match="token"):
            computador(tmp_path, base, "win", token="errado").baixar()
        assert computador(tmp_path, base, "mac", token="segredo").baixar() is None
    finally:
        srv.shutdown()
        srv.server_close()


# ---------------- o servidor recusa o que não é dele ----------------

def test_servidor_recusa_nomes_e_conteudo_ruins(tmp_path, servidor):
    base, _ = servidor
    sync = computador(tmp_path, base, "win")
    for rota in ("/v1/pets/../x", "/v1/pets/bryan/..%2fsenha.json", "/v1/pets/bryan/nervous.txt"):
        with pytest.raises(ErroMemoria):
            sync._pedir("GET", rota)
    with pytest.raises(ErroMemoria, match="400"):
        sync._pedir("PUT", "/v1/pets/bryan/drives.json", {"base": 0, "conteudo": "{quebrado"})
    codigo, _ = sync._pedir("PUT", "/v1/pets/bryan/drives.json", {"base": 5, "conteudo": "{}"})
    assert codigo == 409                                        # base que não existe


def test_documento_desconhecido_nao_e_baixado(tmp_path, servidor):
    base, _ = servidor
    outro = computador(tmp_path, base, "outro")
    outro.arquivos["segredo.json"] = outro.pasta / "segredo.json"
    escrever(outro.arquivos["segredo.json"], {"x": 1})
    outro.enviar()
    win = computador(tmp_path, base, "win")
    win.baixar()
    assert not (win.pasta / "segredo.json").exists()


def test_nome_do_computador_cabe_no_servidor(monkeypatch):
    monkeypatch.setattr(memoria_remota.socket, "gethostname", lambda: "Carlos's MacBook Pro (2) " * 4)
    nome = f"{memoria_remota.PREFIXO_LEMBRANCAS}{memoria_remota.maquina_atual()}.jsonl"
    assert servico.NOME_DE_DOC.match(nome)


def test_desligado_ou_sem_endereco_nao_cria(tmp_path):
    paths = Paths(root=tmp_path)
    pet_paths = paths.pet("bryan")
    perms = dict(config.DEFAULT_PERMISSIONS)
    assert memoria_remota.criar(perms, paths, "bryan", pet_paths) is None
    perms["memoria_compartilhada"] = True
    assert memoria_remota.criar(perms, paths, "bryan", pet_paths) is None
    perms["memoria_url"] = "192.168.0.10"
    sync = memoria_remota.criar(perms, paths, "bryan", pet_paths)
    assert sync.base_url == "http://192.168.0.10:11600"
    assert {"nervous.json", "drives.json", "definicao.json"} <= set(sync.arquivos)
    assert config.DEFAULT_PERMISSIONS["memoria_compartilhada"] is False and config.DEFAULT_PERMISSIONS["lembrar"] is False


# ---------------- lembranças de cada computador ----------------

def test_lembrancas_de_um_computador_aparecem_no_outro(tmp_path, servidor):
    base, _ = servidor
    win, mac = computador(tmp_path, base, "win"), computador(tmp_path, base, "mac", "macos")
    agora = time.time()
    no_win = Lembrancas(win.pasta, "win", "windows")
    assert no_win.anotar("code.exe", "escrevendo o relatório do TCC", agora=agora - 3 * 86400 - 60)
    win.enviar()
    mac.baixar()
    no_mac = Lembrancas(mac.pasta, "mac", "macos")
    texto = no_mac.contexto(agora=agora)
    assert "Você está agora no Mac" in texto
    assert "Windows (win), há 3 dias: escrevendo o relatório do TCC" in texto
    assert no_win.contexto(agora=agora) == ""                   # só as dele: nada de outro computador


def test_lembranca_so_quando_muda_de_assunto_e_com_intervalo(tmp_path):
    lemb = Lembrancas(tmp_path, "win", "windows")
    assert lemb.anotar("code", "programando o pet em Python", agora=1000)
    assert not lemb.anotar("code", "outra coisa totalmente diferente", agora=1000 + ANOTA_A_CADA / 2)
    assert not lemb.anotar("code", "programando o pet em Python ainda", agora=1000 + ANOTA_A_CADA * 2)
    assert lemb.anotar("chrome", "pesquisando passagens para Lisboa", agora=1000 + ANOTA_A_CADA * 3)
    linhas = lemb.caminho.read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 2 and set(json.loads(linhas[0])) == {"em", "sistema", "maquina", "programa", "resumo"}
    assert Lembrancas(tmp_path, "win", "windows").ultima[1] == "pesquisando passagens para Lisboa"


def test_mesmo_assunto():
    assert mesmo_assunto("programando o pet em Python", "programando o pet em Python ainda")
    assert not mesmo_assunto("programando o pet", "pesquisando passagens para Lisboa")
