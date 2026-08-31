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
Looks suspicious because the tests fail in area where there were recent changes. Requires close examination of they type of errors we exepect from the change vs what the test really tests. In this case, moving a module more likey to produce compliation errors, maybe dependency or env error, but not timing.

### Nearest-neighbor distinction
- real-regression: depending on the nature of the change and test, guidelines to distinguish:
    a. Is the diff affects the code the test is checking, is so - a hint that the change caused by a regression
    b. Is the nature of the test is not deterministic (timing, precondition, external input) - a hint towards a direction of flaky-test


## dependency-or-env
### Definition
A CI fail due to a missing or misconfigured/misaligned environment. This includes missing libraries or non compatible
libraries. 

### Decisions rules
1. The log shows errors that complain about missing library
2. The log shows errors that complain about incompatible library (e.g. found x but need y or higher)
    
support evidence (not a must for a label, but add notes)
    a. The diff summary shows update to the project dependecy list, strong signal
    b. even stronger signal is that the dependency that the log complains about changed

3. The log complains about about missing tools or libraries that exist in one env, but not another (e.g. calling linux tools in windows host)
    to be precise, validate if we:
    - Have runner configuration and entries for the tested env build matrix
    - The runner configuration is matching the environment we're testing against

    if not both apply - it's a config error - we didn't select the correct os, or account for it
    if both apply and we have code diff - it's a real-regression
    if both apply AND we don't have code diff - it's a depenency-or-env issue - it wasn't caused due to env selection or code regression

If condition 3 applies - it takes precedency. otherwise if condition 1 or 2 applies mark as 'dependency-or-env' label

### Clear case example
missing dep: couldn't find module 'x' when... AND we see that module x is part of a lib that was removed from dependncy in the project requrements

### Edge case example
diff summary shows that package 'x' was upgraded to a newer version but there are code changes as well. Test 'y' fails, and he calls said lib. However, the test fails due to a logical error in a test and not as a result of call to the lib - real-regression label, not config or env.
**Note**
It's possible that changing the libraries may produce different logical result, but we'll consider this as a real-regression label rather than dependency-or-env as the root cause is related to the core logic of what we're testing

### Nearest-neighbor distinction
- config-error: configuration often dictate what environment or libraries we need to setup for the runner, a wrong configuration can lead to a wrong build. To disinguish - look for diff summary or log for config changes to control the environment - if found, and relate to the error we see, treat as config error.


## Known Gaps
- External resource unreachable, single-run only: deferred from flaky-test, needs an explicit home when writing config-error / real-regression.
- Configuration values, run parameters and environment changes can happen between runs. For a single run, we don't have historic data. If available, need to compare between successful and failed runs.
- Currently, the classifier doesn't receive the workflow yaml or build metadata directly, which can be a problem when classifying build config errors