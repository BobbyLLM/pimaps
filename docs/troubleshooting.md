# Troubleshooting

Pi Maps is easier to diagnose if you follow the request path instead of changing
several layers at once.

```text
browser
  -> nginx/maps
      -> static web + PMTiles
      -> search service -> search.sqlite
      -> BRouter -> .rd5 segments
      -> optional wiki service -> wiki-pois.sqlite -> Kiwix -> ZIM
```

Start at the first failing layer.

## Basic health checks

```sh
docker compose ps
curl -fsS http://127.0.0.1:8090/ >/dev/null
curl -fsS 'http://127.0.0.1:8090/api/search?q=Murdoch%20University'
```

Useful logs:

```sh
docker compose logs --tail=100 bootstrap
docker compose logs --tail=100 maps
docker compose logs --tail=100 search
docker compose logs --tail=100 brouter
```

For FULL mode also inspect:

```sh
docker compose --profile wikipedia logs --tail=100 wikipedia-bootstrap
docker compose --profile wikipedia logs --tail=100 kiwix
```

## `docker compose` cannot connect to Docker

Typical symptom:

```text
permission denied ... /var/run/docker.sock
```

That is a host Docker-permission problem, not a Pi Maps bootstrap failure.
Pi Maps deliberately does not edit Docker groups, sudoers, socket permissions,
or daemon configuration.

Use the privilege/permission model you have chosen for that host, then rerun the
normal Compose command.

## Bootstrap exits non-zero

First read the bootstrap log. The important failure classes are explicit.

### Size mismatch

The downloaded byte count does not equal the manifest. This can be a truncated
or wrong asset.

Do not change the manifest size just to make the error disappear. Confirm the
release asset and expected metadata.

### Checksum mismatch

The downloaded bytes are not the pinned artefact.

Again, do not bypass the check. Verify the release asset and manifest digest.
A failed staged download should leave the previously installed file in place.

### Invalid URL

Bootstrap accepts absolute `http://` or `https://` asset URLs. Relative paths,
`file://`, and placeholder origins are rejected.

### Leftover `.part`

A handled download failure removes its `.part` file. If one exists after a host
crash/power loss, make sure no bootstrap is still running before removing the
stale partial and retrying.

## The page opens but the map is blank

Check the browser developer console/network tab and the PMTiles endpoint.

The map is served from the installed edition filename rather than a hard-coded
WA path. Confirm `data/edition.json` exists and that its `map.filename` exists in
the same data root.

PMTiles requires byte-range reads. A useful HTTP check is:

```sh
curl -I http://127.0.0.1:8090/data/map.pmtiles
```

The exact filename can differ in a custom edition; use the installed manifest.

If the map fails but `/api/search` works, concentrate on nginx/data/PMTiles,
not SQLite search.

## Search returns nothing

First distinguish a service failure from a legitimate no-result query.

```sh
curl -fsS 'http://127.0.0.1:8090/api/search?q=Murdoch%20University'
```

If that returns JSON normally, the service is alive. A particular missing
address may simply not exist in the current local OSM-derived database.

Pi Maps intentionally does not call an Internet geocoder or make up a
coordinate for absent data.

If the API itself fails:

```sh
docker compose logs --tail=100 search
```

For a maintainer diagnosis, verify SQLite directly inside the search container:

```sh
docker compose exec search python3 -c \
'import sqlite3; c=sqlite3.connect("file:/data/search.sqlite?mode=ro", uri=True); print(c.execute("pragma integrity_check").fetchone())'
```

Expected result:

```text
('ok',)
```

## A route field will not resolve

If the UI says **Select a specific local result before routing**, the text is
ambiguous. Pick one of the labelled local results.

If it says there is no local result, the routing engine has not failed yet; the
place could not be resolved from local search data.

Editing a previously selected route field intentionally clears its stored
coordinates. Select/resolve it again.

## Search resolves, but routing fails

Check BRouter:

```sh
docker compose ps brouter
docker compose logs --tail=100 brouter
```

Then verify the current edition's `.rd5` files exist under the configured data
root.

For area POIs Pi Maps first tries the canonical coordinate. If BRouter returns
its specific no-track/island condition, Pi Maps may retry a verified entrance
stored with that POI. If there is no safe entrance, failure is expected; Pi Maps
does not snap to an arbitrary nearby road.

See [routing.md](routing.md).

## Wikipedia Places says unavailable

CORE does not need Wikipedia, so first confirm map/search/routing are healthy.

Then check:

```sh
docker compose --profile wikipedia ps
docker compose --profile wikipedia logs --tail=100 wikipedia-bootstrap
docker compose --profile wikipedia logs --tail=100 kiwix
```

Confirm:

- `wiki-pois.sqlite` exists in the installed edition;
- the configured ZIM exists in `WIKI_ZIM_DIR`;
- its filename matches `WIKI_ZIM_NAME`/edition metadata;
- Kiwix is using the expected article prefix.

If you changed `WIKI_ZIM_DIR` to a custom external location, automatic download
is not a substitute for placing the ZIM in that custom directory. Either use
the default data layout or supply the validated file yourself.

A missing local summary for one POI does not imply Kiwix as a whole is down.

## Tailscale peer is online, but HTTPS cannot connect

Prove Pi Maps works locally first.

If local HTTP works and Tailscale Serve is configured, inspect `tailscaled`.
Inbound TCP/443 drops containing:

```text
no rules matched
```

normally point to the tailnet ACL/grant rather than Pi Maps.

Grant only the intended client/device class access to the Pi endpoint on TCP
443. Keep Funnel off for private access.

See [tailscale.md](tailscale.md).

## Map works remotely but GPS does not

The browser geolocation API needs a secure context and user permission.

Check that you are using the private HTTPS endpoint, then check the browser/site
location permission. Do not change routing data because a browser denied GPS.

## After an update, something is inconsistent

Check the installed edition identity:

```sh
cat data/edition.json
cat data/.edition-complete
```

Avoid manually mixing artefacts from different editions. If necessary, restore
the last known-good edition as a coherent set and rerun map/search/route checks.

See [updating.md](updating.md).
