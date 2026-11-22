/**
 * 当前管理员身份卡片渲染契约（Node，无需浏览器）
 *
 * 为什么存在：身份卡片是 admin-session.js 里用字符串拼出来的，语法检查过了
 * 不代表渲染对了——角色判定、权限中文名映射、XSS 转义、接口失败降级、
 * /super-admin 下的路径改写，这些都要真跑一遍 renderIdentity() 才能发现。
 *
 * 做法：在 vm 里加载 web/static/js/admin-session.js，给一套最小 DOM/fetch 桩，
 * 用预设的 /me 与 /permissions 响应调用 renderIdentity()，对产出的 HTML 做断言。
 *
 * 用法：
 *   node tests/admin_identity_contract.js
 */

'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const ROOT = path.resolve(__dirname, '..');
const SRC = fs.readFileSync(path.join(ROOT, 'web', 'static', 'js', 'admin-session.js'), 'utf8');

const PERM_DEFS = [
    { key: 'skill_view', name: '查看与搜索 Skills' },
    { key: 'skill_import', name: '导入 Skill' },
    { key: 'discover', name: 'GitHub 发现' },
];

let passed = 0;
function check(name, fn) {
    return Promise.resolve().then(fn).then(() => {
        passed += 1;
        console.log('  ok  ' + name);
    }, err => {
        console.error('  FAIL  ' + name + '\n        ' + err.message);
        process.exitCode = 1;
    });
}

function makeBox() {
    return { innerHTML: '', className: '', addEventListener() {} };
}

/** 加载 admin-session.js，返回 sandbox / 各 DOM 节点 / fetch 请求记录 */
function loadSession(opts) {
    const cfg = Object.assign({ proxy: true, pathname: '/admin', me: null, failUrls: [] }, opts);
    const boxes = {};
    const requested = [];
    let styleCount = 0;
    const sandbox = {
        console,
        document: {
            documentElement: { dataset: { adminProxy: cfg.proxy ? 'true' : 'false' } },
            head: { appendChild() { styleCount += 1; } },
            createElement() { return { textContent: '', style: {} }; },
            getElementById(id) { return boxes[id] || (boxes[id] = makeBox()); },
            body: { appendChild() {} },
        },
        window: {},
        location: { pathname: cfg.pathname },
        fetch: async (url) => {
            requested.push(url);
            if (cfg.failUrls.some(u => url.includes(u))) {
                return { ok: false, status: 500, json: async () => ({}) };
            }
            let data = {};
            if (url.includes('/me')) data = { user: cfg.me };
            else if (url.includes('/permissions')) data = { permissions: PERM_DEFS };
            return { ok: true, status: 200, json: async () => data };
        },
    };
    sandbox.window = sandbox.window || {};
    vm.createContext(sandbox);
    vm.runInContext(SRC, sandbox, { filename: 'admin-session.js' });
    return { sandbox, boxes, requested, styleCount: () => styleCount };
}

const SUPER = {
    id: 1, username: 'superAdmin', is_admin: 1, is_super_admin: 1,
    status: 'approved', permissions: ['*'], must_change_password: false,
};
const MANAGER = {
    id: 7, username: 'mgr_alpha', is_admin: 1, is_super_admin: 0,
    status: 'approved', permissions: ['skill_view', 'discover'], must_change_password: false,
};

(async () => {
    console.log('admin identity card contract');

    await check('超管：角色/状态/全部权限/账号ID 均渲染', async () => {
        const s = loadSession({ me: SUPER });
        await s.sandbox.window.AdminSession.renderIdentity('adminIdentity');
        const html = s.boxes.adminIdentity.innerHTML;
        assert.ok(html.includes('>超级管理员</span>'), 'missing super admin role');
        assert.ok(html.includes('状态：已启用'), 'missing approved status');
        assert.ok(html.includes('全部权限'), 'missing all-permissions tag');
        assert.ok(html.includes('账号 ID #1'), 'missing account id');
        assert.ok(html.includes('superAdmin'), 'missing username');
        assert.ok(html.includes('aiRefreshBtn'), 'missing refresh button');
        assert.strictEqual(s.boxes.adminIdentity.className, 'ai-card');
    });

    await check('普通管理员：权限中文名来自 /permissions 定义', async () => {
        const s = loadSession({ me: MANAGER });
        await s.sandbox.window.AdminSession.renderIdentity('adminIdentity');
        const html = s.boxes.adminIdentity.innerHTML;
        assert.ok(html.includes('>管理员</span>'), 'missing admin role');
        assert.ok(!html.includes('>超级管理员</span>'), 'must not be super admin');
        assert.ok(html.includes('查看与搜索 Skills'), 'missing zh name of skill_view');
        assert.ok(html.includes('GitHub 发现'), 'missing zh name of discover');
        assert.ok(!html.includes('全部权限'), 'should not claim all permissions');
        assert.ok(html.includes('权限：2 项'), 'missing permission count');
    });

    await check('XSS：用户名与权限 key 均转义', async () => {
        const evil = Object.assign({}, MANAGER, {
            username: '<script>alert(1)</script>',
            permissions: ['skill_view', '<img onerror=1>'],
        });
        const s = loadSession({ me: evil });
        await s.sandbox.window.AdminSession.renderIdentity('adminIdentity');
        const html = s.boxes.adminIdentity.innerHTML;
        assert.ok(!html.includes('<script>'), 'username not escaped');
        assert.ok(html.includes('&lt;script&gt;'), 'missing escaped username');
        assert.ok(!html.includes('<img onerror=1>'), 'permission key not escaped');
        assert.ok(html.includes('&lt;img onerror=1&gt;'), 'missing escaped permission key');
    });

    await check('非代理（密钥门禁）模式：明确说明未绑定账号', async () => {
        const s = loadSession({ proxy: false, me: null });
        await s.sandbox.window.AdminSession.renderIdentity('adminIdentity');
        const html = s.boxes.adminIdentity.innerHTML;
        assert.ok(html.includes('管理员密钥模式'), 'missing key-mode label');
        assert.ok(html.includes('未绑定具体管理员账号'), 'missing explanation');
        assert.ok(s.requested.length === 0, 'key mode must not call /me');
    });

    await check('/me 失败：降级为错误卡片且不抛异常', async () => {
        const s = loadSession({ me: null, failUrls: ['/me'] });
        await s.sandbox.window.AdminSession.renderIdentity('adminIdentity');
        const html = s.boxes.adminIdentity.innerHTML;
        assert.ok(html.includes('无法读取管理员信息'), 'missing error card');
        assert.ok(html.includes('aiRefreshBtn'), 'missing retry button');
    });

    await check('/permissions 失败：退化为显示原始权限 key', async () => {
        const s = loadSession({ me: MANAGER, failUrls: ['/permissions'] });
        await s.sandbox.window.AdminSession.renderIdentity('adminIdentity');
        const html = s.boxes.adminIdentity.innerHTML;
        assert.ok(html.includes('skill_view'), 'should fall back to raw key');
        assert.ok(html.includes('discover'), 'should fall back to raw key');
        assert.ok(html.includes('>管理员</span>'), 'role still rendered');
    });

    await check('/super-admin 页面：/me 与 /permissions 路径自动改写', async () => {
        const s = loadSession({ me: SUPER, pathname: '/super-admin' });
        await s.sandbox.window.AdminSession.renderIdentity('adminIdentity');
        assert.ok(s.requested.some(u => u.includes('/api/super-admin/me')), 'me path not rewritten');
        assert.ok(s.requested.some(u => u.includes('/api/super-admin/permissions')), 'permissions path not rewritten');
        assert.ok(!s.requested.some(u => u.includes('/api/admin/me')), 'raw admin me leaked');
    });

    await check('样式只注入一次（重复渲染不累积 <style>）', async () => {
        const s = loadSession({ me: MANAGER });
        await s.sandbox.window.AdminSession.renderIdentity('adminIdentity');
        await s.sandbox.window.AdminSession.renderIdentity('adminIdentity');
        assert.strictEqual(s.styleCount(), 1);
    });

    console.log('\n' + passed + ' checks passed');
    if (process.exitCode) process.exit(process.exitCode);
})();
