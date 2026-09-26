# Architecture

Pi Maps is deliberately small. The browser does the map rendering; the Pi serves
static files, answers local search requests, and asks BRouter for routes. There
is no central application database, user account system, or cloud API that the
runtime depends on.

The Western Australia edition is split into two parts:

- **source/runtime code**, kept in this repository;
- **regional data**, downloaded from the edition manifest and stored outside the
  source tree.

That split is important. Updating the web application should not require
rebuilding Western Australia, and rebuilding Western Australia should not
require changing the application.

## Runtime at a glance

```text
browser
  |
  | HTTP / private HTTPS
  v
+---------------------------+
| nginx (`maps`)             |
|                           |
| static UI + MapLibre      |
| PMTiles byte-range reads  |
|                           |
| /api/search  ------------+----> search service ----> search.sqlite
| /api/route   ------------+----> BRouter ----------> routing/*.rd5
| /api/wiki/*  ------------+----> search service ----> wiki-pois.sqlite
|                                      |
|                                      +-------------> Kiwix ----> .zim
+---------------------------+
```

All browser API URLs are app-relative (`./api/search`, `./api/route`, and
`./api/wiki/...`). That is why the same frontend can work at a normal LAN root
or beneath a private reverse-proxy path without a hard-coded host name.

## Compose services

### `bootstrap`

A one-shot Python container. It reads `editions/wa.json`, downloads missing
regional assets, checks the declared byte size and SHA-256 of each download,
and only then promotes the staged files into the configured data directory.

A failed download, size check, or checksum check does not promote the staged
asset. Temporary `.part` files are removed on failure.

The installed edition is recorded in:

```text
data/edition.json
data/.edition-complete
```

`bootstrap` exits after it has established a valid edition. The long-running
services depend on it completing successfully.

### `maps`

An nginx container. It serves:

- the MapLibre frontend from `web/`;
- the installed regional data under `/data/`;
- PMTiles range requests;
- the app-relative API paths, which it proxies to the relevant internal
  service.

The container filesystem is read-only apart from nginx temporary files.

### `search`

A small Python HTTP service backed by read-only SQLite databases.

For normal search it opens `search.sqlite` read-only and uses SQLite FTS5. The
database keeps OSM identity (`osm_type` and `osm_id`), feature class, address
fields, coordinates, and optional routing anchors. Search is therefore not a
remote geocoder: if a place is absent from the local edition, Pi Maps does not
invent or fetch a coordinate from the Internet.

When Wikipedia mode is available, the same service also reads
`wiki-pois.sqlite` and proxies a tightly constrained subset of local Kiwix
content for summaries and full articles.

### `brouter`

BRouter is isolated from the browser. nginx proxies route requests to its
internal port. The Western Australia release uses the pinned BRouter image,
`car-vario`, one worker, and a 128 MiB Java heap.

The BRouter segment directory is mounted read-only.

See [routing.md](routing.md) for the important distinction between a place's
canonical map coordinate and its optional verified entrance used as a routing
fallback.

### `wikipedia-bootstrap` and `kiwix`

These are enabled only by the `wikipedia` Compose profile.

`wikipedia-bootstrap` extends the normal asset check to the optional ZIM. A
validated existing ZIM can be reused. With the default data layout, a missing
ZIM can be downloaded from the pinned Kiwix URL in the edition manifest.

`kiwix` serves that ZIM only inside the Compose network. The browser never needs
to contact Wikipedia.org at runtime.

## CORE and FULL

**CORE** is the normal map/search/routing stack:

```text
bootstrap -> maps + search + brouter
```

It works without Kiwix and without a ZIM.

**FULL** adds local Wikipedia content:

```text
bootstrap
wikipedia-bootstrap
maps + search + brouter + kiwix
```

The small `wiki-pois.sqlite` sidecar is part of the WA edition data. The large
Wikipedia ZIM is optional and comes from Kiwix upstream rather than the Pi Maps
GitHub release.

## Search resolution is deliberately conservative

A search result retains the OSM object identity that produced it. The browser
also keeps the chosen result's coordinates and marks it **Resolved locally**.
If the user edits the field, that resolution is discarded.

Typed route text is auto-resolved only when the local search service reports a
single exact-title top result. Ambiguous names must be selected explicitly.
Missing names remain missing.

This behaviour avoids a particularly unpleasant offline-map failure mode:
silently routing to the wrong thing because a guess happened to look plausible.

## Regional data is not built at runtime

The Raspberry Pi is a **runtime host**, not the intended Western Australia
build host.

A regional build may involve:

- an OSM PBF;
- `osmium-tool`;
- PMTiles extraction;
- SQLite database construction;
- BRouter segment selection;
- optional Kiwix/ZIM title resolution.

Those are batch jobs. They belong on a capable Linux build machine. The Pi
receives the resulting versioned artefacts and verifies them before use.

The runtime is metadata-driven in the places that matter for region selection:
edition name, PMTiles filename, default centre, and default zoom come from the
installed `edition.json`. Search and routing paths are configuration/data
paths rather than WA coordinates embedded in the frontend.

Custom-region construction is nevertheless an advanced, unsupported workflow;
see [custom-region.md](custom-region.md).

## Persistent state

By default, persistent regional data lives in `./data` beside the repository.
Set `MAPS_DATA` to move it elsewhere.

The source tree intentionally excludes generated regional data:

```text
*.sqlite
*.pbf
*.pmtiles
*.rd5
*.zim
```

That keeps Git small and makes the boundary clear: Git contains the program;
the edition manifest describes the data.
