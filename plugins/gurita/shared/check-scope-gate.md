# Check the Scope Gate (shared snippet)

This is the single source of truth for the scope gate, the check that lets only one started
mission at a time take task work in a scope. Its one input is the resolved
`<MISSION_DIR>`. Every runner that enters a task into a mission's list or completes one
runs it as a step of its own, before its work, at the point its own file names. The check
changes nothing.

## What a held scope means

A mission's scope is the directory its mission directory stands in. A mission is
started when it is live — its directory still stands in the working tree — and tasks were
entered into its task list at some time, which the log shows as its `TASKS_TODO.md` changed
after the commit that defined it. It stays started until `/finish-mission` removes its
directory, also after every one of its tasks is completed. A mission that is only defined,
or that is still deciding its questions, is not started.

Another started mission **holds** this mission's scope when its scope is the same
directory, a directory that contains this one, or a directory under this one. Missions in
disjoint scopes never hold each other's. While another mission holds the scope, no task of
this mission enters its list and none is completed: the run waits until every holder is
finished.

## Running the gate

Run, from the workspace root, the plugin's missions tool:

```
python3 ${PLUGIN_ROOT}/tools/missions.py gate <MISSION_DIR>
```

It prints the path of every mission holding the scope, one per line, and nothing when none
does, exiting 0 either way; when it cannot check — a shallow clone, whose truncated log can
read a started mission as unstarted, or a path naming no `mission_` directory — it prints
one `Error: <reason>` line on stderr instead, with a non-zero exit.

- **The call printed nothing, on either stream, and exited 0** — the scope is free: go on to
  the runner's next step.
- **Anything else** — **stop without changing anything**. Report the fixed line
  `Scope gate closed — the scope is held or could not be checked.` first, then below it the
  paths the call printed, verbatim, or, when the call failed, its one `Error: <reason>` line
  from stderr. Those lines are the whole report: the run can be repeated once every holder is
  finished, or once the cause the `Error:` line names is fixed.
