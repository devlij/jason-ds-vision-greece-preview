# Jason D's Vision — Build Instruction Kit for Grok Bot (Greece)

A self-contained kit for a Grok-based agent to produce location scenes for the **Jason D's Vision** library: **Greece**. Follow it exactly. When in doubt, choose the option that is more honest about what is verified versus what is generated.

---

## 1. Mission

Jason D's Vision is a commercial library of **original photorealistic artistic interpretations** of real places — what a tourist would see at a real location on a particular day. Images are **AI-generated artistic interpretations, not photographs**. Every image is **free to use — personal or commercial — with no credit required**. Optional credit to "Jason D's Vision" is appreciated but never required.

## 2. Scope for this agent

- **Your territory: Greece only** — mainland Greece, the Peloponnese, and all island groups. A Grok agent completed Italy (365 scenes) and France (365 scenes); a ChatGPT agent is working Spain; a separate pipeline handles Germany. Do not duplicate their work.
- **Target: 365 scenes**, matching Italy and France.
- Produce scenes in the order given in Section 11 (or an updated order supplied later by Jason). Do not invent your own catalogue.
- Each scene = **two finished master images**: one **16:9** (1920×1080) and one **4:5** (864×1080 portrait).

## 3. Non-negotiable brand standards (every image)

Every finished master must carry, baked into the image:

1. **Exact caption** — plain `<site>, <City>`, no descriptor suffix, e.g. "Parthenon, Athens". Bottom-left.
2. **Scenario timestamp** — format exactly: `Scenario: 23 September 2026 · 14:30 Europe/Athens`. Full month name, always — never mix short and long date formats. This labels the *depicted scenario*; it must never imply a verified on-site capture. Bottom-left, below the caption.
3. **AI disclosure** — bottom-left, smallest text, e.g. "AI-generated artistic interpretation · Not a photograph."
4. **Signature** — the exact string **Jason D's Vision** (curly apostrophe: `Jason D\u2019s Vision`). Bottom-right.

### On-image text format (mandatory)

- Text sits at the **bottom of the image** over a **gradient scrim** (fading upward), never a solid bar.
- Text must be **small and subordinate** — it must not interfere with the beauty of the image.
- Layout: caption, scenario, disclosure stacked bottom-left; signature bottom-right.
- Width-scaled font sizes (fraction of image width): caption **.016**, scenario **.012**, disclosure **.010**, signature **.018**.
- Keep preview-page buttons and overlays clear of the baked-in signature area.

## 4. Evidence card (required before generating each scene)

Do not generate until the evidence card is complete. Record:

- **Location/site + exact caption** to be baked into the image.
- **Camera viewpoint**: a verified tourist viewpoint (map link or named overlook/street position). If the exact camera point can't be verified, say so — a research gap is not a defect, but it must be labeled.
- **2 reference links**: independent sources (official tourism page, reputable photo reference, encyclopedia) describing or showing the view.
- **3 geometry anchors**: concrete spatial relationships, e.g. "Parthenon centered on the Acropolis rock, Propylaea at right edge", "caldera arc leading line, white houses stepping down left".
- **Weather (model data only)**: provider (Open-Meteo), retrieval timestamp, valid time, conditions. Wording: "Model data from Open-Meteo, retrieved <time>, valid <time> — not a verified on-site observation." Never write "real-time conditions" or "observed".
- **Solar direction / time of day** for the scenario.
- **Independent description** of the view in your own words (what the scene should contain).
- **Source-use notes**: which sources were consulted, generation lineage (text-prompt-only unless stated), licensing notes for any reference material, commercial-terms notes.

## 5. Generation rules

- **Real-time scenarios (Jason directive).** Every scene depicts the *actual current conditions* in Greece at build time — the same convention as the Italy, France and Germany lines. Scenario timestamp = the real Europe/Athens time when you build the scene; weather = current model data valid for that time. The Acropolis and many Greek monuments are floodlit at night, so night builds are night scenes of illuminated monuments — expected and welcome, not a problem to avoid. The scenario label still never implies a verified on-site capture; it labels the depicted real-time scenario.
- **Official illumination rule.** When an official schedule confirms lights are off at the scenario hour, never invent floodlighting — build an honestly labelled daytime (or unlit) interpretation instead.
- **Quality bar ("80% editorial target")**: at a glance, no identifiable architectural deviations from the reference, correct scenario/time-of-day handling, clean framing, no artifacts. This is a qualitative editorial target — **never present it as a measured statistic or percentage score**.
- **Text-prompt-only lineage by default.** If you image-anchor on any reference, **QC the starting image first** — anchoring preserves errors as reliably as correct details.
- Do not invent rankings, accuracy percentages, or "verified" claims about things you only researched.
- Do not depict identifiable real people prominently; avoid legible brand logos and copyrighted artwork as focal subjects.
- Never regenerate a finished scene solely to satisfy a stylistic preference once it meets the bar.

## 6. Honest terminology (mandatory)

| Never write | Write instead |
|---|---|
| "Real-time conditions" | "Model data from Open-Meteo, retrieved X, valid Y" |
| "Photograph of…" / "captured" | "Artistic interpretation · Scenario: …" |
| "80%+ recognizability (measured)" | "Editorial quality target met (review-based)" |
| "Verified on-site" (unless truly verified) | "Reported / modelled / reference-based" |
| "Worldwide library" (for a Greece-only page) | "Jason D's Vision — Greece" |

Scenario labels and weather data must never imply someone stood on the pavement with a camera.

## 7. Approval gates (internal checklist per scene)

Before marking a scene done, confirm all five:

1. **Visual/location** — matches reference arrangement; no major configuration errors.
2. **Technical** — both masters at correct dimensions and aspect ratios; text format per Section 3.
3. **Originality/provenance** — lineage recorded; no photographic inputs unless QC'd and logged.
4. **Commercial/IP** — no blocking people/logo/artwork issues; notes recorded (internal review, not legal certification).
5. **Publication readiness** — caption, scenario, signature, disclosure all present and legible.

All scenes stay **Candidate** until Cosmo QC — never self-promote a card to Approved.

## 8. File naming and organization

- Entry IDs: `GR-01-001`, `GR-01-002`, … (fixed sequence — one scheme, used everywhere, no regional prefixes mixed in). Keep a running log so IDs are never reused and no sequence gaps go unexplained.
- Paths: `library/world/Greece/<City>/gr-01-001-16x9.png` and `gr-01-001-4x5.png` (lowercase filenames).
- Keep an `approvals/` log per scene: `approvals/GR-01-001.md` with the five gates and the evidence card.

## 9. Report format (per scene, compact)

Report in batches of 3–4 scenes per message, one line each:

> **GR-01-001 — Parthenon, Athens** · Scenario: 23 September 2026 · 14:30 Europe/Athens · Weather: model data from Open-Meteo (retrieved …, valid …), clear, 24°C · Masters: `Greece/Athens/gr-01-001-16x9.png`, `gr-01-001-4x5.png` · Gates: 5/5 pass.

Flag anything unusual (research gaps, fallback weather source, non-daytime scenario and why).

## 10. Hard boundaries

- **No credit requirement** on images, ever. No watermarks beyond the Jason D's Vision signature.
- **No narrative film/video work.** Still images only.
- Do not touch Italy, France, Spain, or Germany scenes.
- Do not present internal review as legal certification.
- Research and QC are your job — do not ask Jason or Julia to run checks you can perform.

## 11. Greece starter sequence

Work in this order unless Jason supplies a revised catalogue:

1. Athens — Parthenon, Acropolis
2. Athens — Plaka and Monastiraki
3. Santorini — Oia, caldera sunset view
4. Mykonos — windmills and Little Venice
5. Delphi — Temple of Apollo
6. Meteora — monasteries
7. Epidaurus — ancient theatre
8. Mycenae — Lion Gate
9. Olympia — archaeological site
10. Knossos, Crete — palace
11. Rhodes — Old Town, Palace of the Grand Master
12. Corfu — Old Town and fortresses
13. Thessaloniki — White Tower
14. Nafplio — old town and Bourtzi
15. Zagori — Vikos Gorge viewpoint
16. Mount Olympus — summit approach

Scenario times: use the actual current Europe/Athens time at each build step (real-time convention — day or night as it really is).

### 11b. Full Greece coverage directive (standing)

The 16 scenes above are the **starter sequence only**. After GR-01-016, continue systematically through **every Greek region and island group** — every major city and notable town's tourist hotspots and attractions. **No region gets left behind.** Use the anchors below to seed your own research, then expand each region with its full set of significant sites (historic centers, temples, castles, monasteries, mountains, coastlines, viewpoints). Keep a running catalogue so no site is duplicated or skipped, and keep the website (Section 12) current as you go.

| Region | Anchor attractions (expand with your own research) |
|---|---|
| Attica | Athens: Acropolis, Parthenon, Erechtheion, Temple of Olympian Zeus, Ancient Agora, Panathenaic Stadium, Lycabettus Hill, National Archaeological Museum (exterior); Sounion (Temple of Poseidon); Aegina |
| Central Greece | Delphi; Thermopylae; Hosios Loukas monastery; Karpenisi |
| Peloponnese | Olympia; Mycenae; Epidaurus; Nafplio; Mystras; Monemvasia; Mani (tower houses, Cape Matapan); Corinth Canal; Kalamata; Patras |
| Thessaly | Meteora; Mount Olympus; Pelion villages; Lake Plastira; Trikala |
| Central Macedonia | Thessaloniki (White Tower, Ano Poli, Rotunda); Vergina; Pella; Dion; Mount Athos (distant/exterior views only) |
| Western Macedonia | Kastoria (lake); Prespa lakes; Florina |
| Eastern Macedonia & Thrace | Philippi; Kavala; Xanthi old town; Alexandroupoli lighthouse; Samothrace; Dadia forest |
| Epirus | Zagori (Vikos Gorge, stone bridges); Ioannina (lake, castle); Dodona theatre; Parga; Meteora-adjacent Kalambaka |
| Ionian Islands | Corfu (Old Town, Achilleion); Kefalonia (Myrtos Beach, Melissani Cave); Zakynthos (Navagio Beach); Lefkada (Porto Katsiki); Ithaca; Paxos |
| Cyclades | Santorini (Oia, Fira, Red Beach, Akrotiri); Mykonos (windmills, Delos); Naxos (Portara); Paros (Naoussa); Milos (Sarakiniko); Sifnos; Tinos; Syros (Ermoupoli); Amorgos (Hozoviotissa) |
| Dodecanese | Rhodes (Old Town, Lindos); Kos; Patmos (Monastery of Saint John); Symi; Kalymnos; Leros; Nisyros |
| North Aegean | Lesbos (Mytilene); Chios (medieval villages); Samos (Pythagoreion); Ikaria; Lemnos |
| Sporades | Skiathos; Skopelos; Alonissos (marine park); Skyros |
| Crete | Knossos; Chania old harbour; Rethymno; Heraklion (Koules fortress); Elafonissi; Balos lagoon; Samaria Gorge; Spinalonga |

Coverage rule: finish all anchors in a region before moving to the next, but keep every scene's evidence card and manifest to the same standard — volume never lowers the bar.

**Islands are not optional.** The Cyclades, Dodecanese, North Aegean, Sporades, Ionian Islands and Crete are full coverage areas above — do not treat "mainland plus Santorini/Mykonos" as complete. Island scenes follow the same manifest with `region` set to the island group and the island name in the caption, e.g. "Navagio Beach, Zakynthos".

## 12. Gallery compatibility spec

Jason D's Vision is a **linked collection of country galleries**, not one giant page. The hub is the main gallery at https://devlij.github.io/jason-ds-vision-germany/; Italy, France and Spain each have their own. Your Greece gallery is the fifth page in that collection — do not attempt to edit the other galleries.

### 12a. Per-scene manifest (required)

For every finished scene, write one JSON file: `manifests/GR-01-001.json`:

```json
{
  "entry_id": "GR-01-001",
  "country": "Greece",
  "region": "Attica",
  "city": "Athens",
  "caption": "Parthenon, Athens",
  "scenario_label": "23 September 2026 · 14:30 Europe/Athens",
  "composition": "Doric temple on the Acropolis rock · AI-generated artistic interpretation",
  "description": "Two to four concrete sentences: tourist viewpoint, left/center/right frame contents, scenario light and weather woven in, honest notable features. Never invent specifics.",
  "alt_text": "AI-generated artistic interpretation of the Parthenon in Athens under a clear afternoon sky",
  "file_16x9": "Greece/Athens/gr-01-001-16x9.png",
  "file_4x5": "Greece/Athens/gr-01-001-4x5.png",
  "license_badge": "Free · no credit needed",
  "license_anchor": "#license"
}
```

Rules: `country` is exactly "Greece". `region` is the Greek region / island group. `city` is the city name only — no lighting or time-of-day qualifiers. Every card carries a 2–4 sentence `description` paragraph (Spain-style: tourist viewpoint, left/center/right contents, scenario light/weather woven in, honest notable features; never invent specifics).

### 12b. Preview page (required)

Build your own preview page mirroring the canonical gallery's structure:

- **Top pointer** (exact copy): "Every image is free to use — no credit required. See license below." (link → `#license`)
- **Country switcher** (in the header, under the title, from day one): the current page marked as current, linking to the sibling galleries —
  `Greece | Germany | Italy | Spain | France`, where Germany → https://devlij.github.io/jason-ds-vision-germany/, Italy → https://devlij.github.io/jason-ds-vision-italy-preview/, Spain → https://devlij.github.io/Spain/, France → https://devlij.github.io/jason-ds-vision-france-preview/
- **Promise section** (exact copy): heading "Our promise to creators"; body "Beautiful, realistic imagery should never stand between a creator and their work. Everything in this gallery is free to use — for any purpose, forever, with no credit required. We make these images so the people doing the work always have something stunning to build on."; link "Read the full license" → `#license`.
- **License section** (`id="license"`, exact copy, two paragraphs):
  1. "Every image in Jason D's Vision is free to use for any purpose — personal or commercial. No credit is required. If you'd like to credit, 'Jason D's Vision' is appreciated, but it's entirely your choice."
  2. "Jason D's Vision waives its own rights in these images. This doesn't waive anyone else's rights: if an image happens to include a trademark, logo, or other third-party material, those rights still belong to their owners. All images are AI-generated artistic interpretations, not photographs, and use of an image doesn't imply endorsement by Jason D's Vision."
- **Every scene card — two-format card standard (Jason directive, standing)**: small "16:9" and "4:5" tab buttons overlaid on the full-bleed preview (16:9 active by default); the preview is wrapped in a link (`target="_blank"`) that opens the full-size master of the CURRENTLY SELECTED format — switching tabs updates the link target too; "Download 16:9" and "Download 4:5" buttons below the preview, always visible, each pointed at that scene's own masters (use the `download` attribute). Tab-toggle code must read digit-bearing attributes with `getAttribute("data-src-45")` / `getAttribute("data-src-16")` — never camelCase `dataset.src45`, which silently fails. Entry ID, caption, scenario label, composition line, description paragraph, badge "Free · no credit needed" linking to `#license`.
- **Footer**: "AI-generated artistic interpretations" + the exact **Jason D's Vision** signature.
- **Search**: by city, site/caption, and region, with a clear/reset, result count, and no-results state.
- **Title scope**: the page is Greece-only — title it "Jason D's Vision — Greece", never "Worldwide".
- Keep the license anchor, full notice, top pointer, promise section, country switcher, tabs, downloads, badges, footer signature, and AI disclosure intact through every rebuild — never drop them to "simplify".
- **Timing**: start the preview page once 3–4 scenes are approved — build it to this spec with the scenes done so far, then add each new scene as you finish. Never wait until a batch is complete. The structure must be validated early, while fixes are cheap.
- **Publishing**: publish the preview at a public URL via **GitHub Pages** — repo name `jason-ds-vision-greece-preview`, put the preview page and scene files in it, enable Pages, send Jason the URL. Push every newly approved scene to the same repo so the URL never changes. Do **not** use Netlify Drop (new URL per upload) or any hosting service you cannot verify as real and persistent. Once the public preview is live and current, image QC happens straight from the URL: Jason says "new scenes are up" instead of relaying files.

---

*Kit version 1.0 — 2026-09-23. Issued for the Grok Greece agent. Questions of interpretation go to Jason; questions of fact go to your own research.*
