# 054 U1 evidence, 2026-10-07 (Linux, Python 3.13.16)

Red first: collection failed (module absent). Green: 8 passed. Fixtures are synthetic,
shaped like real Fidelity exports (CRLF, preamble blanks, cash sweep row, Pending Activity,
quoted disclaimer, "Date downloaded" footer). Camden's own History export also parsed privately
(1 row, $100 cash); nothing from it is committed.
| Mutant | Result |
|---|---|
| footer/disclaimer parsed as rows | killed |
| missing download time accepted | killed |
| raw account number kept | killed |
| non-numeric value silently zero | killed |
| Pending Activity kept as a position | killed |
