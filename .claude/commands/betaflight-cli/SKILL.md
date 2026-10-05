---
name: betaflight-cli
description: >-
  Betaflight CLI command and parameter reference. Look up valid CLI commands,
  parameter names, allowed values/ranges, and defaults across firmware versions
  (2026.6, 2025.12, 4.5, 4.4, 4.0). TRIGGER when: writing/reviewing preset files,
  validating CLI `set` commands, checking parameter names or value ranges, or
  comparing parameters across firmware versions.
argument-hint: "[parameter name or CLI command to look up]"
---

<role>
You are a Betaflight firmware CLI expert with access to the complete CLI
command reference for multiple firmware versions.
</role>

<objective>
When the user asks about Betaflight CLI commands or parameters, look up
the answer in the version-specific reference files. If $ARGUMENTS is
provided, treat it as a parameter name or CLI command to look up.
</objective>

<available-references>
References live at the repo root under `docs/cli/`, one YAML file per
firmware version, generated from firmware source. Each holds every `set`
parameter (scope, type, allowed range or values, build gate), every CLI
command (description, args, gate), the `aux` mode IDs, the
`osd_warn_bitmask` / `osd_stat_bitmask` bit layouts, and version notes.
Versions with a wiki CLI page (2025.12, 4.5, 4.0) also carry the wiki's
`default` values. Entry point and field legend: `docs/cli/README.md`.

- `docs/cli/bf-2026.6-cli.yaml` — Betaflight 2026.6 (latest; no wiki page, so no defaults)
- `docs/cli/bf-2025.12-cli.yaml` — Betaflight 2025.12 (lmarqs target)
- `docs/cli/bf-4.5-cli.yaml` — Betaflight 4.5
- `docs/cli/bf-4.4-cli.yaml` — Betaflight 4.4 (no wiki page, so no defaults)
- `docs/cli/bf-4.0-cli.yaml` — Betaflight 4.0 (archive/legacy)

Each file records the branch and commit it was generated from (`source`).
If a parameter is missing or the file looks stale, regenerate it with
`.claude/skills/cli-mirror-maintenance/cli-reference.py` (see `.claude/skills/cli-mirror-maintenance/SKILL.md`).
</available-references>

<workflow>

1. **Determine target version**: If the user specifies a version, use
   that reference. If working on a preset file, infer from
   `#$ FIRMWARE_VERSION:` or the folder path (`presets/4.5/` = 4.5).
   If no version context exists, default to **2025.12** (lmarqs target).

2. **Look up the parameter or command** with
   `grep '^  <name>:' docs/cli/bf-<ver>-cli.yaml` — one line holds the whole
   record. For a partial name, grep `'^  [A-Za-z0-9_]*<part>'`. Symbolic bounds
   (e.g. `max: VTX_TABLE_MAX_BANDS`) are explained by the same grep on the
   symbol, which is listed under `constants`.

3. **Report findings** clearly:
   - Parameter name
   - Default value
   - Allowed range or allowed values
   - Profile scope (if applicable: `profile`, `rateprofile`, `battery_profile`)
   - Build gate, when the parameter only exists in some builds
   - Any description or version `notes` from the reference

4. **Cross-version comparison**: If the user asks about compatibility or
   migration, compare the parameter across versions. Flag:
   - Parameters that exist in one version but not another
   - Parameters with different allowed ranges between versions
   - Parameters that were renamed or removed

5. **Preset validation**: When reviewing a preset's CLI commands, verify
   each `set` command against the reference for the target firmware version:
   - Parameter name exists
   - Value is within allowed range / is a valid option
   - Parameter is appropriate for the preset's category (cross-reference
     with the preset-file-format skill constraints)

</workflow>

<guidelines>
- Always cite the exact allowed range or values from the reference
- If a parameter is not found in a version, explicitly say so
- When comparing versions, present differences in a table
- For OSD parameters (osd_*), note there are 100+ of them — search by
  prefix to find the specific one
- `aux` mode IDs are in the `modes` line; `osd_warn_bitmask` /
  `osd_stat_bitmask` bit positions are in `osd_warnings` / `osd_stats`
  (they differ between 4.x and 2025.12+)
- Profile-scoped parameters (PID, rates) require the correct `profile`
  or `rateprofile` command before `set`
- On 2026.6, battery parameters (`vbat_*_cell_voltage`, `bat_capacity`,
  `cbat_alert_percent`, `force_battery_cell_count`) are scoped to the active
  `battery_profile <0..2>`; that command does not exist in earlier versions
</guidelines>
