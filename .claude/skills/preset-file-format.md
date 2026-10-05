---
name: preset-file-format
description: >-
  Betaflight preset `.txt` file format reference. Covers metadata header
  fields (TITLE, FIRMWARE_VERSION, CATEGORY, STATUS, etc.), CLI payload
  syntax, OPTION/OPTION_GROUP blocks, INCLUDE chains, category constraints,
  and validation rules enforced by `node indexer/check.js`. TRIGGER when
  creating or editing any file under `presets/**/*.txt`, or when validating
  preset metadata directives (`#$ ...`).
---

# Preset File Format

Use this skill when creating or editing Betaflight preset `.txt` files.

## File Location

`presets/<firmware_version>/<category>/[subcategory/]<name>.txt`

## Metadata Header

All metadata lines start with `#$ ` and field names are UPPERCASE followed by `:`.

### Mandatory fields

| Field | Description |
|-------|-------------|
| `#$ TITLE:` | Unique, descriptive title |
| `#$ FIRMWARE_VERSION:` | Compatible versions (one per line, multiple allowed) |
| `#$ CATEGORY:` | One of: `TUNE`, `RATES`, `FILTERS`, `RC_LINK`, `RC_SMOOTHING`, `OSD`, `VTX`, `LEDS`, `MODES`, `BNF`, `OTHER` |
| `#$ STATUS:` | `OFFICIAL`, `COMMUNITY`, or `EXPERIMENTAL` |

### Common optional fields

| Field | Description |
|-------|-------------|
| `#$ KEYWORDS:` | Comma-separated search terms |
| `#$ AUTHOR:` | GitHub username or nickname |
| `#$ DESCRIPTION:` | Multi-line description (each line = new paragraph) |
| `#$ DISCUSSION:` | URL to the PR where preset was introduced |
| `#$ PARSER:` | `TEXT` (default) or `MARKED` (enables markdown in descriptions) |
| `#$ WARNING:` | Strong warning shown before applying |
| `#$ INCLUDE_WARNING:` | Path to reusable warning file (e.g., `misc/warnings/en/rpm_filters.txt`) |
| `#$ INCLUDE:` | Path to another preset to include (e.g., `presets/2025.12/tune/defaults.txt`) |
| `#$ FORCE_OPTIONS_REVIEW:` | Forces user to review options before applying |
| `#$ HIDDEN:` | If `true`, preset won't appear in the index |
| `#$ PRIORITY:` | Integer 0-99 for sort order |

## CLI Payload

After metadata, the file contains Betaflight CLI commands:

```
set pid_roll_p = 45
set pid_roll_i = 80
feature GPS
serial 0 64 115200 57600 0 115200
```

## Options

Options create user-selectable checkboxes in the Configurator UI:

```
#$ OPTION BEGIN (CHECKED): DShot600
    set dshot_bidir = ON
    set motor_pwm_protocol = DSHOT600
#$ OPTION END

#$ OPTION BEGIN (UNCHECKED): DShot300
    set dshot_bidir = ON
    set motor_pwm_protocol = DSHOT300
#$ OPTION END
```

- Indent CLI commands inside options with 4 spaces
- Nesting options is NOT allowed
- Each option name must be unique within the file

## Option Groups

Group related options, optionally making them mutually exclusive:

```
#$ OPTION_GROUP BEGIN: (EXCLUSIVE) Radio Protocol
    #$ OPTION BEGIN (UNCHECKED): CRSF
        ...
    #$ OPTION END
    #$ OPTION BEGIN (UNCHECKED): SBUS
        ...
    #$ OPTION END
#$ OPTION_GROUP END
```

## Includes

Compose presets from other files (metadata from included files is ignored):

```
#$ INCLUDE: presets/2025.12/tune/defaults.txt
#$ INCLUDE: presets/2025.12/rc_link/defaults.txt
```

Paths are relative to the repo root. Circular includes are detected and rejected.

## Category Constraints

- **TUNE**: PID params, filters, motor output. Should NOT include RC_LINK/RC_SMOOTHING settings.
- **RATES**: Rate type, rc_rate, expo, s_rate. Should NOT include TPA (that belongs in TUNE).
- **VTX**: Must include a mandatory legal disclaimer about RF regulations.
- **Motor protocol** (`motor_pwm_protocol`): Only allowed in TUNE, FILTERS, OTHER, BNF categories. Must include a WARNING when setting it.

## Validation

Run `mise run verify` after creating or modifying presets. The checker enforces:

- All mandatory fields present and non-empty
- Valid category and status values
- Correct `#$ ` prefix syntax on all directive lines
- No unknown directives
- No nested options
- Matching OPTION/OPTION_GROUP BEGIN/END pairs
- Non-empty option names
- INCLUDE paths resolve to existing files
- No circular include chains
