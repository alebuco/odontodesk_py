#!/bin/bash
# Linux (Mint, Ubuntu): cria o atalho "OdontoDesk (Python)" no menu de aplicativos e na Área de Trabalho.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
python3 -m pip install -q --user -r "$DIR/requirements.txt" 2>/dev/null || python3 -m pip install -q --user --break-system-packages -r "$DIR/requirements.txt"
ARQ="$HOME/.local/share/applications/odontodesk-python.desktop"
mkdir -p "$(dirname "$ARQ")"
cat > "$ARQ" <<D
[Desktop Entry]
Type=Application
Name=OdontoDesk (Python)
Comment=Gestão de clínica odontológica
Exec=python3 "$DIR/desktop.py"
Path=$DIR
Icon=$DIR/odontodesk/static/icone.png
Terminal=false
Categories=Office;MedicalSoftware;
D
chmod +x "$ARQ"
DESK="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
[ -d "$DESK" ] && cp "$ARQ" "$DESK/" && chmod +x "$DESK/odontodesk-python.desktop" && gio set "$DESK/odontodesk-python.desktop" metadata::trusted true 2>/dev/null || true
echo "Pronto! Procure \"OdontoDesk (Python)\" no menu de aplicativos."
