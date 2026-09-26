# Updating and rollback

Pi Maps has two independent things to update:

1. **application source/container images**;
2. **regional edition data**.

Treat them separately. A source update should not quietly become an unreviewed
Western Australia rebuild, and a data update should not require editing the
frontend.

## Before any update

Know which edition is installed:

```sh
cat data/edition.json
cat data/.edition-complete
```

If you keep `MAPS_DATA` somewhere else, use that path instead.

For an important deployment, retain a copy/snapshot of the currently verified
data directory before promoting a new edition. Bootstrap protects the previous
files when a new download fails, but it does not create a permanent historical
rollback archive after a successful update.

## Updating application source

For a Git checkout, review the incoming release/tag, then update the checkout
using your normal Git workflow. Pull the pinned container images and recreate
the stack:

```sh
docker compose pull
docker compose up -d
```

If you use FULL mode:

```sh
docker compose --profile wikipedia pull
docker compose --profile wikipedia up -d
```

The one-shot bootstrap runs as part of Compose and validates the edition
manifest before dependent services start.

After the update, verify the application, not merely the container state:

```sh
docker compose ps
curl -fsS http://127.0.0.1:8090/ >/dev/null
curl -fsS 'http://127.0.0.1:8090/api/search?q=Murdoch%20University'
```

Then perform at least one browser route.

## Updating regional data

A data update should be represented by a new coherent edition manifest, not by
replacing random files in `data/` one at a time.

A maintainer build should pin and record the relevant upstream inputs:

- OSM extract identity/date and, ideally, URL + SHA-256;
- regional boundary used for PMTiles extraction;
- Protomaps source build date;
- BRouter segment set + SHA-256 values;
- optional ZIM identity + SHA-256;
- generated database checksums.

Build the large artefacts on a capable Linux build host. Do not make a 4 GB
Raspberry Pi perform a full WA regional rebuild merely because it runs the
service.

## What bootstrap guarantees

For each selected asset, bootstrap downloads into staging and verifies the
manifest's exact size and SHA-256 before promotion.

If a download is truncated or a checksum is wrong, that staged file is not
promoted. The existing installed file remains in place.

Once all selected downloads have succeeded, the new files and installed
`edition.json` are promoted and `.edition-complete` is updated.

The tests cover successful promotion, bad checksum, bad size, invalid transfer
rate, and reuse of an existing validated ZIM.

## Search database rebuild

For a maintainer/custom edition:

```sh
python3 scripts/build-search.py \
  --osm /path/to/region.osm.pbf \
  --output /path/to/search.sqlite
```

The builder creates `search.sqlite.next`, runs SQLite `integrity_check`, and
replaces the destination only when the new database passes.

Optional explicit route anchors can be supplied with `--anchors`, although the
builder can also discover retained OSM entrance nodes for matching area
features.

## PMTiles rebuild

The included `scripts/setup-pmtiles.sh` is a WA maintainer helper. It uses a
pinned dated Protomaps source and a supplied boundary, writes `.next`, verifies
the PMTiles archive, then promotes it.

Do not use `latest` as a provenance strategy. Record the dated source used for
each published edition.

## BRouter update

Update the tile list and checksum manifest together. The fetch helper stages
each `.rd5`, checks the pinned SHA-256, and then promotes it.

A different region generally needs a different segment set. Copying WA's
routing list into a custom edition simply because Compose starts is not a valid
regional build.

## Wikipedia update

Treat `wiki-pois.sqlite` and the ZIM identity as a matched pair.

If the ZIM changes, rebuild/revalidate the sidecar against that ZIM rather than
assuming every previously resolved title still points to the same local
content.

Keep the ZIM URL, size, SHA-256, article prefix, and sidecar provenance explicit
in the edition.

## Rollback

There are two practical rollback layers:

**Code rollback:** return the checkout to the previously known-good source
release/tag, pull the corresponding images, and recreate the stack.

**Data rollback:** restore the previously retained verified data directory (or
its files plus matching `edition.json` and `.edition-complete`) as one coherent
edition.

Do not roll back only `search.sqlite` while leaving a different edition's map,
routing and metadata unless you have intentionally verified that mixture.

After rollback, repeat the same map/search/route checks used after an update.
