# Reeder Lessons

Reeder exposes multiple viewing surfaces: feed viewer, reader view, and in-app
browser. Public docs do not name its internal parser engines, but the product
shape is enough to guide this skill.

Map those surfaces to portable RSS processing:

- Feed viewer: use the feed payload first.
- Reader view: fetch the item URL and run article extraction.
- In-app browser: a host-rendered page can show content static extraction misses,
  but it is not automatically clean article text.

Do not implement an RSS reader UI or sync service inside this skill. The useful
portable capability is source intake, feed processing, full-text provenance, and
validated feed-content packs.
