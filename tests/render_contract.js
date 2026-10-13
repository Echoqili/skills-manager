/**
 * 详情页渲染契约测试（Node，无需浏览器）
 *
 * 为什么存在：详情页的「附带参考资料」面板与信任芯片都是模板字符串拼出来的，
 * 语法检查过了不代表渲染对了——`.path` 在 Windows 上是反斜杠分隔、`ref_files`
 * 可能缺失、i18n 插值参数个数不对，这些都要真跑一遍渲染才能发现。
 *
 * 做法：把 web/templates/index.html 里的内联脚本抽出来，在 Node 里给一套
 * DOM/窗口桩，然后用**真实接口数据**（tests/fixtures/skill-*.json）调用
 * showSkillDetail() / trustBadges()，对产出的 HTML 做断言。
 *
 * 用法：
 *   python cli/gen-render-fixtures.py      # 先刷新 fixtures（可选，数据变了才需要）
 *   node tests/render_contract.js
 */

'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const HTML = fs.readFileSync(path.join(ROOT, 'web', 'templates', 'index.html'), 'utf8');
const FIXTURES = path.join(__dirname, 'fixtures');

/** 可链式调用的万能桩：任何属性访问都返回同类桩，读回已写入的值 */
function mk() {
    const fn = function () {};
    return new Proxy(fn, {
        get(t, k) {
            if (k === Symbol.toPrimitive) return () => '';
            if (k === Symbol.iterator) return function* () {};
            if (k === 'then') return undefined;
            if (k === 'toString') return () => '';
            if (k === 'valueOf') return () => 0;
            if (k === 'length') return 0;
            if (!Object.prototype.hasOwnProperty.call(t, k)) t[k] = mk();
            return t[k];
        },
        set(t, k, v) { t[k] = v; return true; },
        apply() { return mk(); },
        construct() { return mk(); },
    });
}

function buildSandbox() {
    const elements = {};
    const sandbox = {
        // 页面自己的 console 会打一堆初始化日志、以及桩数据导致的无关告警，
        // 这里全部静音；断言输出走 harness 自己的 console（Node 全局）。
        console: { log() {}, warn() {}, error() {}, info() {}, debug() {} },
        setTimeout, clearTimeout, setInterval, clearInterval,
        Promise, JSON, Math, Date, RegExp, Error, Map, Set, Symbol, AbortController,
        Object, Array, String, Number, Boolean, Function,
        encodeURIComponent, decodeURIComponent, parseInt, parseFloat, isNaN,
        URL, URLSearchParams, TextEncoder, TextDecoder, Buffer,
        requestAnimationFrame: (cb) => { try { cb(); } catch (e) { /* 桩 */ } },
        cancelAnimationFrame() {},
        localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
        sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
        navigator: { language: 'zh-CN', userAgent: 'node-contract-test' },
        location: { href: 'http://127.0.0.1/', search: '', hash: '', pathname: '/', reload() {} },
        alert() {}, confirm: () => false, prompt: () => null,
        fetch: () => Promise.resolve({ ok: true, json: async () => ({}) }),
        // 浏览器观察器 / 样式 API 的桩：脚本加载期会构造它们
        MutationObserver: function () { return mk(); },
        IntersectionObserver: function () { return mk(); },
        ResizeObserver: function () { return mk(); },
        getComputedStyle: () => mk(),
        HTMLElement: function () {},
        CustomEvent: function () {},
        Event: function () {},
        document: {
            readyState: 'loading',
            getElementById: (id) => (elements[id] || (elements[id] = mk())),
            querySelector: () => mk(),
            querySelectorAll: () => [],
            createElement: () => mk(),
            createDocumentFragment: () => mk(),
            addEventListener() {},
            removeEventListener() {},
            body: mk(),
            head: mk(),
            documentElement: mk(),
            cookie: '',
        },
    };
    sandbox.window = sandbox;
    sandbox.globalThis = sandbox;
    sandbox.self = sandbox;
    sandbox.window.addEventListener = () => {};
    sandbox.window.matchMedia = () => ({ matches: false, addEventListener() {}, addListener() {} });
    sandbox._elements = elements;
    return sandbox;
}

function extractInlineScript(html) {
    const blocks = [];
    const re = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi;
    let m;
    while ((m = re.exec(html)) !== null) blocks.push(m[1]);
    return blocks.join('\n;\n');
}

function loadFixtures() {
    const out = {};
    for (const f of fs.readdirSync(FIXTURES)) {
        if (!f.endsWith('.json')) continue;
        out[f.replace(/^skill-|\.json$/g, '')] =
            JSON.parse(fs.readFileSync(path.join(FIXTURES, f), 'utf8'));
    }
    return out;
}

async function main() {
    const sandbox = buildSandbox();
    const ctx = vm.createContext(sandbox);

    let loadError = null;
    try {
        vm.runInContext(extractInlineScript(HTML), ctx, { filename: 'inline.js' });
    } catch (e) {
        loadError = e;
    }
    if (loadError) {
        console.error(`[FAIL] 内联脚本加载失败：${loadError.message}`);
        return 1;
    }

    let failed = 0;
    let total = 0;
    const check = (name, cond, extra) => {
        total++;
        if (cond) { console.log(`[PASS] ${name}`); }
        else { failed++; console.log(`[FAIL] ${name}${extra ? ' — ' + extra : ''}`); }
    };

    const fixtures = loadFixtures();
    const withRefs = fixtures['design-system'];
    const plain = fixtures['brainstorming'];
    if (!withRefs || !plain) {
        console.error('[FAIL] 缺少 fixtures（先跑 python cli/gen-render-fixtures.py）');
        return 1;
    }

    async function render(skill, lang) {
        // currentLang 是脚本里的 `let`（词法绑定），赋到 sandbox 上改不到它，
        // 必须在同一个 context 里赋值。
        vm.runInContext('currentLang = ' + JSON.stringify(lang), ctx);
        sandbox.fetch = () => Promise.resolve({
            ok: true,
            json: async () => JSON.parse(JSON.stringify(skill)),
        });
        await vm.runInContext("showSkillDetail('" + skill.name + "')", ctx);
        return String(sandbox._elements['skillDetail'].innerHTML || '');
    }

    // ---- 有资料的技能（中文） ----
    const zh = await render(withRefs, 'zh');
    check('详情-中文含参考资料面板', zh.includes('附带参考资料'));
    check('详情-中文资料条数正确（7 份）', zh.includes('7 份'));
    check('详情-资料文件名列出', zh.includes('component-specs.md'));
    check('详情-资料用 📎 图标', zh.includes('📎'));
    check('详情-资料面板带独立 class', zh.includes('detail-references'));
    check('详情-解释渐进式加载', zh.includes('按需加载'));

    // 反斜杠路径必须被归一化，否则 Windows 下 references 会被漏判
    const refCount = (zh.match(/📎/g) || []).length;
    check('详情-references 文件全部进面板（7）', refCount === 7, `实际 ${refCount}`);
    // SKILL.md 本体不应被算进资料面板
    check('详情-SKILL.md 不在资料面板', !/📎[^<]*SKILL\.md/.test(zh));

    // 资料项要可点开阅读（渲染成 button，数据走 data 属性）。
    // 直接用 <li class="file-item"> 的旧形态会点不动，这条断言把它钉住。
    const clickable = (zh.match(/file-item file-item-link/g) || []).length;
    check('详情-资料项渲染成可点击按钮（7）', clickable === 7, `实际 ${clickable}`);
    check('详情-可点击项数与 📎 数一致', clickable === refCount,
        `可点击 ${clickable} vs 📎 ${refCount}`);
    check('详情-点击回调走 dataset（规避引号截断）',
        zh.includes('onclick="showRefFile(this.dataset.skill, this.dataset.path)"'), '');
    // Windows 下 files[].path 是反斜杠；原样塞进 URL 会 404
    const dataPaths = zh.match(/data-path="[^"]*"/g) || [];
    check('详情-data-path 已归一化为正斜杠',
        dataPaths.length === 7 && dataPaths.every(p => !p.includes('\\')), dataPaths[0] || '(无)');
    check('详情-data-path 指向 references/',
        dataPaths.every(p => /data-path="references\//.test(p)), dataPaths[0] || '(无)');

    // ---- 有资料的技能（英文） ----
    const en = await render(withRefs, 'en');
    check('详情-英文含 References 面板', en.includes('Bundled References'));
    check('详情-英文条数正确', en.includes('7 files'));
    check('详情-英文无中文残留键名', !en.includes('detail_references'), '出现未翻译 key');

    // ---- 无资料的技能 ----
    const plainZh = await render(plain, 'zh');
    check('详情-无资料技能不显示面板', !plainZh.includes('detail-references'));

    // ---- 信任芯片 ----
    vm.runInContext("currentLang = 'zh'", ctx);
    const badges1 = String(vm.runInContext(
        'trustBadges(' + JSON.stringify(withRefs) + ')', ctx));
    check('芯片-有资料技能显示「附带资料 ×7」', badges1.includes('附带资料 ×7'));

    const badges2 = String(vm.runInContext(
        'trustBadges(' + JSON.stringify(plain) + ')', ctx));
    check('芯片-无资料技能不显示该芯片', !badges2.includes('附带资料'));

    // ref_files 字段缺失时不能崩、也不能显示 0
    const legacy = Object.assign({}, plain);
    delete legacy.ref_files;
    const badges3 = String(vm.runInContext(
        'trustBadges(' + JSON.stringify(legacy) + ')', ctx));
    check('芯片-旧数据缺 ref_files 时不误报', !badges3.includes('附带资料'));

    // ---- 阅读器与筛选函数的可用性 ----
    for (const fn of ['showRefFile', 'closeRefViewer', 'toggleRefFilter', 'renderSkillsPage']) {
        check(`脚本导出 ${fn}()`,
            vm.runInContext(`typeof ${fn}`, ctx) === 'function', '未定义');
    }

    // ---- 「含参考资料」筛选 ----
    // ref_files 已随列表接口返回，筛选是纯前端过滤（不额外发请求）。
    // 断言两条路径：关闭时全量、开启时只剩带资料的技能。
    vm.runInContext('currentSearchResults = ' + JSON.stringify([withRefs, plain]), ctx);
    vm.runInContext('showRefsOnly = false', ctx);
    vm.runInContext('renderSkillsPage(1)', ctx);
    const allView = String(sandbox._elements['searchResults'].innerHTML || '');
    check('筛选-关闭时两份技能都在',
        allView.includes('design-system') && allView.includes('brainstorming'));

    vm.runInContext('showRefsOnly = true', ctx);
    vm.runInContext('renderSkillsPage(1)', ctx);
    const refsView = String(sandbox._elements['searchResults'].innerHTML || '');
    check('筛选-开启时只剩带资料的技能',
        refsView.includes('design-system') && !refsView.includes('brainstorming'));
    check('筛选-开启时结果非空', refsView.length > 0 && refsView !== allView);

    vm.runInContext('showRefsOnly = false', ctx);

    console.log(`\n合计 ${total} 项断言，失败 ${failed} 项`);
    if (failed) return 1;
    console.log('全部通过 ✅');
    return 0;
}

module.exports = { buildSandbox, extractInlineScript };
if (require.main === module) main().then((c) => process.exit(c)).catch((e) => {
    console.error('[FAIL] 契约测试异常：', e && e.stack ? e.stack : e);
    process.exit(1);
});
