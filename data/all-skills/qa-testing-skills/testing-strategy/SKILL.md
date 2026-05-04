---
name: testing-strategy
description: >
  Analyzes any web project and recommends a comprehensive testing strategy: what to test,
  which test type to use (unit, integration, component, E2E), how to prioritize coverage,
  and what mocking approach to follow. Can also generate tests based on its recommendations
  when the user asks. Use this skill when the user asks "what should I test", "create a
  testing strategy", "what tests does this project need", "analyze test coverage gaps",
  "which parts of my code need tests", "help me prioritize testing", "review my tests",
  "generate tests for this module", or any request to plan, evaluate, or create tests for
  a codebase. Also triggers when the user mentions testing pyramid, test coverage, TDD,
  test-driven development, or asks about the right type of test for a piece of code.
license: MIT
compatibility: >
  Requires file system read access to the project source code. Works with any web stack
  and any testing framework. For test generation mode, requires write access to create
  test files. Compatible with any agent that supports the Agent Skills standard.
metadata:
  version: "1.0.0"
  category: "testing"
  modifies-files: "only-when-generating-tests"
---

# Testing Strategy

Analyzes a web project and produces a testing strategy that answers the three questions developers struggle with most: what to test, with which type of test, and in what order of priority. When asked, also generates the tests themselves.

## Before You Start

### Stack and Framework Detection

Scan the project for configuration files, dependency manifests, and existing test files to determine:

- Language(s) and runtime
- Web framework(s)
- Existing testing framework(s) (Jest, Vitest, pytest, JUnit, RSpec, PHPUnit, etc.)
- Existing test files — their location, naming convention, and approximate count
- Mocking libraries already in use
- Test runner configuration (if any)
- CI/CD test pipeline (if detectable)

If the project already has tests, the strategy should build on what exists rather than propose a replacement. If no testing framework is present, recommend one based on the detected stack.

Record the detected stack and testing setup at the top of the strategy document.

### Scope Assessment

Identify the codebase areas that are testable:

- **Business logic** — Pure functions, calculations, transformations, rules
- **Data mutation handlers** — Server actions, controllers, API routes, views
- **Data access layer** — Repositories, services, ORM queries
- **UI components** — Interactive components with user-facing behavior
- **Utilities** — Helpers, formatters, validators, parsers
- **Integrations** — External API calls, third-party services, database operations
- **Critical user flows** — Authentication, checkout, data submission, onboarding

Map each area to the test types it needs. Read `references/test-type-guide.md` for detailed decision criteria.

## The Testing Pyramid

The testing pyramid is the foundation of the strategy. It defines the ratio of test types:

```
        /  E2E  \          Few, slow, expensive — critical flows only
       /----------\
      / Component  \       Moderate — UI behavior and interaction
     /--------------\
    /  Integration   \     More — module boundaries, APIs, data access
   /------------------\
  /     Unit Tests     \   Many, fast, cheap — business logic and utilities
 /______________________\
```

The pyramid exists because of economics: unit tests are fast, cheap, and precise. E2E tests are slow, expensive, and brittle. A healthy strategy has many unit tests, fewer integration tests, fewer component tests, and very few E2E tests.

**Recommended ratios** (adapt based on project type):

| Project Type | Unit | Integration | Component | E2E |
|---|---|---|---|---|
| API / Backend | 60% | 30% | — | 10% |
| Fullstack web app | 40% | 25% | 25% | 10% |
| SPA with external API | 30% | 15% | 40% | 15% |
| Static site with forms | 20% | 10% | 50% | 20% |

This adaptive model reconciles the classic testing pyramid with the Testing Trophy (Kent C. Dodds), which argues that integration tests deliver the most confidence per dollar invested. Both models are valid — the ratios above shift based on where your project's complexity lives, not on dogma. An API-heavy backend leans toward the pyramid; a frontend-heavy SPA leans toward the trophy.

These are guidelines, not rules. The right ratio depends on where the complexity lives.

## Decision Framework

For each piece of code in the project, use this decision tree to determine the right test type:

**Is it a pure function with no dependencies?**
→ **Unit test.** Fast, isolated, test inputs and outputs.

**Does it coordinate multiple internal modules?**
→ **Integration test.** Test the modules working together with real (or realistic) dependencies.

**Does it call an external service, database, or API?**
→ **Integration test** with mocked external boundaries. The external service is mocked, but internal logic runs for real.

**Is it a UI component with user interaction?**
→ **Component test.** Render the component, simulate user actions, assert on visible output. Don't test implementation details.

**Is it a critical end-to-end user flow?**
→ **E2E test.** Only for flows where failure means business impact: authentication, checkout, data submission, onboarding.

**Is it glue code, configuration, or trivial logic?**
→ **Don't test it.** Testing configuration files, simple getters, or framework boilerplate adds cost without value.

Read `references/test-type-guide.md` for detailed criteria, examples, and edge cases for each test type.

## Coverage Prioritization

When time is limited (it always is), test in this order:

**Priority 1 — Security and data integrity:**
- Authentication and authorization logic
- Data mutation handlers (create, update, delete)
- Input validation (especially server-side)
- Payment or financial calculations

**Priority 2 — Core business logic:**
- Domain rules and calculations
- Data transformations
- State machines and workflow logic
- Complex conditional logic

**Priority 3 — Integration boundaries:**
- API endpoint contracts (request/response shapes)
- Database queries for critical operations
- External service interactions

**Priority 4 — User-facing behavior:**
- Interactive UI components (forms, modals, wizards)
- Error states and loading states
- Accessibility-critical interactions

**Priority 5 — Utilities and edge cases:**
- Helper functions and formatters
- Edge cases in already-tested code
- Error message accuracy

Read `references/coverage-strategy.md` for coverage targets, metrics guidance, and how to assess existing coverage gaps.

## Mocking Strategy

Mocking is necessary but dangerous. Over-mocking means testing mocks instead of code. Under-mocking means slow, flaky tests.

**Mock at the boundary, not inside the unit:**
- Mock external services (APIs, databases, file systems, email providers)
- Mock time-dependent operations (dates, timers, randomness)
- Don't mock the code you're testing
- Don't mock internal collaborators unless they're expensive to set up

**Use the lightest mock that works:**
- **Stub** — Returns predetermined data. Use when you need to control what a dependency returns.
- **Spy** — Records calls. Use when you need to verify a dependency was called correctly.
- **Fake** — Working implementation with shortcuts. Use for databases (in-memory DB) or APIs (local server).
- **Full mock** — Replaces everything. Use only when nothing lighter works.

**When testing tells you something:**
If a function is hard to test because it has too many dependencies, that's not a testing problem — it's a design problem. The difficulty of testing is feedback about the code's design. Consider refactoring the code rather than adding more mocks.

## Anti-Patterns

Read `references/anti-patterns.md` for detailed descriptions and fixes. The most critical ones:

- **Testing implementation, not behavior** — Tests break when you refactor, even though behavior didn't change
- **Over-mocking** — Tests pass but code is broken because mocks hide real bugs
- **Shared mutable state** — Tests pass individually but fail when run together
- **Slow tests** — External calls in unit tests, no test isolation
- **Testing trivial code** — Wasting effort on getters, setters, and configuration

## Output Modes

This skill operates in two modes:

### Strategy Mode (default)

When the user asks for a testing strategy, analysis, or recommendations, produce a strategy document that includes:

1. **Detected stack and testing setup**
2. **Current coverage assessment** (if tests exist)
3. **Testing pyramid recommendation** with ratios for this project
4. **Prioritized test plan** — what to test, in what order, with which test type
5. **Mocking recommendations** — what to mock and how
6. **Suggested testing framework and tools** (if not already in place)
7. **Quick wins** — 3-5 highest-impact tests to write first

### Generation Mode

When the user asks to generate, write, or create tests, switch to generation mode:

1. Read the strategy (generate one first if none exists)
2. Identify the target code to test
3. Determine the appropriate test type from the decision framework
4. Generate tests following the project's existing conventions (naming, file location, framework)
5. Apply the AAA pattern (Arrange-Act-Assert) for every test
6. Include happy path, error cases, and critical edge cases
7. Use the mocking strategy from the recommendations

When generating tests, follow the project's existing test conventions. If no conventions exist, place test files adjacent to the code they test and use the framework's standard naming convention.

## Critical Rules

- **Strategy before code.** Always understand what needs testing before writing tests. A strategy document, even a brief one, prevents wasted effort.
- **Behavior over implementation.** Tests should verify what code does, not how it does it. If a refactor breaks tests without changing behavior, the tests are wrong.
- **One reason to fail.** Each test should fail for exactly one reason. If a test has multiple assertions testing different behaviors, split it.
- **Tests are documentation.** A well-named test tells the next developer what the code is supposed to do. Invest in test names.
- **Don't chase 100%.** 100% coverage is not the goal. Meaningful coverage of critical paths is worth more than exhaustive coverage of trivial code.
- **Adapt to the stack.** Use the project's native testing vocabulary. If it's pytest, say "fixtures" not "beforeEach". If it's JUnit, say "@BeforeEach" not "setup".

## Edge Cases

- **No tests exist yet**: Start with the strategy document. Recommend a testing framework. Identify the 5 highest-priority test targets. Generate those first.
- **Tests exist but no strategy**: Analyze existing tests for patterns, coverage gaps, and anti-patterns. Build the strategy around what exists.
- **Microservices**: Each service gets its own strategy. Cross-service tests are E2E by definition.
- **Legacy code without dependency injection**: Acknowledge that some code is hard to test without refactoring first. Recommend testing at the integration level and refactoring incrementally.
- **Project with only E2E tests**: This is an inverted pyramid. The strategy should propose adding unit and integration tests to reduce reliance on slow E2E tests.
