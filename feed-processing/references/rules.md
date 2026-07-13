# Rules

Rules are used to filter, score, or route items after parsing and windowing.
Every selected or rejected item should carry a short reason.

Useful rule categories:

- include and exclude keywords;
- required and blocked domains;
- source, folder, and tag selectors;
- author and category selectors;
- date window and cadence;
- media or enclosure filters;
- minimum and maximum content length;
- language, if a dependency is available;
- scoring weights and tie-breakers.

Natural-language rules are acceptable for one-off runs. Use JSON/YAML rule files
when the rule should be repeatable or audited.
