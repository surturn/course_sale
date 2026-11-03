# UI conventions

The visual rules the storefront follows. All styling is plain CSS in `frontend/src/styles.css` (tokens at the top, the "Design pass" block near the end). There is no CSS framework.

## Principles

- **Flat and quiet.** Surfaces are separated by a step in tone, not by lines or shadows. White rows sit on a grey page with a sliver of page showing between them.
- **Nothing decorative.** No glass or blur, no gradients, no glows. The one exception is the yellow highlighter swipe behind page headings (`.hl`), which is the brand's mark.
- **Shadow only on what floats.** The disclaimer dialog is the only element with a shadow.
- **One accent.** Navy ink, one yellow highlight, and tinted greys for controls. Dark mode keeps the same roles.
- **Round controls.** Buttons, chips and the search box are fully round. Lists and boxes use 14px corners. Form fields keep an outline, because people need to see where to type.
- **Real content over ornament.** Covers are real uploads or generated geometry, never stock art, emoji or icon-in-a-square cards.

## Measurable rules

Checked in the browser at 390x844 and 1440x900, in light and dark:

| Rule | Value |
|---|---|
| Body and secondary text contrast | at least 4.5:1 (secondary grey is `--ink-soft`, `#59627a` on light) |
| Tap targets | at least 44px tall (chips, buttons, links in the header) |
| Headlines on the free and news pages | two lines or fewer at every width |
| Sideways page scroll | none. A flex or grid child that must scroll needs `min-width: 0` or `minmax(0, 1fr)` on its parent. |
| Resting shadows and `backdrop-filter` | none, apart from the dialog |
| Text sizes | a handful: large display, headings, body, small |

## Typography

One family, Schibsted Grotesk (variable, self-hosted through `@fontsource-variable`). Display text is tight (`letter-spacing` about -0.03em), small text slightly open (+0.005em). Headings use `text-wrap: balance`, paragraphs `text-wrap: pretty`. Numbers in prices are not set in tabular figures because the comma spaces badly.

## Components

| Component | Notes |
|---|---|
| `ChipRow` | One horizontally scrollable row of filter chips. Swipe on touch; arrow buttons on mouse devices; the selected chip scrolls into view. |
| `Cover` | Shows the uploaded cover if there is one, otherwise a generated geometric cover (see below). Decorative, so hidden from screen readers. |
| `Disclaimer` | `DisclaimerGate` holds back a page and its data until accepted. `DisclaimerNote` reopens the text. Uses the native `<dialog>`. |
| `StoreCta` | Paid-catalog block under the free pages. |
| `ListSkeleton` | Loading placeholder with the same shape as the rows. |

## Motion

- Press feedback is instant (`:active`, `scale(0.97)` on buttons and chips).
- Hover effects apply only on devices with a real pointer (`@media (hover: hover) and (pointer: fine)`).
- The dialog fades in with a small scale (never from nothing), 200ms, ease-out. Closing is instant.
- List rows settle in with a short stagger on first load.
- Everything respects `prefers-reduced-motion`.

## Covers

- **Generated.** `Cover.jsx` draws a deterministic cover from the title: four compositions with mirroring and colour swaps, palette by type (PDF navy, book yellow, course pale). The same title always gets the same cover.
- **Uploaded.** Admins add a cover in Manage. See the README for limits. An uploaded cover wins; if it is missing or fails to load, the generated one shows.

## Not covered yet

The PDF reader and the admin pages share the global colours and corner radii but were not redesigned or re-checked in the latest design pass.
