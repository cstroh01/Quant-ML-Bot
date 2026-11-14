"""Rule 12 driver for spec 067: the item 1 record's LF-bytes test must go red for each plausible regression."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
p = ROOT / "scripts" / "run_mutation_suite.py"
orig = p.read_text(encoding="utf-8")
orig_bytes = p.read_bytes()
WRITE = "    a.out.write_bytes(record_bytes(record))"
muts = {
    # The pre-067 line: text mode, so CRLF on Windows (and under the test's CRLF emulation anywhere).
    "write_text again": (WRITE, '    a.out.write_text(json.dumps(record, indent=1) + "\\n", encoding="utf-8")'),
    # The other everyday text-mode write: builtin open without newline="\n".
    "open in text mode": (WRITE, '    with open(a.out, "w", encoding="utf-8") as f:\n        f.write(record_bytes(record).decode("utf-8"))'),
    # The digest taken over the text before writing, not over the bytes on disk.
    "digest over unterminated text": ("    digest = hashlib.sha256(a.out.read_bytes()).hexdigest()",
                                      "    digest = hashlib.sha256(json.dumps(record, indent=1).encode()).hexdigest()"),
}
for name, (a, _b) in muts.items():  # every anchor is checked before any mutant is written
    assert orig.count(a) == 1, name
killed = 0
try:
    for name, (a, b) in muts.items():
        p.write_bytes(orig.replace(a, b).encode("utf-8"))
        r = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_059_mutation_suite_runner.py", "-q",
                            "-p", "no:cacheprovider"], capture_output=True, cwd=ROOT)
        ok = r.returncode != 0
        killed += ok
        print(("KILLED  " if ok else "SURVIVED"), name)
finally:
    p.write_bytes(orig_bytes)  # a crash never leaves a mutant; exact bytes, so item 1 sees no change
print(f"{killed}/{len(muts)} killed")
sys.exit(0 if killed == len(muts) else 1)
