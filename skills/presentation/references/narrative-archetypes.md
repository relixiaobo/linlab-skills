# Narrative Archetypes

An archetype controls the deck's argument sequence. It is not a theme and does
not prescribe colors, typography, or fixed slide templates. Select one
archetype before choosing the core layout set, then adapt its sequence to the
real audience and evidence.

The executable catalog is `assets/archetypes/index.json`. Run
`node scripts/studio_tool.mjs archetypes` to inspect it or initialize a project
with `--archetype <id>`.

## Included Archetypes

| Archetype | Best for | Default rhythm |
| --- | --- | --- |
| `research-report` | Industry, policy, strategy, and technical research | Question -> context -> evidence -> synthesis -> implication |
| `investment-case` | M&A, asset review, capital allocation, board decision | Thesis -> asset -> value -> downside -> decision |
| `product-launch` | Product reveal, new capability, press or all-hands | Tension -> reveal -> use -> proof -> adoption |
| `sales-proposal` | Enterprise sales, advisory, solution, partnership | Client change -> diagnosis -> future state -> proof -> decision |
| `learning-workshop` | Training, course, onboarding, workshop | Orient -> model -> explain -> example -> practice -> transfer |
| `operating-review` | Weekly review, QBR, portfolio or program status | Headline -> scorecard -> variance -> blockers -> commitments |
| `conference-talk` | Keynote, thought leadership, founder or technical talk | Tension -> old model -> idea -> proof -> takeaways |

## Selection Rules

- Select from the audience decision and use setting, not from the topic name
  alone. The same AI subject may be a product launch, an investment case, or a
  learning workshop.
- Treat the catalog sequence as a reasoning prior. Remove, repeat, or reorder a
  phase when the evidence demands it.
- Do not fill a fixed page count mechanically. Assign slide jobs first, then
  choose layouts from `references/layout-library.md`.
- Keep one dominant archetype. A section may borrow a local move from another
  archetype, but the deck should not switch argument logic every few slides.
- Record material deviations in the Studio brief so the final sequence remains
  intentional rather than accidental.

## Prototype Implications

Use the selected archetype's `prototypeRoles` to choose risk frames. A research
report needs a dense evidence prototype; a launch needs a real product or media
prototype; a workshop needs an explanation and practice frame. Opening and
closing frames alone cannot certify the system.
