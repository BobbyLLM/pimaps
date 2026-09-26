# Pi Maps — Western Australia

Pi Maps is a small self-hosted map for Western Australia: local vector maps,
local search, and local BRouter driving routes, with an optional local Wikipedia
layer through Kiwix.

It is designed to keep working when the wider Internet does not. After the
regional data has been installed, normal map/search/routing use does not depend
on a public geocoder or map API.

This repository is maintained for *private* use, but you are welcome to use it.
Pull requests are not accepted.
No support or compatibility guarantee is provided.

## What you get

**CORE** runs:

- MapLibre + PMTiles map rendering;
- SQLite/FTS5 local search;
- BRouter driving routes.

**FULL** adds:

- a local Wikipedia-linked POI layer;
- local article summaries;
- full local articles from a Kiwix ZIM.

The supported v1.0.0 edition is **Western Australia on ARM64 Linux / Raspberry
Pi**. Custom regions are possible as a maintainer exercise but are not a v1
compatibility promise.

## Quick start

You need Docker Engine, Docker Compose, persistent storage, Internet access for
the first data download, and a host user that already has permission to use
Docker.

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

The first start downloads the published WA data bundle and verifies every
asset's byte size and SHA-256 before the long-running services start. The 22
required regional assets total about 429 MiB.

For first-install checks, data location, bind settings and expected container
state, read **[Installation](docs/installation.md)**.

## Optional local Wikipedia

CORE does not require Kiwix.

To enable FULL mode:

```sh
docker compose --profile wikipedia pull
docker compose --profile wikipedia up -d
```

The WA edition pins `wikipedia_en_all_mini_2026-06.zim` from Kiwix upstream.
It is about 12.5 GB and is not hosted as a Pi Maps GitHub Release asset. With
the default data layout, Pi Maps can download and verify it automatically at a
deliberately gentle default rate of about 5 MiB/s.

See **[Wikipedia Places](docs/wikipedia.md)** for details.

## Private remote access and GPS

LAN HTTP works for map/search/routing. Tailscale is optional.

For private remote access, Tailscale Serve can put HTTPS in front of the local
Pi Maps port without exposing it through Funnel. HTTPS is also useful because
normal browsers require a secure context for geolocation/GPS.

See **[Private HTTPS with Tailscale](docs/tailscale.md)**.

## What Pi Maps is not

Pi Maps plans routes; it is not yet a live navigation app. There is no automatic
rerouting, spoken guidance, background navigation, live traffic, Android Auto,
or CarPlay integration.

Search is also deliberately local. If the edition's OSM-derived search data
does not contain an address or place, Pi Maps does not ask a public geocoder or
invent a coordinate.

See **[Limitations](docs/limitations.md)**.

## How the data is organised

The source repository does not contain the heavy regional artefacts. The
edition manifest describes and pins them instead:

```text
map.pmtiles
search.sqlite
wiki-pois.sqlite
routing/segments/*.rd5
optional Wikipedia .zim
```

The normal Raspberry Pi installation consumes these files; it does not build a
full Western Australia dataset.

For the design and data contract, read:

- **[Architecture](docs/architecture.md)**
- **[Data bundle format](docs/data-bundle-format.md)**
- **[Data sources and provenance](docs/data-sources.md)**
- **[Routing](docs/routing.md)**

## Maintaining or adapting Pi Maps

- **[Updating and rollback](docs/updating.md)** — code vs data updates and safe
  rollback.
- **[Troubleshooting](docs/troubleshooting.md)** — diagnose bootstrap, map,
  search, routing, Wikipedia and Tailscale separately.
- **[Custom regions](docs/custom-region.md)** — advanced, unsupported workflow,
  including a worked Scotland design example.
- **[Security model](docs/security.md)** — deployment boundary and why Pi Maps
  should remain on a trusted LAN/private overlay unless you add your own auth.

Normal WA users do not need Python, osmium-tool, the PMTiles CLI, or Java on the
host. Those are maintainer/build-host tools.

## Licence

Pi Maps project-authored code is licensed under **AGPL-3.0-only**.
Third-party components and data keep their own licences. See `NOTICE.md` and
[data sources and provenance](docs/data-sources.md) before redistributing a
regional data bundle.
