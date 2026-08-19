# Taxonomy for labeling the CI failures

Use this doc to declare how each CI failures is categorized to a certain label. Each label should consist:
- A clear definition: in plain language
- A decision rules: concrete, checkable test. Should be determinstic. If passed to another, should expect the
same result
- A clear case: one unambiguous case
- An Edge case - a case that's genuinely hard within this label
- Nearest-neighbor distinction: which other label this one most often confused with, and the exact test that
separaretes them

This guide should give clear and concrete instruction on how to differentiate between the CI labels.

## flaky-test

### Definition
A failure due to an non deterministic nature of a test. Some test/s can produce different result on the same
run, simply because they depend on: timing, not guarenteed order, or specific condition that's not always present.

### Decision rules
1. 
    a.Is this a re-run of a previous commit which produced different result (no commit changes)
    OR 
    b. Does the diff summary shows that the code changes are unrelated to the failing bug and/or touch non code area?

Check the logs for failing test:

2. Log summary shows tests failed due to timeout of specific action of the test, distinguished from a timeout of the underlying infrastrucure to run the test.
    * To disinguish between test timeout and infratimeout - look for these signs:
        a. Has the test started, do we have notification that the test itself has timed out -> test fault
        b. Do we have keywords involving waiting for specific action, callback, request -> test fault
        c. The testing hasn't started yet -> infra fault
        d. Error contains messages about the runner itself timing out -> infra fault
        e. Messages about waiting for resources to set up the runner -> infra fault
    

If and only if condition 1 + 2 - apply flaky-test


### Clear case example
"log_excerpt": "FAIL src/components/Modal.test.tsx\n  \u2715 closes when Escape is pressed (312 ms)\n  Timeout - Async callback was not invoked within the 5000ms timeout", "diff_summary": "No changes to Modal.tsx in this PR; unrelated CSS refactor in Button.tsx."

**Explanation**
clear case - the tests waits on a timing of an action that didn't occur on time. the diff summary show no logical changes for this model

### Edge case example
"log_excerpt": "FAIL src/hooks/useDebounce.test.ts\n  \u2715 debounces rapid calls (5023 ms)\n  thrown: \"Exceeded timeout of 5000ms for a test.\"", "diff_summary": "Moved debounce module to a new dir"

**Explanation**
Looks suspicious because the tests fail in area where there were recent changes. Requires close examination of they type of errors we exepect from the change vs what the test really tests. In this case, moving a module more likey to produce compliation errors, maybe depenecy or env error, but not timing.

### Nearest-neighbor distinction
- real-regression: depending on the nature of the change and test, guidelines to distinguish:
    a. Is the diff affects the code the test is checking, is so - a hint that the change caused by a regression
    b. Is the nature of the test is not deterministic (timing, precondition, external input) - a hint towards a direction of flaky-test


## Known Gaps
- External resource unreachable, single-run only: deferred from flaky-test, needs an explicit home when writing config-error / real-regression.