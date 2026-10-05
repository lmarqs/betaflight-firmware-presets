#!/usr/bin/env python3
"""Generate a Betaflight CLI reference YAML (parameters + commands) from firmware source.

usage: cli-reference.py <betaflight-checkout> <out.yaml> [--wiki FILE]

<betaflight-checkout> is a clone of betaflight/betaflight at a `<version>-maintenance`
branch. --wiki takes the text of the version's wiki CLI page (or a previous mirror of it)
and fills `default` (and `description`, where the page has prose) per parameter. Without
--wiki, `default` and `description` are kept from the existing <out.yaml>, as are `wiki` and
`notes`; everything else is regenerated.

Every parameter and command is written on one line, so `grep '^  <name>:'` returns
the whole record. Field meanings are documented in docs/cli/README.md.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

import yaml

# Symbols whose value depends on the target MCU or board; kept symbolic.
TARGET_DEPENDENT = {
    "ADCDEV_COUNT", "CANDEV_COUNT", "I2CDEV_COUNT", "SDIODEV_COUNT", "SPIDEV_COUNT",
    "GYRO_COUNT", "STATUS_LED_COUNT", "TASK_COUNT", "MCO_SOURCE_COUNT", "MCO_DIVIDER_COUNT",
    "OSD_PROFILE_COUNT", "MAX_SUPPORTED_MOTORS", "MAX_SUPPORTED_SERVOS",
}

SCOPES = [
    ("PROFILE_BATTERY_VALUE", "battery_profile"),
    ("PROFILE_RATE_VALUE", "rateprofile"),
    ("PROFILE_VALUE", "profile"),
    ("HARDWARE_VALUE", "hardware"),
]

TARGET_DIRS = ("src/main/target/", "src/platform/", "src/config/")

YAML_RESERVED = {"y", "n", "yes", "no", "on", "off", "true", "false", "null"}


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r'//[^\n"]*$', "", text, flags=re.M)


def normalize_cond(expr):
    expr = strip_comments(expr)
    expr = re.sub(r"defined\s*\(\s*(\w+)\s*\)", r"\1", expr)
    expr = re.sub(r"defined\s+(\w+)", r"\1", expr)
    return re.sub(r"\s+", " ", expr).strip()


def negate(cond):
    if re.fullmatch(r"\w+", cond):
        return "!" + cond
    if re.fullmatch(r"!\w+", cond):
        return cond[1:]
    return f"!({cond})"


def wrap(cond):
    return cond if re.fullmatch(r"!?\w+", cond) else f"({cond})"


class Gates:
    """Tracks the active preprocessor conditions while walking source lines."""

    def __init__(self):
        self.stack = []  # per #if level: [conditions of earlier branches, active condition]

    def feed(self, line):
        """Consume a conditional directive; return False for any other line."""
        m = re.match(r"\s*#\s*(ifdef|ifndef|if|elif|else|endif)\b(.*)", line)
        if not m:
            return False
        kind, cond = m.group(1), normalize_cond(m.group(2))
        if kind == "ifdef":
            self.stack.append([[cond], cond])
        elif kind == "ifndef":
            self.stack.append([["!" + cond], "!" + cond])
        elif kind == "if":
            self.stack.append([[cond], cond])
        elif not self.stack:
            pass
        elif kind == "elif":
            earlier = self.stack[-1][0]
            self.stack[-1][1] = " && ".join([negate(c) for c in earlier] + [wrap(cond)])
            earlier.append(cond)
        elif kind == "else":
            self.stack[-1][1] = " && ".join(negate(c) for c in self.stack[-1][0])
        else:
            self.stack.pop()
        return True

    def current(self):
        return [frame[1] for frame in self.stack]


def gate_str(conds):
    return " && ".join(wrap(c) if len(conds) > 1 else c for c in conds)


def compiled_out(conds):
    return "0" in conds


def region(text, start_pattern):
    m = re.search(start_pattern, text)
    if not m:
        sys.exit(f"pattern not found: {start_pattern}")
    end = re.search(r"^\};", text[m.end():], re.M)
    return text[m.end():m.end() + end.start()]


def split_top(s):
    """Split on commas at bracket depth 0, outside string literals."""
    out, cur, depth, in_str, i = [], [], 0, False, 0
    while i < len(s):
        ch = s[i]
        cur.append(ch)
        if in_str:
            if ch == "\\":
                cur.append(s[i + 1])
                i += 1
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
        elif ch == "," and depth == 0:
            cur.pop()
            out.append("".join(cur).strip())
            cur = []
        i += 1
    if "".join(cur).strip():
        out.append("".join(cur).strip())
    return out


def c_string(expr, macros):
    """Evaluate a concatenation of C string literals and string macros; None for NULL."""
    out, pos = [], 0
    token = re.compile(r'\s*(?:"((?:[^"\\]|\\.)*)"|(\w+))')
    expr = expr.strip()
    while pos < len(expr):
        m = token.match(expr, pos)
        if not m:
            return None
        if m.group(1) is not None:
            out.append(m.group(1).encode().decode("unicode_escape"))
        elif m.group(2) in macros:
            out.append(macros[m.group(2)])
        else:
            return None
        pos = m.end()
    return "".join(out)


def walk_entries(body, opener, closer):
    """Yield (conditions, entry_text) for each entry of a C initializer body.

    Function-like macros defined inside the body and invoked as entries are expanded.
    """
    templates, gates, lines = {}, Gates(), body.split("\n")
    buf, buf_conds, i = None, None, 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"\s*#\s*define\s+(\w+)\(([^)]*)\)(.*)", line)
        if m and buf is None:
            text = m.group(3)
            while text.rstrip().endswith("\\"):
                i += 1
                text = text.rstrip()[:-1] + "\n" + lines[i]
            templates[m.group(1)] = ([a.strip() for a in m.group(2).split(",")], text)
            i += 1
            continue
        if buf is None and gates.feed(line):
            i += 1
            continue
        if buf is None:
            stripped = strip_comments(line).strip()
            call = re.match(r"(\w+)\((.*)\)\s*,?$", stripped)
            if call and call.group(1) in templates:
                params, text = templates[call.group(1)]
                for p, a in zip(params, (a.strip() for a in call.group(2).split(","))):
                    text = re.sub(rf"\b{p}\b", a, text)
                text = re.sub(r"STR\((\w+)\)", r'"\1"', strip_comments(text))
                for entry in split_top(re.sub(r"\s+", " ", text)):
                    yield gates.current(), entry
                i += 1
                continue
            idx = stripped.find(opener)
            if idx == -1:
                i += 1
                continue
            buf, buf_conds, line = [], gates.current(), stripped[idx:]
        buf.append(strip_comments(line))
        joined = "\n".join(buf)
        if joined.count(opener) - joined.count(closer) <= 0:
            yield buf_conds, re.sub(r"\s+", " ", joined).strip().rstrip(",")
            buf = None
        i += 1


class Source:
    def __init__(self, root):
        self.root = root
        self.settings_c = self.read("src/main/cli/settings.c")
        self.macros = {}
        path = os.path.join(root, "src/main/fc/parameter_names.h")
        if os.path.exists(path):
            for m in re.finditer(r'#define\s+(\w+)\s+"([^"]*)"', open(path).read()):
                self.macros[m.group(1)] = m.group(2)
        self._c_files = None

    def read(self, rel):
        return open(os.path.join(self.root, rel), errors="replace").read()

    def c_files(self):
        if self._c_files is None:
            self._c_files = {}
            for base, _, files in os.walk(os.path.join(self.root, "src")):
                for f in files:
                    if f.endswith(".c") and "/test" not in base:
                        p = os.path.join(base, f)
                        self._c_files[p] = open(p, errors="replace").read()
        return self._c_files

    def macro_sites(self):
        """name -> [(body, conditions, path)] for every object-like #define under src/."""
        sites = {}
        for base, _, files in os.walk(os.path.join(self.root, "src")):
            if "/test" in base:
                continue
            for f in files:
                if not f.endswith((".h", ".c")):
                    continue
                path = os.path.join(base, f)
                rel = os.path.relpath(path, self.root)
                gates = Gates()
                for line in open(path, errors="replace"):
                    if gates.feed(line):
                        continue
                    m = re.match(r"\s*#\s*define\s+(\w+)(?![\w(])(.*)", line)
                    if m:
                        body = strip_comments(m.group(2)).strip()
                        conds = [c for c in gates.current() if not re.fullmatch(r"!?(__\w+|\w+_H_?)", c)]
                        sites.setdefault(m.group(1), []).append((body, conds, rel))
        return sites

    def gated_enum_members(self):
        """Enum members preceded by an #if inside their enum, so their value depends on the build."""
        members = set()
        for base, _, files in os.walk(os.path.join(self.root, "src/main")):
            for f in files:
                if not f.endswith(".h"):
                    continue
                text = open(os.path.join(base, f), errors="replace").read()
                for body in re.findall(r"\benum\b[^{;]*\{(.*?)\}", text, re.S):
                    first_if = re.search(r"^\s*#\s*if", body, re.M)
                    if first_if:
                        members |= set(re.findall(r"^\s*([A-Z]\w*)\b", body[first_if.start():], re.M))
        return members

    def string_array(self, name):
        """Values of `const char * const name[] = {...}` as [(value, conditions)]; NULLs dropped."""
        pattern = rf"\bconst\s+char\s*\*\s*const\s+{re.escape(name)}\s*\[[^\]]*\]\s*=\s*\{{"
        hits = [t for t in self.c_files().values() if re.search(pattern, t)]
        if len(hits) != 1:
            sys.exit(f"lookup array {name}: {len(hits)} definitions")
        m = re.search(pattern, hits[0])
        body = hits[0][m.end():hits[0].index("};", m.end())]
        values, gates = [], Gates()
        for line in body.split("\n"):
            if gates.feed(line) or compiled_out(gates.current()):
                continue
            for s in re.findall(r'"((?:[^"\\]|\\.)*)"|\bNULL\b', strip_comments(line)):
                if s:
                    values.append((s, gates.current()))
        return values

    def lookup_tables(self):
        """Map TABLE_* names to string arrays by pairing lookupTableIndex_e with lookupTables[]."""
        header = self.read("src/main/cli/settings.h")
        enum_body = header[:header.index("} lookupTableIndex_e;")]
        enum_body = enum_body[enum_body.rindex("typedef enum"):]
        names, gates = [], Gates()
        for line in enum_body.split("\n"):
            if gates.feed(line):
                continue
            for t in re.findall(r"\b(TABLE_\w+)\b", strip_comments(line)):
                names.append((t, gates.current()))
        arrays, gates = [], Gates()
        for line in region(self.settings_c, r"const lookupTableEntry_t lookupTables\[\] = \{").split("\n"):
            if gates.feed(line):
                continue
            for a in re.findall(r"LOOKUP_TABLE_ENTRY\((\w+)\)|^\s*\{\s*(\w+)\s*,", line):
                arrays.append((a[0] or a[1], gates.current()))
        # Outer gates may nest differently in the two lists (e.g. USE_GPS around USE_GPS_RESCUE).
        if len(names) != len(arrays) or any(n[1][-1:] != a[1][-1:] for n, a in zip(names, arrays)):
            sys.exit("lookupTableIndex_e and lookupTables[] do not line up")
        return {n[0]: self.string_array(a[0]) for n, a in zip(names, arrays)}

    def params(self):
        rows = []
        body = region(self.settings_c, r"const clivalue_t valueTable\[\] = \{")
        for conds, entry in walk_entries(body, "{", "}"):
            if compiled_out(conds):
                continue
            fields = split_top(entry[entry.index("{") + 1:entry.rindex("}")])
            name = c_string(fields[0], self.macros)
            if not name:
                sys.exit(f"unresolved parameter name: {entry}")
            cfg = next((f for f in fields[2:] if f.startswith(".config")), "")
            rows.append({"name": name, "flags": fields[1], "config": cfg, "conds": conds})
        return rows

    def commands(self):
        out = []
        body = region(self.read("src/main/cli/cli.c"), r"const clicmd_t cmdTable\[\] = \{")
        for conds, entry in walk_entries(body, "CLI_COMMAND_DEF(", ")"):
            if compiled_out(conds) or not entry.startswith("CLI_COMMAND_DEF("):
                continue
            args = split_top(entry[len("CLI_COMMAND_DEF("):entry.rindex(")")])
            name, desc, usage = (c_string(a, {}) for a in args[:3])
            if usage:
                usage = usage.replace("\r\n\t", "\n").replace("\r\n", "\n").strip("\n")
            out.append({"name": name, "description": desc, "args": usage, "conds": conds})
        return out

    def modes(self):
        """`aux` mode IDs: permanentId -> box name, from msp_box.c."""
        body = region(self.read("src/main/msp/msp_box.c"), r"const box_t boxes\[[^\]]*\] = \{")
        found = re.findall(r'\.boxName\s*=\s*"([^"]+)"\s*,\s*\.permanentId\s*=\s*(\d+)', body)
        return {int(i): name for name, i in sorted(found, key=lambda f: int(f[1]))}

    def bit_names(self, enum_name, prefix):
        """Bit index -> name for a positional OSD enum in osd.h (the *_COUNT terminator excluded)."""
        text = self.read("src/main/osd/osd.h")
        end = text.index(f"}} {enum_name};")
        body = strip_comments(text[text.rindex("typedef enum", 0, end):end])
        if re.search(r"^\s*#\s*if|=", body, re.M):
            sys.exit(f"{enum_name}: gated or explicit members; positions need manual review")
        names = re.findall(rf"^\s*{prefix}(\w+)", body, re.M)
        return {i: n for i, n in enumerate(names) if n != "COUNT"}

    def eval_exprs(self, exprs):
        """Evaluate integer expressions by compiling against the checkout's SITL target headers."""
        prologue = self.settings_c[:self.settings_c.index("const lookupTableEntry_t lookupTables[]")]
        sim = os.path.join(self.root, "src/platform/SIMULATOR")
        if os.path.isdir(sim):
            incs = [os.path.join(sim, "target/SITL"), sim, os.path.join(sim, "include")]
        else:
            incs = [os.path.join(self.root, "src/main/target/SITL")]
        incs += [os.path.join(self.root, p) for p in ("src/main", "src/main/cli", "lib/main/dyad",
                                                     "lib/main/MAVLink", "lib/main/google/olc")]
        flags = ["-std=gnu17", "-w", "-D_GNU_SOURCE", "-DSITL", "-DSIMULATOR", "-DSIMULATOR_BUILD",
                 '-D__TARGET__="SITL"', '-D__FORKNAME__="betaflight"', '-D__MCU_NAME__="SIMULATOR"',
                 '-D__REVISION__="norevision"', "-DTARGET_FLASH_SIZE=2048", "-DHSE_VALUE=8000000"]
        flags += [f"-I{p}" for p in incs if os.path.isdir(p)]
        pending = sorted(exprs)
        with tempfile.TemporaryDirectory() as tmp:
            src, exe = os.path.join(tmp, "eval.c"), os.path.join(tmp, "eval")
            while pending:
                body = [f'    printf("%lld\\n", (long long)({e}));' for e in pending]
                text = "\n".join([prologue, "#include <stdio.h>", "int main(void) {", *body, "    return 0;", "}"])
                first = text.split("\n").index("int main(void) {") + 2
                open(src, "w").write(text)
                r = subprocess.run(["gcc", *flags, src, "-o", exe], capture_output=True, text=True)
                if r.returncode == 0:
                    values = subprocess.run([exe], capture_output=True, text=True, check=True).stdout.split()
                    return {e: int(v) for e, v in zip(pending, values)}
                bad = {int(n) - first for n in re.findall(r"eval\.c:(\d+):\d+: error", r.stderr)}
                bad = {b for b in bad if 0 <= b < len(pending)}
                if not bad:
                    sys.exit("constant evaluation failed:\n" + r.stderr[:3000])
                pending = [e for i, e in enumerate(pending) if i not in bad]
        return {}


def bound_exprs(cfg):
    m = re.search(r"\{(.*)\}", cfg)
    if m:
        return split_top(m.group(1))[:2]
    return [cfg.split("=", 1)[1].strip()] if "=" in cfg else []


def describe(row, tables, num):
    flags, cfg = row["flags"], row["config"]
    vtype = re.search(r"VAR_(\w+)", flags).group(1).lower()
    scope = next((s for k, s in SCOPES if re.search(rf"\b{k}\b", flags)), None)
    entry = {"scope": scope} if scope else {}

    if "MODE_LOOKUP" in flags:
        gates = {}
        for v, conds in tables[re.search(r"\b(TABLE_\w+)", cfg).group(1)]:
            gates.setdefault(v, []).append(gate_str([c for c in conds if c not in row["conds"]]))
        entry.update(type="enum", values=list(gates))
        extra = {v: g[0] if len(g) == 1 else g for v, g in gates.items() if "" not in g}
        if extra:
            entry["value_gates"] = extra
    elif "MODE_BITSET" in flags:
        entry["type"] = "bitset"
    elif "MODE_ARRAY" in flags:
        entry.update(type=vtype, length=num(row_exprs(row)[0], row))
    elif "MODE_STRING" in flags:
        lo, hi = row_exprs(row)
        entry.update(type="string", min_length=num(lo, row), max_length=num(hi, row))
    elif vtype == "int32":
        hi = num(row_exprs(row)[0], row)
        entry.update(type=vtype, min=-hi if isinstance(hi, int) else f"-{hi}", max=hi)
    else:
        lo, hi = row_exprs(row)
        entry.update(type=vtype, min=num(lo, row), max=num(hi, row))
    return entry


def row_exprs(row):
    """The integer expressions a row's range is built from (uint32 rows: 0 and u32Max)."""
    flags, cfg = row["flags"], row["config"]
    if "MODE_LOOKUP" in flags or "MODE_BITSET" in flags:
        return []
    if "MODE_ARRAY" in flags:
        return [re.search(r"length\s*=\s*(.+)", cfg).group(1).strip()]
    if "VAR_UINT32" in flags and "MODE_STRING" not in flags:
        return ["0", bound_exprs(cfg)[0].strip()]
    return [e.strip() for e in bound_exprs(cfg)]


def idents(expr):
    return set(re.findall(r"\b[A-Za-z_]\w*\b", expr))


class Resolver:
    """Turns range expressions into numbers when every build that compiles the row agrees.

    Symbols defined differently per target or feature set stay symbolic and are listed in
    `constants`, with each definition and the condition it applies under.
    """

    def __init__(self, src):
        self.src = src
        self.sites = src.macro_sites()
        self.gated_enum = src.gated_enum_members()
        self.symbolic = set()
        self.values = {}

    def classify(self, ident, seen=()):
        """None if ident has one value in every build; otherwise a note or a list of definitions."""
        if ident in TARGET_DEPENDENT:
            return "target-dependent"
        sites = self.sites.get(ident, [])
        if any(path.startswith(TARGET_DIRS) for _, _, path in sites):
            return "target-dependent"
        if not sites:
            return "depends on enabled features" if ident in self.gated_enum else None
        unique = self.unique_sites(ident)
        if len(unique) == 1 and not unique[0][1]:
            body = unique[0][0]
            nested = [i for i in idents(body) if i not in seen and self.classify(i, seen + (ident,))]
            return f"= {body}" if nested else None
        return sorted(unique, key=lambda u: u[1])

    def unique_sites(self, ident):
        return list({(body, tuple(conds)) for body, conds, _ in self.sites.get(ident, [])})

    def plan(self, expr, row):
        """Expression with row-determined symbols substituted, or None if it stays symbolic.

        Single-definition macros are inlined too, so the compiler does not need the
        (possibly feature-gated) header that defines them.
        """
        for _ in range(64):
            open_symbols = []
            for ident in sorted(idents(expr)):
                kind = self.classify(ident)
                if kind is None:
                    sites = self.unique_sites(ident)
                    if len(sites) == 1 and sites[0][0]:
                        expr = re.sub(rf"\b{ident}\b", f"({sites[0][0]})", expr)
                        break
                    continue
                if isinstance(kind, list):
                    overridable = any(conds == ("!" + ident,) for _, conds in kind)
                    picked = [body for body, conds in kind if set(conds) <= set(row["conds"])]
                    if not overridable and len({body for body, _ in kind}) == 1:
                        picked = [kind[0][0]]  # the only value any build that compiles the row can see
                    if len(picked) == 1:
                        expr = re.sub(rf"\b{ident}\b", f"({picked[0]})", expr)
                        break
                open_symbols.append(ident)
            else:
                if open_symbols:
                    self.symbolic.update(open_symbols)
                    return None
                return expr
        return None

    def resolve(self, rows):
        planned = {}
        for row in rows:
            for e in row_exprs(row):
                planned[(e, gate_str(row["conds"]))] = self.plan(e, row)
        pending = {p for p in planned.values() if p and idents(p)}
        for ident in list(self.symbolic):
            self.note_nested(ident)
        for ident in self.symbolic:
            kind = self.classify(ident)
            if isinstance(kind, list):
                pending |= {body for body, _ in kind if body and not self.classify_expr(body)}
        self.values = self.src.eval_exprs(pending)
        for (e, gate), p in planned.items():
            if p is not None and not idents(p):
                self.values[p] = int(eval_literal(p))
        self.planned = planned

    def note_nested(self, ident, seen=()):
        kind = self.classify(ident)
        if isinstance(kind, str) and kind.startswith("= "):
            for i in idents(kind):
                if i not in seen and self.classify(i):
                    self.symbolic.add(i)
                    self.note_nested(i, seen + (ident,))

    def classify_expr(self, expr):
        return [i for i in idents(expr) if self.classify(i)]

    def num(self, expr, row):
        expr = expr.strip()
        if re.fullmatch(r"-?\d+", expr):
            return int(expr)
        planned = self.planned.get((expr, gate_str(row["conds"])))
        if planned is not None and planned in self.values:
            return self.values[planned]
        if planned is not None:  # compiler could not evaluate it
            self.symbolic.update(i for i in idents(expr) if not self.classify(i))
        return expr

    def constants(self):
        out = {}
        for ident in sorted(self.symbolic):
            kind = self.classify(ident)
            if kind is None:
                kind = "not resolvable from the SITL headers"
            if isinstance(kind, list):
                kind = [{"value": self.values.get(body, int(body) if re.fullmatch(r"-?\d+", body) else body),
                         "gate": "default" if conds == ("!" + ident,) else gate_str(list(conds)) or "always"}
                        for body, conds in kind]
            out[ident] = [kind]
        return out


def eval_literal(expr):
    """Evaluate a C integer literal expression that has no identifiers."""
    return eval(re.sub(r"(?<=\d)[uUlL]+\b", "", expr).replace("/", "//"), {"__builtins__": {}})


def parse_wiki(path):
    """Read `name = value` lines (any wiki dump format).

    Prose is collected only after Markdown-emphasized headers (`**name** = value`, the 4.0 page
    style); plain `get` dumps have none, and page chrome after them must not become a description.
    """
    defaults, descriptions, current = {}, {}, None
    header = re.compile(r"^[*_\\]*((?=\w*[a-z])[A-Za-z0-9]\w*)[*_\\ ]*(?:=\s*(.*?))?[*_\s]*$")
    for raw in open(path):
        line = raw.strip()
        m = header.match(line)
        if m and (m.group(2) is not None or line.startswith(("**", "_"))):
            current = m.group(1) if line.startswith(("**", "_")) else None
            if m.group(2) is not None and m.group(1) not in defaults:
                defaults[m.group(1)] = m.group(2).strip("*_ ")
            continue
        if line.startswith("#") or line.startswith("```"):
            current = None
            continue
        if (not current or not line or re.match(r"(Allowed (range|values)|Array length|String length):", line)
                or re.fullmatch(r"(profile|rateprofile|battery_profile) \d+", line)
                or re.fullmatch(r"[A-Za-z0-9]+(-[A-Za-z0-9]+)+", line)):
            continue
        descriptions.setdefault(current, []).append(line)
    return defaults, {k: "\n".join(v) for k, v in descriptions.items()}


def previous_wiki_fields(previous):
    """`default` / `description` from an existing reference, reused when no --wiki is given."""
    defaults, descriptions = {}, {}
    for name, entry in (previous.get("parameters") or {}).items():
        first = entry[0] if isinstance(entry, list) else entry
        if "default" in first:
            defaults[name] = str(first["default"])
        if "description" in first:
            descriptions[name] = first["description"]
    return defaults, descriptions


def scalar(value):
    return int(value) if re.fullmatch(r"-?\d+", value) else value


class OneLineDumper(yaml.SafeDumper):
    """Double-quotes multi-line strings so each entry stays on one line (newlines become \\n)."""


OneLineDumper.add_representer(str, lambda d, s: d.represent_scalar(
    "tag:yaml.org,2002:str", s, style='"' if "\n" in s else None))


def flow(value):
    text = yaml.dump(value, Dumper=OneLineDumper, default_flow_style=True, width=float("inf"),
                     sort_keys=False, allow_unicode=True).strip()
    return text.removesuffix("\n...").strip()


def entries_block(items, key_pattern=r"[A-Za-z0-9_]+"):
    lines = []
    for name in sorted(items):
        if name.lower() in YAML_RESERVED or not re.fullmatch(key_pattern, name):
            sys.exit(f"unsafe key: {name}")
        variants = items[name]
        lines.append(f"  {name}: {flow(variants[0] if len(variants) == 1 else variants)}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("checkout")
    ap.add_argument("out")
    ap.add_argument("--wiki")
    a = ap.parse_args()

    src = Source(a.checkout)
    git = lambda *args: subprocess.run(["git", "-C", a.checkout, *args], capture_output=True,
                                       text=True, check=True).stdout.strip()
    ref = git("rev-parse", "--abbrev-ref", "HEAD")
    commit, date = git("log", "-1", "--format=%h %cs").split()
    previous = yaml.safe_load(open(a.out)) if os.path.exists(a.out) else {}

    rows, tables = src.params(), src.lookup_tables()
    resolver = Resolver(src)
    resolver.resolve(rows)
    if a.wiki:
        defaults, descriptions = parse_wiki(a.wiki)
    else:
        defaults, descriptions = previous_wiki_fields(previous)

    params = {}
    for row in rows:
        entry = describe(row, tables, resolver.num)
        if row["name"] in defaults:
            entry["default"] = scalar(defaults[row["name"]])
        if row["name"] in descriptions:
            entry["description"] = descriptions[row["name"]]
        if row["conds"]:
            entry["gate"] = gate_str(row["conds"])
        params.setdefault(row["name"], []).append(entry)

    commands = {}
    for cmd in src.commands():
        entry = {k: cmd[k] for k in ("description", "args") if cmd[k]}
        if cmd["conds"]:
            entry["gate"] = gate_str(cmd["conds"])
        commands.setdefault(cmd["name"], []).append(entry)

    head = {
        "version": ref.removesuffix("-maintenance"),
        "source": {"repo": "betaflight/betaflight", "ref": ref, "commit": commit, "date": date},
        "wiki": previous.get("wiki"),
        "notes": previous.get("notes") or [],
    }
    tables_text = "\n".join([
        f"modes: {flow(src.modes())}",
        f"osd_warnings: {flow(src.bit_names('osdWarningsFlags_e', 'OSD_WARNING_'))}",
        f"osd_stats: {flow(src.bit_names('osd_stats_e', 'OSD_STAT_'))}",
    ])
    text = "\n".join([
        f"# Generated by .claude/skills/cli-mirror-maintenance/cli-reference.py from {ref}@{commit}. Edit only `wiki` and `notes`.",
        yaml.safe_dump(head, sort_keys=False, width=float("inf"), allow_unicode=True).strip(),
        tables_text,
        "constants:", entries_block(resolver.constants(), key_pattern=r"[A-Z0-9_]+"),
        "commands:", entries_block(commands),
        "parameters:", entries_block(params), "",
    ])
    if yaml.safe_load(text)["parameters"].keys() != params.keys():
        sys.exit("round-trip check failed")
    open(a.out, "w").write(text)
    print(f"{a.out}: {len(params)} parameters ({len(rows)} rows), {len(commands)} commands, "
          f"{len(resolver.symbolic)} symbolic constants, wiki defaults {sum(n in params for n in defaults)}/{len(defaults)}")


if __name__ == "__main__":
    main()
