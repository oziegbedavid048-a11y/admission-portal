# Hyperframes Composition Brief: Apply Gabstep

## Objective
Create a short, premium vertical launch video for Apply Gabstep.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: vertical — 1080x1920, 30fps
- Duration: 23.8s

## Source Material
- Project root: this repository
- Primary files read: frontend/src/features/landing/LandingPage.jsx, HeroCarousel.jsx,
  styles/tokens.css, styles/home.css, features/applicant/AdmissionCelebrationModal.jsx,
  backend/apps/applications/constants.py (DEFAULT_STAGES), backend catalog data,
  backend/apps/accounts/emails.py (welcome copy)
- Product name: Apply Gabstep
- Tagline / strongest claim: "Begin your global education journey"
- Key UI moments to recreate: course card, document checklist, stage tracker,
  admission celebration card with confetti
- Copy that must appear verbatim:
  - Begin your global education journey
  - Fifteen years of opening doors abroad.
  - Paris Business Academy (PBA) · Paris, France · Bachelor's in Web Marketing · 3 Years ·
    €7,500/yr · September / October & January
  - Passport · Transcripts · CV
  - Pay the fee in your own currency.
  - Submitted & payment confirmed · Document verification · Institution review ·
    Offer letter decision · Visa guidance & enrolment
  - Offer of admission · Congratulations
  - Apply in four simple steps.
  - Start your application · apply.gabstep.com
  - Earn with every student you place.

## Creative Direction
- Tone preset: polished (with cinematic touches)
- Creative direction: premium study-abroad launch film
- Angle: see brag-plan.md
- Hook: graduates photo + the hero line
- Outro: lockup + "Start your application" + apply.gabstep.com
- Avoid: generic SaaS language, abstract filler, any invented claims or figures

## Visual Identity
- Background white #ffffff with a faint dotted grid, soft mint glow (#9fd8b8 / #e1f6dd)
  that breathes with the music, and thin green outline rings
- The product journey plays inside a phone mockup (dark bezel #0e1513, cream screen
  #fbf7ef) that rises in, tilts gently, and swipes between screens with tap indicators
- Product cards #ffffff on #fbf7ef, ink #08211b / #54665f, action #0b5c43
- Leaf mark #65e005 / #107b00 (traced vector, exact proportions)
- Font: Montserrat (bundled)
- All layout inside safe margins (80px sides); nothing may overflow or collide

## Storyboard
Use brag-plan.md as the contract. Scenes: Hook 0–2.8 · Reveal 2.8–5.2 · Pick a course
5.2–9.4 · Upload and pay 9.4–13.0 · Track to the offer 13.0–20.2 · Outro 20.2–23.8.

## Audio
- Music: assets/music/happy-beats-business-moves-vol-12-by-ende-dot-app.mp3 at ~0.32,
  fade out last 1.5s
- Cue guidance: bundled preset; lock the celebration near 17.47s and the outro near 18.56s
- Audio-reactive: subtle background glow breathing from extracted bands
- SFX: sparse and motion-matched (soft impact on hook, soft drop on lockup, mouse clicks on
  taps, drop on first/last document tick, bell on the offer letter)
- SFX analysis guidance: brag/assets/sfx/sfx-analysis.md; prefer low high-frequency risk

## Hyperframes Instructions
Follow hyperframes-core / -animation / -creative / -cli conventions (single paused GSAP
timeline, seek-safe, deterministic, clips via data-start/data-duration, ids on audio).
Run `npx hyperframes check` before render; render locally.
