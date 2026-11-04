#!/bin/sh
# Linux launcher: right-click -> "Run as a Program" (GNOME Files) or double-click (KDE, Xfce).
# A file manager starts it without a window, so it reopens itself in a terminal: the window shows
# the panel's address, and closing it stops the panel.
here=$(cd "$(dirname "$0")" && pwd) || exit 1
self="$here/$(basename "$0")"
cd "$here" || exit 1

if [ ! -t 1 ] && [ -z "$EXPRESO_PANEL_IN_TERMINAL" ]; then
    for term in xdg-terminal-exec x-terminal-emulator gnome-terminal konsole xfce4-terminal kitty alacritty ghostty foot xterm; do
        command -v "$term" >/dev/null 2>&1 || continue
        export EXPRESO_PANEL_IN_TERMINAL=1
        case "$term" in
            xdg-terminal-exec|kitty|foot) exec "$term" "$self" ;;
            gnome-terminal) exec "$term" -- "$self" ;;
            xfce4-terminal) exec "$term" -x "$self" ;;
            *) exec "$term" -e "$self" ;;
        esac
    done
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Hace falta Python 3.9 o superior para abrir el panel."
    echo "Instalalo con el gestor de paquetes del sistema (el paquete suele llamarse python3)."
    printf "Apretá Enter para cerrar esta ventana."
    read -r _
    exit 1
fi
exec python3 -m panel.launcher --pause-on-error
