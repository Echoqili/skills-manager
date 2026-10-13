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
    window.AdminSession = { api, ready, changePassword, user: null };
})();
