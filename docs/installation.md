# Installation

The supported v1.0.0 edition is **Pi Maps — Western Australia** on ARM64 Linux,
with Raspberry Pi as the tested runtime target.

A normal installation does not build map data. The published edition manifest
already names the files, sizes, SHA-256 hashes, and download locations required
for Western Australia.

## What you need

- ARM64 Linux;
- Docker Engine;
- Docker Compose (`docker compose`);
- permission to use Docker with your host's normal setup;
- persistent disk space;
- Internet access during the initial asset download.

Pi Maps does **not** configure Docker permissions for you. If `docker compose`
fails with a Docker socket permission error, fix that at the host level rather
than changing Pi Maps.

You do not need Python, Java, osmium-tool, or a PMTiles CLI for a normal WA
installation. Those are build/maintainer tools.

## Disk use

The 22 required v1.0.0 WA assets total about **429 MiB**. They include the map,
search database, Wikipedia POI sidecar, and 19 BRouter segment files.

FULL mode additionally uses the pinned English mini Wikipedia ZIM, approximately
**12.5 GB**. Allow additional free space for Docker images, temporary download
staging, and future updates.

## Quick start

```sh
git clone https://github.com/BobbyLLM/pimaps.git
cd pimaps
docker compose pull
docker compose up -d
```

Open:

```text
http://<host>:8090
```

On first start, the one-shot `bootstrap` service downloads and verifies the WA
edition before the map/search/routing services start.

To watch that process:

```sh
docker compose logs -f bootstrap
```

A completed bootstrap container showing `Exited (0)` is normal.

## Verify a CORE install

Start with Compose itself:

```sh
docker compose ps
```

The long-running services should include `maps`, `search`, and `brouter`.
`bootstrap` should have completed successfully.

Then check the application rather than relying only on container state:

```sh
curl -fsS http://127.0.0.1:8090/ >/dev/null
curl -fsS 'http://127.0.0.1:8090/api/search?q=Murdoch%20University'
```

In a browser, verify that:

1. the basemap renders;
2. a local search returns labelled results;
3. selecting a result centres the map;
4. a From/To pair can produce a driving route.

A PMTiles map that renders does **not** by itself prove that search and routing
are healthy; they are separate data paths.

## Where the data goes

The default persistent data directory is:

```text
./data
```

You can override it with `MAPS_DATA`, for example in a local `.env` file.
`.env.example` lists the supported runtime overrides.

The installed directory will contain files such as:

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
```

Do not copy generated data into the Git source tree.

## Bind address and port

The defaults are:

```text
BIND_ADDRESS=0.0.0.0
HTTP_PORT=8090
```

Change these only if your host/network design requires it. For example, a host
that should expose Pi Maps only through a local reverse proxy can bind it more
narrowly.

Pi Maps itself has no authentication; read [security.md](security.md) before
making it reachable outside a trusted network.

## FULL mode: local Wikipedia

CORE does not require Wikipedia. To add local Wikipedia content, enable the
`wikipedia` profile:

```sh
docker compose --profile wikipedia pull
docker compose --profile wikipedia up -d
```

With the default data layout, FULL bootstrap can obtain the pinned ZIM from the
Kiwix upstream URL in `editions/wa.json`. The transfer is intentionally limited
to about 5 MiB/s by default to reduce storage I/O pressure on a Raspberry Pi.
A 12.5 GB download therefore takes time.

Progress is visible with:

```sh
docker compose logs -f wikipedia-bootstrap
```

The download is written to a temporary `.part` file, hashed while streaming,
checked for exact size and SHA-256, then promoted only if validation succeeds.
A matching existing ZIM is reused instead of downloaded again.

If you override `WIKI_ZIM_DIR` to a custom external directory, place the
validated ZIM there before starting FULL. Automatic acquisition is designed for
the default `data/zim` layout.

See [wikipedia.md](wikipedia.md) for how the sidecar database, Kiwix, map layer,
and local article proxy fit together.

## Private remote access

LAN HTTP is enough for local use. Browser geolocation normally requires a
secure context, so private HTTPS through Tailscale Serve is useful when you want
GPS or remote access without publishing the service to the Internet.

See [tailscale.md](tailscale.md).

## What a normal user should not have to do

For the official WA edition, you should not need to:

- install Python build dependencies;
- run osmium;
- extract PMTiles yourself;
- select BRouter tiles;
- edit `editions/wa.json`;
- manually copy regional databases into place.

If you are doing those things, you are in maintainer/custom-region territory;
start with [custom-region.md](custom-region.md) and [data-bundle-format.md](data-bundle-format.md).
