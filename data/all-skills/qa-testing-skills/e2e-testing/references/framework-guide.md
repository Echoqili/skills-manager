# E2E Framework Selection Guide

How to choose the right browser automation framework for a project. Use this reference when no E2E framework is installed and the agent needs to recommend one.

---

## Decision Matrix

| Factor | Playwright | Cypress | Selenium/WebDriverIO | Laravel Dusk | Capybara |
|---|---|---|---|---|---|
| **Best for** | Modern web apps, cross-browser | JS-heavy SPAs, developer experience | Legacy apps, enterprise, multi-language | Laravel PHP projects | Ruby/Rails projects |
| **Languages** | JS/TS, Python, Java, C# | JS/TS only | Any (Java, Python, JS, Ruby, C#) | PHP only | Ruby only |
| **Browsers** | Chromium, Firefox, WebKit | Chromium, Firefox, WebKit (limited) | All major browsers + mobile | Chrome | Chrome, Firefox via drivers |
| **Speed** | Fast (parallel by default) | Medium (single browser tab) | Slow (WebDriver protocol overhead) | Medium | Medium |
| **Auto-wait** | Built-in, excellent | Built-in, good | Manual | Basic | Built-in via Capybara DSL |
| **Network mocking** | Built-in route interception | Built-in cy.intercept | Requires external tools | Limited | Limited |
| **Mobile testing** | Device emulation | Viewport only | Real devices via Appium | No | Viewport only |
| **CI integration** | Excellent (Docker, GitHub Actions) | Good | Good but heavier setup | Good with Laravel Forge | Good with Rails CI |
| **Trace/debug** | Trace viewer, video, screenshots | Time-travel debugger, screenshots | Screenshots, logs | Screenshots | Screenshots |
| **Learning curve** | Low-medium | Low | High | Low (Laravel devs) | Low (Ruby devs) |

## Recommendation by Stack

| Project Stack | Recommended Framework | Reason |
|---|---|---|
| React / Next.js / Vue / Nuxt / Svelte | **Playwright** | Best cross-browser support, fastest, best auto-wait |
| React / Vue SPA (small team, rapid iteration) | **Cypress** | Best developer experience, time-travel debugger |
| Laravel + Blade/Livewire/Vue | **Laravel Dusk** | Native Laravel integration, uses project's PHP |
| Ruby on Rails | **Capybara + Selenium** | Ruby-native, Rails convention |
| Django / Flask | **Playwright (Python)** | Native Python API, no JS needed |
| Java / Spring Boot | **Playwright (Java)** or **Selenium** | Both have Java APIs; Playwright is faster |
| .NET / ASP.NET | **Playwright (.NET)** | Native C# API |
| Multi-language / enterprise | **Selenium/WebDriverIO** | Most language bindings, widest browser support |
| Static site with forms | **Playwright** | Overkill but simplest to set up and maintain |

## When to Avoid E2E Frameworks

Not every project needs a dedicated E2E framework:

- **API-only projects** — Use HTTP client tests (supertest, httpx, RestAssured). No browser needed.
- **Simple static sites** — A few smoke tests with curl or a lightweight HTTP check may be enough.
- **Projects with < 3 critical flows** — Consider testing them manually with a checklist rather than automating. The maintenance cost of E2E infrastructure may not justify it.

## Installation Quick Reference

After recommending a framework, the agent should install it following the framework's official setup. Common commands:

```
Playwright:    npm init playwright@latest
               pip install playwright && playwright install
Cypress:       npm install cypress --save-dev && npx cypress open
Laravel Dusk:  composer require laravel/dusk --dev && php artisan dusk:install
Capybara:      gem install capybara selenium-webdriver
WebDriverIO:   npm init wdio@latest
```

Always use the project's package manager (npm, yarn, pnpm, pip, composer, gem, etc.).
