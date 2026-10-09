"""Rule 12 driver for 055 F03 (exec/paper_loop durable integration). Fakes only."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
p = ROOT / "exec" / "paper_loop.py"
orig = p.read_text()
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
killed = 0
for name, (a, b) in MUTS.items():
    assert orig.count(a) == 1, name
    p.write_text(orig.replace(a, b))
    try:
        r = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_055_paper_loop_durable.py", "tests/test_049_paper_loop.py",
                            "tests/test_051_paper_loop_profile.py", "-q", "-p", "no:cacheprovider"], capture_output=True, cwd=ROOT)
    finally:
        p.write_text(orig)
    ok = r.returncode != 0
    killed += ok
    print(("KILLED  " if ok else "SURVIVED"), name)
print(f"{killed}/{len(MUTS)} killed")
sys.exit(0 if killed == len(MUTS) else 1)
