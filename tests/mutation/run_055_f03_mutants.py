"""Rule 12 driver for 055 F03 (exec/paper_loop durable integration). Fakes only.

A mutant counts as killed only when pytest's JUnit report shows a FAILURE (never an error) in its
intended test whose message is an assertion (AssertionError / "assert" / pytest's "DID NOT RAISE")
containing the intended witness text. An unmutated control run must be fully green first, and each
mutated file's bytes are verified restored afterwards.
"""
import hashlib
import pathlib
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[2]
PL, RT, RN = ROOT / "exec" / "paper_loop.py", ROOT / "scripts" / "ops_runtime.py", ROOT / "scripts" / "ops_runner.py"
MUTS = {
    "random client ids": ("intent = OrderIntent(client_order_id(owner, today, order.ticker, side), order.ticker, order.delta_quantity)",
                          "import uuid; intent = OrderIntent(uuid.uuid4().hex, order.ticker, order.delta_quantity)"),
    "send before persist": ("            try:\n                durable.persist()\n            except Exception as exc:  # noqa: BLE001 - any persist failure means \"do not send\"\n                raise PersistFailed(f\"state not persisted ({type(exc).__name__}); order not sent\") from None\n        return client.submit_market_on_open(intent)",
                            "            result = client.submit_market_on_open(intent)\n            durable.persist()\n            return result\n        return client.submit_market_on_open(intent)"),
    "intent not recorded": ("            record_intent(durable.intents_dir, intent.client_order_id,", "            (lambda *a: None)(durable.intents_dir, intent.client_order_id,"),
    "persist failure keeps sending": ("            halted_by_persist = True", "            halted_by_persist = False"),
    "unsent reservation kept open": ("            gate.record_order_outcome(intent.client_order_id, terminal=True, reason=\"NOT_SENT_PERSIST_FAILED\",\n                                      now=now_fn())\n", ""),
    "unknown reservations ignored": ("    if unresolved:\n        raise RunAborted(", "    if False:\n        raise RunAborted("),
    "account not verified": ("        if not number or hashlib.sha256(number.encode()).hexdigest() != profile.account_fingerprint:", "        if False:"),
    "earlier deployment ignored": ("            deployed_today_usd=_deployed_today(durable, today), min_notional_usd=1.0)", "            deployed_today_usd=0.0, min_notional_usd=1.0)"),
    "cli submits without persist": ("    if args.submit and profile is not None and not args.persist_command:", "    if False:"),
}
MUTS.update({
    "namespace not checked": (PL, '        namespace = require_storage_identifier(profile.log_namespace, "log_namespace")',
                              "        namespace = profile.log_namespace"),
    "lease name not checked": (RT, 'f"{require_storage_identifier(profile)}-{session.isoformat()}.json"',
                               'f"{profile}-{session.isoformat()}.json"'),
    "runner profile not checked": (RN, "    require_storage_identifier(profile)  # names lease and outbox files",
                                   "    (lambda _p: None)(profile)  # names lease and outbox files"),
    "device names allowed": (RT, " or value in _WINDOWS_DEVICES:", ":"),
    "redirected folder accepted": (PL, "    if base.resolve() != root.resolve() / namespace:",
                                   "    if base.resolve().parent != root.resolve():"),
    "gate DB leaf redirect accepted": (PL, "    if gate.resolve() != base.resolve() / gate.name:", "    if False:"),
    "run-log leaf redirect accepted": (PL, "    if runs.resolve() != base.resolve() / runs.name:", "    if False:"),
})
# mutant -> (intended test-name prefix, required text in the assertion message)
WITNESS = {
    "random client ids": ("test_client_ids_are_deterministic", "AssertionError"),
    "send before persist": ("test_each_send_happens_only_after", "ORDERING: broker send happened before any successful durable persist"),
    "intent not recorded": ("test_each_send_happens_only_after", "in set()"),
    "persist failure keeps sending": ("test_failed_persist_sends_nothing", "ORDERING: order sent although its persist failed"),
    "unsent reservation kept open": ("test_failed_persist_sends_nothing", "all("),
    "unknown reservations ignored": ("test_restart_with_an_unknown_reservation", "DID NOT RAISE"),
    "account not verified": ("test_credentials_for_another_account", "DID NOT RAISE"),
    "earlier deployment ignored": ("test_daily_deployment_counts_earlier", "assert ("),
    "cli submits without persist": ("test_workflow_gives_the_paper_loop", "CLI: reached broker or network"),
    # The resolved-folder guard also refuses the Codex alias, so the identifier check is witnessed by a
    # case only it can refuse (an uppercase name resolves to itself).
    "namespace not checked": ("test_any_non_identifier_namespace_is_refused[Paper_Small]", "DID NOT RAISE"),
    "lease name not checked": ("test_lease_refuses_non_identifier_profiles", "DID NOT RAISE"),
    "runner profile not checked": ("test_runner_refuses_non_identifier_profiles", "DID NOT RAISE"),
    # Lease names never touch resolve(), so this witness holds on Windows too (where con may resolve to a device).
    "device names allowed": ("test_lease_refuses_non_identifier_profiles[nul]", "DID NOT RAISE"),
    "redirected folder accepted": ("test_profile_dir_redirected_to_a_sibling_is_refused", "DID NOT RAISE"),
    "gate DB leaf redirect accepted": ("test_a_leaf_redirected_into_a_sibling_profile_is_refused[paper-gate.sqlite]",
                                       "DID NOT RAISE"),
    "run-log leaf redirect accepted": ("test_a_leaf_redirected_into_a_sibling_profile_is_refused[paper-runs]",
                                       "DID NOT RAISE"),
}
FILES = ["tests/test_055_paper_loop_durable.py", "tests/test_049_paper_loop.py",
         "tests/test_051_paper_loop_profile.py", "tests/test_055_storage_identifiers.py"]
ASSERTION = ("AssertionError", "assert ", "Failed: DID NOT RAISE")


def junit() -> list[tuple[str, str, str]]:
    """(kind, testcase name, message) for every failure/error in one pytest run."""
    with tempfile.TemporaryDirectory() as tmp:
        report = pathlib.Path(tmp) / "junit.xml"
        subprocess.run([sys.executable, "-B", "-m", "pytest", *FILES, "-q", "-p", "no:cacheprovider",
                        f"--junitxml={report}"], capture_output=True, cwd=ROOT)
        cases = list(ET.parse(report).iter("testcase"))
    return [(kind, case.get("name", ""), el.get("message") or "")
            for case in cases for kind in ("failure", "error") for el in case.findall(kind)]


control = junit()
assert not control, f"control run is not green: {control[:3]}"
assert set(WITNESS) == set(MUTS), sorted(set(WITNESS) ^ set(MUTS))
killed = 0
for name, spec in MUTS.items():
    path, a, b = spec if len(spec) == 3 else (PL, *spec)
    orig = path.read_bytes()
    text = orig.decode("utf-8")
    assert text.count(a) == 1, name
    path.write_bytes(text.replace(a, b).encode("utf-8"))
    try:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")  # a mutant must still be valid Python
        results = junit()
    finally:
        path.write_bytes(orig)
    assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(orig).digest(), f"{name}: source not restored"
    prefix, witness = WITNESS[name]
    ok = not any(kind == "error" for kind, _, _ in results) and any(
        kind == "failure" and test.startswith(prefix) and message.startswith(ASSERTION) and witness in message
        for kind, test, message in results)
    killed += ok
    print(("KILLED  " if ok else "SURVIVED"), name)
print(f"{killed}/{len(MUTS)} killed (control green, sources restored)")
sys.exit(0 if killed == len(MUTS) else 1)
