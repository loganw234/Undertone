"""Three facts of rtl/core/core.sv's pool that no simulation can see, held by the file's text.

Parcel POOLRAM, round 5 (docs/rtl/poolram.md). Icarus Verilog ignores synthesis attributes, and a
register's reset that no record can reach is invisible to every bench. So what the out-of-context
synthesis of the core was run on is held here, as text:

  1. the pool's memory is marked for UltraRAM: `(* ram_style = "ultra" *)` is the line before
     `pool_mem`'s declaration, and the only `ram_style` in the file;
  2. the memory has one write and one read, the form of a simple dual-port memory: outside
     comments `pool_mem[` occurs exactly twice, as `pool_mem[pool_wp] <= s4_rect;` and
     `pool_q <= pool_mem[pool_rp];`;
  3. the read register `pool_q` has no reset: it is assigned once, and the block `st4_pool` that
     assigns it holds exactly the one line `if (!rst && vld[ST_S3]) pool_q <= pool_mem[pool_rp];`.

Each check is shown to report a fault planted in a copy of the text (`PLANTS`), one at a time.

WHAT IT CANNOT SEE: whether Vivado makes UltraRAM of this text, which is the lead's synthesis to
show; a comment that hides code from these checks by a form other than `//` (a block comment);
and anything about the memory but these three facts.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, "rtl", "core", "core.sv")

ATTRIBUTE = '(* ram_style = "ultra" *)'
DECLARATION = re.compile(r"^\s*logic \[B_FILTERS\*W_RECT-1:0\]\s+pool_mem \[0:B_POOL-1\];\s*$")
WRITE = "pool_mem[pool_wp] <= s4_rect;"
READ = "pool_q <= pool_mem[pool_rp];"
READ_LINE = "if (!rst && vld[ST_S3]) pool_q <= pool_mem[pool_rp];"
BLOCK = "always @(posedge clk) begin : st4_pool"


def code_of(line):
    """A line without its `//` comment."""
    return line.split("//", 1)[0]


def check_attribute(text):
    lines = text.split("\n")
    found = []
    at = [i for i, line in enumerate(lines) if DECLARATION.match(line)]
    if len(at) != 1:
        return ["pool_mem is declared %d time(s) in the form looked for" % len(at)]
    if at[0] == 0 or lines[at[0] - 1].strip() != ATTRIBUTE:
        found.append("the line before pool_mem's declaration is not %s" % ATTRIBUTE)
    n = sum(code_of(line).count("ram_style") for line in lines)
    if n != 1:
        found.append("ram_style occurs %d time(s) outside comments, not once" % n)
    return found


def check_one_write_one_read(text):
    code = "\n".join(code_of(line) for line in text.split("\n"))
    found = []
    if code.count("pool_mem[") != 2:
        found.append("pool_mem[ occurs %d time(s) outside comments, not twice" % code.count("pool_mem["))
    for what in (WRITE, READ):
        if code.count(what) != 1:
            found.append("%s occurs %d time(s) outside comments, not once" % (what, code.count(what)))
    return found


def check_read_register_unreset(text):
    code = [code_of(line).strip() for line in text.split("\n")]
    found = []
    assigned = [line for line in code if re.search(r"\bpool_q\s*<=", line)]
    if assigned != [READ_LINE]:
        found.append("pool_q is assigned by %s, not once by %s" % (assigned, READ_LINE))
    if code.count(BLOCK) != 1:
        found.append("the block st4_pool is written %d time(s)" % code.count(BLOCK))
        return found
    i = code.index(BLOCK)
    body = []
    for line in code[i + 1:]:
        if line == "end":
            break
        if line:
            body.append(line)
    if body != [READ_LINE]:
        found.append("the block st4_pool holds %s, not the one line %s" % (body, READ_LINE))
    return found


# (what is planted, the check that must report it, the text replaced, its replacement)
PLANTS = (
    ("the attribute removed", check_attribute, ATTRIBUTE + "\n", ""),
    ("the attribute asking for block RAM", check_attribute, ATTRIBUTE, '(* ram_style = "block" *)'),
    ("a second ram_style, on the read register", check_attribute,
     "    logic [B_FILTERS*W_RECT-1:0]   pool_q;", '    (* ram_style = "registers" *) logic [B_FILTERS*W_RECT-1:0]   pool_q;'),
    ("a second read of the memory", check_one_write_one_read,
     "fwd_val <= s4_rect;", "fwd_val <= pool_mem[pool_wp];"),
    ("the read from the write pointer", check_one_write_one_read, READ, "pool_q <= pool_mem[pool_wp];"),
    ("a reset of the read register", check_read_register_unreset,
     "        " + READ_LINE, "        if (rst) pool_q <= '0;\n        else " + READ_LINE),
    ("the read register's enable dropped", check_read_register_unreset, READ_LINE, READ),
    ("pool_q assigned a second time", check_read_register_unreset,
     "fwd_val <= s4_rect;", "fwd_val <= s4_rect; pool_q <= '0;"),
)


def shipped():
    with open(CORE, encoding="utf-8") as f:
        return f.read()


def test_poolram_marked_for_ultraram():
    assert check_attribute(shipped()) == []


def test_poolram_one_write_one_read():
    assert check_one_write_one_read(shipped()) == []


def test_poolram_read_register_has_no_reset():
    assert check_read_register_unreset(shipped()) == []


def test_poolram_each_plant_is_reported():
    text = shipped()
    for what, check, old, new in PLANTS:
        assert text.count(old) == 1, "the plant %r does not apply: %r occurs %d time(s)" % (what, old, text.count(old))
        planted = text.replace(old, new)
        found = check(planted)
        assert found, "%s: %s reported nothing" % (what, check.__name__)
        print("%s: %s" % (what, found))
