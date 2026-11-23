"""STAT: the recipe printed in docs/model/stat.md is run here, as printed.

A code block in a document nothing runs goes stale without anyone seeing it. This test takes the
block under "Handing a detector to the check" out of the page and executes it, then repeats its
last steps with one tap negated.

The page states the counts it saw on 2026-11-23 (99,944 and 97,245 of 200,000). They are printed
here, not asserted: they are exact only for one numpy's generator. What is asserted is the verdict,
which a correct implementation gets wrong with probability 6.3e-5 over seeds (the first) and below
1e-15 (the second).
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def recipe():
    with open(os.path.join(ROOT, "docs", "model", "stat.md"), encoding="utf-8") as f:
        text = f.read()
    section = text.split("## Handing a detector to the check", 1)[1].split("\n## ", 1)[0]
    assert section.count("```python\n") == 1, "the section must hold exactly one python block"
    return section.split("```python\n", 1)[1].split("```", 1)[0]


def test_stat_the_recipe_in_the_doc_runs_as_printed_and_gives_the_verdicts_the_doc_states():
    code = recipe()
    assert "check_efficiency" in code and "recovery_count" in code and "threshold_known_sigma" in code
    ns = {}
    exec(compile(code, "docs/model/stat.md", "exec"), ns)
    verdict = ns["verdict"]
    print("\nthe recipe: found %d of %d, %+.1f se, inside %s" % (verdict["found"], verdict["n"], verdict["z_score"], verdict["inside"]))
    assert verdict["n"] == 200_000
    assert verdict["inside"] is True

    # The same steps with coeffs[51] negated before the filtering: the doc says it is then outside.
    coeffs = list(ns["coeffs"])
    assert coeffs[51] == 293
    coeffs[51] = -coeffs[51]
    scores = ns["matched"].matched_scores(ns["stream"], "s16x1", coeffs)
    threshold = ns["recovery"].threshold_known_sigma(ns["pfa"], ns["sigma"], coeffs)
    found = ns["recovery"].recovery_count(scores, ns["truth"], threshold, lag=ns["taps"] - 1,
                                          taps=ns["taps"], pulse_len=ns["taps"])
    wrong = ns["tolerance"].check_efficiency(found["at_index"], found["n"], ns["pfa"], ns["claimed_d"])
    print("with tap 51 negated: found %d of %d, %+.1f se, inside %s" % (wrong["found"], wrong["n"], wrong["z_score"], wrong["inside"]))
    assert wrong["inside"] is False
    assert wrong["z_score"] < -8.0, "the fault is predicted at -12.1 standard errors"
