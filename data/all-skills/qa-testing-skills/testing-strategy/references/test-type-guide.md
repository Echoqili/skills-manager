# Test Type Guide

Detailed decision criteria, characteristics, and examples for each type of test. Use this reference when determining which test type to apply to a specific piece of code.

## Table of Contents
- [Unit Tests](#unit-tests)
- [Integration Tests](#integration-tests)
- [Component Tests](#component-tests)
- [E2E Tests](#e2e-tests)
- [What Not to Test](#what-not-to-test)

---

## Unit Tests

### What They Test
Isolated units of business logic — pure functions, calculations, transformations, validators, parsers, formatters, and any code that takes input and produces output without reaching outside its own scope.

### Characteristics
- Execute in milliseconds (under 100ms per test)
- No external dependencies (no database, no network, no file system)
- Fully deterministic — same input always produces same output
- Run in memory only
- Can run in any order without affecting each other

### When to Use

| Code Pattern | Unit Test? | Reason |
|---|---|---|
| Pure function (input → output) | ✅ Yes | Ideal candidate — no dependencies, fast, precise |
| Data transformation or mapping | ✅ Yes | Verify transformation logic in isolation |
| Validation logic | ✅ Yes | Test each rule independently |
| Calculation or formula | ✅ Yes | Verify mathematical correctness and edge cases |
| Business rule or policy | ✅ Yes | Critical — these are the core of your application |
| String formatting or parsing | ✅ Yes | Test expected formats, edge cases, malformed input |
| State machine transitions | ✅ Yes | Verify each valid transition and reject invalid ones |
| Function that calls database | ❌ No | Use integration test — external dependency involved |
| Function that calls an API | ❌ No | Use integration test with mocked API boundary |
| UI rendering logic | ❌ No | Use component test — needs rendering context |

### Structure

Every unit test follows the AAA pattern:

```
TEST "descriptive name of the scenario"
  ARRANGE: Set up input data and expected output
  ACT:     Call the function being tested
  ASSERT:  Verify the result matches expectations
```

### What to Cover in Unit Tests

For each function under test, cover:

1. **Happy path** — Normal, expected usage with valid input
2. **Boundary values** — Minimum, maximum, zero, empty, exactly-at-threshold
3. **Error cases** — Invalid input, null/undefined, wrong types, out-of-range
4. **Edge cases** — Empty collections, single-element collections, Unicode, special characters
5. **Business rule variations** — Each branch of conditional logic

### Naming Convention

Test names should answer: "Given [context], when [action], then [expected result]."

```
Good:  "returns 10% discount when order total exceeds 100"
Good:  "throws validation error when email format is invalid"
Good:  "returns empty array when no items match filter"
Bad:   "test calculateDiscount"
Bad:   "works correctly"
Bad:   "test case 1"
```

---

## Integration Tests

### What They Test
Interactions between modules, layers, or systems. Integration tests verify that components work together correctly — that the API route calls the service, the service calls the database, and the data flows through correctly.

### Characteristics
- Slower than unit tests (100ms–5s per test)
- May use real or simulated dependencies (test database, mock server)
- Test the boundaries between components
- Require setup and teardown (database state, server state)
- Should still be deterministic

### When to Use

| Code Pattern | Integration Test? | Reason |
|---|---|---|
| API endpoint / route handler | ✅ Yes | Verify request → processing → response flow |
| Database query or ORM operation | ✅ Yes | Verify query correctness against real schema |
| Service that coordinates modules | ✅ Yes | Verify modules interact correctly |
| Authentication/authorization flow | ✅ Yes | Verify middleware → handler → response chain |
| External API integration | ✅ Yes | Mock the external API, test your client code |
| File upload processing | ✅ Yes | Test the full pipeline from receipt to storage |
| Pure calculation function | ❌ No | Use unit test — no integration boundaries |
| UI component rendering | ❌ No | Use component test |

### Boundary Definition

The key question for integration tests: **where is the boundary?**

- **Internal boundaries** (always test with real implementations): Service → Repository, Handler → Service, Middleware → Handler
- **External boundaries** (mock at the edge): Your code → External API, Your code → Third-party service, Your code → Email provider

Mock at the outermost edge. Everything inside that edge should run for real.

### Database Testing Approaches

| Approach | Speed | Reliability | Use When |
|---|---|---|---|
| In-memory database (SQLite) | Fast | Good for simple queries | Schema is compatible |
| Test container (real DB in Docker) | Medium | Excellent | Complex queries, DB-specific features |
| Transaction rollback | Fast | Good | Each test wraps in a rolled-back transaction |
| Seed and truncate | Medium | Good | Need specific data states |

Always reset database state between tests. Shared state is the top cause of flaky integration tests.

---

## Component Tests

### What They Test
UI components in isolation — render the component, simulate user interaction, assert on visible output and behavior. Component tests verify what the user sees and experiences, not the internal implementation.

### Characteristics
- Medium speed (50ms–2s per test)
- Render components in a simulated DOM environment
- Simulate real user actions (click, type, submit)
- Assert on visible output (text, elements, accessibility attributes)
- Don't assert on internal state, props passed, or implementation details

### When to Use

| Code Pattern | Component Test? | Reason |
|---|---|---|
| Form with validation | ✅ Yes | Test input → validation → error/success display |
| Interactive widget (modal, dropdown, accordion) | ✅ Yes | Test open/close, selection, keyboard navigation |
| Data display component with loading/error states | ✅ Yes | Test all three states: loading, data, error |
| Component with conditional rendering | ✅ Yes | Test each condition's visible output |
| Static presentational component (no logic) | ❌ No | No behavior to test — snapshot at most |
| Component that only passes props down | ❌ No | No logic — test the child components instead |

### The User-Centric Testing Principle

Test components the way a user would interact with them:

```
Good: Find the input by its label, type into it, click submit, verify the success message appears
Bad:  Check that setState was called with the right value after onChange fired
```

If your test breaks because you renamed an internal variable but the component still works exactly the same for the user, the test was wrong.

### What to Assert

- **Visible text** — Is the right content displayed?
- **Element presence** — Does the error message appear? Does the loading spinner show?
- **Accessibility** — Are roles, labels, and ARIA attributes correct?
- **User flow** — Does the form submit? Does the modal close? Does navigation happen?

### What NOT to Assert

- Internal component state
- Props passed to child components
- Number of re-renders
- CSS class names (unless they control visibility)
- Implementation details of event handlers

---

## E2E Tests

### What They Test
Complete user flows through the entire application — browser, frontend, backend, database, external services. E2E tests verify that the whole system works together from the user's perspective.

### Characteristics
- Slow (5–60 seconds per test)
- Expensive to maintain
- Run against a fully deployed (or locally running) application
- Prone to flakiness (network timing, animation delays, race conditions)
- Test the most critical paths only

### When to Use

Only for **critical business flows** where failure means significant business impact:

| Flow | E2E Test? | Reason |
|---|---|---|
| User registration and login | ✅ Yes | Broken auth = no users |
| Checkout and payment | ✅ Yes | Broken checkout = no revenue |
| Core data submission (the main thing your app does) | ✅ Yes | Broken core flow = app is useless |
| User onboarding | ✅ Yes | Broken onboarding = user churn |
| Password reset | ✅ Maybe | Important but testable at integration level |
| Settings page | ❌ No | Not critical enough for E2E cost |
| Admin dashboard | ❌ No | Low traffic, testable at component/integration level |
| Marketing pages | ❌ No | No dynamic behavior worth E2E testing |

### Keep E2E Tests Minimal

The rule of thumb: if you have more than 10-15 E2E tests, you probably have too many. Each E2E test should cover a complete user journey, not a single interaction.

```
Good: "User can register, verify email, log in, and see their dashboard"
Bad:  "Login button is visible on the homepage"
```

### Dealing with Flakiness

- Add explicit waits for network requests and animations, not arbitrary timeouts
- Use deterministic test data (seed the database, don't depend on production data)
- Isolate test environments (each test run gets a clean state)
- Retry failed tests once before marking them as failures
- If a test is consistently flaky, fix it or delete it. Flaky tests erode trust.

---

## What Not to Test

Testing everything is not the goal. Testing the right things is.

**Don't test:**

| Category | Example | Why Not |
|---|---|---|
| Trivial code | Getters, setters, simple assignments | No logic to break |
| Framework behavior | Does the router route? Does the ORM connect? | The framework's maintainers test this |
| Configuration | Env var loading, static config objects | No logic, changes rarely, breaks obviously |
| Third-party libraries | Does the date library format dates? | Test your code, not theirs |
| Generated code | ORM migrations, auto-generated types | Generated from a source of truth — test the source |
| Glue code | Wiring up dependencies, passing props through | No logic, breaks obviously, tested by integration |

**The litmus test:** If the code has no conditional logic, no calculations, and no business rules, it probably doesn't need a dedicated test. It will be exercised by tests of the code that uses it.
