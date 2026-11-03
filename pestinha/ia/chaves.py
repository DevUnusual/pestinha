"""
CHAVES - as chaves de API no arquivo .env da pasta do Pestinha.

A tela de Configurações grava a chave aqui (botão "Salvar chave") e o app carrega o .env ao abrir.
A chave vai também para o ambiente do processo, então vale na hora, sem reabrir. O .env fica fora
do git (.gitignore) e fora de memory/: "apagar todos os dados" não leva a chave junto.

Formato: uma linha NOME=valor por chave; comentários (#) e outras linhas são mantidos como estão.
"""

import os
import re

from ..store import read_lines, write_lines

NOME_VALIDO = re.compile(r"^[A-Z][A-Z0-9_]*$")


def parece_chave(texto):
    """Diz se o texto tem cara de chave de API (para não aceitar chave no campo de modelo)."""
    texto = (texto or "").strip()
    return texto.startswith(("sk-", "sk_")) or (len(texto) >= 40 and " " not in texto and ":" not in texto)


def valor_valido(valor):
    """Uma chave é uma palavra só: sem espaço, aspas nem quebra de linha."""
    return bool(valor) and not re.search(r"[\s\"'=]", valor)


def ler_env(path):
    """{NOME: valor} das linhas NOME=valor do .env (aspas em volta são tiradas)."""
    valores = {}
    for linha in read_lines(path):
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        nome, valor = linha.split("=", 1)
        nome = nome.strip().removeprefix("export ").strip()
        if NOME_VALIDO.match(nome):
            valores[nome] = valor.strip().strip('"').strip("'")
    return valores


def carregar_env(path):
    """Põe as chaves do .env no ambiente do processo. O .env ganha: é o que você salvou pelo app."""
    valores = {nome: valor for nome, valor in ler_env(path).items() if valor}
    os.environ.update(valores)
    return sorted(valores)


def salvar_chave(path, nome, valor):
    """Grava (ou troca) NOME=valor no .env, mantendo o resto, e já põe no ambiente do processo."""
    valor = (valor or "").strip()
    if not NOME_VALIDO.match(nome or "") or not valor_valido(valor):
        raise ValueError("chave inválida: cole só a chave, sem espaços nem aspas")
    linhas, trocou = [], False
    for linha in read_lines(path):
        atual = linha.split("=", 1)[0].strip().removeprefix("export ").strip() if "=" in linha else None
        if atual == nome and not linha.lstrip().startswith("#"):
            if not trocou:
                linhas.append(f"{nome}={valor}")
                trocou = True
            continue                                  # linha repetida da mesma chave: some
        linhas.append(linha)
    if not trocou:
        if not linhas:
            linhas.append("# Chaves de API do Pestinha (gravadas pela tela de Configurações). Não compartilhe.")
        linhas.append(f"{nome}={valor}")
    write_lines(path, linhas)
    os.environ[nome] = valor


def final_da_chave(nome):
    """Os 4 últimos caracteres da chave no ambiente (para mostrar qual está em uso), ou None."""
    valor = os.environ.get(nome, "").strip()
    return valor[-4:] if valor else None
