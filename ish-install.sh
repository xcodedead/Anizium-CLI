#!/bin/sh
set -eu

REPO_URL="https://github.com/xcodedead/Anizium-CLI.git"
INSTALL_DIR="${HOME:-.}/Anizium-CLI"

if ! command -v apk >/dev/null 2>&1; then
    echo "Bu betik iSH içindir; apk komutu bulunamadı." >&2
    exit 1
fi

echo "Gerekli paketler kuruluyor..."
apk update
apk add git python3

python3 - <<'PY'
import sys
if sys.version_info < (3, 10):
    sys.exit(
        f"Anizium CLI Python 3.10+ gerektiriyor; bulunan sürüm: {sys.version.split()[0]}. "
        "iSH Alpine depolarında daha yeni Python sürümü mevcut olmayabilir."
    )
PY

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Anizium CLI zaten kurulu: $INSTALL_DIR"
else
    if [ -e "$INSTALL_DIR" ]; then
        echo "Kurulum yolu mevcut ancak bir Git deposu değil: $INSTALL_DIR" >&2
        exit 1
    fi
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
exec python3 anizium.py
