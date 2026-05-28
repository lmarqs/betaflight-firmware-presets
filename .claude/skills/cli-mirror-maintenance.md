---
name: cli-mirror-maintenance
description: >-
  Maintain `docs/cli/bf-*-cli-commands.md` — per-version mirrors of the
  Betaflight CLI parameter reference. Use when refreshing a mirror against
  upstream firmware source, scaffolding a new bf-<version>-cli-commands.md
  for a freshly released BF version, or validating that all mirror headers
  follow the standardized template (Status / Authoritative source / Wiki
  mirror / Cross-version index → Refresh → Lookup → Compat notes).
  TRIGGER when the user asks to refresh CLI docs, add a new BF version
  mirror, check for upstream drift, or verify the docs/cli/ headers are
  consistent. For per-parameter lookups during preset authoring, defer to
  the `/betaflight-cli` slash command — this skill handles the *upkeep* of
  the reference itself, not lookups against it.
---

# docs/cli/ Mirror Maintenance

Use this skill to keep the per-version CLI mirrors under `docs/cli/`
healthy: refreshing them against upstream firmware, adding new versions
when Betaflight ships a release, and ensuring all files share the same
header structure.

## Why these mirrors exist

The Betaflight project publishes a wiki page for the CLI parameters of
*some* releases (currently 4.0, 4.5, 2025.12) and not others (4.4 has no
wiki page). The wiki also lags behind firmware source. The mirrors in
`docs/cli/` exist so preset authoring (and the `/betaflight-cli`
command) can grep a local file rather than scraping the wiki, and so
4.4 has any reference at all. The firmware source
(`betaflight/betaflight@<ver>-maintenance`) is always the
authoritative source — these mirrors are a convenience layer over it.

## File inventory

| File | Authoritative source | Notes |
|---|---|---|
| `docs/cli/bf-2025.12-cli-commands.md` | `betaflight/betaflight@2025.12-maintenance` | latest, wiki-derived body |
| `docs/cli/bf-4.5-cli-commands.md` | `betaflight/betaflight@4.5-maintenance` | current stable, wiki-derived body |
| `docs/cli/bf-4.4-cli-commands.md` | `betaflight/betaflight@4.4-maintenance` | source-derived (no wiki page); body is a hand-curated table of the MARX5 preset surface |
| `docs/cli/bf-4.0-cli-commands.md` | `betaflight/betaflight@4.0-maintenance` | legacy/archive |
| `docs/cli/README.md` | — | cross-version index + lookup workflow |

The body content of each file differs in shape (wiki dump vs.
source-derived table), but the **header block must be identical in
structure** across all four. See "Standard header template" below.

## Standard header template

Every `bf-*-cli-commands.md` opens with this exact section structure:

```markdown
# Betaflight <VERSION> CLI Reference[ (legacy)]

- **Status**: <one of: active (latest) | active (current stable) | active, no wiki page | archive — <reason>>
- **Authoritative source** (overrides this mirror on conflict): [`betaflight/betaflight@<VERSION>-maintenance`](https://github.com/betaflight/betaflight/tree/<VERSION>-maintenance/src/main/cli)
- **Wiki mirror**: <URL or "none">
- **Cross-version index**: [README.md](./README.md)

## Refresh

​```bash
gh api -H "Accept: application/vnd.github.raw" \
  repos/betaflight/betaflight/contents/src/main/cli/settings.c?ref=<VERSION>-maintenance \
  > /tmp/bf-<VERSION>-settings.c
gh api -H "Accept: application/vnd.github.raw" \
  repos/betaflight/betaflight/contents/src/main/fc/parameter_names.h?ref=<VERSION>-maintenance \
  > /tmp/bf-<VERSION>-pnames.h
​```

## Lookup

- Default in this mirror: `grep '^<param_name>' <this-file>` for parameter default; section headers (`## ...`) for command syntax.
- Range/enum from source: `grep '"<param_name>"' /tmp/bf-<VERSION>-settings.c` — row contains `.config.minmaxUnsigned = { lo, hi }` or `.config.lookup = { TABLE_<NAME> }` (enum table earlier in same file as `lookupTable<Name>`).
- `PARAM_NAME_*` macros: `grep '#define PARAM_NAME_<UPPER> ' /tmp/bf-<VERSION>-pnames.h`.

## Compat notes

- <version-specific gotchas, or "None known.">

<original body — wiki dump, source-derived table, etc.>
```

The four section headings (`## Refresh`, `## Lookup`, `## Compat notes`,
then the body's first heading) and the four metadata bullet keys
(`Status`, `Authoritative source`, `Wiki mirror`, `Cross-version index`)
must match exactly so a reader can scan any file and know where to
look. The `Lookup` bullets vary slightly when a mirror is source-derived
rather than wiki-derived (see `bf-4.4` for an example) — that's fine.

## Workflows

### Workflow 1 — Refresh a mirror against upstream

Run when the user says "refresh", "check for drift", or asks whether a
parameter has changed.

1. **Pull current source** for the target version using the `Refresh`
   recipe at the top of the target mirror file. Confirm `gh` is
   authenticated (`gh auth status`).
2. **Spot-check a handful of parameters** the user cares about (or
   parameters used by MARX5 presets — `roll_rc_rate`, `osd_warn_bitmask`,
   `motor_pwm_protocol`, etc.):
   - Grep the mirror for the documented default + range.
   - Grep `/tmp/bf-<ver>-settings.c` for the same parameter.
   - Compare. Any divergence = upstream changed; the mirror is stale.
   - **Enum gotcha**: `settings.c` only names the enum table (e.g.
     `TABLE_RATES_TYPE`), not the literal values. To verify allowed
     values, also `grep 'lookupTableRatesType\|lookupTableMotorPwmProtocol\|...'`
     (camelCase of the table name) in the same file — that's where the
     actual `{ "BETAFLIGHT", "RACEFLIGHT", ... }` array lives.
3. **If the mirror's body is a wiki dump** (2025.12, 4.5, 4.0) and you
   find drift, the right fix is usually to refetch the wiki page (the
   wiki is the source for the body content, even though firmware source
   wins on conflicts). The wiki URLs are in each file's `Wiki mirror`
   bullet.
4. **If the mirror's body is source-derived** (4.4), update the table
   in-place from `/tmp/bf-4.4-settings.c`.
5. **Update the Compat notes section** if the drift reveals a
   per-version difference worth flagging (e.g., a parameter gated
   behind a build flag, a renamed key).

### Workflow 2 — Add a new version mirror

Run when Betaflight ships a new release (e.g. `2026.6-maintenance` is
cut) and the user wants to add `bf-2026.6-cli-commands.md`.

1. **Confirm the maintenance branch exists**:
   `gh api repos/betaflight/betaflight/branches/<VERSION>-maintenance`.
   Don't add a mirror for an unreleased version — the branch needs to
   exist upstream first.
2. **Decide body source**:
   - If the Betaflight wiki publishes a CLI page for this version, the
     body should be the wiki dump (like 4.5/2025.12). The wiki URL
     pattern is
     `https://betaflight.com/docs/wiki/guides/{current,archive}/Betaflight-<VERSION>-CLI-commands`.
   - If no wiki page, build a source-derived table covering at minimum
     the MARX5 preset surface (use `bf-4.4-cli-commands.md` as the
     model).
3. **Write the file** at `docs/cli/bf-<VERSION>-cli-commands.md` using
   the Standard header template above. Substitute `<VERSION>` in:
   - The H1 title
   - `Authoritative source` bullet (URL + tree path)
   - `Wiki mirror` bullet (URL or "none")
   - The `gh api` recipe (both `?ref=` params)
   - The `grep` commands in `Lookup` (`/tmp/bf-<VERSION>-...` paths)
4. **Update `docs/cli/README.md`**:
   - Add a row to the version table (Version / File / Status /
     Authoritative source).
   - If a known cross-version divergence applies, add a row to the
     "Known cross-version divergences" table.
5. **Update `.claude/commands/betaflight-cli/SKILL.md`** if the new
   version should be the default lookup target (i.e., it becomes the
   "latest"). Update the bullet list in the `<available-references>`
   block and the default-version rule in `<workflow>` step 1.
6. **Run `mise run verify`** — the indexer doesn't validate docs, but
   running it confirms you didn't accidentally break a preset file
   while editing.

### Workflow 3 — Validate header consistency

Run when the user asks "are the headers consistent?" or after editing
any mirror's metadata block.

For each `bf-*-cli-commands.md`:

1. The H1 line matches `^# Betaflight <VERSION> CLI Reference( \(legacy\))?$`.
2. The next non-empty lines are exactly four bullets, in this order,
   with these exact keys: `Status`, `Authoritative source`,
   `Wiki mirror`, `Cross-version index`.
3. The first three `##` headings, in order, are `## Refresh`,
   `## Lookup`, `## Compat notes`.
4. The `gh api` block in `## Refresh` references the version-matching
   `<ver>-maintenance` branch and writes to `/tmp/bf-<ver>-...` paths.
5. The `Lookup` bullets reference `/tmp/bf-<ver>-settings.c` and
   `/tmp/bf-<ver>-pnames.h` matching the file's version.

If any check fails, fix it in place to match the template. Don't touch
the body content below `## Compat notes` — only the header block is
standardized.

A quick way to spot-check all four files at once:

```bash
for v in 2025.12 4.5 4.4 4.0; do
  echo "=== bf-$v ==="
  sed -n '1,8p' docs/cli/bf-$v-cli-commands.md
done
```

## Don'ts

- **Don't hand-edit a wiki-dump body to add or correct individual
  parameters.** That body is a snapshot; corrections drift on the next
  refresh. Either fix it via wiki refresh (Workflow 1) or capture the
  divergence in `Compat notes` so the next reader knows to trust source
  over the body.
- **Don't add per-parameter explanations to the mirror.** The mirror's
  job is to be greppable, not to explain physics. If a parameter is
  surprising, that's what `Compat notes` and the auto-memory system are
  for.
- **Don't skip Workflow 2 step 4 (README update).** A new mirror that
  isn't in the index is invisible — `/betaflight-cli` won't find it.

## Cross-references

- Per-parameter lookups during preset authoring →
  `.claude/commands/betaflight-cli/SKILL.md` (the slash command reads
  these mirrors).
- Cross-version index + known divergences → `docs/cli/README.md`.
- Preset file format these mirrors support →
  `.claude/skills/preset-file-format.md`.
