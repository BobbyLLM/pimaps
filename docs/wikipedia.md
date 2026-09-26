# Wikipedia Places

Wikipedia Places is an optional layer that joins local OSM places to articles
inside a local Kiwix ZIM.

It is designed so that, once installed, opening a map marker, reading the lead
paragraph, and opening the full article do **not** require a request to
Wikipedia.org.

CORE remains fully usable without it.

## What FULL mode adds

The `wikipedia` Compose profile adds Kiwix and the optional ZIM acquisition
step. Two pieces of data are involved:

```text
wiki-pois.sqlite     small regional sidecar, part of the WA release assets
Wikipedia .zim       large article archive, obtained from Kiwix upstream
```

The sidecar answers a regional question:

> Which OSM places in this edition have Wikipedia identities that resolve in
> this specific ZIM?

The ZIM supplies the article content itself.

## Runtime flow

```text
user enables "Wikipedia places"
             |
             v
browser requests ./api/wiki/pois for current map bounds
             |
             v
search service reads wiki-pois.sqlite R-tree
             |
             v
GeoJSON points -> clustered MapLibre layer

user clicks a place
             |
             v
./api/wiki/summary?osm_type=...&osm_id=...
             |
             v
search service finds sidecar row
             |
             v
local Kiwix article -> sanitised lead paragraph
```

The layer is off by default. When enabled, nearby points are clustered at lower
zoom levels to avoid drawing thousands of individual markers at once.

Clicking a place opens a local summary popup. The **Read full article** link is
also same-origin from the browser's point of view; the search service fetches
the corresponding article from local Kiwix.

## Install FULL mode

From an already working CORE checkout:

```sh
docker compose --profile wikipedia pull
docker compose --profile wikipedia up -d
```

The WA manifest pins:

```text
wikipedia_en_all_mini_2026-06.zim
```

including its authoritative Kiwix download URL, exact byte size, and SHA-256.
The Pi Maps GitHub release does not host this ~12.5 GB file.

With the default `data/zim` layout, the FULL bootstrap can download a missing
ZIM. The default transfer limit is about 5 MiB/s on Raspberry Pi. This is
intentional: sustained writes to shared storage can cause noticeable I/O wait.

The download is:

1. written to a `.part` file;
2. hashed while bytes arrive;
3. checked for exact declared size;
4. checked for exact SHA-256;
5. atomically promoted only after validation.

If a matching ZIM already exists in `WIKI_ZIM_DIR`, it is validated and reused.

If you set a custom external `WIKI_ZIM_DIR`, put the validated ZIM there before
starting FULL. Automatic download is intended for the default data layout.

## Building `wiki-pois.sqlite`

Normal WA users do not need to run this builder; the released sidecar is already
an edition asset.

Maintainers/custom-region builders can run:

```sh
python3 scripts/build-wiki-pois.py \
  --osm /path/to/region.osm.pbf \
  --zim /path/to/archive.zim \
  --output /path/to/wiki-pois.sqlite \
  --kiwix http://127.0.0.1:<port>/content/<zim-name>/
```

The builder uses `osmium-tool` to select OSM objects carrying English Wikipedia
tags, canonicalises duplicates, resolves titles against the supplied local
Kiwix service, and writes only successful direct/redirect matches.

The output contains:

- OSM type/ID and coordinates;
- feature class/subclass;
- Wikipedia title/fragment;
- Wikidata ID where present;
- resolved local ZIM target;
- resolution type;
- an R-tree for viewport queries;
- build/provenance counters and ZIM metadata.

It writes to `.next`, runs SQLite `integrity_check`, and only then replaces the
requested output.

## Summary HTML is constrained

Pi Maps does not dump arbitrary Kiwix HTML directly into the popup. The summary
parser extracts the first useful paragraph and keeps only a small set of inline
markup (`p`, links, emphasis, spans, superscript/subscript, and similar).

Links are rewritten toward the local article proxy where appropriate, and
unexpected external/scheme links are not treated as local article links.

Full article requests are restricted to the configured Kiwix article prefix;
unexpected redirects outside the local Kiwix base are rejected.

## Failure isolation

Wikipedia is optional by design.

If `wiki-pois.sqlite`, Kiwix, or the ZIM is unavailable, map/search/routing CORE
should still work. The Wikipedia layer reports itself unavailable rather than
turning a missing article archive into a map outage.

If a marker exists but its summary cannot be read locally, the popup can still
identify the place and report that the local summary is unavailable.
