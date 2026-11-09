"""Windows: a API do sistema (user32, dwmapi) via ctypes e pywin32. Retângulos em pixels físicos."""

import ctypes
import sys
import threading
import winreg
from ctypes import wintypes
from pathlib import Path

import psutil
import pywintypes
import win32api
import win32con
import win32gui
import win32process

from ..log import log

SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
WM_HOTKEY = 0x0312
HOTKEY_ID = 0xB0DD
HOTKEY_FALAR_ID = 0xB0DE

CHAVE_INICIO = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALOR_INICIO = "Pestinha"


class LASTINPUTINFO(ctypes.Structure):
    """Estrutura da API do Windows que guarda o instante da última entrada (teclado ou mouse)."""
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def ocioso_segundos():
    """Tempo ocioso lido da API do Windows (GetLastInputInfo)."""
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    now = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
    return ((now - info.dwTime) & 0xFFFFFFFF) / 1000.0


def processo_ativo():
    """Nome do programa da janela ativa, pelo pid da janela e o psutil."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return "unknown.exe"
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).name().lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, ValueError,
            pywintypes.error):
        return "unknown.exe"


_caminhos = {}                  # pid -> caminho do executável (o caminho de um processo não muda)


def caminho_ativo():
    """Caminho do executável da janela ativa ('' se não deu): é por ele que um jogo novo é reconhecido."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return ""
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid not in _caminhos:
            if len(_caminhos) > 200:
                _caminhos.clear()
            _caminhos[pid] = psutil.Process(pid).exe()
        return _caminhos[pid]
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, ValueError, OSError,
            pywintypes.error):
        return ""


def titulo_ativo():
    """Título da janela ativa. Só é lido com "Ver minha tela" ligado (ver mind/visao.py)."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return ""
    try:
        return win32gui.GetWindowText(hwnd)
    except pywintypes.error:
        return ""


def tela_cheia():
    """Janela em primeiro plano cobrindo o monitor inteiro (jogo, vídeo, apresentação)."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return False
    try:
        if win32gui.GetClassName(hwnd) in SHELL_CLASSES:
            return False
        # maximizada também passa das bordas do monitor quando não há barra de tarefas nele (ou ela se
        # esconde sozinha); o que separa as duas é a moldura, que a tela cheia de verdade não tem
        estilo = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        if ctypes.windll.user32.IsZoomed(hwnd) and estilo & (win32con.WS_CAPTION | win32con.WS_THICKFRAME):
            return False
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        m_left, m_top, m_right, m_bottom = win32api.GetMonitorInfo(monitor)["Monitor"]
    except Exception:
        return False
    return left <= m_left and top <= m_top and right >= m_right and bottom >= m_bottom


def _is_cloaked(hwnd):
    """Diz se o Windows está mostrando a janela como escondida (ex.: ela está em outro desktop virtual)."""
    cloaked = ctypes.c_int(0)
    try:
        ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
        )
    except Exception:
        return False
    return cloaked.value != 0


def _frame_rect(hwnd):
    """Retângulo visível (sem as bordas invisíveis de redimensionar do Windows 10/11)."""
    rect = wintypes.RECT()
    try:
        if ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), 9, ctypes.byref(rect), ctypes.sizeof(rect)
        ) == 0:
            return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        pass
    return win32gui.GetWindowRect(hwnd)


def janelas_visiveis(excluir, escala=1.0):
    """Janelas visíveis em ordem de z (de cima para baixo): [(hwnd, (l, t, r, b), maximizada)]."""
    found = []
    user32 = ctypes.windll.user32

    def callback(hwnd, _):
        """Chamado pelo Windows para cada janela: guarda só as que estão visíveis e são janelas de verdade."""
        try:
            if hwnd in excluir or not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                return True
            if win32gui.GetClassName(hwnd) in SHELL_CLASSES:
                return True
            # só janelas "de verdade" (as do Alt+Tab): sem dono, sem overlay transparente
            ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if ex & (win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_NOACTIVATE):
                return True
            if win32gui.GetWindow(hwnd, win32con.GW_OWNER) or _is_cloaked(hwnd):
                return True
            rect = _frame_rect(hwnd)
            if rect[2] - rect[0] < 120 or rect[3] - rect[1] < 60:
                return True
            found.append((hwnd, rect, bool(user32.IsZoomed(hwnd))))
        except Exception:
            pass        # janela sumiu no meio da leitura
        return True

    try:
        win32gui.EnumWindows(callback, None)
    except Exception as error:
        log(f"[senses] não deu para listar janelas: {error}")
    return found


def retangulo_ativo(escala=1.0):
    """Retângulo da janela ativa (pixels físicos), para ele olhar para ela."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None
    try:
        if win32gui.GetClassName(hwnd) in SHELL_CLASSES:
            return None
        return _frame_rect(hwnd)
    except Exception:
        return None


def sem_foco_nativo(janela_id):
    """A janela não ativa nem rouba o foco ao aparecer ou ser clicada."""
    try:
        style = win32gui.GetWindowLong(janela_id, win32con.GWL_EXSTYLE)
        style |= win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW
        win32gui.SetWindowLong(janela_id, win32con.GWL_EXSTYLE, style)
    except Exception:
        pass    # sem janela nativa (ex.: teste offscreen)


def comando_de_inicio():
    """O comando que abre o programa ao entrar no Windows, sem a tela de permissões nem terminal."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --direto'
    python = Path(sys.executable)
    sem_terminal = python.with_name("pythonw.exe")
    if sem_terminal.exists():
        python = sem_terminal
    return f'"{python}" "{Path(__file__).resolve().parents[2] / "main.py"}" --direto'


def inicia_com_sistema():
    """Diz se o registro do usuário abre esta cópia do programa ao entrar no Windows."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_INICIO) as chave:
            return winreg.QueryValueEx(chave, VALOR_INICIO)[0] == comando_de_inicio()
    except OSError:
        return False


def definir_inicio_com_sistema(ligado):
    """Liga ou desliga o início com o Windows (só para este usuário); devolve True se conseguiu."""
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CHAVE_INICIO) as chave:
            if ligado:
                winreg.SetValueEx(chave, VALOR_INICIO, 0, winreg.REG_SZ, comando_de_inicio())
            else:
                try:
                    winreg.DeleteValue(chave, VALOR_INICIO)
                except FileNotFoundError:
                    pass
    except OSError as error:
        log(f"[início] não deu para mudar o início com o Windows: {error}")
        return False
    return True


def _registrar(tecla, ident, callback, nome):
    """RegisterHotKey de Ctrl+Alt+Shift+`tecla` numa thread com fila de mensagens própria. True se conseguiu."""
    pronto = threading.Event()
    resultado = {"ok": False}

    def laco():
        """Laço da thread que registra o atalho e recebe as teclas do sistema."""
        user32 = ctypes.windll.user32
        resultado["ok"] = bool(user32.RegisterHotKey(
            None, ident, MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_NOREPEAT, ord(tecla)
        ))
        pronto.set()
        if not resultado["ok"]:
            log(f"[{nome}] não deu para registrar o atalho (outro programa usa?)")
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam == ident:
                callback()

    threading.Thread(target=laco, daemon=True).start()
    pronto.wait(2.0)
    return resultado["ok"]


def iniciar_atalho(callback):
    """Ctrl+Alt+Shift+B (pânico). Devolve True se conseguiu."""
    return _registrar("B", HOTKEY_ID, callback, "pânico")


def iniciar_atalho_falar(callback):
    """Ctrl+Alt+Shift+V (segurar para falar). Devolve True se conseguiu."""
    return _registrar("V", HOTKEY_FALAR_ID, callback, "voz")


def tecla_falar_segurada():
    """A tecla V ainda está apertada? (o Windows sabe: dá para soltar e parar de ouvir)."""
    return bool(ctypes.windll.user32.GetAsyncKeyState(ord("V")) & 0x8000)
