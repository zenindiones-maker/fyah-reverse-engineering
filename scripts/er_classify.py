"""Classifica as ferramentas Essencial (LOCAL_OK) da curadoria: instalado / referência / pendente.

instalado = tem smoke test em er-toolcheck (via INSTALLED abaixo). referência = awesome lists, datasets, docs/cursos,
apps só-GUI, plugins de IDA/Ghidra/x64dbg, coleções de scripts Frida, ferramentas só-Windows/iOS/dispositivo, cheats.
"""
import csv, pathlib, re, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
INSTALLED = {
    # áudio
    "librosa/librosa", "spotify/pedalboard", "MTG/essentia", "libAud
