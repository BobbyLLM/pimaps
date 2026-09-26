# Private HTTPS with Tailscale

Tailscale is optional. Pi Maps works over ordinary LAN HTTP without it.

It becomes useful for two reasons:

1. private access when you are away from home; and
2. HTTPS, which browsers normally require for geolocation/GPS APIs outside
   localhost.

The intended pattern is:

```text
browser on authorised tailnet device
             |
             | HTTPS :443
             v
       Tailscale Serve
             |
             | local proxy
             v
       Pi Maps :8090
```

**Tailscale Funnel is not required. Keep it off for a private deployment.**

## Configure Serve, not Pi Maps, for HTTPS

Pi Maps itself remains an HTTP service on the host. Tailscale Serve provides
the private HTTPS endpoint and forwards to the local Pi Maps listener.

Tailscale's CLI syntax changes over time, so use the Serve command appropriate
to the Tailscale version installed on your host. The important result is that
the private HTTPS endpoint proxies to the Pi Maps HTTP port rather than opening
a public Funnel.

Pi Maps uses app-relative URLs for search, routing and Wikipedia requests, so it
can work either at the host root or behind a private path prefix when the proxy
is configured consistently.

## Tailnet policy still matters

Serve being configured does not grant access by itself.

The tailnet policy must allow the intended client/device class to reach the Pi's
Tailscale endpoint on TCP 443. Prefer a narrow client-to-service grant rather
than broad tailnet access.

A useful failure signature is:

```text
no rules matched
```

in `tailscaled` logs for the inbound connection. If the peer is online but the
browser cannot connect, check the ACL/grant before changing Pi Maps.

## Prove remote access from a genuinely remote path

Testing while the phone or laptop is still on the home Wi-Fi can hide routing
mistakes.

A better field test is:

1. disable Wi-Fi on the client;
2. leave Tailscale connected;
3. open the private HTTPS Pi Maps URL;
4. load the map and perform a local search;
5. request a route;
6. test the browser geolocation control if you intend to use GPS.

That proves the path you actually care about.

## GPS and secure contexts

The frontend uses the browser's geolocation API. Whether a device will expose
that API depends on browser/platform rules and user permission, but normal
browsers require a secure context.

Consequently:

- LAN `http://...:8090` can render maps/search/routes but may not be allowed to
  use geolocation;
- the private Tailscale HTTPS endpoint provides the secure context needed for a
  normal remote GPS test.

If the map works but GPS does not, do not immediately blame routing or search.
Check the browser permission and secure-context status first.

## Troubleshooting order

When remote HTTPS fails, separate the layers:

```text
Is Pi Maps healthy locally?
        |
        v
Does Tailscale Serve proxy the local port?
        |
        v
Does tailnet policy allow this client -> Pi:443?
        |
        v
Does the browser trust/accept the private HTTPS endpoint?
```

That order avoids "fixing" the application when the actual problem is the
network policy.
