# CI/CD Pipeline Templates for E2E Tests

Ready-to-use pipeline configurations for running E2E tests in continuous integration. Adapt the framework-specific commands to your project.

## Table of Contents
- [General Principles](#general-principles)
- [GitHub Actions — Playwright](#github-actions--playwright)
- [GitHub Actions — Cypress](#github-actions--cypress)
- [GitHub Actions — Generic](#github-actions--generic)
- [GitLab CI](#gitlab-ci)
- [Pipeline Optimization](#pipeline-optimization)

---

## General Principles

Every E2E CI pipeline follows the same structure regardless of framework:

```
1. CHECKOUT code
2. INSTALL dependencies (app + test framework + browsers)
3. START application (or point to staging URL)
4. WAIT for application to be healthy
5. RUN E2E tests
6. UPLOAD artifacts (always — screenshots, videos, traces, reports)
```

**CI-specific configuration:**
- Sequential test execution (1 worker) unless the framework guarantees isolation
- Retry failed tests 1-2 times to absorb transient failures
- Generous but bounded timeouts (30s navigation, 10s actions, 5min total)
- Install only required browsers (Chromium usually sufficient for CI)
- Capture artifacts on both success and failure

---

## GitHub Actions — Playwright

```yaml
name: E2E Tests
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm

      - name: Install dependencies
        run: npm ci

      - name: Install Playwright (Chromium only)
        run: npx playwright install --with-deps chromium

      - name: Start application
        run: |
          npm run build
          npm run start &
          npx wait-on http://localhost:3000 --timeout 60000

      - name: Run E2E tests
        run: npx playwright test --project=chromium
        env:
          BASE_URL: http://localhost:3000

      - name: Upload HTML report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 14

      - name: Upload traces and screenshots
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: test-artifacts
          path: test-results/
          retention-days: 7
```

---

## GitHub Actions — Cypress

```yaml
name: E2E Tests
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm

      - name: Install dependencies
        run: npm ci

      - name: Start application
        run: |
          npm run build
          npm run start &
          npx wait-on http://localhost:3000 --timeout 60000

      - name: Run Cypress tests
        run: npx cypress run --browser chrome
        env:
          CYPRESS_BASE_URL: http://localhost:3000

      - name: Upload screenshots and videos
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: cypress-artifacts
          path: |
            cypress/screenshots/
            cypress/videos/
          retention-days: 14
```

---

## GitHub Actions — Generic

For any framework (Selenium, WebDriverIO, Laravel Dusk, Capybara, etc.):

```yaml
name: E2E Tests
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - uses: actions/checkout@v4

      # Language setup — adapt to your stack
      - name: Setup runtime
        uses: actions/setup-node@v4  # or setup-python, setup-java, setup-ruby
        with:
          node-version: 20

      # Browser setup — most frameworks need Chrome at minimum
      - name: Install Chrome
        uses: browser-actions/setup-chrome@latest

      - name: Install dependencies
        run: |
          # App dependencies
          npm ci
          # Test dependencies (if separate)
          # pip install -r requirements-test.txt
          # bundle install

      - name: Start application
        run: |
          npm run build
          npm run start &
          # Wait for app to be healthy
          timeout 60 bash -c 'until curl -s http://localhost:3000 > /dev/null; do sleep 2; done'

      - name: Run E2E tests
        run: |
          # Replace with your framework's run command
          npm run test:e2e
        env:
          BASE_URL: http://localhost:3000
          CI: true

      - name: Upload test artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: e2e-artifacts
          path: |
            test-results/
            screenshots/
            reports/
          retention-days: 14
```

---

## GitLab CI

```yaml
e2e-tests:
  stage: test
  image: mcr.microsoft.com/playwright:v1.40.0-focal  # or node:20
  timeout: 15 minutes

  variables:
    BASE_URL: http://localhost:3000

  before_script:
    - npm ci
    - npx playwright install --with-deps chromium  # if not using Playwright image

  script:
    - npm run build
    - npm run start &
    - npx wait-on $BASE_URL --timeout 60000
    - npx playwright test --project=chromium

  artifacts:
    when: always
    paths:
      - playwright-report/
      - test-results/
    expire_in: 14 days
    reports:
      junit: playwright-results.xml

  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "main"
```

---

## Pipeline Optimization

### Run E2E Only When Relevant

Don't run E2E tests on every commit — only when frontend, backend, or test files change:

```yaml
# GitHub Actions — path filter
on:
  push:
    branches: [main]
    paths:
      - 'src/**'
      - 'e2e/**'
      - 'package.json'
      - 'playwright.config.*'
  pull_request:
    paths:
      - 'src/**'
      - 'e2e/**'
```

### Parallel Sharding

For large test suites, split across multiple CI jobs:

```yaml
# GitHub Actions — matrix sharding
strategy:
  matrix:
    shard: [1, 2, 3, 4]

steps:
  - name: Run E2E tests (shard ${{ matrix.shard }})
    run: npx playwright test --shard=${{ matrix.shard }}/4
```

### Cache Browsers

Browser downloads are large. Cache them:

```yaml
- name: Cache Playwright browsers
  uses: actions/cache@v4
  with:
    path: ~/.cache/ms-playwright
    key: playwright-${{ runner.os }}-${{ hashFiles('package-lock.json') }}
```

### Smoke Tests on Deploy

Run a minimal subset of E2E tests after deployment:

```yaml
# Tag critical tests and run only those post-deploy
- name: Run smoke tests
  run: npx playwright test --grep @smoke
```

Tag tests in your test files:

```
TEST "login flow" @smoke
TEST "checkout flow" @smoke
TEST "search filters" // not tagged — runs in full suite only
```
