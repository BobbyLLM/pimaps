# Custom regions (advanced, unsupported)

Pi Maps v1.0.0 ships and tests **Western Australia**. The runtime has enough
metadata-driven behaviour to make other regions possible, but the project does
not promise a one-command region builder or support arbitrary datasets.

Treat this as a maintainer workflow.

A custom region needs more than a PMTiles file:

```text
regional PMTiles
+ search.sqlite from the same region
+ BRouter segment coverage
+ edition.json with correct metadata/checksums/provenance
(+ optional wiki-pois.sqlite and ZIM)
```

Build these on a capable Linux machine. Do not use a 4 GB Raspberry Pi as your
full regional build box merely because it is the runtime target.

## What is generic already

The runtime reads the following from edition metadata/configuration rather than
hard-coding WA into the browser:

- edition name;
- map filename;
- default map centre;
- default zoom;
- asset paths/URLs/checksums;
- search database path;
- routing segment directory/profile;
- optional Wikipedia filenames/prefix.

The search and Wikipedia builders accept an explicit OSM PBF path and output
path.

## What is still WA-specific

Not every maintainer helper is generic.

In particular, `scripts/setup-pmtiles.sh` deliberately rejects any
`REGION` other than `wa`. For another region, use the PMTiles CLI directly or
write your own small build wrapper rather than editing that script and assuming
the rest of the pipeline has been validated.

The repository also ships only the WA BRouter segment list/checksums and WA
release manifest.

## Build sequence

A sensible custom-region workflow is:

1. pin an OSM PBF and record its provenance;
2. obtain a region boundary suitable for PMTiles extraction;
3. extract a compatible PMTiles archive;
4. build `search.sqlite` from the same regional OSM input;
5. determine and pin the BRouter `.rd5` tiles covering the region;
6. optionally build a Wikipedia sidecar against a chosen local ZIM;
7. create a new edition manifest with exact sizes and SHA-256 hashes;
8. serve the bundle with Pi Maps on an isolated ARM64 runtime;
9. test map, search and routing together before trusting the edition.

## Worked example: Scotland (design example only)

Scotland is useful here because it forces every WA assumption to be removed.
It is **not** a bundled or tested Pi Maps edition.

### 1. Prepare a build workspace

For example:

```text
build/scotland/
  source/
    scotland.osm.pbf
    scotland-boundary.geojson
  out/
    map.pmtiles
    search.sqlite
    routing/segments/
    wiki-pois.sqlite          # optional
```

Pin the real source URL, date, size, and checksum in your own build record. Do
not use a floating `latest` URL as the only provenance you retain.

### 2. Build the PMTiles archive

Use a dated Protomaps build and your pinned Scotland boundary. The repository's
WA helper is not the right tool because it intentionally enforces `REGION=wa`.

The equivalent PMTiles operation is conceptually:

```sh
pmtiles extract \
  'https://build.protomaps.com/<YYYYMMDD>.pmtiles' \
  build/scotland/out/map.pmtiles.next \
  --region=build/scotland/source/scotland-boundary.geojson \
  --minzoom=0 \
  --maxzoom=15

pmtiles verify build/scotland/out/map.pmtiles.next
mv build/scotland/out/map.pmtiles.next build/scotland/out/map.pmtiles
sha256sum build/scotland/out/map.pmtiles
```

Choose and record the actual dated Protomaps source yourself. The example does
not claim a particular Scotland source date.

### 3. Build local search

```sh
python3 scripts/build-search.py \
  --osm build/scotland/source/scotland.osm.pbf \
  --output build/scotland/out/search.sqlite
```

The builder filters OSM features, creates an FTS5 database, runs
`integrity_check`, and atomically promotes the output.

Before proceeding, test several Scotland-specific place/address searches against
the database/API. A database that merely opens is not sufficient evidence of a
good search edition.

### 4. Select BRouter coverage

Determine which BRouter `segments4` tiles cover the region and the routes you
expect users to plan. Create a Scotland-specific tile list and SHA-256 manifest.

Do **not** reuse `brouter/segments-wa.txt`.

The included fetch helper can work with another list/checksum file when you set
its environment variables:

```sh
BROUTER_SEGMENT_PATH=build/scotland/out/routing/segments \
BROUTER_MANIFEST=build/scotland/segments-scotland.txt \
BROUTER_SHA256_MANIFEST=build/scotland/segments-scotland.sha256 \
  scripts/fetch-brouter-segments.sh
```

You are responsible for determining the correct regional tile set and pinning
its hashes.

### 5. Optional Wikipedia sidecar

If the edition will support Wikipedia Places, run a local Kiwix instance with
your chosen ZIM and build:

```sh
python3 scripts/build-wiki-pois.py \
  --osm build/scotland/source/scotland.osm.pbf \
  --zim /path/to/wikipedia.zim \
  --output build/scotland/out/wiki-pois.sqlite \
  --kiwix http://127.0.0.1:<port>/content/<zim-name>/
```

Record the ZIM identity and checksum in the edition.

### 6. Create `editions/scotland.json`

Start from the schema/shape described in
[data-bundle-format.md](data-bundle-format.md), not by blindly copying WA
values.

At minimum change:

- `edition_id` and `edition_name`;
- `data_version`;
- `map.filename` if different;
- default centre and zoom;
- every asset URL, size, SHA-256 and local path;
- routing coverage/provenance;
- OSM/PMTiles provenance;
- Wikipedia metadata if enabled.

There should be no WA filenames, WA checksums, WA centre coordinates, or WA
routing tile assumptions left in the Scotland edition.

### 7. Point Compose at the edition

v1.0.0's stock `compose.yaml` mounts `editions/wa.json` as the bootstrap
manifest. A custom edition therefore requires an explicit Compose override (or
a deliberately maintained variant) that mounts your `scotland.json` at
`/app/edition.json` for both bootstrap services.

That is one reason custom regions are labelled unsupported rather than
presented as a normal end-user switch.

Do not edit frontend source merely to change the map name or centre; those are
edition metadata.

### 8. Validate the region as a system

Test at least:

- map render and zoom across the region;
- PMTiles range requests;
- several city, street, address and POI searches;
- ambiguous names;
- routes in several parts of the region;
- routes near the edges of your BRouter coverage;
- page reload/restart behaviour;
- optional Wikipedia markers/summaries/articles if enabled.

A successful Compose start is not a custom-region acceptance test.

## Why custom regions remain unsupported in v1

The core pieces are reusable, but Pi Maps does not yet ship:

- a universal boundary/source acquisition tool;
- automatic BRouter tile selection;
- a generic release packager;
- a supported edition selector in stock Compose;
- a regression suite for arbitrary vector-tile schemas/regions.

The Scotland steps above show the intended architecture without pretending those
missing pieces already exist.
