# Mission workflow guidance (shared)

This is the single source of truth for the `## Mission Workflow` section of
`AGENTS.md`, the guidance that tells anyone working in the project where missions live
and how each is named and finished. `init-mission-base-workflow` writes it into a project
whose `AGENTS.md` lacks it or holds the older `## Milestone Workflow` section in its place,
and states which of the cases below it writes, and this file states what the section is and how
each case writes it.

## The section

The section is this heading and paragraph, exactly:

```markdown
## Mission Workflow

This project uses the mission-driven workflow. Each mission lives at
`<scope>/mission_<slug>/`, directly in the directory holding the core of its work, with
`requirements.md`, `open_questions.xml`, and `TASKS_TODO.md`. No mission is current: every
skill working inside one is given its path as `--mission <path>`, exactly as
`/define-mission-goal` printed it, trailing slash included.
A mission directory is removed only by `/finish-mission`, whose `Mission-finish: <path>`
commit carries the mission's record, so the directories standing are the live missions and
the git log holds the finished ones.
```

Never write a mission path into it, and never document the project's environment context in
it.

## Writing it

- **`AGENTS.md` does not exist** — create it with this minimal content, the section
  last:

  ```markdown
  # AGENTS.md

  This file provides guidance to the coding agent working in this repository.

  <the section>
  ```

- **`AGENTS.md` exists and holds neither a `## Mission Workflow` nor a
  `## Milestone Workflow` section** — append the section to the end of the file, leaving every
  existing line untouched.
- **`AGENTS.md` holds a `## Milestone Workflow` section and no `## Mission Workflow`
  one** — the older section an earlier copy of the plugin wrote: `init-mission-base-workflow`
  replaces it whole, from its heading line down to the line before the next `# ` or `## `
  heading, or to the end of the file when none follows, with the section, leaving every line
  outside it untouched.
