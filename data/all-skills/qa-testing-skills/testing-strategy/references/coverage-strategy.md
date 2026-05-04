# Coverage Strategy

How to prioritize test coverage, set meaningful targets, assess gaps, and measure progress.

## Table of Contents
- [Coverage Targets](#coverage-targets)
- [Assessing Existing Coverage](#assessing-existing-coverage)
- [The Quick Wins Approach](#the-quick-wins-approach)
- [Coverage Metrics That Matter](#coverage-metrics-that-matter)
- [Building Coverage Incrementally](#building-coverage-incrementally)

---

## Coverage Targets

Coverage targets should vary by code area. Not all code deserves the same level of testing investment.

### Recommended Targets by Area

| Code Area | Target | Rationale |
|---|---|---|
| Authentication and authorization | 95%+ | Security-critical — a bug here is a vulnerability |
| Payment and financial logic | 95%+ | Errors mean financial loss or liability |
| Core business rules | 90%+ | The reason the application exists |
| Data mutation handlers | 85%+ | Create, update, delete operations affect data integrity |
| Input validation | 85%+ | First line of defense against bad data |
| Data transformations | 80%+ | Common source of subtle bugs |
| API contracts | 80%+ | Breaking changes affect consumers |
| UI components with logic | 70%+ | User-facing behavior matters |
| Utilities and helpers | 70%+ | Widely used, high leverage |
| Configuration and setup | Low | Minimal logic, breaks obviously |
| Glue code and wiring | Low | No logic to test |

### What "Coverage" Means

Line coverage alone is misleading. A function can have 100% line coverage but miss critical branches.

**Useful coverage metrics** (in order of value):
1. **Branch coverage** — Were both sides of every if/else exercised?
2. **Path coverage** — Were different combinations of conditions tested?
3. **Line coverage** — Were all lines executed? (necessary but not sufficient)

A project with 70% branch coverage is usually better tested than one with 90% line coverage.

---

## Assessing Existing Coverage

When a project already has tests, assess them before recommending new ones.

### Step 1: Map What Exists

For each testable area of the codebase:
- Count existing test files and tests
- Identify which code areas have tests and which don't
- Note the test types in use (unit, integration, component, E2E)
- Check for test runner configuration and CI integration

### Step 2: Identify Gaps

Compare existing coverage against the priority list:

| Priority | Area | Has Tests? | Gap |
|---|---|---|---|
| 1 | Auth logic | ❌ | Critical gap |
| 1 | Data mutations | Partial | Missing error cases |
| 2 | Business rules | ✅ | Adequate |
| 2 | Validation | ❌ | Important gap |
| 3 | API contracts | ❌ | Notable gap |
| 4 | UI components | ✅ | Adequate |

### Step 3: Evaluate Quality

Existing tests may have coverage but still be low quality. Check for:

- **Tests that never fail** — They might not be asserting anything meaningful
- **Tests with no assertions** — Only verify code runs without throwing
- **Tests tightly coupled to implementation** — Break on refactor, not on behavior change
- **Flaky tests** — Pass sometimes, fail sometimes (shared state, timing dependencies)
- **Slow tests** — Unit tests taking seconds instead of milliseconds
- **Disabled or skipped tests** — Why? Are they outdated or covering a real bug?

A test suite with 200 tests and 30 skipped is worse than 170 tests and 0 skipped.

---

## The Quick Wins Approach

When starting from zero or low coverage, identify the 5 highest-impact tests to write first.

### How to Find Quick Wins

**High impact = high risk × low test effort**

1. **Pure functions with business logic** — Easy to test (no setup), high value (core rules). These are always the first tests to write.

2. **Input validation on mutation handlers** — Test that invalid input is rejected. Each test is simple but catches real bugs.

3. **Authentication check on protected handlers** — Verify that unauthenticated requests are rejected. Simple tests that prevent security holes.

4. **Happy path of the core user flow** — One E2E test that walks through the main thing your app does. Catches integration breakage.

5. **Error handling in critical paths** — Verify that errors in data mutations are caught and handled, not swallowed silently.

### Quick Win Template

For each quick win, specify:
- **What to test** — The specific function, handler, or flow
- **Test type** — Unit, integration, component, or E2E
- **Why it's high priority** — What risk it mitigates
- **Estimated effort** — How many tests, how complex
- **Dependencies** — Does it need mocks, fixtures, or test infrastructure?

---

## Coverage Metrics That Matter

### Metrics to Track

| Metric | What It Tells You | Target |
|---|---|---|
| Branch coverage by module | Which modules have untested logic branches | Track per-module, not global |
| Test count by type | Is the pyramid balanced? | Unit > Integration > Component > E2E |
| Test execution time | Are tests fast enough to run on every commit? | Unit suite < 30s, full suite < 5min |
| Flaky test rate | How trustworthy is the suite? | 0% flaky (fix or delete) |
| Tests per mutation handler | Are data-changing operations covered? | At least 3 per handler (auth, happy, error) |
| Skipped test count | Are there abandoned tests? | 0 skipped (fix or delete) |

### Metrics to Ignore

| Metric | Why It's Misleading |
|---|---|
| Global line coverage % | Averages out critical gaps with trivial coverage |
| Test count | 500 bad tests are worse than 50 good ones |
| Coverage badges | Gameable and don't reflect actual quality |

### The Right Way to Use Coverage

Coverage tools are best used as **gap finders**, not score keepers.

Run coverage, then look at the uncovered lines. Ask: "If this code broke, would anyone notice?" If yes, it needs a test. If no, it probably doesn't.

---

## Building Coverage Incrementally

### For New Projects

1. Set up the testing framework and CI integration before writing production code
2. Write tests for business logic as you build features (not after)
3. Add integration tests for each API endpoint or handler as you create it
4. Add one E2E test for each critical user flow
5. Review coverage weekly, not daily — focus on trends, not numbers

### For Existing Projects with No Tests

1. Don't try to backfill everything at once — it's demoralizing and unsustainable
2. Apply the "boy scout rule": every time you touch a file, add at least one test for it
3. Start with the quick wins (see above)
4. Set a rule: no new feature merges without tests for the new code
5. Dedicate 20% of sprint capacity to backfilling tests for the highest-risk untested areas

### For Projects with Some Tests

1. Assess what exists (see above)
2. Fix flaky and skipped tests before adding new ones — trust in the suite matters more than coverage percentage
3. Fill the gaps by priority (security → business logic → integrations → UI → utilities)
4. Rewrite tests that are coupled to implementation details — they create false security
5. Add missing test types — if you only have unit tests, add integration tests for critical paths
