# Betaflight Firmware Presets

Collection of CLI-based configuration presets for Betaflight flight controller firmware. Presets are browsed and applied through the Betaflight Configurator UI.

## Scope (this fork)

**IMPORTANT:** This fork (branch `lmarqs-custom-presets`) maintains **only the lmarqs presets** (`lmarqs_rates.txt`, `lmarqs_modes.txt`, `lmarqs_osd.txt`) under `presets/2025.12/{rates,modes,osd}/`. The other preset directories are kept in sync with upstream but are not edited here. Limit changes, validations, and indexing work to lmarqs files unless explicitly asked otherwise.

## Commands

```bash
mise run verify             # Validate all presets (wraps node indexer/check.js)
mise run index              # Generate index.json and index_hash.txt
mise run build              # Verify only (wraps scripts/build.sh)
bash scripts/build.sh deploy  # Verify + index + stage artifacts to public/
```

`npm run verify` and `npm run index` are equivalent fallbacks if mise is unavailable.

**IMPORTANT:** Always run `mise run verify` after modifying or creating preset files.

## Project Structure

```
presets/                    # Preset .txt files organized by firmware version
  ├── 2025.12/              # Latest version
  ├── 4.5/
  ├── 4.4/
  └── 4.3/
indexer/                    # Node.js validation & indexing system
  ├── check.js              # Validation entry point (forks indexer.js with "nosave")
  ├── indexer.js             # Generates index.json and index_hash.txt
  ├── Settings.js            # Metadata type definitions, categories, status enums
  ├── PresetsFile.js         # Preset file parser and validator
  ├── PresetsFolder.js       # Directory traversal, circular include detection
  └── IndexContent.js        # Index JSON builder
scripts/
  └── build.sh              # CI build/deploy orchestration
misc/
  └── warnings/en/          # Reusable warning texts (referenced via INCLUDE_WARNING)
```

Generated files: `index.json` and `index_hash.txt` are committed on this fork so the
presets load straight from the repo without a build step — regenerate and commit them
whenever a preset changes. `public/` stays untracked.

## CI/CD

GitHub Actions (`.github/workflows/build.yml`):
- Triggers on push and PR
- PRs/non-master: runs checker only
- Master (betaflight org): runs full build + deploys to Cloudflare Pages

## Contribution Rules

- One preset per PR
- **IMPORTANT:** Run `mise run index` and commit the refreshed `index.json` and `index_hash.txt` alongside any preset change. Upstream excludes them, so keep them out of PRs opened against `betaflight/firmware-presets`.
- Always validate locally before pushing
- Include `#$ DISCUSSION:` pointing to your PR URL

## Deep Dive

- Preset `.txt` syntax (metadata, options, includes) → [.claude/skills/preset-file-format.md](skills/preset-file-format.md)
- CLI parameter lookup workflow → [.claude/commands/betaflight-cli/SKILL.md](commands/betaflight-cli/SKILL.md)
- Per-version CLI parameter references → [docs/cli/README.md](../docs/cli/README.md)
- Maintaining the CLI mirrors (refresh / add version / validate headers) → [.claude/skills/cli-mirror-maintenance.md](skills/cli-mirror-maintenance.md)
