# E2E Patterns and Anti-Patterns

Best practices, common mistakes, and a diagnostic flowchart for flaky tests. All examples use pseudocode — adapt to your framework.

## Table of Contents
- [Wait Patterns](#wait-patterns)
- [Test Data Patterns](#test-data-patterns)
- [Network Mocking Patterns](#network-mocking-patterns)
- [Auth State Patterns](#auth-state-patterns)
- [Visual Regression Patterns](#visual-regression-patterns)
- [Accessibility Testing Patterns](#accessibility-testing-patterns)
- [Anti-Patterns](#anti-patterns)
- [Flaky Test Diagnosis Flowchart](#flaky-test-diagnosis-flowchart)

---

## Wait Patterns

### Wait for Navigation
```
// After clicking a link or submitting a form
CLICK submitButton
WAIT for URL to contain "/dashboard"
```

### Wait for Element State
```
// Wait for loading to complete
WAIT for element "loading-spinner" to be hidden
WAIT for element "data-table" to be visible
```

### Wait for Network Response
```
// Wait for a specific API call to complete
START listening for response matching "/api/users"
CLICK loadButton
WAIT for the response
VERIFY response status is 200
```

### Wait for Multiple Conditions
```
// After a complex action, wait for several things to settle
CLICK confirmPayment
WAIT for ALL of:
  - URL changes to "/confirmation"
  - Element "order-number" is visible
  - Network is idle
```

### Wait for Debounced Input
```
// Search inputs with debounce need a wait after typing
FILL searchInput WITH "query"
WAIT for response matching "/api/search"
// Now assert on results
```

---

## Test Data Patterns

### Create via API, Interact via UI, Verify via API
```
TEST "user can edit their profile"
  // Setup via API (fast, reliable)
  SET user = CREATE user via POST /api/test/users { name: "Before" }

  // Test via UI (what we're actually testing)
  LOGIN as user
  NAVIGATE to "/profile"
  CLEAR nameField
  FILL nameField WITH "After"
  CLICK saveButton
  WAIT for success toast

  // Verify via API (confirms persistence, not just UI update)
  SET updatedUser = GET /api/test/users/{user.id}
  EXPECT updatedUser.name to be "After"

  // Cleanup via API
  DELETE /api/test/users/{user.id}
```

### Unique Identifiers for Parallel Safety
```
TEST "create new item"
  // Use unique identifiers to prevent collisions
  SET uniqueName = "Test Item " + RANDOM_ID()

  CREATE item with name uniqueName
  VERIFY item with name uniqueName exists

  // Cleanup targets only our specific item
  DELETE item with name uniqueName
```

### Database Reset Strategy
```
// Option A: Clean specific data in beforeEach
BEFORE EACH TEST:
  DELETE FROM test_users WHERE email LIKE 'test-%@example.com'
  DELETE FROM test_orders WHERE reference LIKE 'TEST-%'

// Option B: Transaction rollback (if framework supports it)
BEFORE EACH TEST:
  START database transaction
AFTER EACH TEST:
  ROLLBACK transaction

// Option C: Full reset between test files (slowest but cleanest)
BEFORE ALL TESTS IN FILE:
  RESET database to seed state
```

---

## Network Mocking Patterns

### Mock External API Error
```
INTERCEPT requests to "api.external-service.com/*"
  RESPOND with status 500, body { error: "Service unavailable" }

NAVIGATE to page that calls external service
EXPECT error message "Unable to connect to service" to be visible
EXPECT retry button to be visible
```

### Mock Slow Response (Test Loading State)
```
INTERCEPT requests to "/api/data"
  DELAY response by 3 seconds
  THEN respond with status 200, body { items: [...] }

NAVIGATE to data page
EXPECT loading indicator to be visible
WAIT for loading indicator to be hidden
EXPECT data items to be visible
```

### Mock Payment Gateway
```
INTERCEPT requests to "api.stripe.com/v1/charges"
  RESPOND with status 200, body { id: "ch_mock_123", status: "succeeded" }

PROCEED through checkout flow
EXPECT confirmation page with order number
```

### Don't Mock Your Own Backend
```
// WRONG: Mocking your own API defeats the purpose of E2E testing
INTERCEPT "/api/users" → RESPOND with mock data    // ❌

// RIGHT: Let the request hit your real backend
// Only mock EXTERNAL services you don't control
INTERCEPT "api.third-party.com/*" → RESPOND with mock    // ✅
```

---

## Auth State Patterns

### Save and Reuse Authentication
```
// Setup file — runs once before all tests
SETUP "authenticate"
  NAVIGATE to "/login"
  FILL email WITH "testuser@example.com"
  FILL password WITH "TestPassword123!"
  CLICK signInButton
  WAIT for URL "/dashboard"
  SAVE browser state (cookies, localStorage) to file "auth-state.json"

// All other tests load saved state — no login UI needed
CONFIGURE test project:
  USE storage state from "auth-state.json"
  DEPENDS ON "setup" project
```

### Multiple User Roles
```
// Save state for different roles
SETUP "admin-auth"
  LOGIN as admin
  SAVE state to "admin-state.json"

SETUP "user-auth"
  LOGIN as regular user
  SAVE state to "user-state.json"

// Tests specify which role they need
TEST "admin can delete users" using admin-state.json
TEST "user cannot access admin panel" using user-state.json
```

---

## Visual Regression Patterns

### Full Page Screenshot
```
TEST "homepage matches baseline"
  NAVIGATE to "/"
  WAIT for page to fully load
  CAPTURE full page screenshot
  COMPARE against baseline "homepage.png" with threshold 100 pixels
```

### Component State Screenshots
```
TEST "button renders correctly in all states"
  NAVIGATE to "/components"
  SET button = element by role "button" name "Submit"

  CAPTURE screenshot of button as "button-default.png"

  HOVER over button
  CAPTURE screenshot of button as "button-hover.png"

  DISABLE button
  CAPTURE screenshot of button as "button-disabled.png"
```

### Exclude Dynamic Content
```
TEST "dashboard layout is consistent"
  NAVIGATE to "/dashboard"

  // Hide dynamic content before screenshot
  HIDE element "timestamp"
  HIDE element "user-avatar"
  HIDE element "live-chart"

  CAPTURE full page screenshot
  COMPARE against baseline with threshold 50 pixels
```

---

## Accessibility Testing Patterns

### Page-Level Scan
```
TEST "homepage has no accessibility violations"
  NAVIGATE to "/"
  WAIT for full page load

  RUN accessibility scan on full page
    EXCLUDE third-party widgets

  EXPECT violations count to be 0
```

### Component-Level Scan
```
TEST "registration form is accessible"
  NAVIGATE to "/register"

  RUN accessibility scan on form element only

  EXPECT violations count to be 0
```

### Keyboard Navigation
```
TEST "user can complete form using only keyboard"
  NAVIGATE to "/login"

  PRESS Tab → EXPECT focus on email input
  TYPE "user@example.com"
  PRESS Tab → EXPECT focus on password input
  TYPE "password123"
  PRESS Tab → EXPECT focus on submit button
  PRESS Enter
  WAIT for URL "/dashboard"
```

---

## Anti-Patterns

### 1. Testing UI State Instead of Behavior
```
// ❌ WRONG: Tests that a dropdown opens
CLICK dropdown
EXPECT listbox to be visible

// ✅ RIGHT: Tests that selecting an option changes behavior
CLICK dropdown
SELECT option "Admin"
SAVE changes
RELOAD page
EXPECT dropdown value to be "Admin"
```

### 2. Hardcoded Timeouts
```
// ❌ WRONG
WAIT 3000 milliseconds
CLICK button

// ✅ RIGHT
WAIT for button to be enabled
CLICK button
```

### 3. Tests That Depend on Execution Order
```
// ❌ WRONG: Test B assumes Test A created the user
TEST A: "create user"
TEST B: "edit user"  // fails if A didn't run first

// ✅ RIGHT: Each test is independent
TEST B: "edit user"
  CREATE user via API   // setup its own data
  EDIT user via UI
  VERIFY changes
  DELETE user via API   // clean up
```

### 4. Force-Clicking Hidden Elements
```
// ❌ WRONG: Forcing click bypasses real UX issues
CLICK button WITH force: true

// ✅ RIGHT: Make element visible first
HOVER over parent container
WAIT for button to be visible
CLICK button
```

### 5. Asserting Element Existence Instead of Content
```
// ❌ WRONG: Passes even if element shows wrong data
EXPECT userProfile to be visible

// ✅ RIGHT: Verifies actual content
EXPECT userProfile to contain text "Alice Smith"
EXPECT userProfile to contain text "alice@example.com"
```

### 6. Over-Testing with E2E
```
// ❌ WRONG: Testing input validation with E2E (slow, expensive)
TEST "email field rejects invalid format"
TEST "password requires 8 characters"
TEST "name field is required"

// ✅ RIGHT: Test form validation as unit/component test
// E2E only tests the critical happy path
TEST "valid registration creates account and redirects to dashboard"
```

### 7. Multiple Assertions on Unrelated Behaviors
```
// ❌ WRONG: Testing three different things
TEST "user page works"
  VERIFY user can be created
  VERIFY user can be searched
  VERIFY user can be deleted

// ✅ RIGHT: One behavior per test
TEST "user can be created"
TEST "user can be searched"
TEST "user can be deleted"
```

---

## Flaky Test Diagnosis Flowchart

When a test fails intermittently, follow this decision tree:

```
Test fails intermittently
│
├─ Does it pass when run in isolation?
│  ├─ YES → Shared state problem
│  │        → Fix: Ensure test creates and cleans its own data
│  │
│  └─ NO → Timing problem
│          │
│          ├─ Does it fail on a specific step?
│          │  ├─ Click/interaction fails → Element not ready
│          │  │  → Fix: Add explicit wait for element state
│          │  │
│          │  ├─ Assertion fails → Data not ready
│          │  │  → Fix: Wait for API response before asserting
│          │  │
│          │  └─ Navigation fails → Page not loaded
│          │     → Fix: Wait for load state after navigation
│          │
│          └─ Does it fail only in CI?
│             ├─ YES → Environment difference
│             │  → Fix: Check viewport, network speed, cold start state
│             │
│             └─ NO → Non-deterministic data
│                → Fix: Use unique identifiers, avoid time-dependent data
```

**The fix-one-at-a-time protocol:**
1. Identify all flaky tests
2. Pick ONE test
3. Run it 10 times in isolation
4. Diagnose using the flowchart above
5. Apply fix
6. Run it 10 times again to confirm stability
7. Move to next flaky test
8. Run full suite only after all individual fixes are confirmed
