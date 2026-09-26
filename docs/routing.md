# Routing

Pi Maps uses **BRouter** for local driving routes. BRouter runs as its own
container and reads a fixed set of `.rd5` routing segments from the installed
edition. The browser never talks to BRouter directly; nginx proxies
`./api/route` to the internal BRouter service.

The WA release uses:

- the pinned ARM64-capable BRouter image from `compose.yaml`;
- profile `car-vario`;
- one worker;
- a 128 MiB Java heap;
- 19 checksum-pinned WA segment files.

## Search comes before routing

The route boxes are not free-form remote geocoders. They resolve against the
local `search.sqlite` database.

When you select a result, Pi Maps keeps:

- its display label;
- OSM type and ID;
- canonical longitude/latitude;
- an optional verified route anchor.

The field is shown as **Resolved locally**. Editing the text clears that stored
resolution so stale coordinates cannot silently survive a changed label.

If you type text and press Route without selecting a result, Pi Maps will only
auto-resolve it when the local API reports one unambiguous exact-title top
match. Otherwise it asks you to select a specific result.

This is intentional. Offline routing to the wrong place is worse than refusing
to guess.

## Canonical point first

Every route starts with the selected POI's canonical map coordinate.

Conceptually:

```text
selected place
    |
    +--> canonical OSM coordinate
             |
             v
          BRouter
```

If BRouter can route that coordinate, the job is done.

For point features and many street addresses this is straightforward. Large
polygon POIs are harder: the canonical point may be the centre of a zoo,
university, park, hospital campus, or other area that is not itself on a
routable road.

## Verified entrance fallback

The search builder can record a second coordinate for an area POI: a retained
OSM entrance node that lies **inside the matching POI geometry**. `entrance=main`
is preferred over a generic `entrance=yes` candidate.

This is not nearest-road snapping.

Pi Maps does **not** pick an arbitrary road, car park, bus stop, or guessed
coordinate because it happens to be nearby.

The browser tries an entrance only when the canonical BRouter attempt fails
with BRouter's specific no-track diagnostic (`no track found` or
`island detected`, HTTP 400):

```text
canonical point
     |
     | route succeeds ----------------------------> use route
     |
     | BRouter says no track / island
     v
verified OSM entrance available?
     |
     +-- no --------------------------------------> report no routable local access point
     |
     +-- yes --> retry with entrance ------------> use route if successful
```

The place does not become the entrance. Its label, marker, OSM identity, and
canonical coordinates stay unchanged. The route status tells the user when the
route used an entrance fallback.

The same logic applies independently to the From and To ends of a route.

### Concrete WA example

The production validation case was **Perth Zoo** (`way/8046233`). Its canonical
polygon coordinate remains the displayed POI location. The search build also
found OSM `node/2487994136`, tagged `entrance=main`, inside the same POI area.
That entrance is used only after the canonical routing attempt returns the
specific no-track condition.

POIs for which no safe associated entrance is available simply keep null anchor
fields; Pi Maps does not manufacture one.

## Route request and response

The frontend requests BRouter GeoJSON using the resolved coordinates and
`car-vario`. A successful response supplies the route geometry and properties
such as route length, estimated time, and BRouter voice hints.

Pi Maps draws the returned geometry and converts the available voice hints into
a simple on-screen instruction list.

This is **route planning**, not a live navigation engine. There is no route
progress tracker, spoken guidance, automatic off-route detection, or automatic
rerouting. See [limitations.md](limitations.md).

## Routing coverage

BRouter can only route where the installed `.rd5` files contain the required
road graph. The official WA edition declares and verifies the segment set in
`editions/wa.json`.

For maintainer builds, the repository also contains:

```text
brouter/segments-wa.txt
brouter/segments-wa.sha256
scripts/fetch-brouter-segments.sh
```

The fetch script downloads from BRouter's official `segments4` endpoint into
temporary names, verifies each pinned checksum, and only then promotes the
file.

## Diagnosing a routing failure

First separate **resolution** from **routing**.

If the route field says that there is no local result or asks you to select a
specific result, BRouter has not been called yet. That is a search/data issue.

If both endpoints are resolved but routing fails:

```sh
docker compose ps brouter
docker compose logs --tail=100 brouter
```

Then confirm that the installed routing directory contains the segment files
declared by the current edition manifest.

A canonical polygon coordinate that cannot be routed is not automatically an
error: Pi Maps may retry a verified entrance. If there is no safe entrance, the
correct result is a clear failure rather than a guessed destination.
