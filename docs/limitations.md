# Limitations

Pi Maps v1.0.0 is a small offline-first route-planning application, not a
replacement for the full Google/Apple Maps navigation stack.

## Supported release

The official tested edition is **Western Australia on Raspberry Pi / ARM64
Linux**.

The runtime has been deliberately made less WA-specific, but custom regions are
an advanced, unsupported workflow. A Scotland build is documented as an example
of the process; Scotland is not bundled or claimed as tested.

## Search is local, not a global geocoder

Search uses the edition's local SQLite/FTS5 database. There is no remote geocoder
fallback.

Consequences:

- an address missing from the OSM-derived source can return no result;
- ambiguous names can return several labelled alternatives;
- Pi Maps prefers explicit selection over guessing;
- search quality is bounded by the source extract and builder rules.

This behaviour is intentional. A missing local result is safer than silently
routing to a fabricated coordinate.

## Routing is route planning, not live navigation

Pi Maps can draw a BRouter driving route, show distance and estimated time, and
turn BRouter voice hints into a basic instruction list.

It does **not** currently provide:

- automatic off-route detection;
- automatic rerouting;
- live route progress;
- a native turn-by-turn navigation workflow;
- spoken/TTS guidance;
- background or screen-off navigation;
- traffic-aware routing;
- live road closures/incidents;
- Android Auto or CarPlay integration.

The project author's suggested direction for a future navigation layer is
https://aussie.zone/post/36937974/25148282. That is design discussion, not
implemented functionality.

## BRouter coverage is finite

Routes are limited to the road graph in the installed `.rd5` segment set and
the behaviour of the chosen `car-vario` profile.

For large polygon POIs, the canonical map point may not lie on a routable road.
Pi Maps can retry a verified OSM entrance associated with that same POI, but it
will not invent a nearest-road snap when no safe anchor is available.

## Map/search/routing data can age differently

An edition should pin these sources together, but they remain distinct
artefacts. A map can render while the search database or routing coverage is
wrong or stale.

That is why release validation checks all three paths rather than treating
"the map loaded" as proof of a healthy edition.

## Wikipedia is optional and local

Wikipedia Places requires FULL mode, the regional `wiki-pois.sqlite` sidecar,
and the matching local Kiwix ZIM.

Not every OSM feature has a Wikipedia tag, not every tagged title necessarily
resolves in the chosen ZIM, and a local summary can be unavailable even when
the rest of Pi Maps is healthy.

## GPS depends on browser security rules

The frontend uses the browser geolocation API; it is not a native GPS service.
Normal browsers require a secure context and user permission. LAN HTTP can work
perfectly for maps/search/routes while geolocation remains unavailable.

Private HTTPS through Tailscale Serve is one supported way to supply a secure
context.

## No application accounts or access control

Pi Maps has no login system. Network reachability is effectively application
access.

Use a trusted LAN or private overlay. Do not expose the default service directly
to the public Internet and assume the application will authenticate users.
