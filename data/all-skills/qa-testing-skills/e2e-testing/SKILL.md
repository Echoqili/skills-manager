---
name: e2e-testing
description: >
  Generates and manages end-to-end tests for critical user flows in any web project.
  Covers test design, Page Object Model, selector strategy, wait patterns, auth state
  reuse, test data management, network mocking, visual regression, accessibility testing,
  flaky test diagnosis, and CI/CD pipeline configuration. Stack-agnostic — adapts to
  Playwright, Cypress, Selenium, Laravel Dusk, Capybara, or any browser automation
  framework. Use this skill when the user asks to write E2E tests, automate browser
  tests, test user flows end-to-end, fix flaky tests, set up visual regression testing,
  configure E2E in CI/CD, debug failing E2E tests, or test across multiple browsers.
  Also triggers when the user mentions Playwright, Cypress, browser testing, smoke tests,
  critical path testing, or end-to-end test automation. Works with testing-strategy —
  use testing-strategy first to decide WHAT to test, then this skill to implement the
  E2E tests.
license: MIT
compatibility: >
  Requires file system read and write access. Requires a browser automation framework
  installed in the project (Playwright, Cypress, Selenium, etc.). For CI/CD configuration,
  requires access to the pipeline configuration files.
metadata:
  version: "1.0.0"
  category: "testing"
  modifies-files: true
  toolkit: "testing-toolkit"
---

# E2E Testing

Generates end-to-end tests that validate complete user flows through a real browser. E2E tests are the most expensive type of test — slow, brittle, hard to maintain. This skill exists to make them as reliable and valuable as possible.

## The E2E Mindset

E2E tests are not unit tests run in a browser. They test **product behavior**, not UI states.

**Test behavior, not appearance:**
- Don't test that a dropdown opens — test that selecting an option changes system behavior
- Don't test that a loading spinner shows — test that the loaded data is correct
- Don't test that a form field is visible — test that submitting valid data produces the expected outcome
- Don't test that an error message appears — test that invalid input is rejected AND valid input succeeds

If the feature broke but the UI still looked the same, would your test catch it? If not, the test is wrong.

---

## Before You Start

### Framework Detection

Scan the project for the E2E testing framework already in use:

- Configuration files: `playwright.config.*`, `cypress.config.*`, `wdio.conf.*`, `.seleniumrc`, `dusk.php`
- Dependencies in package manifest: `@playwright/test`, `cypress`, `selenium-webdriver`, `webdriverio`, `laravel/dusk`, `capybara`
- Existing test files: `*.spec.ts`, `*.e2e-spec.ts`, `*.test.ts` in an `e2e/` or `tests/e2e/` directory
- CI/CD pipeline steps that run E2E tests

If no E2E framework is present, recommend one based on the project stack. Read `references/framework-guide.md` for selection criteria.

If a framework exists, adopt its conventions entirely — file locations, naming patterns, configuration style, assertion library.

### Scope Check

E2E tests should only cover **critical user flows** where failure means business impact. Before writing any test, verify the target flow qualifies:

- Authentication (login, logout, password reset)
- Core transaction (checkout, payment, data submission)
- Onboarding (registration, setup wizard)
- Critical CRUD (the main thing the app does)

If the flow is not critical, push back and suggest a component or integration test instead. E2E tests are expensive — every one must justify its cost.

---

## Test Architecture

### File Structure

Organize tests by feature, not by page:

```
e2e/
├── config.*                    # Framework configuration
├── fixtures/
│   ├── auth.*                  # Authentication state setup
│   └── test-data.*             # Test data creation and cleanup
├── pages/
│   ├── base.*                  # Base page object with shared methods
│   ├── login.*                 # Login page object
│   └── [feature].*             # One page object per page or major section
├── tests/
│   ├── auth/
│   │   ├── login.*
│   │   └── logout.*
│   ├── [feature]/
│   │   └── [flow].*
│   └── smoke/
│       └── critical-paths.*    # Quick smoke tests for deploy verification
└── helpers/
    ├── api.*                   # Direct API calls for test setup
    └── constants.*             # Shared test constants
```

### Page Object Model

Every page gets a page object that encapsulates selectors and actions. Tests never interact with selectors directly.

**Rules for page objects:**
- One page object per page or major UI section
- Selectors are properties, actions are methods
- Page objects handle waits internally after actions
- Page objects NEVER contain assertions — tests assert, page objects act
- Page objects navigate and interact, tests verify outcomes

Read `references/page-object-patterns.md` for base class templates and concrete examples.

### Selector Strategy

Use the most resilient selector available, in this priority order:

| Priority | Type | When to Use |
|---|---|---|
| 1 | Test ID (`data-testid`) | Interactive elements, dynamic content |
| 2 | Accessible role + name | Buttons, links, headings, inputs |
| 3 | Label text | Form inputs with visible labels |
| 4 | Placeholder text | Search inputs, text fields |
| 5 | Visible text | Static content, unique strings |

**Never use:**
- CSS class selectors — break on styling changes
- XPath — unreadable, extremely brittle
- DOM structure selectors (`div > span:nth-child(2)`) — break on layout changes
- IDs generated by frameworks — not stable

If a component lacks a good test hook, recommend adding `data-testid` to the source code. Convention: `kebab-case`, descriptive, pattern `action-entity-element` (e.g., `create-user-btn`, `user-email-input`).

---

## Core Patterns

### Wait Strategies

Never use hardcoded timeouts. They are the #1 cause of flaky tests.

**Instead, wait for specific conditions:**
- Wait for a URL change after navigation
- Wait for a specific element to become visible or hidden
- Wait for a network response to complete
- Wait for the page to reach a stable load state

Most modern frameworks auto-wait before interacting with elements. Explicit waits are needed only for assertions or complex state transitions (e.g., waiting for a debounced search to settle, waiting for a WebSocket message).

Read `references/patterns-and-anti-patterns.md` for wait strategy examples in pseudocode and common framework equivalents.

### Authentication State Reuse

Logging in through the UI before every test is slow and brittle. Instead:

1. Perform real login once in a setup step
2. Save the authentication state (cookies, storage, tokens)
3. Load saved state in subsequent tests — skip the login UI entirely

This pattern works across all frameworks. The mechanism differs (storage state files in Playwright, programmatic login in Cypress, cookie injection in Selenium) but the principle is the same.

### Test Data Management

**Principles:**
- Each test creates its own data — never depend on pre-existing state
- Each test cleans up after itself — or the suite resets state before each run
- Use API calls for data setup, not UI interactions — faster and more reliable
- Use unique identifiers in test data to prevent collisions in parallel execution

**Pattern:**
```
BEFORE EACH TEST:
  Create test data via API (not UI)
  Navigate to the feature under test

DURING TEST:
  Interact through the UI
  Assert on outcomes

AFTER EACH TEST:
  Delete test data via API
  OR: reset database state
```

### Network Mocking and Interception

Mock external services at the network level when:
- Testing error states (API returns 500, timeout, malformed response)
- Testing loading states (delayed response)
- Avoiding flakiness from real third-party APIs
- Testing payment flows without real transactions

Don't mock your own backend — E2E tests should exercise the full stack. Only mock external boundaries you don't control.

### Visual Regression Testing

Capture screenshots and compare against baselines to catch unintended visual changes. Useful for:
- Design system consistency
- Cross-browser rendering differences
- Responsive layout verification
- Component state appearance (hover, disabled, error)

**Rules:**
- Set a pixel difference threshold — exact match is too brittle
- Exclude dynamic content (timestamps, avatars, ads) from comparisons
- Update baselines intentionally, not automatically
- Run visual tests on a single browser first, expand later

### Accessibility Testing

Integrate automated accessibility scanning into E2E tests. Run axe-core or equivalent after page load to catch:
- Missing alt text, labels, ARIA attributes
- Contrast violations
- Keyboard navigation issues
- Landmark and heading structure problems

Automated tools catch ~30-40% of accessibility issues. They don't replace manual testing, but they prevent regressions.

---

## Debugging Flaky Tests

Flaky tests erode trust faster than missing tests. Fix or delete them immediately.

### Common Causes and Fixes

| Cause | Fix |
|---|---|
| Hardcoded timeouts | Wait for specific conditions |
| Shared test data | Each test creates its own data |
| Animation interference | Disable animations in test config |
| Race conditions | Wait for API responses before assertions |
| Viewport-dependent behavior | Set explicit viewport in config |
| Session leaks between tests | Reset state in beforeEach/afterEach |
| Tests depending on execution order | Make each test fully independent |

### Diagnosis Process

1. Run the failing test in isolation — does it pass alone?
2. Run it 10 times consecutively — does it fail intermittently?
3. Run in headed/debug mode — watch what happens visually
4. Enable trace/video recording — review the recording on failure
5. Check for timing issues — add explicit waits, see if it stabilizes
6. Check for data issues — is the test depending on state from another test?

Read `references/patterns-and-anti-patterns.md` for the flaky test diagnosis flowchart and anti-pattern catalog.

---

## CI/CD Integration

E2E tests in CI require specific considerations:

**Configuration:**
- Run tests sequentially in CI (not parallel) unless the framework guarantees isolation
- Retry failed tests once or twice — transient failures happen in CI
- Capture artifacts on failure: screenshots, videos, traces, HTML reports
- Set generous but bounded timeouts (30s navigation, 10s actions)
- Install only the browsers you need — don't install all three if you only test Chromium

**Pipeline structure:**
1. Install dependencies and browsers
2. Start the application (or use a staging URL)
3. Wait for the application to be healthy
4. Run E2E tests
5. Upload artifacts (always, even on success)
6. Upload HTML report for team review

Read `references/ci-pipeline-templates.md` for ready-to-use pipeline configurations for GitHub Actions, GitLab CI, and generic CI systems.

---

## Output Modes

### Design Mode

When the user asks to plan E2E tests, produce:

1. List of critical flows that justify E2E testing
2. For each flow: test scenarios (happy path, error cases, edge cases)
3. Page objects needed
4. Test data requirements
5. Mocking requirements (external services only)
6. Recommended file structure

### Generation Mode

When the user asks to write E2E tests:

1. Detect the framework and adopt its conventions
2. Create page objects for involved pages (if they don't exist)
3. Generate test files following the project's naming convention
4. Include setup/teardown for test data
5. Use the selector strategy from this skill
6. Apply the wait patterns from this skill
7. Include both happy path and critical error scenarios

### Fix Mode

When the user asks to fix flaky or failing tests:

1. Read the failing test and its error output
2. Identify the cause using the diagnosis process
3. Apply the appropriate fix from the causes table
4. Run the test multiple times to confirm stability
5. If the test is fundamentally flawed (testing UI state instead of behavior), rewrite it

---

## Critical Rules

- **Behavior over appearance.** Test what the product does, not what it looks like. If the feature broke but the UI looked the same, the test must catch it.
- **Independence.** Every test must run in isolation. No test depends on another test having run first. No shared mutable state between tests.
- **No hardcoded waits.** Every `sleep`, `timeout`, or `waitForTimeout` is a bug. Wait for a specific condition.
- **Minimal E2E surface.** Test only critical flows. Everything else belongs in unit or integration tests. More E2E tests means slower pipelines and more maintenance.
- **Clean data.** Create it before, destroy it after. Never depend on pre-existing data.
- **Fix or delete flaky tests.** A flaky test is worse than no test. Zero tolerance.
- **Adapt to the framework.** Use the project's framework idioms. If it's Playwright, use locators and auto-wait. If it's Cypress, use commands and intercepts. Don't fight the framework.
