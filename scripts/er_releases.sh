#!/usr/bin/env bash
# Baixa releases oficiais em runtime (cache em ~/.er-tools). Sem token além do GITHUB_TOKEN automático.
set -u
D=~/.er-tools; mkdir -p "$D"
export GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"

need() { [ -x "$1" ] || [ -f "$1" ]; }

if [ "${ER_CAPA:-}" = 1 ]; then
  d="$D/capa"
  if ! need "$d/capa"; then
    mkdir -p "$d" /tmp/capa && rm -rf /tmp/capa/* 
    tag=$(gh api repos/mandiant/capa/releases/latest --jq .tag_name)
    gh release download "$tag" -R mandiant/capa -p "*linux*" -D /tmp/capa --clobber
    f=$(ls /tmp/capa/*linux* 2>/dev/null | head -1)
    case "$f" in *.zip) unzip -q -o "$f" -d "$d";; *) tar -xaf "$f" -C "$d" 2>/dev/null || cp "$f" "$d/";; esac
    b=$(find "$d" -type f \( -name capa -o -name 'capa-*' \) ! -name '*.json' | head -1)
    cp "$b" "$d/capa" && chmod +x "$d/capa"
  fi
  echo "$d" >> "$GITHUB_PATH"
fi

if [ "${ER_FLOSS:-}" = 1 ]; then
  d="$D/floss"
  if ! need "$d/floss"; then
    mkdir -p "$d" /tmp/floss && rm -rf /tmp/floss/*
    tag=$(gh api repos/mandiant/flare-floss/releases/latest --jq .tag_name)
    gh release download "$tag" -R mandiant/flare-floss -p "*linux*" -D /tmp/floss --clobber
    f=$(ls /tmp/floss/*linux* 2>/dev/null | head -1)
    case "$f" in *.zip) unzip -q -o "$f" -d "$d";; *) tar -xaf "$f" -C "$d" 2>/dev/null || cp "$f" "$d/";; esac
    b=$(find "$d" -type f \( -name floss -o -name 'floss-*' \) | head -1)
    cp "$b" "$d/floss" && chmod +x "$d/floss"
  fi
  echo "$d" >> "$GITHUB_PATH"
fi

if [ "${ER_DEXTOOLS:-}" = 1 ]; then
  d="$D/dex"
  if [ ! -f "$d/d2j-dex2jar.sh" ]; then
    mkdir -p "$d" /tmp/dex && rm -rf /tmp/dex/*
    tag=$(gh api repos/pxb1988/dex2jar/releases/latest --jq .tag_name)
    gh release download "$tag" -R pxb1988/dex2jar -p "*.zip" -D /tmp/dex --clobber
    unzip -q -o /tmp/dex/*.zip -d "$d"
    if [ ! -f "$d/d2j-dex2jar.sh" ]; then
      src=$(find "$d" -name d2j-dex2jar.sh | head -1)
      cp -r "$(dirname "$src")/." "$d/"
    fi
    chmod +x "$d"/d2j-*.sh || true
  fi
  # smali: jar from JesusFreke if available; else baksmali via apktool is enough — try release
  if ! ls "$d"/smali*.jar >/dev/null 2>&1; then
    tag=$(gh api repos/JesusFreke/smali/releases/latest --jq .tag_name 2>/dev/null || true)
    if [ -n "${tag:-}" ]; then
      gh release download "$tag" -R JesusFreke/smali -p "*.jar" -D "$d" --clobber 2>/dev/null || true
    fi
  fi
  if ls "$d"/smali*.jar >/dev/null 2>&1; then
    jar=$(ls "$d"/smali*.jar | head -1)
    printf '#!/bin/sh\nexec java -jar "%s" "$@"\n' "$jar" > "$d/smali"
    chmod +x "$d/smali"
  fi
  echo "$d" >> "$GITHUB_PATH"
fi
