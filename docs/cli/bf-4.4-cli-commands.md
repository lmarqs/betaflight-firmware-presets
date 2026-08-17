# Betaflight 4.4 CLI Reference

- **Status**: active, no wiki page (Betaflight wiki publishes 4.0, 4.5, 2025.12 only — firmware source IS the reference)
- **Authoritative source** (overrides this mirror on conflict): [`betaflight/betaflight@4.4-maintenance`](https://github.com/betaflight/betaflight/tree/4.4-maintenance/src/main/cli)
- **Wiki mirror**: none
- **Cross-version index**: [README.md](./README.md)

## Refresh

```bash
gh api -H "Accept: application/vnd.github.raw" \
  repos/betaflight/betaflight/contents/src/main/cli/settings.c?ref=4.4-maintenance \
  > /tmp/bf-4.4-settings.c
gh api -H "Accept: application/vnd.github.raw" \
  repos/betaflight/betaflight/contents/src/main/fc/parameter_names.h?ref=4.4-maintenance \
  > /tmp/bf-4.4-pnames.h
```

## Lookup

- This mirror is source-derived, not a wiki dump — see the verified-keys table below for the preset surface covered here.
- Range/enum from source: `grep '"<param_name>"' /tmp/bf-4.4-settings.c` — row contains `.config.minmaxUnsigned = { lo, hi }` or `.config.lookup = { TABLE_<NAME> }` (enum table earlier in same file as `lookupTable<Name>`).
- Macro-form params (e.g. `rates_type`, `throttle_limit_*`): `grep 'PARAM_NAME_<UPPER>' /tmp/bf-4.4-settings.c`.
- `PARAM_NAME_*` macros: `grep '#define PARAM_NAME_<UPPER> ' /tmp/bf-4.4-pnames.h`.

## Compat notes

- Compat divergence vs 2025.12: only `osd_canvas_width/height` differ (present here, gated out in 2025.12 production). Wrap those keys in a per-version `OPTION_GROUP` when authoring presets that target both 4.4/4.5 and 2025.12.

## Verified preset surface (2026-05-28)

All keys below confirmed in `4.4-maintenance/src/main/cli/settings.c`. Identical names and ranges across 4.4 → 4.5 → 2025.12 unless noted.

| Key | Type | Notes |
|---|---|---|
| `rates_type` | enum (rateprofile) | `BETAFLIGHT, RACEFLIGHT, KISS, ACTUAL, QUICK` |
| `roll_rc_rate`, `pitch_rc_rate`, `yaw_rc_rate` | uint8 (rateprofile) | 1..255 |
| `roll_srate`, `pitch_srate`, `yaw_srate` | uint8 (rateprofile) | 0..255 |
| `throttle_limit_type` | enum (rateprofile) | `OFF, SCALE, CLIP` |
| `throttle_limit_percent` | uint8 (rateprofile) | 25..100 |
| `aux <slot> <mode> <chan> <lo> <hi> <logic> <link>` | command | verified mode IDs: 0 ARM, 1 ANGLE, 2 HORIZON, 15 LEDLOW, 35 FLIP_OVER_AFTER_CRASH, 36 PREARM |
| `osd_warn_bitmask`, `osd_stat_bitmask` | uint32 | bitmasks |
| `osd_rssi_dbm_alarm`, `osd_link_quality_alarm` | int/uint8 | per-row range |
| `osd_displayport_device` | enum | `NONE, AUTO, MAX7456, MSP, FRSKYOSD` |
| `vcd_video_system` | enum | `AUTO, PAL, NTSC, HD` (HD requires `USE_VIDEO_SYSTEM` build flag) |
| `osd_canvas_width` | uint8 | 0..63 — **present here, not in 2025.12 production** |
| `osd_canvas_height` | uint8 | 0..31 — **present here, not in 2025.12 production** |
| `osd_*_pos` | uint16 | 0..65535. Verified: `rssi`, `link_quality`, `rssi_dbm`, `vtx_channel`, `camera_frame`, `flip_arrow`, `crosshairs`, `tim_2`, `disarmed`, `avg_cell_voltage`, `ready_mode`, `throttle`, `flymode`, `craft_name`, `g_force`, `warnings`, `altitude` |
