# Testing Anti-Patterns

Common mistakes that make test suites unreliable, slow, or misleading. For each anti-pattern: what it looks like, why it's harmful, and how to fix it.

## Table of Contents
- [1. Testing Implementation, Not Behavior](#1-testing-implementation-not-behavior)
- [2. Over-Mocking](#2-over-mocking)
- [3. Shared Mutable State](#3-shared-mutable-state)
- [4. Slow Unit Tests](#4-slow-unit-tests)
- [5. Testing Trivial Code](#5-testing-trivial-code)
- [6. Logic in Tests](#6-logic-in-tests)
- [7. Multiple Concerns per Test](#7-multiple-concerns-per-test)
- [8. Invisible Assertions](#8-invisible-assertions)
- [9. The Flaky Test Graveyard](#9-the-flaky-test-graveyard)
- [10. Snapshot Overuse](#10-snapshot-overuse)

---

## 1. Testing Implementation, Not Behavior

### What It Looks Like
Tests verify how code does something internally rather than what it produces. Common symptoms:
- Asserting that specific internal methods were called
- Asserting on internal state variables
- Tests break when you refactor without changing behavior

### Why It's Harmful
These tests give false negatives — they fail when the code is correct because you changed the implementation. This erodes trust and makes developers fear refactoring.

### How to Fix
Test inputs and outputs. Ask: "If I completely rewrote the internals but the function still returns the same result for the same input, would my test still pass?" If not, the test is coupled to implementation.

```
BAD:  Assert that internal method "calculateTax" was called with (price, rate)
GOOD: Assert that the total equals price + expected tax amount
```

---

## 2. Over-Mocking

### What It Looks Like
Every dependency is mocked, including internal collaborators. The test ends up verifying that mocks return what you told them to return — not that the code works.

### Why It's Harmful
Tests pass even when code is broken because the real behavior is replaced by mock behavior. You get 100% coverage with 0% confidence.

### How to Fix
Only mock at external boundaries (APIs, databases, file system, time). Let internal code run for real. If a function is hard to test without mocking its internals, that's a signal the function does too much — refactor it.

```
BAD:  Mock the validator, mock the formatter, mock the calculator, then test the orchestrator
GOOD: Let validator, formatter, and calculator run for real. Mock only the database call.
```

### The Mock Audit Question
For every mock in a test, ask: "If the real implementation of this mock had a bug, would this test catch it?" If the answer is no, you're testing the mock, not the code.

---

## 3. Shared Mutable State

### What It Looks Like
Tests share data, database state, or objects that change during execution. Tests pass when run individually but fail when run together or in a different order.

### Why It's Harmful
Non-deterministic test suites are worse than no tests. Developers stop trusting the suite, start ignoring failures, and eventually stop running tests.

### How to Fix
- Each test gets its own fresh data (use factory functions, not shared objects)
- Reset database state before each test (transaction rollback, truncate, or fresh seed)
- Clear all mocks between tests
- Never depend on test execution order

```
BAD:  Shared "testUser" object modified by multiple tests
GOOD: Factory function creates a fresh user for each test
```

---

## 4. Slow Unit Tests

### What It Looks Like
Unit tests take seconds instead of milliseconds. Common causes: hitting a real database, making network calls, reading files, importing heavy modules unnecessarily.

### Why It's Harmful
Slow tests don't get run. Developers skip them locally and only run them in CI. Feedback loops expand from seconds to minutes. Bugs that could have been caught immediately are caught 20 minutes later.

### How to Fix
- Unit tests must run entirely in memory — no I/O
- If a test needs a database, it's an integration test, not a unit test. Categorize it correctly.
- Lazy-load expensive imports
- Use the lightest possible test runner configuration
- Target: entire unit test suite completes in under 30 seconds

---

## 5. Testing Trivial Code

### What It Looks Like
Tests for getters, setters, configuration loading, constant values, simple assignments, or code with no conditional logic.

### Why It's Harmful
These tests add maintenance cost without catching bugs. They inflate coverage numbers without adding confidence. They make the test suite slower and harder to maintain.

### How to Fix
Apply the litmus test: "If this code broke, would it be caught by a test of the code that *uses* it?" If yes, you don't need a dedicated test for it.

```
BAD:  Test that "getName()" returns the name property
GOOD: Test the business function that uses getName() to make a decision
```

---

## 6. Logic in Tests

### What It Looks Like
Tests contain if/else statements, loops, try/catch blocks, or complex setup logic. The test itself has logic that could have bugs.

### Why It's Harmful
If a test has bugs, it might pass when the code is broken or fail when the code is correct. Tests should be straightforward sequences: set up, execute, verify.

### How to Fix
- No conditionals in tests
- No loops in tests (use parameterized tests instead)
- No try/catch in tests (let the framework handle assertion failures)
- If setup is complex, extract it into a factory or helper function that is itself simple

```
BAD:  if (user.role === "admin") { expect(result).toBe(true) } else { expect(result).toBe(false) }
GOOD: Two separate tests — one for admin, one for non-admin, each with a single assertion
```

---

## 7. Multiple Concerns per Test

### What It Looks Like
A single test verifies multiple unrelated behaviors. It tests creation AND validation AND error handling in one test function.

### Why It's Harmful
When the test fails, you don't know which behavior broke. You have to read the entire test and debug to find the failure point.

### How to Fix
One behavior per test. Each test should have a single reason to fail. If you find yourself writing "and" in the test name, split it.

```
BAD:  "creates user and validates email and sends welcome email"
GOOD: Three tests — "creates user with valid data", "rejects invalid email", "sends welcome email on creation"
```

---

## 8. Invisible Assertions

### What It Looks Like
Tests that only verify code doesn't throw an exception. No actual assertions on output or behavior. The test "passes" because nothing exploded.

### Why It's Harmful
The code could return completely wrong data and the test would still pass. These tests provide false confidence.

### How to Fix
Every test must assert on a specific, expected outcome. If you can't figure out what to assert, ask: "What would break if this code had a bug?"

```
BAD:  Call the function, no assertion (just checking it doesn't throw)
GOOD: Call the function, assert the return value equals the expected result
```

---

## 9. The Flaky Test Graveyard

### What It Looks Like
Tests that are disabled, skipped, or marked as "known flaky". They accumulate over time as developers skip failing tests rather than fixing them.

### Why It's Harmful
Each skipped test is a blind spot. Flaky tests that sometimes pass create a "cry wolf" effect — developers start ignoring real failures. The test suite becomes a liability rather than a safety net.

### How to Fix
- Zero tolerance for skipped tests. If a test is skipped, either fix it or delete it within one sprint.
- Zero tolerance for flaky tests. If a test fails intermittently, it has a bug — find it.
- Common flakiness causes: shared state, timing dependencies, race conditions, external service calls, test order dependency.
- Track flaky test rate as a team metric. It should always be 0%.

---

## 10. Snapshot Overuse

### What It Looks Like
Large snapshot tests that capture entire component output, API responses, or complex objects. When something changes, the developer just updates the snapshot without reviewing what changed.

### Why It's Harmful
Snapshots become rubber stamps. The developer doesn't actually review the change — they just run "update snapshots" and commit. This provides no more safety than not having the test at all.

### How to Fix
- Use snapshots only for small, specific outputs (a formatted string, a simple data structure)
- Never snapshot entire page or component renders
- If a snapshot is more than 20 lines, it's too big — replace it with specific assertions
- When a snapshot update is needed, always review the diff before accepting it

```
BAD:  Snapshot of an entire rendered page (500+ lines of HTML)
GOOD: Assert that the heading text is "Welcome", the button says "Get Started", and the error div is hidden
```
