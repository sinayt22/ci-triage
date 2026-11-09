# Taxonomy for labeling the CI failures

Use this doc to declare how each CI failure is categorized to a certain label. Each label should consist:
- A clear definition: in plain language
- A decision rules: concrete, checkable test. Should be deterministic. If passed to another, should expect the
  same result
- A clear case: one unambiguous case
- An Edge case - a case that's genuinely hard within this label
- Nearest-neighbor distinction: which other label this one most often confused with, and the exact test that
  separates them

This guide should give clear and concrete instruction on how to differentiate between the CI labels.

## General Scan - where to start
This section orients you. It points you to the labels whose decision rules you should check.
If the rules doesn't resolve, follow the label's rules or nearest-neighbor disinction.

### Step 0 - Is there a failure to classify?
Apply `unknown` (unknown label rule #3) when either of these are true:
Check unknown rule 3. If it applies, apply `unknown`. Otherwise, continue to step 1.

### Step 1 - Read the context fields first
| Field | What it tells you |
|---|---|
| `event`| `pull_request`: the diff is the PR, tested as a merge preview with the target branch. fork PRs get no secrets. `push`: the pushed commit(s). `schedule`: a nightly run - the diff is not what changed, suspect the environment. `workflow_dispatch`: started manually. |
| `run_attempt` | Greater than 1 means someone re-ran this one. Failing again on the same commit weakens flaky-test (if you have historic information on the same run)|
| `failed_step_name` | The layer that broke - see step 2 |
| `diff_summary` | Classify what the diff touches: product code / tests / dependency files (requirements, lockfile, pyproejct) / CI config (`.github/`) / docs only / nothing. |
| `workflow_config` | Which steps exists, the matrix, secrets used, timeout, `continue on error`. |

### Step 2 - Which layer failed?
Map the failed step to a layer and start with the label in the middle column.
| Layer (typical step names) | Start with | Common alternatives
|---|---|---|
| Run never started: no jobs, "Invalid workflow file", startup failure | config-error | - |
| Set up job (runner provisioning, downloading actions) | infra-error | config-error if an action or ref doesn't exist |
| Checkout, cache restore, toolchain setup (setup-python, setup-node, ...) | infra-error for network errors, 5xx, timeouts | dependency-or-env if a requested version isn't available, config-error for a typo or invalid input |
| Install dependencies/build (pip, uv, npm, compiling) | dependency-or-env | real-regression if the diff broke the build code itself (C sources, build scripts) |
| static checks (lint, format, type check, docs build) | real-regression if the flagged lines are in files the diff touched | dependecy-or-env if the checker's version changed and it flags untouched code. config-error if the checker's own config is broken |
| Tests | real-regression vs flaky-test | infra-error (a service the tests need is unreachable), config-error (missing secret or parameter), dependecy-or-env (import errors) |  
| Upload / public / deploy | config-error (tokens, secrets, permissions) | infra-error (third party service down) |

## flaky-test

### Definition
A failure due to an non deterministic nature of a test. Some test/s can produce different result on the same
run, simply because they depend on: timing, not guaranteed order, or specific condition that's not always present.

### Decision rules
1.
    a. Is this a re-run of a previous commit which produced different result (no commit changes)
OR
    b. Does the diff summary shows that the code changes are unrelated to the failing bug and/or touch non code area?
    Check the logs for failing test

2. Log summary shows tests failed due to timeout of specific action of the test, distinguished from a timeout of the underlying infrastructure to run the test.
    * Apply infra-error's origin tests. If test-origin, continue below:
    * Do we have keywords involving waiting for specific action, callback, request:
        - Check build configuration according to the config-error label rules
        if not applies:
        - Check whether necessary infrastrucure was available - if not -> infra fault
        if not applies:
        - apply flaky-test


3. Logs shows that a test is failing due to certain input is not in expected order.
    - If the code logic itself supports different order or agnostic to it - apply flaky-test, otherwise check for real-regression label conditions.
4. Logs shows that a test is failing due to a certain unmet condition, check for:
    - If the condition relate to library/tool use - check for env-or-dependency label conditions.
    - If the condition relates to certain unset flag or wrong test parameter - check for config-error conditions.
    - If the condition is related to missing infrastructure - check for config-error conditions.
    - If the condition is related to the code of the test itself and the diff summary shows changes related to the code of the test - check for real-regression.
    - If none of the above apply unknown.

If condition 1 + 2 - apply flaky-test. Or if condition 3 or 4 resolve to flaky-test.

### Clear case example
"log_excerpt": "FAIL src/components/Modal.test.tsx\n  ✕ closes when Escape is pressed (312 ms)\n  Timeout - Async callback was not invoked within the 5000ms timeout", "diff_summary": "No changes to Modal.tsx in this PR; unrelated CSS refactor in Button.tsx."

**Explanation**
clear case - the tests waits on a timing of an action that didn't occur on time. the diff summary show no logical changes for this model

### Edge case example
"log_excerpt": "FAIL src/hooks/useDebounce.test.ts\n  ✕ debounces rapid calls (5023 ms)\n  thrown: \"Exceeded timeout of 5000ms for a test.\"", "diff_summary": "Moved debounce module to a new dir"

**Explanation**
Looks suspicious because the tests fail in area where there were recent changes. Requires close examination of the type of errors we expect from the change vs what the test really tests. In this case, moving a module more likely to produce compilation errors, maybe dependency or env error, but not timing.

### Nearest-neighbor distinction
- real-regression: depending on the nature of the change and test, guidelines to distinguish:
    - Is the diff affects the code the test is checking, if so - a hint that the change caused by a regression
    - Is the nature of the test is not deterministic (timing, precondition, external input) - a hint towards a direction of flaky-test

## dependency-or-env

### Definition
A CI fail due to a missing or misconfigured/misaligned environment. This includes missing libraries or non compatible
libraries.

### Decision rules
1. The log shows errors that complain about missing library
2. The log shows errors that complain about incompatible library (e.g. found x but need y or higher)

    support evidence (not a must for a label, but add notes):
    - The diff summary shows update to the project dependency list, strong signal
    - even stronger signal is that the dependency that the log complains about changed

3. The log complains about missing tools or libraries that exist in one env, but not another (e.g. calling linux tools in windows host)
    to be precise, validate if we:
    - Have runner configuration and entries for the tested env build matrix
    - The runner configuration is matching the environment we're testing against

    if not both apply - it's a config error - we didn't select the correct os, or account for it.
    if both apply and we have code diff - it's a real-regression.
    if both apply AND we don't have code diff - it's a dependency-or-env issue - it wasn't caused due to env selection or code regression.

If condition 3 applies - it takes precedence. otherwise if condition 1 or 2 applies mark as 'dependency-or-env' label

### Clear case example
missing dep: couldn't find module 'x' when... AND we see that module x is part of a lib that was removed from dependency in the project requirements

### Edge case example
diff summary shows that package 'x' was upgraded to a newer version but there are code changes as well. Test 'y' fails, and he calls said lib. However, the test fails due to a logical error in a test and not as a result of call to the lib - real-regression label, not config or env.

**Note**
It's possible that changing the libraries may produce different logical result, but we'll consider this as a real-regression label rather than dependency-or-env as the root cause is related to the core logic of what we're testing

### Nearest-neighbor distinction
- config-error: configuration often dictate what environment or libraries we need to setup for the runner, a wrong configuration can lead to a wrong build. To distinguish - see rule 3 above for the exact test.

## real-regression

### Definition
The build failed due to changes introduced in the latest patch. There's no problem in the infrastructure of the build
or its test - it functions as it should and could a true positive of when a breaking change occurred.

### Decision rules

1. The log excerpt show that tests fail due to assertions or timeout AND we have code changes in diff summary that may affect the code being tested - apply real-regression.
If timeout errors and no code changes - apply criteria by flaky-test rule 2.

2. If dependency-or-env rule 3 applies (runner config exists and correct and code diff present) -> apply real-regression. Otherwise if rule 3 resolves to config-error or dependency-or-env, this rule doesn't apply - use that label.

3. If we have assertion tests fails, not related to env errors, but without code changes relavant to the code the test checks = apply unknown.


### Clear case example
A change to function 'y' logic in log excerpt, unit tests that checks function 'y' logic (not timing) fail related to said logic

### Edge case example
A timeout error in a test, but caused due to real regression because the call to a certain function never returns. Diff summary shows a change to how the call is being made. Should not be confused with flaky-test as in this case the diff summary shows that the timeout can be related to the change that was introduced.

### Nearest-neighbor distinction
- flaky-test: when assertion fails, we need to consider carefully on whether the test is faulty or it's a result of a
  change we introduced. A lot of time, historic runs help distinguish this (test that always succeeds suddenly fails), but, even without historic data, we should assume that if we introduced a change that logically affects the test, we should first check for regression


## infra-error
### Definition
The build fails because a component outside the repository's code and configuration failed or was unavailable during the run: the runner, the network, a package registry, or a service the job connects to. It can show as a timeout or as another error: a refused or reset connection, a 5xx response, the runner losing communication or shutting down, a process killed for lack of memory, or a service rejecting connections because a limit was reached.

### Decision rules
1. The log excerpt shows timeout errors, that origin from components that are related to the run itself, not from tests that test the code. To distinguish between test timeout and infra timeout - look for these signs by order of relevance:
    - Messages about waiting for resources to set up the runner -> infra fault
    - Error contains messages about the runner itself timing out -> infra fault
    - The testing hasn't started yet -> infra fault
    - Has the test started, do we have notification that the test is waiting for a specific action, callback, request -> check for flaky-test rule 2
    - If none of the above signs are present in the log -> cannot determine origin from a single run -> apply unknown
2. The log excerpt shows a non-timeout error that originates outside the repository’s code: a runner message (“The runner has received a shutdown signal”, “lost communication with the server”), a refused or reset connection, a DNS failure, a 5xx response from a registry, download or API, a process killed for lack of memory (exit code 137, Killed), or a service rejecting connections because a limit was reached (e.g. too many connections) → infra-error.

### Clear case example
Timeout error when trying to connect to repo to checkout the code - infra-error

### Edge case example
Timeout error accessing a db - preflight check in the runner says db unavailable and times out, the code itself trying to access the resource
and times out. First we check configuration, it exists and correct, so moving to check the conditions for the infra-error - preflight says db should be available, but it times out, no need to continue checking - apply infra-error. If preflight check for a db shows healthy, but code reaches timeout accessing db -> apply flaky-test.

### Nearest-neighbor distinction
- flaky-test: timeout errors coming from flaky-test needs to be distinguished from infra timeouts. They will both contain keywords related to timeout, but we need to consider the origin of the timeout itself.

## config-error
### Definition
A build fails due to wrong or missing configuration. Configuration errors can manifest in different forms:
- Wrong/missing environment
- Wrong/missing paramenters
- Wrong/missing credentials
- Wrong/missing resources

### Decision rules
The configuration must be present in some form - either in logs or as additional parameter, if it's absent, skip to other labels, as we have
no way to verify that. Then check:
1. Log complains about wrong missing/wrong environment - check dependency-or-env label rule 3 to deterimine label.
2. Log complains about test asseration caused by wrong test parameters. Check the test configuration and is it matching the intented the build setup. If not apply config-error
3. Log complains about wrong credentials - check configuration on what resources with credentials are needed and whether we have the proper configuration to pass them on. If not - apply config-error.
4. If log complains about missing resource, check the configuration on whether we have a list of resources that should be available and what the runner expects, there's a mismatch - apply config-error. If not - check infra-error rules. If they don't apply - apply unknown and state that resource was not available due to unknown reason.

### Clear case example
Configuration logs exists and show entries for windows and linux setups. The configuration shows that the build is running on windows machine, but the code runner envirnment itself is configured for a linux machine. Log complain about missing tools in environment -> rule 1 of config error shows to go to dependency or env rule 3 -> the configuration exists and there's a mismatch -> config-error

### Edge case example
Configuration logs exists and show entries for 2 different build setups - A and B. Setup A test config parameters is different from setup B. Setup B is chosen in configuration, while the test setup is chosen for A. Test fail on assertions. rule 2 of config-error applies - apply config-error. If we're checking from the flaky-test path rule 4 -> will lead to config-error

### Nearest-neighbor distinction
- flaky-test: config errors can manifest in tests failing seemingly randomly. Problem accessing resources, wrong test parameters - can originate from configuration problem. Need to check first configuration is correct and matching.

## unknown
### Definition
The build fails with ambiguity, we cannot determine the exact label fit after investigating all other labels and reasoning why they don't apply.

1. Apply unknown only if the other five lable's rules were checked and none resolves the case and you canot commit to them with reasonable confidence, provide evidence to your decision.  
OR
2. one of the lable's rules explicitly stated to mark as unknown. 

When setting as unknown - provide evidence to reasoning - if debating between 2 labels, document in the notes the ones that came closest and why.

### Case example
`Test run interrupted: runner lost connection to Docker daemon\nError response from daemon: dial unix docker.sock: connect: no such file or directory`
Genuinely unsure if this is infra or something else entirely (runner-level Docker failure). Diff is trivial so not a regression. Punting to unknown rather than forcing a bucket

OR
`E   elasticsearch.exceptions.ConnectionTimeout: Connection timed out\nE   TransportError(N/A, 'timeout')`
Could be infra-error (ES cluster slow) or real-regression (new fields causing slow queries) - genuinely can't tell without more info. Leaving as unknown rather than guessing.

### Nearest-neighbor distinction
Doesn't really have any - by definition the errors are when either not enough information or there's ambuiguity regarding what label should be applied.

## Known Gaps
- Configuration values, run parameters and environment changes can happen between runs. For a single run, we don't have historic data. If available, need to compare between successful and failed runs.
- Currently, the classifier doesn't receive the workflow yaml or build metadata directly, which can be a problem when classifying build config errors