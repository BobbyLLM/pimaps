#!/bin/sh
set -eu
REGION="${REGION:-wa}"; SOURCE_DATE="${SOURCE_DATE:?set SOURCE_DATE, e.g. 2026-09-25}"
APP_DATA_ROOT="${APP_DATA_ROOT:-.}"; PMTILES_CLI="${PMTILES_CLI:-$APP_DATA_ROOT/bin/pmtiles}"
BOUNDARY="${BOUNDARY:?set BOUNDARY to a pinned regional GeoJSON file}"
OUT="${OUTPUT:-$APP_DATA_ROOT/data/map.pmtiles}"
[ "$REGION" = wa ] || { echo 'This release currently supports REGION=wa only' >&2; exit 2; }
SRC="https://build.protomaps.com/${SOURCE_DATE}.pmtiles"
mkdir -p "$(dirname "$OUT")"; tmp="$OUT.next"; rm -f "$tmp"
"$PMTILES_CLI" extract "$SRC" "$tmp" --region="$BOUNDARY" --minzoom=0 --maxzoom=15 --download-threads="${DOWNLOAD_THREADS:-4}"
"$PMTILES_CLI" verify "$tmp"; mv -f "$tmp" "$OUT"; sha256sum "$OUT"
