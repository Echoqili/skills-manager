'use strict';

// Run with Node; PLAYWRIGHT_MODULE can point to an existing Playwright install.
const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const html = fs.readFileSync(process.env.AUTH_HTML_PATH || path.join(__dirname, '../web/templates/index.html'), 'utf8');

async function dragCaptcha(page, x) {
    const track = await page.locator('#auth-captcha-track').boundingBox();
    const handle = await page.locator('#auth-captcha-handle').boundingBox();
    await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
    await page.mouse.down();
    await page.mouse.move(track.x + handle.width / 2 + x / 278 * (track.width - 2 - handle.width), handle.y + handle.height / 2, { steps: 12 });
    await page.mouse.up();
}

async function main() {
    const browser = await chromium.launch({ headless: true });
    let failures = 0;
    async function test(name, fn, options = {}) {
        const context = await browser.newContext(options);
        const page = await context.newPage();
        page.setDefaultTimeout(4000);
        const state = { user: null, verified: false, loginCalls: 0, errors: [], loginResponse: null, failCaptcha: false };
        page.on('pageerror', error => state.errors.push(error.message));
        await page.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.pathname === '/') return route.fulfill({ contentType: 'text/html', body: html });
            if (!url.pathname.startsWith('/api/')) return route.abort();
            let data = {};
            switch (url.pathname) {
                case '/api/config': data = { email_verify_required: false }; break;
                case '/api/auth/me': data = { user: state.user }; break;
                case '/api/captcha/new':
                    if (state.failCaptcha) return route.fulfill({ status: 503, json: { error: '验证码服务暂不可用' } });
                    state.verified = false;
                    data = { id: 'test-challenge', width: 320, height: 160, gap_y: 60, gap_size: 42,
                        svg: '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="160"><rect width="320" height="160" fill="#ac8bd9"/><rect x="140" y="60" width="42" height="42" fill="#514268"/></svg>' };
                    break;
                case '/api/captcha/verify': {
                    const payload = route.request().postDataJSON();
                    state.verified = payload.id === 'test-challenge' && Math.abs(payload.x - 140) <= 6;
                    return route.fulfill({ status: state.verified ? 200 : 400, json: state.verified
                        ? { success: true, token: 'test-challenge' } : { error: '未对准缺口，请重试' } });
                }
                case '/api/auth/login':
                    state.loginCalls++;
                    assert.ok(state.verified, 'login must require a verified captcha');
                    if (state.loginResponse) return route.fulfill(state.loginResponse);
                    state.user = { username: 'browser_test', is_admin: false };
                    data = { success: true, user: state.user }; break;
                case '/api/skills/all': data = { results: [], skills: [], total: 0 }; break;
                case '/api/categories': data = { categories: [] }; break;
                case '/api/stats': data = { total: 0, categories: {}, sources: {} }; break;
            }
            await route.fulfill({ json: data });
        });
        try {
            await page.goto('https://skills.test/');
            await page.waitForFunction(() => window.VIEWER_MODE === true, null, { timeout: 15000 });
            await page.evaluate(() => window.openAuthModal('login'));
            await fn(page, state);
            assert.deepEqual(state.errors, [], 'browser JavaScript errors');
            console.log(`[PASS] ${name}`);
        } catch (error) {
            failures++;
            console.error(`[FAIL] ${name}: ${error.message}`);
        } finally { await context.close(); }
    }
    const hidden = page => page.locator('#auth-overlay').waitFor({ state: 'hidden' });
    await test('关闭按钮返回游客页面并可再次打开', async page => {
        assert.equal(await page.getByRole('button', { name: '关闭登录窗口' }).count(), 1);
        await page.getByRole('button', { name: '关闭登录窗口' }).click();
        await hidden(page);
        await page.locator('#guest-login-btn').click();
        await page.locator('#auth-overlay').waitFor({ state: 'visible' });
    });
    await test('Esc 返回游客页面', async page => {
        await page.keyboard.press('Escape'); await hidden(page);
    });
    await test('点击卡片保持弹窗，点击遮罩关闭', async page => {
        await page.locator('#auth-title').click();
        assert.equal(await page.locator('#auth-overlay').isVisible(), true);
        await page.locator('#auth-overlay').click({ position: { x: 5, y: 5 } });
        await hidden(page);
    });
    await test('游客入口和注册切换可以返回', async page => {
        await page.locator('#auth-switch-link').click();
        assert.equal(await page.locator('#auth-title').textContent(), '注册新账号');
        await page.getByRole('button', { name: '以游客身份继续浏览', exact: true }).click();
        await hidden(page);
        assert.equal(await page.evaluate(() => window.VIEWER_MODE), true);
    });
    await test('未验证不能提交登录，验证码加载失败仍可关闭', async (page, state) => {
        await page.locator('#auth-username').fill('browser_test');
        await page.locator('#auth-password').fill('Test#123456');
        await page.locator('#auth-submit').click();
        assert.equal(await page.locator('#auth-error').textContent(), '请先完成滑块验证');
        assert.equal(state.loginCalls, 0);
        state.failCaptcha = true;
        await page.locator('#auth-captcha-refresh').click();
        await page.waitForFunction(() => document.getElementById('auth-captcha-msg').textContent.includes('暂不可用'));
        await page.keyboard.press('Escape'); await hidden(page);
    });
    await test('键盘焦点留在弹窗并在关闭后返回登录入口', async page => {
        await page.keyboard.press('Escape');
        await page.locator('#guest-login-btn').click();
        await page.locator('#auth-close').focus();
        await page.keyboard.press('Shift+Tab');
        assert.equal(await page.evaluate(() => document.activeElement.id), 'auth-guest-continue');
        await page.keyboard.press('Tab');
        assert.equal(await page.evaluate(() => document.activeElement.id), 'auth-close');
        await page.keyboard.press('Escape');
        assert.equal(await page.evaluate(() => document.activeElement.id), 'guest-login-btn');
    });
    await test('取消拖动不会继续移动或提交验证码', async page => {
        const handle = page.locator('#auth-captcha-handle');
        await handle.dispatchEvent('pointerdown', { pointerId: 1, clientX: 100, button: 0 });
        await handle.dispatchEvent('pointercancel', { pointerId: 1 });
        await page.evaluate(() => window.dispatchEvent(new PointerEvent('pointermove', { pointerId: 1, clientX: 400 })));
        assert.equal(await handle.evaluate(el => el.classList.contains('dragging')), false);
        assert.equal(await handle.evaluate(el => el.style.left), '0px');
    });
    await test('错误滑块提示后可重新拖动并登录', async (page, state) => {
        await page.locator('#auth-username').fill('browser_test');
        await page.locator('#auth-password').fill('Test#123456');
        await dragCaptcha(page, 70);
        await page.waitForFunction(() => document.getElementById('auth-captcha-msg').textContent.includes('未对准'));
        await dragCaptcha(page, 140);
        await page.locator('#auth-captcha-pass').waitFor({ state: 'visible' });
        await page.locator('#auth-submit').click(); await hidden(page);
        await page.waitForFunction(() => window.VIEWER_MODE === false);
        assert.equal(state.loginCalls, 1);
    });
    for (const [name, loginResponse, expected] of [
        ['密码错误', { status: 401, json: { error: '用户名或密码错误' } }, '用户名或密码错误'],
        ['账号待审批', { status: 403, json: { error: '账号待审批', code: 'pending' } }, '账号待审批'],
        ['服务返回非 JSON', { status: 502, contentType: 'text/html', body: 'Bad Gateway' }, '服务器返回非 JSON'],
    ]) {
        await test(`${name}显示反馈且可以返回游客页面`, async (page, state) => {
            state.loginResponse = loginResponse;
            await page.locator('#auth-username').fill('browser_test');
            await page.locator('#auth-password').fill('Test#123456');
            await dragCaptcha(page, 140);
            await page.locator('#auth-captcha-pass').waitFor({ state: 'visible' });
            await page.locator('#auth-submit').click();
            await page.waitForFunction(text => document.getElementById('auth-error').textContent.includes(text), expected);
            await page.keyboard.press('Escape'); await hidden(page);
            assert.equal(state.user, null);
            assert.equal(await page.evaluate(() => window.VIEWER_MODE), true);
        });
    }
    await test('手机注册窗口的退出入口可以滚动到并点击', async page => {
        await page.locator('#auth-switch-link').click();
        await page.getByRole('button', { name: '以游客身份继续浏览', exact: true }).click();
        await hidden(page);
    }, { viewport: { width: 375, height: 568 }, isMobile: true, hasTouch: true });
    await test('触屏滑块可以验证', async page => {
        const track = await page.locator('#auth-captcha-track').boundingBox();
        const handle = await page.locator('#auth-captcha-handle').boundingBox();
        const client = await page.context().newCDPSession(page);
        const y = handle.y + handle.height / 2;
        await client.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: handle.x + handle.width / 2, y }] });
        await client.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: track.x + handle.width / 2 + 140 / 278 * (track.width - 2 - handle.width), y }] });
        await client.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
        await page.locator('#auth-captcha-pass').waitFor({ state: 'visible' });
    }, { viewport: { width: 375, height: 667 }, isMobile: true, hasTouch: true });
    await browser.close();
    process.exitCode = failures ? 1 : 0;
}
main().catch(error => { console.error(error); process.exitCode = 1; });
