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
    window.AdminSession = { api, ready, changePassword, manageUser, user: null };
})();
