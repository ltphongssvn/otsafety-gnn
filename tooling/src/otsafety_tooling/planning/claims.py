# tooling/src/otsafety_tooling/planning/claims.py
"""A step's title may not promise what its evidence cannot observe.

THE DEFECT THIS EXISTS FOR. A step titled "computed from evidence and
attested" declared a task, a Rego rule and a test as its acceptance criteria --
none of which can see a signature. It closed on a claim nothing tested, and
only reading it caught that.

MECHANICAL, NOT SEMANTIC. Judging whether a test really asserts a requirement
needs a reader, and a gate here cannot have one: no gate reaches the network.
This is narrower and decidable -- certain words name a KIND of evidence, and a
title using one must carry evidence of that kind. Finding an id in a test name
proves traceability formatting rather than that the test asserts anything, so
this checks the vocabulary and claims nothing more.

AND THE VOCABULARY IS NOT A PREFERENCE. "Attested" and "signed" are defined
here: E.37 says a DSSE envelope over an in-toto statement, logged for
transparency. A step claiming one and proving it with a file path says
something a reader believes and nothing checks.

NO KIND CAN PROVE A SIGNATURE TODAY. The contract offers pr, release, path,
task and proof; none observes an envelope. So a promise of one is refused
outright rather than redirected to a kind that cannot carry it -- a rule
satisfiable only by declaring impossible evidence would be worse than none.
"""

from __future__ import annotations

from collections.abc import Mapping

# THE WORDS THAT NAME A SIGNATURE, and the kinds that could observe one. The
# set is empty until the contract can express an attestation, which is why a
# title using these words is refused rather than redirected.
SIGNATURE_WORDS = frozenset({"attested", "attestation", "signed", "countersigned"})
SEES_A_SIGNATURE: frozenset[str] = frozenset()

# A DEFINITION IS NOT A CLAIM. "Signed means a DSSE envelope over an in-toto
# statement" states what the word denotes here; the step's whole product IS the
# definition, and nothing was signed. A scanner carrying a known false positive
# gets suppressed wholesale within a week, so this is excluded -- and the
# exclusion is as mechanical as the rule: the word is followed by "means".
DEFINES = "means"


def overclaimed(step: Mapping[str, object]) -> tuple[str, ...]:
    """The words in this step's title that its evidence cannot support.

    A WORD IS MATCHED WHOLE. "Signed" appears inside "designed", and a scanner
    flagging that would be ignored within a week -- which is how an
    overclaiming check stops being read.
    """
    title = str(step.get("title", "")).casefold()
    words = [word.strip(".,:;()") for word in title.split()]

    promised = sorted(
        {
            word
            for index, word in enumerate(words)
            if word in SIGNATURE_WORDS
            # THE NEXT WORD DECIDES: a definition says what the term means,
            # where a claim says something was done to a thing.
            and words[index + 1 : index + 2] != [DEFINES]
        }
    )
    if not promised:
        return ()

    declared = step.get("done_when")
    kinds = {
        str(item.get("kind"))
        for item in (declared if isinstance(declared, list) else [])
        if isinstance(item, Mapping)
    }
    if kinds & SEES_A_SIGNATURE:
        return ()
    return tuple(promised)
