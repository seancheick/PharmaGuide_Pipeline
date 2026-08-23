# Device verification — 2026-08-22

iPhone 16 Pro (iOS 18.5) simulator, `Runner.app` built from the Flutter branch
HEAD at the time of capture, running against the **currently shipped** bundled
catalog. No candidate bundle was imported.

- `device_product_detail_light.png`
- `device_product_detail_dark.png`

Thorne FloraSport 20B (a probiotic product), reached by search → product detail.
The app builds, launches, imports its bundled catalog, searches, navigates and
renders the changed screen's host correctly in both appearances.

## What these do not show, and why

The probiotic research card itself does not render here. Detail blobs are not
bundled with the app — they are fetched from the production blob store — so this
simulator shows the product's header and the honest
"Personalized checks are incomplete" banner instead of the deep-dive sections.
Making the card appear on device would require either importing the candidate
bundle or fetching production blobs, and both are outside the boundary for this
candidate.

The card is covered instead by golden images at
`test/features/product_detail/v2/sections/goldens/` in the Flutter repo, in the
same two appearances, with the clinician-review gate exercised in both
directions: a reviewed strain states its research, an unreviewed formula-level
match does not.
