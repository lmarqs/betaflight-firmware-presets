# Betaflight CLI Reference

Per-version CLI parameter mirrors. Use when validating preset `set` commands.

| Version | File | Status | Authoritative source |
|---|---|---|---|
| 2025.12 (latest) | [bf-2025.12-cli-commands.md](./bf-2025.12-cli-commands.md) | active | `betaflight/betaflight@2025.12-maintenance` |
| 4.5 (stable)     | [bf-4.5-cli-commands.md](./bf-4.5-cli-commands.md) | active | `betaflight/betaflight@4.5-maintenance` |
| 4.4              | [bf-4.4-cli-commands.md](./bf-4.4-cli-commands.md) | active, no wiki page | `betaflight/betaflight@4.4-maintenance` |
| 4.0 (legacy)     | [bf-4.0-cli-commands.md](./bf-4.0-cli-commands.md) | archive | `betaflight/betaflight@4.0-maintenance` |

## Lookup workflow (for agents)

1. Determine target version from preset's `#$ FIRMWARE_VERSION:` lines (or default to 2025.12).
2. `grep '<param_name>' docs/cli/bf-<ver>-cli-commands.md` to find default + range.
3. If the mirror is silent or stale, re-pull from firmware source — see refresh command at the top of each `bf-*-cli-commands.md` file.
4. Validate: parameter exists in target version, value within range, profile scope correct (`set` vs `rateprofile` vs `profile`).

## Known cross-version divergences

| Key | 4.4 | 4.5 | 2025.12 | Note |
|---|---|---|---|---|
| `osd_canvas_width` / `osd_canvas_height` | exposed | exposed | **gated by `OSD_CANVAS_SIZE_DEBUG`, not in production builds** | Wrap in OPTION_GROUP when targeting both |

Multi-version presets: declare every supported version with repeated `#$ FIRMWARE_VERSION:` lines in a single file (see `presets/4.5/rates/AOS_rates.txt` for the established pattern).
