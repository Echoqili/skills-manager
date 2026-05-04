# Page Object Model Patterns

Templates and examples for implementing the Page Object Model in E2E tests. All examples use pseudocode — adapt to your framework's API.

---

## Base Page Object

Every page object inherits from a base that provides shared functionality:

```
CLASS BasePage
  PROPERTY page    // The browser page/driver instance

  CONSTRUCTOR(page)
    SET this.page = page

  METHOD waitForLoad()
    WAIT for page to reach stable network state

  METHOD getToast()
    RETURN element with role "alert"

  METHOD getHeading()
    RETURN element with role "heading" level 1

  METHOD navigateTo(url)
    GO TO url
    CALL waitForLoad()
```

## Concrete Page Object

Each page encapsulates its selectors and actions:

```
CLASS LoginPage EXTENDS BasePage

  // ─── Selectors (defined once, reused everywhere) ───
  PROPERTY emailInput    = element by label "Email"
  PROPERTY passwordInput = element by label "Password"
  PROPERTY submitButton  = element by role "button" name "Sign in"
  PROPERTY errorMessage  = element by test-id "login-error"

  // ─── Actions (async, handle waits internally) ───
  METHOD goto()
    CALL navigateTo("/login")

  METHOD login(email, password)
    FILL emailInput WITH email
    FILL passwordInput WITH password
    CLICK submitButton
    WAIT for URL to change OR error to appear

  METHOD getError()
    RETURN text content of errorMessage
```

## Page Object Rules

### Do
- **One page object per page or major UI section.** A multi-step wizard might have one page object per step.
- **Expose selectors as properties.** Tests may need them for assertions.
- **Make actions async methods.** Every user interaction is asynchronous.
- **Handle waits inside actions.** After clicking "Submit", the page object waits for navigation or response — the test doesn't have to.
- **Return data, not elements** when the test needs values (e.g., `getError()` returns a string, not a locator).

### Don't
- **Never put assertions in page objects.** The page object clicks and reads. The test decides if the result is correct.
- **Never expose raw selectors** (CSS strings, XPaths). Expose locator objects or methods.
- **Never duplicate page objects.** If two tests need the same page, they share the same page object.
- **Never add framework-specific workarounds** in the page object. If you need a `force: true` click, fix the underlying issue instead.

---

## Common Page Object Patterns

### Pattern 1: CRUD Page

For pages that list, create, edit, and delete items:

```
CLASS UsersPage EXTENDS BasePage

  // Selectors
  PROPERTY createButton = element by test-id "create-user-btn"
  PROPERTY searchInput  = element by role "searchbox"
  PROPERTY userTable    = element by role "table"

  // Actions
  METHOD goto()
    CALL navigateTo("/users")

  METHOD search(query)
    FILL searchInput WITH query
    WAIT for API response containing "/api/users?"

  METHOD clickCreate()
    CLICK createButton

  METHOD getUserRow(identifier)
    RETURN row in userTable containing text identifier

  METHOD getUserCount()
    RETURN count of rows in userTable minus 1 (header)

  METHOD deleteUser(identifier)
    FIND row containing identifier
    CLICK delete button within that row
    WAIT for confirmation dialog
    CLICK confirm
    WAIT for row to disappear
```

### Pattern 2: Form Page

For pages with form submission:

```
CLASS CreateUserPage EXTENDS BasePage

  // Selectors
  PROPERTY nameInput     = element by label "Full name"
  PROPERTY emailInput    = element by label "Email"
  PROPERTY roleSelect    = element by label "Role"
  PROPERTY saveButton    = element by role "button" name "Save"
  PROPERTY cancelButton  = element by role "button" name "Cancel"
  PROPERTY successToast  = element by text "User created successfully"

  // Actions
  METHOD goto()
    CALL navigateTo("/users/new")

  METHOD fillForm(data)
    IF data.name    THEN FILL nameInput WITH data.name
    IF data.email   THEN FILL emailInput WITH data.email
    IF data.role    THEN SELECT data.role IN roleSelect

  METHOD submit()
    CLICK saveButton
    WAIT for URL to change OR error to appear

  METHOD cancel()
    CLICK cancelButton
    WAIT for URL to change

  METHOD getValidationErrors()
    RETURN all elements with role "alert" within the form
```

### Pattern 3: Multi-Step Flow

For wizards or multi-page flows:

```
CLASS CheckoutFlow

  PROPERTY cartPage     = new CartPage(page)
  PROPERTY shippingPage = new ShippingPage(page)
  PROPERTY paymentPage  = new PaymentPage(page)
  PROPERTY confirmPage  = new ConfirmationPage(page)

  METHOD completeCheckout(shippingData, paymentData)
    CALL cartPage.proceedToCheckout()
    CALL shippingPage.fillAddress(shippingData)
    CALL shippingPage.continue()
    CALL paymentPage.fillPayment(paymentData)
    CALL paymentPage.placeOrder()
    WAIT for confirmPage URL
    RETURN confirmPage.getOrderNumber()
```

---

## Using Page Objects in Tests

Tests read like user stories when page objects are well designed:

```
TEST "user can search and find existing users"
  // Arrange
  CREATE test user via API with name "Alice Smith"

  // Act
  SET usersPage = new UsersPage(page)
  CALL usersPage.goto()
  CALL usersPage.search("Alice")

  // Assert
  EXPECT usersPage.getUserCount() to be greater than 0
  EXPECT usersPage.getUserRow("Alice Smith") to be visible

  // Cleanup
  DELETE test user via API


TEST "user sees error when submitting invalid form"
  // Arrange
  SET createPage = new CreateUserPage(page)
  CALL createPage.goto()

  // Act — submit empty form
  CALL createPage.submit()

  // Assert
  EXPECT createPage.getValidationErrors() to have length greater than 0
  EXPECT URL to still be "/users/new"


TEST "complete checkout flow produces order confirmation"
  // Arrange
  ADD item to cart via API
  SET checkout = new CheckoutFlow(page)

  // Act
  SET orderNumber = CALL checkout.completeCheckout(
    { address: "123 Main St", city: "Springfield" },
    { card: "4111111111111111", exp: "12/28" }
  )

  // Assert
  EXPECT orderNumber to match pattern "ORD-XXXXX"
  VERIFY order exists in database via API
```
