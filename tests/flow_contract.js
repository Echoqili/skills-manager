'use strict';
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { buildSandbox, extractInlineScript } = require('./render_contract');
const html = fs.readFileSync(path.join(__dirname, '../web/templates/index.html'), 'utf8');
const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
const deferred = () => { let resolve; const promise = new Promise(r => resolve = r); return { promise, resolve }; };
function page() {
    const sandbox = buildSandbox();
    const ctx = vm.createContext(sandbox);
    vm.runInContext(extractInlineScript(html), ctx);
    const run = code => vm.runInContext(code, ctx);
    sandbox.document.getElementById('searchInput').value = '';
    sandbox.document.getElementById('sortOrder').value = 'default';
    return { sandbox, run, el: id => sandbox.document.getElementById(id) };
}
const skill = (name, category = 'design', namespace = category) => ({ name, category, namespace, id: `${namespace}/${name}` });
async function main() {
    let failures = 0;
    async function test(name, fn) {
        try { await fn(); console.log(`[PASS] ${name}`); }
        catch (e) { failures++; console.error(`[FAIL] ${name}: ${e.message}`); }
    }
    await test('本地结果不等待慢 AI', async () => {
        const p = page(), ai = deferred();
        p.el('searchInput').value = 'guide';
        p.sandbox.fetch = url => url.startsWith('/api/search/ai') ? ai.promise : Promise.resolve(response({ results: [skill('guide')], count: 1 }));
        let done = false;
        const pending = p.run('searchSkills()').then(() => { done = true; });
        await new Promise(r => setTimeout(r, 20));
        const ready = done && p.run('currentSearchResults.length') === 1;
        ai.resolve(response({ recommendation: null }));
        await pending;
        assert.ok(ready, 'AI 未完成时本地搜索仍被阻塞');
    });
    await test('过期搜索不会覆盖最近搜索', async () => {
        const p = page(), old = deferred();
        p.sandbox.fetch = url => url.startsWith('/api/search/ai') ? Promise.resolve(response({})) : url.includes('q=old') ? old.promise : Promise.resolve(response({ results: [skill('new')], count: 1 }));
        p.el('searchInput').value = 'old'; const pending = p.run('searchSkills()');
        p.el('searchInput').value = 'new'; await p.run('searchSkills()');
        old.resolve(response({ results: [skill('old')], count: 1 })); await pending;
        assert.equal(p.run('currentSearchResults[0].name'), 'new');
    });
    await test('完整加载超过 300 条技能', async () => {
        const p = page(), skills = Array.from({ length: 325 }, (_, i) => skill(`s${i}`));
        p.sandbox.fetch = async url => { const q = new URL(url, 'http://test').searchParams; const size = Number(q.get('per_page')); const start = (Number(q.get('page')) - 1) * size; return response({ results: skills.slice(start, start + size), total: skills.length }); };
        await p.run('loadInitialSkills()');
        assert.equal(p.run('allLoadedSkills.length'), 325);
    });
    await test('分类筛选保留关键词并组合结果', async () => {
        const p = page(); p.el('searchInput').value = 'guide';
        p.sandbox.fetch = async () => response({ results: [skill('design-guide'), skill('test-guide', 'qa-testing')], skills: [skill('design-guide'), skill('test-guide', 'qa-testing')], count: 2 });
        await p.run("setCategoryFilter('design')");
        assert.equal(p.el('searchInput').value, 'guide');
        assert.equal(p.run('currentSearchResults.length'), 1);
    });
    await test('损坏清单不会破坏应用状态', async () => {
        const p = page(); p.sandbox.localStorage.getItem = () => '{"bad":true}';
        p.run('loadCart()'); assert.equal(p.run('Array.isArray(cart)'), true);
        p.sandbox.localStorage.getItem = () => '["guide","guide",7,null]';
        p.run('loadCart()'); assert.equal(p.run('cart.length'), 1);
    });
    await test('打包失败明确反馈且重复提交被阻止', async () => {
        const p = page(), pending = deferred(); let calls = 0;
        p.run("cart = ['design/guide']; showToast = (msg) => { window.lastToast = msg; }");
        p.sandbox.fetch = () => { calls++; return pending.promise; };
        const first = p.run('packageSelected()'), second = p.run('packageSelected()');
        pending.resolve(response({ error: 'Selected skill missing' }, 404));
        await Promise.all([first, second]);
        assert.equal(calls, 1); assert.match(p.sandbox.lastToast, /Selected skill missing/);
        assert.equal(p.run('cart.length'), 1);
    });
    await test('详情返回保留原视图且清除详情状态', async () => {
        const p = page(); p.run("currentView = 'curated'; prevView = 'search'; currentPage = 3; window.curatedCalls = 0; loadCurated = () => { window.curatedCalls++; }");
        const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/skill-brainstorming.json')));
        p.sandbox.fetch = async () => response(fixture);
        await p.run("showSkillDetail('brainstorming')"); p.run('goBack()');
        assert.equal(p.run('currentView'), 'curated');
        assert.equal(p.run('currentDetailSkillName'), null);
        assert.equal(p.run('currentPage'), 3);
        assert.equal(p.sandbox.curatedCalls, 0, '返回详情不应重置已打开的精选专题');
    });
    await test('详情使用项目实际安装命令', async () => {
        const p = page(); const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/skill-brainstorming.json')));
        p.sandbox.fetch = async () => response(fixture);
        await p.run("showSkillDetail('brainstorming')");
        assert.ok(String(p.el('skillDetail').innerHTML).includes('python cli/sm.py install'));
    });
    await test('离开详情后晚到的请求不重新打开详情', async () => {
        const p = page(), pending = deferred();
        p.sandbox.fetch = () => pending.promise;
        const loading = p.run("showSkillDetail('guide')");
        p.run("showSection('search')");
        pending.resolve(response({ ...skill('guide'), files: [] })); await loading;
        assert.equal(p.run('currentDetailSkillName'), null);
        assert.equal(p.run('currentView'), 'search');
    });
    await test('旧名称清单迁移且同名实现保持独立', async () => {
        const p = page();
        p.run('allLoadedSkills = ' + JSON.stringify([skill('guide'), skill('guide', 'qa-testing'), skill('unique')]) + "; cart = ['guide', 'unique']; libraryReady = true; cacheSkills(allLoadedSkills); reconcileCart()");
        assert.equal(p.run("cart.includes('design/unique')"), true);
        assert.equal(p.run("cart.includes('guide')"), true);
        p.run("addToCart('design/guide'); addToCart('qa-testing/guide')");
        assert.equal(p.run('cart.length'), 4);
    });
    await test('手动导入成功刷新技能库且阻止重复导入', async () => {
        const p = page(), pending = deferred(); let imports = 0;
        p.el('importName').value = 'new'; p.el('importDesc').value = 'description'; p.el('importContent').value = '# Body';
        p.sandbox.fetch = url => {
            if (url === '/api/import/user') { imports++; return pending.promise; }
            if (url.startsWith('/api/skills/all')) return Promise.resolve(response({ results: [skill('new')], total: 1 }));
            return Promise.resolve(response({ total: 1, categories: [] }));
        };
        const first = p.run('submitImport()'), second = p.run('submitImport()');
        pending.resolve(response({ success: true, name: 'new' })); await Promise.all([first, second]);
        assert.equal(imports, 1);
        assert.equal(p.run('allLoadedSkills[0]?.name'), 'new');
        assert.equal(p.el('importName').value, '');
    });
    if (failures) process.exitCode = 1;
}
main().catch(e => { console.error(e); process.exitCode = 1; });
