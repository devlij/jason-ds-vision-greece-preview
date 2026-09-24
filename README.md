# Jason D’s Vision — Greece

Preview gallery of original photorealistic AI artistic interpretations of real places in Greece. Every image is free to use for any purpose, with no credit required. Scenes are labelled **Candidate** until an independent QC pass. Nothing on this page is marked Approved.

Live page: https://devlij.github.io/jason-ds-vision-greece-preview/

Country switcher: Greece, [Germany](https://devlij.github.io/jason-ds-vision-germany/), [Italy](https://devlij.github.io/jason-ds-vision-italy-preview/), [Spain](https://devlij.github.io/Spain/), [France](https://devlij.github.io/jason-ds-vision-france-preview/).

## This build

- **GR-01-001 through GR-01-336**, with no gaps.
- Each scene has a 1920×1080 master and an 864×1080 master under `library/world/Greece/<City>/`.
- Latest scenario label: 24 September 2026 · 12:15 Europe/Athens (Crete, Dodecanese, Cyclades, Ionian Islands, Attica, Central Macedonia, and Eastern Macedonia and Thrace, GR-01-321 through GR-01-336).
- Weather for that batch is Open-Meteo model data retrieved 2026-09-24T09:05Z, valid 2026-09-24T12:00 Europe/Athens. The scenario label is the build time, 12:15 Europe/Athens. It is not a verified on-site observation.
- Earlier batch GR-01-305 through GR-01-320 remains labelled 24 September 2026 · 11:45 Europe/Athens.
- Evidence cards are in `approvals/`. Manifests are in `manifests/`. The build kit is `docs/kit-greece-v1.0.md`.

## Run locally

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```
