"""Programas de trabalho: VS Code, Claude e Codex contam como programação."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pestinha.sense.senses import ACTIVITY_APPS, detect_activity  # noqa: E402


def test_editores_e_assistentes_sao_programacao():
    for app in ("code.exe", "claude.exe", "codex.exe"):
        assert detect_activity(app, 0.0, 300.0) == "PROGRAMMING"


def test_outro_programa_nao_e_programacao():
    assert detect_activity("discord.exe", 0.0, 300.0) == "SOCIAL"


def test_ocioso_vira_ausente_mesmo_com_editor_aberto():
    assert detect_activity("code.exe", 400.0, 300.0) == "AWAY"


def test_design_video_e_fatiadores_3d_sao_design():
    for app in ("blender.exe", "Photoshop.exe", "Adobe Photoshop", "Resolve.exe", "CapCut.exe",
                "bambu-studio.exe", "Bambu Studio", "orca-slicer.exe", "prusa-slicer", "PrusaSlicer",
                "ultimaker-cura", "UltiMaker Cura", "Figma"):
        assert detect_activity(app, 0.0, 300.0) == "DESIGNING", app


def test_jogos_populares_sao_jogo():
    for app in ("League of Legends.exe", "RobloxPlayerBeta.exe", "Roblox", "Minecraft.Windows.exe",
                "Minecraft", "FortniteClient-Win64-Shipping.exe", "r5apex.exe", "dota2"):
        assert detect_activity(app, 0.0, 300.0) == "GAMING", app


def test_novos_editores_sao_programacao():
    for app in ("Antigravity.exe", "Kiro.exe", "studio64.exe"):
        assert detect_activity(app, 0.0, 300.0) == "PROGRAMMING", app


def test_cada_programa_esta_numa_categoria_so():
    vistos = {}
    for categoria, apps in ACTIVITY_APPS.items():
        for app in apps:
            assert app == app.lower() and not app.endswith(".exe"), app
            assert app not in vistos, f"{app} em {vistos.get(app)} e {categoria}"
            vistos[app] = categoria
