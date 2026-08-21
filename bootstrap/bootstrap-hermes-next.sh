#!/bin/sh
set -eu

TARGET="${HERMES_NEXT_HOME:-$HOME/.hermes-next}"

if [ -e "$TARGET" ]; then
  echo "Refusing to overwrite existing path: $TARGET" >&2
  exit 1
fi

mkdir -p "$TARGET/state" "$TARGET/cache" "$TARGET/memory" "$TARGET/config"
chmod 700 "$TARGET" "$TARGET/state" "$TARGET/cache" "$TARGET/memory" "$TARGET/config"

cat > "$TARGET/README" <<EOT
Hermes Next experimental profile

This directory was created in isolation from the existing Hermes profile.
Do not enable writable sharing with production memory until the installed
Hermes configuration format and memory semantics have been verified.
EOT

echo "Created isolated experimental directory: $TARGET"
echo "No existing Hermes files were modified."
echo "Next step: map the actual installed Hermes profile/config mechanism."
