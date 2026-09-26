# Data bundle format

An **edition** is the contract between Pi Maps code and a regional dataset.
The application should not need source-code edits merely because the map has
moved from one region to another; it should be able to learn the region's name,
map file, default view, routing profile, and downloadable assets from the
edition manifest.

For v1, manifests use:

```json
"schema_version": 1
```

The official example is `editions/wa.json`.

## Installed layout

A normal edition installs into the configured `MAPS_DATA` root:

```text
data/
  edition.json
  .edition-complete
  map.pmtiles
  search.sqlite
  wiki-pois.sqlite
  routing/
    segments/
      *.rd5
  zim/                         # optional FULL-mode data
    *.zim
```

The filenames are not all intrinsically fixed. The manifest tells the frontend
which PMTiles file to use and tells bootstrap where each asset belongs.

## Top-level metadata

A useful manifest identifies at least:

```json
{
  "schema_version": 1,
  "edition_id": "wa",
  "edition_name": "Western Australia",
  "data_version": "2026-09-26",
  "map": {
    "filename": "map.pmtiles",
    "default_center": [121.5, -25.0],
    "default_zoom": 4.2
  },
  "search": { "filename": "search.sqlite" },
  "routing": {
    "profile": "car-vario",
    "directory": "routing"
  }
}
```

The browser consumes `edition_name`, map filename, centre, and zoom from the
installed copy of this file.

## Asset entries

Each downloadable asset has four core fields:

```json
{
  "path": "routing/segments/E115_S35.rd5",
  "url": "https://example.invalid/E115_S35.rd5",
  "size": 12003876,
  "sha256": "..."
}
```

`path` and `url` serve different purposes:

- **`path`** is where the file belongs under the local data root;
- **`url`** is where bootstrap downloads it from.

They do not have to contain the same directory structure. The official GitHub
release, for example, uses flat BRouter asset names while installing them under
`routing/segments/` locally.

Bootstrap rejects absolute local paths and `..` path traversal. Download URLs
must be absolute HTTP or HTTPS URLs.

## Required and optional assets

Assets are required unless they carry:

```json
"optional": true
```

CORE bootstrap selects required assets only. The `wikipedia` profile enables
optional acquisition as well.

In the WA v1.0.0 manifest, the large Wikipedia ZIM is optional. The smaller
`wiki-pois.sqlite` sidecar is part of the required regional bundle, although it
is only used when Wikipedia mode is enabled.

## Validation and promotion

Bootstrap does not trust a successful HTTP response by itself.

For every selected asset it:

1. downloads into staging;
2. hashes incoming bytes with SHA-256;
3. checks the exact declared size;
4. checks the exact declared digest;
5. promotes the staged file with `os.replace()` only after validation.

Only after the selected set has been staged successfully is the edition
metadata promoted and `.edition-complete` written.

This is why a bad checksum can fail safely without replacing the installed
asset with a partial download.

## Wikipedia metadata

An edition that supports local Wikipedia also describes the sidecar and ZIM:

```json
"wikipedia": {
  "available": true,
  "filename": "wiki-pois.sqlite",
  "zim_name": "wikipedia_en_all_mini_2026-06.zim",
  "article_prefix": "/content/wikipedia_en_all_mini_2026-06/"
}
```

The ZIM URL may point to Kiwix upstream rather than the same release server as
the smaller regional assets.

## Provenance

A release manifest should record enough provenance to understand which upstream
inputs produced the bundle. At minimum, preserve what is actually known about:

- OSM provider/input identifier and date;
- source URL and SHA-256 when retained;
- PMTiles build/source date;
- BRouter source and checksum set;
- optional ZIM identity;
- applicable licensing/attribution.

Do not invent missing provenance. `UNKNOWN_NOT_RETAINED` is better than a
plausible-looking URL that was not actually recorded at build time.

## What PMTiles does not contain

A `.pmtiles` archive is only the rendered vector-map side of an edition. It does
not provide Pi Maps local search or BRouter routing.

A usable edition therefore needs a coherent set:

```text
PMTiles map
+ search.sqlite
+ routing segment coverage
+ edition metadata
+ matching checksums/provenance
(+ optional Wikipedia sidecar/ZIM)
```

If those pieces come from different regions or incompatible source dates, the
frontend can look correct while search or routing is wrong. Treat the edition
as one versioned unit.
