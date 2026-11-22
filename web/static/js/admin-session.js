(function () {
    const proxy = document.documentElement.dataset.adminProxy === 'true';
    const api = async (url, options = {}) => {
        if (location.pathname.startsWith('/super-admin') && url.startsWith('/api/admin/')) {
            url = url.replace('/api/admin/', '/api/super-admin/');
        }
        const response = await fetch(url, {
            credentials: 'same-origin', ...options,
            headers: { 'Content-Type': 'application/json', 'X-Admin-Request': '1', ...options.headers }
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || '请求失败 (' + response.status + ')');
        return data;
    };
    const changePassword = (mandatory = false) => {
        if (document.getElementById('adminPasswordDialog')) return;
        const mask = document.createElement('div');
        mask.id = 'adminPasswordDialog';
        mask.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:5000;display:grid;place-items:center;padding:20px';
        mask.innerHTML = '<form style="background:white;color:#1f2937;max-width:440px;width:100%;padding:24px;border-radius:14px">'
            + '<h2 style="font-size:20px;margin-top:0">' + (mandatory ? '请先修改初始密码' : '修改管理员密码') + '</h2>'
            + '<p>新密码至少 12 位，包含大小写字母、数字和符号中的至少三类。</p>'
            + '<label>当前密码<input id="apOld" type="password" autocomplete="current-password" required></label>'
            + '<label>新密码<input id="apNew" type="password" autocomplete="new-password" minlength="12" required></label>'
            + '<label>确认新密码<input id="apConfirm" type="password" autocomplete="new-password" required></label>'
            + '<p id="apError" role="alert" style="color:#dc2626"></p>'
            + '<button type="submit" class="btn-primary">修改并重新登录</button>'
            + (mandatory ? '' : '<button type="button" id="apCancel">取消</button>') + '</form>';
        document.body.appendChild(mask);
        mask.querySelector('#apCancel')?.addEventListener('click', () => mask.remove());
        mask.querySelector('form').addEventListener('submit', async event => {
            event.preventDefault();
            const old = mask.querySelector('#apOld').value;
            const password = mask.querySelector('#apNew').value;
            const error = mask.querySelector('#apError');
            if (password !== mask.querySelector('#apConfirm').value) { error.textContent = '两次密码不一致'; return; }
            const button = mask.querySelector('[type=submit]');
            button.disabled = true;
            try {
                await api('/api/admin/change-password', { method: 'POST', body: JSON.stringify({ old_password: old, new_password: password }) });
                alert('密码已修改，请在浏览器验证框中使用新密码重新登录。');
                location.reload();
            } catch (err) { error.textContent = err.message; }
            finally { button.disabled = false; }
        });
    };
    const ready = proxy ? api('/api/admin/me').then(data => {
        if (!data.user) throw new Error('管理员登录已失效');
        window.AdminSession.user = data.user;
        if (data.user.must_change_password) { changePassword(true); return new Promise(() => {}); }
        return data.user;
    }) : Promise.resolve(null);
    // 兜底：身份卡等组件会自行取 /me，不依赖 ready；避免页面漏挂 .catch 时出现
    // unhandled rejection。原 Promise 仍保持 reject，外层 .catch 照常收到错误。
    ready.catch(() => {});
    const manageUser = (user, action, headers = {}) => new Promise(resolve => {
        if (document.getElementById('userLifecycleDialog')) { resolve(false); return; }
        const deleting = action === 'delete';
        const title = deleting ? '删除用户' : action === 'restore' ? '恢复用户' : user.status === 'approved' ? '停用用户' : '启用用户';
        const dialog = document.createElement('dialog');
        dialog.id = 'userLifecycleDialog';
        dialog.setAttribute('aria-labelledby', 'userLifecycleTitle');
        dialog.style.cssText = 'max-width:460px;width:calc(100% - 32px);border:1px solid #e2e8f0;border-radius:14px;padding:24px;color:#1f2937;background:white;margin:auto';
        dialog.innerHTML = '<form><h2 id="userLifecycleTitle"></h2><p id="userLifecycleTarget"></p><p id="userLifecycleHint" style="line-height:1.7"></p>'
            + (deleting ? '<label>输入完整用户名确认<input id="userLifecycleConfirm" autocomplete="off" required style="display:block;width:100%;padding:10px;margin:12px 0;box-sizing:border-box"></label>' : '')
            + '<p id="userLifecycleError" role="alert" style="color:#dc2626"></p><div style="display:flex;gap:10px">'
            + '<button type="button" id="userLifecycleCancel">取消</button><button type="submit" id="userLifecycleSubmit"></button></div></form>';
        dialog.querySelector('#userLifecycleTitle').textContent = title;
        dialog.querySelector('#userLifecycleTarget').textContent = '账号：' + user.username;
        dialog.querySelector('#userLifecycleHint').textContent = deleting
            ? '删除后立即禁止登录并移入“已删除”列表。私有技能、配置和操作记录保留；用户名及邮箱仍保留，不能重复注册。可恢复，不会永久清除数据。'
            : action === 'restore' ? '恢复后，原已批准账号保持停用，需另行启用；原待审批或已拒绝账号恢复原状态。用户必须重新登录。'
            : '停用会立即使已有登录失效，保留全部数据。启用后用户必须重新登录；待审批账号仍需先走审批流程。';
        const submit = dialog.querySelector('#userLifecycleSubmit');
        submit.textContent = title;
        submit.style.cssText = deleting ? 'background:#dc2626;color:white' : 'background:#2563eb;color:white';
        const cancel = dialog.querySelector('#userLifecycleCancel');
        cancel.onclick = () => dialog.close();
        dialog.addEventListener('close', () => { dialog.remove(); resolve(false); });
        dialog.querySelector('form').onsubmit = async event => {
            event.preventDefault();
            const confirmation = dialog.querySelector('#userLifecycleConfirm')?.value;
            const error = dialog.querySelector('#userLifecycleError');
            if (deleting && confirmation !== user.username) { error.textContent = '用户名不一致，请输入完整用户名'; return; }
            submit.disabled = true; cancel.disabled = true; error.textContent = '';
            try {
                await api('/api/admin/users/' + action, { method: 'POST', headers, body: JSON.stringify({
                    user_id: user.id, ...(deleting ? {confirm_username: confirmation} : {}),
                    ...(action === 'status' ? {enabled: user.status !== 'approved'} : {})
                }) });
                resolve(true); dialog.close();
            } catch (err) { error.textContent = err.message; }
            finally { submit.disabled = false; cancel.disabled = false; }
        };
        document.body.appendChild(dialog); dialog.showModal(); cancel.focus();
    });
    // ---------- 当前管理员身份卡片 ----------
    // 两个后台页共用：数据取自 /api/admin/me（/super-admin 页由 api() 自动改写路径），
    // 权限中文名取自 /api/admin/permissions。纯前端渲染，不新增后端接口。
    const IDENTITY_CSS = `
.ai-card{background:#fff;border:1px solid #e3e8ef;border-radius:12px;padding:16px 18px;margin:0 0 18px;color:#1f2937}
.ai-label{font-size:12px;color:#6b7280;font-weight:600;margin-bottom:10px}
.ai-head{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.ai-avatar{width:42px;height:42px;border-radius:50%;flex:none;display:grid;place-items:center;
  background:linear-gradient(135deg,#2563eb,#7c3aed);color:#fff;font-size:18px;font-weight:700}
.ai-name{font-size:17px;font-weight:700;color:#1f2937;word-break:break-all}
.ai-role{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600;margin-left:8px}
.ai-role.super{background:#ede9fe;color:#7c3aed}
.ai-role.admin{background:#dbeafe;color:#1d4ed8}
.ai-meta{color:#6b7280;font-size:12px;margin-top:4px}
.ai-badges{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.ai-badge{display:inline-block;padding:3px 9px;border-radius:6px;font-size:12px;background:#eef2f7;color:#334155}
.ai-badge.ok{background:#dcfce7;color:#166534}
.ai-badge.warn{background:#fef3c7;color:#92400e}
.ai-badge.err{background:#fee2e2;color:#991b1b}
.ai-perms{margin-top:12px;border-top:1px solid #f1f5f9;padding-top:10px}
.ai-perms-title{font-size:12px;color:#6b7280;margin-bottom:6px}
.ai-perm{display:inline-block;background:#f1f5f9;color:#334155;border-radius:6px;padding:2px 8px;font-size:12px;margin:2px 7px 2px 0}
.ai-perm.all{background:#dcfce7;color:#166534;font-weight:600}
.ai-actions{margin-top:10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.ai-refresh{background:#eef2f7;color:#1f2937;border:0;border-radius:6px;padding:5px 10px;font-size:12px;cursor:pointer;font-weight:600}
.ai-error{color:#dc2626;font-size:12px}
`;
    const escText = s => String(s ?? '').replace(/[&<>"']/g, c =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const IDENTITY_STATUS = {
        approved: ['已启用', 'ok'], disabled: ['已停用', 'warn'],
        pending: ['待审批', 'warn'], rejected: ['已拒绝', 'err'], deleted: ['已删除', 'err']
    };
    let identityStyleInjected = false;

    const renderIdentity = async (containerId) => {
        const box = document.getElementById(containerId || 'adminIdentity');
        if (!box) return;
        if (!identityStyleInjected) {
            const style = document.createElement('style');
            style.textContent = IDENTITY_CSS;
            document.head.appendChild(style);
            identityStyleInjected = true;
        }
        box.className = 'ai-card';
        if (!proxy) {
            // 密钥门禁模式没有「当前管理员账号」，明确说明避免误解
            box.innerHTML = '<div class="ai-label">当前登录身份</div>'
                + '<div class="ai-head"><div class="ai-avatar">&#128273;</div>'
                + '<div><div class="ai-name">管理员密钥模式</div>'
                + '<div class="ai-meta">使用门禁密钥访问，未绑定具体管理员账号。</div></div></div>';
            return;
        }
        try {
            const me = await api('/api/admin/me');
            const user = me.user;
            if (!user) throw new Error('登录已失效，请重新认证');
            window.AdminSession.user = user;
            let defs = [];
            try {
                const d = await api('/api/admin/permissions');
                defs = d.permissions || [];
            } catch (e) { /* 权限定义不可用时退化为显示原始 key */ }
            const nameMap = {};
            defs.forEach(p => { nameMap[p.key] = p.name || p.key; });
            const perms = Array.isArray(user.permissions) ? user.permissions : [];
            const all = !!user.is_super_admin || perms.includes('*');
            const permHtml = all
                ? '<span class="ai-perm all">全部权限</span>'
                : (perms.length
                    ? perms.map(p => '<span class="ai-perm">' + escText(nameMap[p] || p) + '</span>').join('')
                    : '<span class="ai-perm">无功能权限</span>');
            const st = IDENTITY_STATUS[user.status] || [user.status || '未知', ''];
            const role = user.is_super_admin ? '超级管理员' : (user.is_admin ? '管理员' : '普通用户');
            const roleCls = user.is_super_admin ? 'super' : 'admin';
            const initial = escText(String(user.username || '?').charAt(0).toUpperCase());
            box.innerHTML = '<div class="ai-label">当前登录身份</div>'
                + '<div class="ai-head"><div class="ai-avatar">' + initial + '</div>'
                + '<div style="min-width:0;flex:1">'
                + '<div class="ai-name">' + escText(user.username)
                + '<span class="ai-role ' + roleCls + '">' + role + '</span></div>'
                + '<div class="ai-meta">账号 ID #' + escText(user.id) + ' · 浏览器 Basic 认证</div>'
                + '</div></div>'
                + '<div class="ai-badges">'
                + '<span class="ai-badge ' + st[1] + '">状态：' + escText(st[0]) + '</span>'
                + (user.must_change_password ? '<span class="ai-badge warn">需修改初始密码</span>' : '')
                + '<span class="ai-badge">权限：' + (all ? '全部' : perms.length + ' 项') + '</span>'
                + '</div>'
                + '<div class="ai-perms"><div class="ai-perms-title">已分配功能权限</div>' + permHtml + '</div>'
                + '<div class="ai-actions"><button type="button" class="ai-refresh" id="aiRefreshBtn">刷新</button>'
                + '<span class="ai-meta">信息来自当前登录凭据；切换账号后点刷新可更新。</span></div>';
            const btn = document.getElementById('aiRefreshBtn');
            if (btn) btn.addEventListener('click', () => renderIdentity(containerId));
        } catch (err) {
            box.innerHTML = '<div class="ai-label">当前登录身份</div>'
                + '<div class="ai-head"><div class="ai-avatar">!</div>'
                + '<div><div class="ai-name">无法读取管理员信息</div>'
                + '<div class="ai-error">' + escText(err.message) + '</div></div></div>'
                + '<div class="ai-actions"><button type="button" class="ai-refresh" id="aiRefreshBtn">重试</button></div>';
            const btn = document.getElementById('aiRefreshBtn');
            if (btn) btn.addEventListener('click', () => renderIdentity(containerId));
        }
    };

    window.AdminSession = { api, ready, changePassword, manageUser, renderIdentity, user: null };
})();
