# Jason D’s Vision — Greece

Preview gallery of original photorealistic AI artistic interpretations of real places in Greece. Every image is free to use for any purpose, with no credit required. Scenes are labelled **Candidate** until an independent QC pass. Nothing on this page is marked Approved.

Live page: https://devlij.github.io/jason-ds-vision-greece-preview/

Country switcher: Greece, [Germany](https://devlij.github.io/jason-ds-vision-germany/), [Italy](https://devlij.github.io/jason-ds-vision-italy-preview/), [Spain](https://devlij.github.io/Spain/), [France](https://devlij.github.io/jason-ds-vision-france-preview/).

## This build

- **GR-01-001 through GR-01-365**, with no gaps. There is no GR-01-366.
- Each scene has a 1920×1080 master and an 864×1080 master under `library/world/Greece/<City>/`.
- Latest scenario label: 24 September 2026 · 12:58 Europe/Athens (closing batch GR-01-353 through GR-01-365).
- Weather for that batch is Open-Meteo model data retrieved 2026-09-24T09:52Z, valid 2026-09-24T12:45 Europe/Athens. The scenario label is the build time, 12:58 Europe/Athens. It is not a verified on-site observation.
- Earlier batch GR-01-337 through GR-01-352 remains labelled 24 September 2026 · 12:45 Europe/Athens.
- GR-01-355 is Paleochora on Aegina, not the Cretan waterfront. GR-01-356 is Faneromeni Monastery on Salamina, not the Paloukia ferry. GR-01-358 is the boat approach to Chrissi. GR-01-360 is Kalamiotissa on Anafi, not Anafiotika in Athens. GR-01-362 is Kioni, not Vathy. GR-01-364 is the main avenue at Dion, not the Sanctuary of Isis. GR-01-365 is the Presidential Mansion, not the Academy, the Zappeion, or the National Archaeological Museum.
- GR-01-350 is the Corycian Cave approach. The closed Parnassus chairlift remains GR-01-041. Zea Marina is the circular harbor also called Pasalimani, not Mikrolimano. Petra Bay is the Lesbos village, not Skala Loutron.
- Evidence cards are in `approvals/`. Manifests are in `manifests/`. The build kit is `docs/kit-greece-v1.0.md`.

## Run locally

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```
