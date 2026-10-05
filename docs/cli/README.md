# Betaflight CLI Reference

Per-version CLI references, generated from firmware source by [`.claude/skills/cli-mirror-maintenance/cli-reference.py`](../../.claude/skills/cli-mirror-maintenance/cli-reference.py). Use when validating preset `set` commands.

| Version | File | Status | Authoritative source |
|---|---|---|---|
| 2026.6 (latest)  | [bf-2026.6-cli.yaml](./bf-2026.6-cli.yaml) | active, no wiki page | `betaflight/betaflight@2026.6-maintenance` |
| 2025.12 (lmarqs target) | [bf-2025.12-cli.yaml](./bf-2025.12-cli.yaml) | active | `betaflight/betaflight@2025.12-maintenance` |
| 4.5 (stable)     | [bf-4.5-cli.yaml](./bf-4.5-cli.yaml) | active | `betaflight/betaflight@4.5-maintenance` |
| 4.4              | [bf-4.4-cli.yaml](./bf-4.4-cli.yaml) | active, no wiki page | `betaflight/betaflight@4.4-maintenance` |
| 4.0 (legacy)     | [bf-4.0-cli.yaml](./bf-4.0-cli.yaml) | archive | `betaflight/betaflight@4.0-maintenance` |

## Lookup workflow (for agents)

1. Determine target version from preset's `#$ FIRMWARE_VERSION:` lines (or default to 2025.12, the version the lmarqs presets target).
2. `grep '^  <name>:' docs/cli/bf-<ver>-cli.yaml` returns the whole record of a parameter, command or constant on one line (names are unique across sections). `grep -E '^(modes|osd_warnings|osd_stats):'` returns those tables, one line each. `yq '.parameters.<name>'` works too.
3. If the file is stale (its `source.commit` is behind the maintenance branch), regenerate it — see `.claude/skills/cli-mirror-maintenance/SKILL.md`.
4. Validate: parameter exists in target version, value within range, profile scope correct (`set` vs `rateprofile` vs `profile`, plus `battery_profile` on 2026.6).

## File format

One YAML file per version, one line per parameter, command or constant:

- `source`: repo, branch, commit and date the file was generated from. `wiki`: the version's wiki CLI page, or `null`.
- `notes`: version-specific behaviour the data alone does not show (hand-written; kept on regeneration).
- `modes`: `aux` mode IDs (`permanentId: name`). `osd_warnings` / `osd_stats`: bit index → name for `osd_warn_bitmask` / `osd_stat_bitmask`.
- `constants`: symbols that stay symbolic in ranges because their value depends on the build — `target-dependent`, or each definition with the condition it applies under (`default` = used unless the target overrides it).
- `commands.<name>`: `description`, `args` (lines separated by `\n`), `gate`.
- `parameters.<name>`:
  - `scope`: `profile`, `rateprofile`, `battery_profile` or `hardware`; omitted = master.
  - `type`: `uint8` … `int32` (number, `min`/`max`), `enum` (`values`; `value_gates` lists values that exist only under a build condition), `bitset` (`OFF`/`ON`), `string` (`min_length`/`max_length`); a `length` field marks an array.
  - `gate`: preprocessor condition the parameter is compiled under; omitted = always.
  - `default`: value printed on the wiki page (2025.12, 4.5, 4.0 only; board-specific for hardware settings). `description`: wiki prose (4.0 only).
- A name defined differently under different gates holds a list of variants.

## Known cross-version divergences

| Key | 4.4 | 4.5 | 2025.12 | 2026.6 | Note |
|---|---|---|---|---|---|
| `osd_canvas_width` / `osd_canvas_height` | exposed | exposed | **gated by `OSD_CANVAS_SIZE_DEBUG`, not in production builds** | **gated** (same as 2025.12) | Wrap in OPTION_GROUP when targeting both |
| `osd_warn_bitmask` bit layout | bit 8 `RC_SMOOTHING`; bits 9–17 `FAIL_SAFE` … `RSNR` | as 4.4, plus bit 18 `LOAD` | no `RC_SMOOTHING`: 4.5's bits 9–18 sit at bits 8–17; bit 18 `POSHOLD_FAILED` | as 2025.12, with bit 11 `GPS_RESCUE_FAILING` and bit 19 `AUTOPILOT_ABORT` | The same mask value enables different warnings on 4.x and 2025.12+. `lmarqs_osd.txt` (321535) uses the 2025.12 layout |
| `vbat_min_cell_voltage`, `vbat_warning_cell_voltage`, `vbat_max_cell_voltage`, `vbat_full_cell_voltage`, `bat_capacity`, `cbat_alert_percent`, `force_battery_cell_count` | master | master | master | **battery_profile** (3 profiles) | `set` writes only the active battery profile on 2026.6; `battery_profile <n>` is not a command before 2026.6 |
| `osd_displayport_device` | `NONE, AUTO, MAX7456, MSP, FRSKYOSD` | same | same | adds `FBOSD` | |

Multi-version presets: declare every supported version with repeated `#$ FIRMWARE_VERSION:` lines in a single file (see `presets/4.5/rates/AOS_rates.txt` for the established pattern).
