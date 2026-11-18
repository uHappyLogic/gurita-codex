# Resolve Mission (shared snippet)

This is the single source of truth for resolving `<MISSION_DIR>`. It takes one input, the
required `--mission <path>` at the start of the skill's invocation text, naming the
mission by its repo-relative path exactly as the definition tool printed it, trailing slash
included, e.g. `mission_user-guide/`. Nothing stored and nothing computed picks a
mission: no pointer is read, and there is no default.

## Recognizing the flag

The flag is present only when the first whitespace-separated token of the invocation text is
exactly `--mission`. Its value, `<path>`, is the token right after it. Strip those two tokens
and the whitespace following them; what remains is the skill's own positional text, read
exactly as if the flag had never been written. Any other first token, including a
`--mission` that appears later in the text, means the flag is absent, and the whole
invocation text is the skill's own. A leading `--mission` with no token after it names no
mission.

A skill that reads positional text strips the flag by this rule at its own parse point; the
value found there is the input the resolution below uses.

## Resolving the path

1. Take `<path>` verbatim, with no normalization: no prefix is added or stripped, no bare
   number or directory name is looked up, and a missing trailing slash is not supplied.

2. `<path>` matches when it ends in `/` and `<path>/requirements.md` exists in the working
   tree. No check is made that the path's last directory name opens with `mission_`. On a match,
   `<MISSION_DIR>` is `<path>`.

3. Otherwise — no flag, a flag with no value, or a value that does not match — **stop without
   changing anything**. Run, from the workspace root, the plugin's missions tool:

   ```
   python3 ${PLUGIN_ROOT}/tools/missions.py live
   ```

   It prints one tab-separated line per live mission — its path, `started` or `defined`, and
   its title — and nothing when no mission is live. Report the fixed line
   `No mission resolved — pass --mission with a live mission's path.` first, then below
   it the call's output verbatim, or, when the call fails, its one `Error: <reason>` line from
   stderr, so the caller can retry with one of the printed paths. Those lines are the whole
   report.

## Using `<MISSION_DIR>`

Use `<MISSION_DIR>` as the prefix for all mission-relative file reads
(e.g. `<MISSION_DIR>/TASKS_TODO.md`, `<MISSION_DIR>/requirements.md`).
