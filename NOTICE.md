# Pi Maps notices

PROJECT LICENCE: AGPL-3.0-only

Pi Maps project-authored code is licensed under the GNU Affero General Public
License version 3.0, only. Third-party components are not relicensed by the
project licence; their individual upstream licences and notices remain
authoritative.

THIRD-PARTY COMPONENTS:

- OpenStreetMap data: OpenStreetMap contributors; ODbL applies to the data.
- Protomaps PMTiles reference library: BSD 3-Clause; see `scripts/LICENSE`
  and the vendored `web/pmtiles.js` bundle.
- MapLibre GL JS/CSS: v6.11.2, BSD 3-Clause; see
  `LICENSES/MAPLIBRE-BSD-3-CLAUSE.txt` and the vendored bundle/header.
- Noto fonts: SIL Open Font License 1.1; see `web/assets/fonts/OFL.txt`.
- BRouter: MIT License; see `LICENSES/BROUTER-MIT.txt`. Routing data is
  generated from OpenStreetMap data.
- Kiwix and Wikipedia/ZIM content: follow the applicable Kiwix, Wikimedia,
  Wikipedia and ZIM licensing/attribution requirements.
- nginx, Python, osmium-tool and container images remain external dependencies
  under their respective upstream licences.

This release candidate does not redistribute OSM extracts, PMTiles data,
BRouter segments, ZIM files, or container images; those are acquired at
deployment time under `docs/updating.md`.
