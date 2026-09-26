# BRouter setup

The release uses the pinned ARM64-capable BRouter image from `compose.yaml`,
profile `car-vario`, one worker, and the segment list in `segments-wa.txt`.
Run `scripts/fetch-brouter-segments.sh` with `BROUTER_SEGMENT_PATH` and
`BROUTER_SHA256_MANIFEST` set before starting Compose. The script downloads
only official `.rd5` files from `https://brouter.de/brouter/segments4/`,
verifies each checksum, and uses temporary names before promotion. BRouter
segments are generated from OpenStreetMap data and are not committed to Git.
