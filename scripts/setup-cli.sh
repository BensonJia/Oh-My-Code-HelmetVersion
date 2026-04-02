#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY_MINOR="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
BIN_DIR="$HOME/Library/Python/$PY_MINOR/bin"
LOCAL_BIN="$HOME/.local/bin"
ZSHRC="$HOME/.zshrc"
PATH_LINE="export PATH=\"$BIN_DIR:\$PATH\""
LOCAL_PATH_LINE="export PATH=\"$LOCAL_BIN:\$PATH\""

echo "[setup-cli] Installing editable package from: $ROOT_DIR"
cd "$ROOT_DIR"
pip3 install -e ".[dev]"

if [ ! -d "$BIN_DIR" ]; then
  echo "[setup-cli] Creating user bin directory: $BIN_DIR"
  mkdir -p "$BIN_DIR"
fi

if [ -f "$ZSHRC" ]; then
  ZSHRC_CONTENT="$(cat "$ZSHRC")"
  if [[ "$ZSHRC_CONTENT" != *"$LOCAL_BIN"* ]]; then
    echo "$LOCAL_PATH_LINE" >> "$ZSHRC"
    echo "[setup-cli] Added local bin PATH entry to $ZSHRC"
  else
    echo "[setup-cli] Local bin PATH entry already exists in $ZSHRC"
  fi
  if [[ "$ZSHRC_CONTENT" != *"$BIN_DIR"* ]]; then
    echo "$PATH_LINE" >> "$ZSHRC"
    echo "[setup-cli] Added PATH entry to $ZSHRC"
  else
    echo "[setup-cli] PATH entry already exists in $ZSHRC"
  fi
else
  printf "%s\n%s\n" "$LOCAL_PATH_LINE" "$PATH_LINE" > "$ZSHRC"
  echo "[setup-cli] Created $ZSHRC with PATH entries"
fi

mkdir -p "$LOCAL_BIN"

# Stable global shim: this is the command users/agents should run everywhere.
cat > "$LOCAL_BIN/ohmycode" <<EOF
#!/usr/bin/env bash
exec "$BIN_DIR/ohmycode" "\$@"
EOF
chmod +x "$LOCAL_BIN/ohmycode"

export PATH="$LOCAL_BIN:$BIN_DIR:$PATH"

echo "[setup-cli] Verifying CLI wiring..."
pip3 show ohmycode
which ohmycode
ohmycode --help >/dev/null
echo "[setup-cli] OK: use 'ohmycode' to start."
