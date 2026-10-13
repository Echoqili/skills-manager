'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert/strict');
const { buildSandbox, extractInlineScript } = require('./render_contract');

async function main() {
    const sandbox = buildSandbox();
    sandbox.document.documentElement.dataset.adminProxy = 'true';
    let cleared = false;
    sandbox.sessionStorage = {
        getItem() { throw new Error('Proxy mode must not read stored admin keys'); },
        removeItem(key) { cleared = key === 'admin_key'; },
    };
    const calls = [];
    sandbox.fetch = async (url, options) => {
        calls.push({ url, options });
        return { ok: true, status: 200, json: async () => ({ user:{username:'manager',is_admin:true,must_change_password:false}, users: [], logs: [], permissions: [], all: '*' }) };
    };
    for (const id of ['gate', 'panel', 'keyCard']) {
        const element = sandbox.document.getElementById(id);
        element.classList.toggle = (_, hidden) => { element.hidden = hidden; };
    }
    const ctx = vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/static/js/admin-session.js'), 'utf8'), ctx);
    const html = fs.readFileSync(path.join(__dirname, '../web/templates/admin_approvals.html'), 'utf8');
    vm.runInContext(extractInlineScript(html), ctx);
    await new Promise(r => setTimeout(r, 20));
    assert.ok(cleared);
    assert.equal(sandbox.document.getElementById('gate').hidden, true);
    assert.equal(sandbox.document.getElementById('panel').hidden, false);
    assert.equal(sandbox.document.getElementById('keyCard').hidden, true);
    assert.ok(calls.length >= 4);
    for (const { options } of calls) {
        assert.equal(options.headers['X-Admin-Request'], '1');
        assert.equal(options.headers['X-Admin-Key'], undefined);
    }
    console.log('PASS proxy-authenticated console loads without browser-stored admin keys');
    console.log('PASS admin panel and protected write headers remain available');
}
main().catch(e => { console.error(e); process.exitCode = 1; });
