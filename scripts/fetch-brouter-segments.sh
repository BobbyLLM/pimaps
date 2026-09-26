#!/bin/sh
set -eu
DEST="${BROUTER_SEGMENT_PATH:?set BROUTER_SEGMENT_PATH}"
BASE="${BROUTER_SEGMENT_SOURCE:-https://brouter.de/brouter/segments4}"
MANIFEST="${BROUTER_MANIFEST:-brouter/segments-wa.txt}"
CHECKSUMS="${BROUTER_SHA256_MANIFEST:?set BROUTER_SHA256_MANIFEST to a pinned checksum file}"
mkdir -p "$DEST"
while IFS= read -r tile; do
  case "$tile" in ''|'#'*) continue;; esac
  expected=$(awk -v name="$tile" '$2 == name {print $1; exit}' "$CHECKSUMS")
  test "${#expected}" -eq 64 || { echo "missing checksum for $tile" >&2; exit 1; }
  tmp="$DEST/$tile.next"; curl -fL --retry 3 "$BASE/$tile" -o "$tmp"
  printf '%s  %s\n' "$expected" "$tmp" | sha256sum -c -
  mv -f "$tmp" "$DEST/$tile"
done < "$MANIFEST"
