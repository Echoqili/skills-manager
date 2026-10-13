'use strict';
const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.TEST_BASE_URL || 'http://127.0.0.1:5555';
const output = process.env.QA_OUTPUT_DIR;

async function main() {
    const browser = await chromium.launch({ headless: true });
    let failures = 0, passed = 0;
    async function test(name, fn, viewport = { width: 1280, height: 900 }) {
        const context = await browser.newContext({ viewport, acceptDownloads: true });
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', e => errors.push(e.message));
        page.setDefaultTimeout(15000);
        try {
            if (process.env.TEST_HTML_PATH) {
                await page.route(base + '/', route => route.fulfill({ contentType: 'text/html', body: fs.readFileSync(process.env.TEST_HTML_PATH, 'utf8') }));
            }
            await page.goto(base, { waitUntil: 'domcontentloaded' });
            await page.waitForFunction(() => window.VIEWER_MODE === true && document.querySelectorAll('#searchResults .skill-card').length > 0);
            await fn(page, context);
            assert.deepEqual(errors, [], 'uncaught JavaScript errors');
            passed++;
            console.log(`[PASS] ${name}`);
        } catch (e) {
            failures++;
            console.error(`[FAIL] ${name}: ${e.message}`);
            if (output) await page.screenshot({ path: path.join(output, `public-failure-${failures}.png`) });
        } finally { await context.close(); }
    }
    async function search(page, query) {
        const input = await page.locator('#searchInput').isVisible() ? page.locator('#searchInput') : page.locator('#heroSearchInput');
        await input.fill(query);
        const response = page.waitForResponse(r => r.url().includes('/api/search?'));
        await input.press('Enter');
        await response;
        await page.waitForFunction(() => !document.querySelector('#searchResults .skeleton-card'));
    }
    const firstCard = page => page.locator('#searchResults .skill-card').first();
    await test('首页、分页、搜索和无结果反馈', async page => {
        assert.ok(Number(await page.locator('#totalSkills').textContent()) > 200);
        await page.locator('#searchPagination').getByRole('button', { name: '2', exact: true }).click();
        assert.equal(await page.locator('#searchPagination .active').textContent(), '2');
        await search(page, 'brainstorming');
        assert.ok(await page.locator('#searchResults .skill-card').count() > 0);
        await search(page, 'qzx_nonexistent_987654321');
        await page.locator('#searchResults .empty-state').waitFor({ state: 'visible' });
    });
    await test('分类筛选和排序', async page => {
        const category = page.locator('#browseCategoryGrid .category-card').first();
        await category.click();
        await page.waitForFunction(() => currentCategoryFilter !== null && document.querySelector('#searchResults .skill-card'));
        await page.locator('#sortOrder').selectOption({ index: 1 });
        assert.ok(await page.locator('#searchResults .skill-card').count() > 0);
    });
    await test('详情、参考资料预览和返回', async page => {
        await search(page, 'design-system');
        await firstCard(page).getByRole('button', { name: /查看详情|详情/ }).click();
        await page.locator('#skillDetail .ref-file-btn, #skillDetail [data-path]').first().waitFor({ state: 'visible' });
        await page.locator('#skillDetail [data-path]').first().click();
        await page.waitForFunction(() => document.getElementById('refViewerBody').textContent.length > 50 && !document.getElementById('refViewerBody').classList.contains('is-msg'));
        await page.keyboard.press('Escape');
        await page.locator('#refViewer').waitFor({ state: 'hidden' });
        await page.locator('#detailSection .btn-back').click();
        await page.locator('#searchSection').waitFor({ state: 'visible' });
        assert.equal(await page.locator('#heroSearchInput').inputValue(), 'design-system');
    });
    await test('游客清单刷新后保留', async page => {
        await firstCard(page).locator('[data-skill-name]').click();
        assert.equal(await page.locator('#cartCount').textContent(), '1');
        await page.reload({ waitUntil: 'domcontentloaded' });
        await page.waitForFunction(() => window.VIEWER_MODE === true && document.querySelector('#searchResults .skill-card'));
        assert.equal(await page.locator('#cartCount').textContent(), '1', 'guest cart lost after refresh');
    });
    await test('游客下载明确引导登录并可返回', async page => {
        await firstCard(page).getByRole('button', { name: /查看详情|详情/ }).click();
        const button = page.locator('#skillDetail').getByRole('button', { name: /单独下载/ });
        await button.waitFor({ state: 'visible' });
        await button.click();
        await page.locator('#auth-overlay').waitFor({ state: 'visible' });
        await page.keyboard.press('Escape');
        await page.locator('#auth-overlay').waitFor({ state: 'hidden' });
        await page.locator('#detailSection').waitFor({ state: 'visible' });
    });
    await test('精选专题与场景推荐', async page => {
        await page.locator('#sidebar [data-tab="curated"]').click();
        await page.locator('#curatedList .curated-card').first().click();
        await page.locator('#curatedList .skill-card').first().waitFor({ state: 'visible' });
        await page.locator('#curatedBackBtn').click();
        await page.locator('#curatedList .curated-card').first().waitFor({ state: 'visible' });
        await page.locator('#sidebar [data-tab="scenarios"]').click();
        await page.locator('#scenariosList .scenario-card').first().waitFor({ state: 'visible' });
    });
    await test('手机布局、搜索、详情与清单', async page => {
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2), 'horizontal overflow');
        await search(page, 'brainstorming');
        await firstCard(page).locator('[data-skill-name]').click();
        await page.getByRole('button', { name: '清单', exact: true }).click();
        assert.ok(await page.locator('#cartSection .skill-card').count() > 0);
    }, { width: 375, height: 667 });
    await test('游客不能读取私有配置或进入后台', async (page, context) => {
        for (const url of ['/api/ai/config', '/api/trash', '/api/admin/pending', '/admin/']) {
            const response = await context.request.get(base + url);
            assert.ok([401, 403].includes(response.status()), `${url}: ${response.status()}`);
        }
    });
    await test('语言切换及刷新后保留', async page => {
        await page.locator('#langToggle').click();
        await page.locator('#langMenu [data-lang="en"]').click();
        assert.equal(await page.locator('#langLabel').textContent(), 'EN');
        await page.reload({ waitUntil: 'domcontentloaded' });
        await page.waitForFunction(() => currentLang === 'en');
        assert.equal(await page.locator('#langLabel').textContent(), 'EN');
    });
    await browser.close();
    console.log(`RESULT passed=${passed} failed=${failures}`);
    process.exitCode = failures ? 1 : 0;
}
main().catch(e => { console.error(e); process.exitCode = 1; });
