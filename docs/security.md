# Security model

Pi Maps is designed for a trusted home/LAN deployment or a private overlay such
as Tailscale. It is **not** an Internet-facing multi-user application.

There is no Pi Maps login screen, user database, session system, role model, or
application-level authentication.

If you expose the HTTP port to an untrusted network, anyone who can reach it can
use the application.

## Recommended boundary

Use one of these deployment shapes:

```text
trusted LAN client ---> Pi Maps HTTP
```

or:

```text
private Tailscale client ---> Tailscale Serve HTTPS ---> Pi Maps HTTP
```

For private Tailscale use, keep Funnel off. Funnel makes a service reachable
from the public Internet and is not required for Pi Maps.

If your deployment genuinely needs public access, put an appropriate,
maintained authentication/reverse-proxy/security layer in front of Pi Maps and
own that design separately. The repository does not provide one.

## Default listener

The Compose default is:

```text
BIND_ADDRESS=0.0.0.0
HTTP_PORT=8090
```

That means the host port listens on all host interfaces. On a trusted LAN that
may be exactly what you want. On a host with other network exposure, bind it to
a more appropriate address or place it behind a private proxy/overlay.

## Runtime write boundaries

The long-running map/search/routing containers are intentionally constrained:

- nginx serves the frontend and regional files read-only;
- the search service mounts regional SQLite data read-only;
- BRouter mounts routing segments read-only;
- Kiwix mounts the ZIM read-only;
- container root filesystems are read-only where practical.

The one-shot bootstrap service is the component that writes regional data. It
downloads into staging, checks declared size and SHA-256, and promotes verified
files.

This is useful hardening, but it is not a sandbox against a hostile Docker host.
Anyone with effective control of the Docker daemon is already highly privileged
on that machine.

## Download trust

The edition manifest pins asset size and SHA-256. Bootstrap rejects an asset
whose bytes do not match the manifest.

Checksums protect the identity/integrity of the expected release artefacts; they
do not replace HTTPS, upstream security, or review of the manifest itself.

Do not casually edit an edition manifest to point at an untrusted mirror and
then treat checksum errors as something to work around.

## Wikipedia proxy

FULL mode does not expose Kiwix directly through a public container port. The
search service acts as the application-facing bridge.

For summaries it parses local Kiwix HTML and emits only a small allow-list of
inline tags. External/scheme-bearing links are not passed through as arbitrary
browser links. Full article requests are constrained to the configured local
Kiwix article prefix and reject unexpected redirects outside that local base.

This reduces the proxy surface; it is not a claim that Pi Maps is a hardened
public content gateway.

## No telemetry requirement

The runtime map, search, routing, and installed Wikipedia path are local. Pi
Maps does not require a public geocoder or public Wikipedia API for normal
operation after the regional data is installed.

Initial installation and future data/code updates do require access to the
configured download sources.

## Tailscale is access control, not magic

A device appearing online in a tailnet does not automatically mean it is
allowed to reach Pi Maps. The tailnet ACL/grant must permit the intended client
to reach the Pi endpoint (normally TCP 443 when using Serve HTTPS).

Use the narrowest practical policy rather than an allow-all rule. See
[tailscale.md](tailscale.md).
