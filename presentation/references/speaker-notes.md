# Speaker Notes And Presenter Mode

Use this when the deck is for a live talk, lesson, roadshow, demo day, training,
or any user request mentioning speaker notes, script, presenter view, teleprompter,
talk track, rehearsal, timing, or "I need to present this".

## Density And Timing

- Live talks: one idea per slide, fewer words, stronger section rhythm, larger
  type, and more slides when needed.
- Reading decks: more self-contained detail is acceptable, but preserve strong
  scanning hierarchy.
- Estimate pacing from the venue:
  - 15 minutes: about 6-10 content slides
  - 30 minutes: about 10-16 content slides
  - 45 minutes: about 14-22 content slides
  - 60 minutes: about 18-28 content slides

Split a dense slide instead of shrinking text below comfortable reading size.

## Notes Writing

Speaker notes are prompts for the presenter, not a formal essay.

- write in natural spoken language matching the user's language
- keep most slide notes around 120-250 words unless the user asks for verbatim
  script
- bold or otherwise mark key phrases when the output format supports it
- put transition lines in their own paragraph so the presenter can glance at
  them
- keep presenter-only reminders out of visible slide content
- end each note with a bridge to the next slide when the talk needs flow

For HTML decks, put notes inside hidden slide-local markup:

```html
<aside class="notes">
  <p>Opening cue with <strong>the key phrase</strong>.</p>
  <p>Short explanation in spoken language.</p>
  <p>Transition to the next slide.</p>
</aside>
```

For PPTX, use native slide notes whenever the library/tool supports them.

## Presenter Mode For HTML

When building an HTML deck for a live talk, include at least:

- keyboard navigation: arrows, space, Home, End
- visible progress outside the slide safe area
- fullscreen-friendly stage scaling
- hidden speaker notes per slide
- a presenter view or notes drawer when feasible
- timer support when the user mentions rehearsal or talk length

Presenter controls must not appear inside the audience-facing slide canvas.

## QA

Before delivery:

- navigate through every slide with the keyboard
- verify notes are hidden from the audience view
- verify notes exist on slides that need a talk track
- check that slide text and notes do not contradict each other
- rehearse the first two slide transitions mentally; if the bridge feels abrupt,
  rewrite the notes or add a section reset
