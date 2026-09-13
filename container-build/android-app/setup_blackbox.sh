#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HERE/vendor/NewBlackbox"
REPO="https://github.com/ALEX5402/NewBlackbox.git"
COMMIT="89b59836c66f173756a4ae258cf379a957649820"
rm -rf "$DEST"
mkdir -p "$(dirname "$DEST")"
git clone --filter=blob:none --no-checkout "$REPO" "$DEST"
git -C "$DEST" checkout "$COMMIT"
echo "BlackBox fixado em $COMMIT"
