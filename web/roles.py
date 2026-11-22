"""Role maintenance and dynamic Nginx authentication, sharing the existing account DB."""
import base64
from datetime import datetime, timezone
from functools import wraps
import json
import re
import secrets
import time
from flask import jsonify, make_response, render_template, request
from werkzeug.security import check_password_hash, generate_password_hash


def seed_super_admin(db, username, password):
    conn = db.get_conn()
    existing = conn.execute('SELECT username FROM users WHERE is_super_admin=1').fetchone()
    if existing:
        return existing['username'], False
    if conn.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone():
        raise ValueError('Initial super administrator username is already in use')
    conn.execute(
        "INSERT INTO users(username,password_hash,is_admin,is_super_admin,status,permissions,must_change_password) "
        "VALUES(?,?,1,1,'approved','[\"*\"]',1)", (username, generate_password_hash(password)))
    conn.commit()
    return username, True


def password_error(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        return '新密码需要 12–128 位'
    groups = [r'[a-z]', r'[A-Z]', r'[0-9]', r'[^A-Za-z0-9]']
    if sum(bool(re.search(pattern, password)) for pattern in groups) < 3:
        return '新密码需包含大小写字母、数字、符号中的至少三类'
    return None


def register(app, ctx):
    db = ctx.skills_db

    def super_only(fn):
        @ctx.admin_only
        @wraps(fn)
        def guarded(*args, **kwargs):
            if not (ctx.get_admin_actor() or {}).get('is_super_admin'):
                return jsonify({'error': '仅超级管理员可管理管理员账户'}), 403
            return fn(*args, **kwargs)
        return guarded

    @app.get('/api/internal/admin-auth')
    def internal_auth():
        if not ctx._admin_key_valid():
            return jsonify({'error': 'internal authentication required'}), 401
        original = request.headers.get('X-Original-URI', '')
        super_scope = original.startswith(('/super-admin', '/api/super-admin'))
        realm = 'Skills Manager Super Admin' if super_scope else 'Skills Manager Admin'
        def challenge():
            response = make_response('', 401)
            response.headers['WWW-Authenticate'] = f'Basic realm="{realm}", charset="UTF-8"'
            return response
        value = request.headers.get('Authorization', '')
        user = None
        try:
            if not value.startswith('Basic ') or len(value) > 2048:
                raise ValueError()
            name, password = base64.b64decode(value[6:], validate=True).decode('utf-8').split(':', 1)
            row = db.get_conn().execute('SELECT * FROM users WHERE username=?', (name,)).fetchone()
            bucket = f'gateway:{ctx._client_ip()}:{name[:40]}'
            if not ctx._rate_limit(bucket, 20, 900):
                return jsonify({'error': '尝试过多，请稍后重试'}), 403
            if row and check_password_hash(row['password_hash'], password):
                user = dict(row)
                ctx._rate_clear(bucket)
        except (ValueError, UnicodeError):
            pass
        if not user:
            return challenge()
        # 账号被删/停用后必须用 401 challenge 让浏览器重新弹出凭据框，
        # 否则浏览器会一直复用失效的 Basic 凭据并收到空 body 的 403，
        # 前端只能显示“请求失败 (403)”而看不到真正原因。
        if user['status'] != 'approved' or not user['is_admin']:
            return challenge()
        if super_scope and not user['is_super_admin']:
            return challenge()
        response = make_response('', 200)
        response.headers['X-Authenticated-User'] = base64.b64encode(user['username'].encode()).decode()
        return response

    @app.get('/api/admin/me')
    @app.get('/api/super-admin/me')
    @ctx.admin_only
    def admin_me():
        user = ctx.get_admin_actor()
        if not user:
            return jsonify({'user': None}), 401
        user['permissions'] = ctx._parse_permissions(user['permissions'])
        return jsonify({'user': user})

    @app.post('/api/admin/change-password')
    @app.post('/api/super-admin/change-password')
    @ctx.admin_only
    def change_password():
        actor = ctx.get_admin_actor()
        data = request.get_json() or {}
        password = data.get('new_password')
        error = password_error(password)
        if error:
            return jsonify({'error': error}), 400
        conn = db.get_conn()
        row = conn.execute('SELECT password_hash FROM users WHERE id=?', (actor['id'],)).fetchone()
        old = data.get('old_password')
        if not isinstance(old, str) or not check_password_hash(row['password_hash'], old):
            return jsonify({'error': '当前密码不正确'}), 400
        if check_password_hash(row['password_hash'], password):
            return jsonify({'error': '新密码不能与原密码相同'}), 400
        conn.execute('UPDATE users SET password_hash=?,must_change_password=0 WHERE id=?',
                     (generate_password_hash(password), actor['id']))
        conn.commit()
        ctx._log_approval(actor['username'], 'change_password', '修改管理员密码')
        return jsonify({'success': True, 'message': '密码已修改，请使用新密码重新登录'})

    @app.get('/super-admin')
    @app.get('/super-admin/')
    def super_page():
        if ctx.admin_dynamic_auth_enabled():
            actor = ctx.get_admin_actor()
            if not actor:
                return jsonify({'error': '需要超级管理员认证'}), 401
            if not actor.get('is_super_admin'):
                return jsonify({'error': '仅超级管理员可访问'}), 403
        return render_template('super_admin.html')

    # HTTP Basic 凭据由浏览器缓存、没有服务端会话，无法靠清 session 退出。
    # 退出方式：返回一个 realm 每次都不同的 401 challenge —— 浏览器无法用旧凭据
    # 匹配新 realm，必然重新弹出登录框；用户取消即退出，输入凭据则以新身份继续。
    _logout_nonces = {}

    def _logout_page(title, text, link='/admin'):
        return (
            '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>' + title + '</title><style>'
            'body{margin:0;background:#f5f7fa;color:#1f2937;font:15px/1.7 -apple-system,'
            'BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}'
            '.c{max-width:460px;margin:14vh auto;background:#fff;border:1px solid #e3e8ef;'
            'border-radius:14px;padding:28px;text-align:center}'
            'h1{font-size:20px;margin:0 0 10px}p{color:#64748b;margin:0 0 20px}'
            'a{display:inline-block;background:#2563eb;color:#fff;text-decoration:none;'
            'padding:10px 18px;border-radius:8px;font-weight:600}'
            '</style></head><body><div class="c"><h1>' + title + '</h1><p>' + text + '</p>'
            '<a href="' + link + '">返回管理后台</a></div></body></html>'
        )

    @app.get('/admin/logout')
    @app.get('/super-admin/logout')
    def admin_logout():
        now = time.time()
        # 清理 5 分钟前的 nonce，避免长期累积
        for key in [k for k, ts in _logout_nonces.items() if now - ts > 300]:
            _logout_nonces.pop(key, None)
        nonce = request.args.get('n', '')
        if not nonce:
            # 直接访问：先跳到带 nonce 的地址。浏览器重试 401 时会原样带上 query，
            # 后端据此区分「首次 challenge」和「用户已提交凭据的重试」。
            new_nonce = secrets.token_hex(12)
            html = ('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" '
                    'content="0;url=' + request.path + '?n=' + new_nonce + '">')
            resp = make_response(html, 200)
            resp.headers['Cache-Control'] = 'no-store'
            return resp
        if _logout_nonces.get(nonce):
            # 用户已在弹出的登录框里提交凭据并重试：消费 nonce，落到成功页，
            # 不让同一 nonce 再次触发 challenge，避免循环弹框。
            _logout_nonces.pop(nonce, None)
            resp = make_response(_logout_page('登录已更新', '凭据已刷新，可以返回管理后台继续操作。'))
            resp.headers['Cache-Control'] = 'no-store'
            return resp
        # 首次请求：记录 nonce 并返回 realm 每次都不同的 401 challenge。
        # Chrome 按 realm 缓存 Basic 凭据，旧凭据对新 realm 无效 → 弹出登录框。
        # 用户点“取消”即退出；输入凭据则带上同一 ?n= 重试并进入上面的消费分支。
        _logout_nonces[nonce] = now
        realm = 'Skills Manager - ' + nonce
        html = _logout_page(
            '已退出登录',
            '若在弹出的登录框中点击“取消”即完成退出；'
            '如需切换账号，请输入新的管理员凭据。'
            '浏览器会缓存登录凭据，请关闭浏览器窗口以彻底退出。',
        )
        resp = make_response(html, 401)
        resp.headers['WWW-Authenticate'] = 'Basic realm="' + realm + '", charset="UTF-8"'
        resp.headers['Cache-Control'] = 'no-store'
        return resp

    @app.get('/api/super-admin/users')
    @super_only
    def super_users():
        rows = db.get_conn().execute(
            'SELECT id,username,email,is_admin,is_super_admin,status,permissions,hide_unauthorized,'
            'must_change_password,created_at,deleted_at,deleted_by FROM users ORDER BY id DESC').fetchall()
        users = []
        for row in rows:
            user = dict(row)
            user['permissions'] = ctx._parse_permissions(user['permissions'])
            users.append(user)
        return jsonify({'users': users})

    def target():
        data = request.get_json() or {}
        name = data.get('username')
        if not isinstance(name, str) or not name:
            return data, None, (jsonify({'error': '用户名必填'}), 400)
        row = db.get_conn().execute('SELECT * FROM users WHERE username=?', (name,)).fetchone()
        if not row:
            return data, None, (jsonify({'error': '账户不存在'}), 404)
        if row['is_super_admin']:
            return data, None, (jsonify({'error': '超级管理员账号受保护，不能降级、禁用或由此重置密码'}), 409)
        if row['status'] == 'deleted':
            return data, None, (jsonify({'error': '账号已删除，请先恢复'}), 409)
        return data, dict(row), None

    @app.post('/api/admin/users/<action>')
    @app.post('/api/super-admin/users/<action>')
    @ctx.admin_only
    def user_lifecycle(action):
        if action not in ('delete', 'restore', 'status'):
            return jsonify({'error': '操作不存在'}), 404
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or type(data.get('user_id')) is not int:
            return jsonify({'error': '需要有效的用户 ID'}), 400
        actor = ctx.get_admin_actor() or {}
        if request.path.startswith('/api/super-admin/') and not actor.get('is_super_admin'):
            return jsonify({'error': '仅超级管理员可访问'}), 403
        conn = db.get_conn()
        user = conn.execute('SELECT * FROM users WHERE id=?', (data['user_id'],)).fetchone()
        if not user:
            return jsonify({'error': '账号不存在'}), 404
        if user['is_super_admin'] or user['id'] == actor.get('id'):
            return jsonify({'error': '不能操作自己或受保护的超级管理员'}), 409
        if user['is_admin'] and not actor.get('is_super_admin'):
            return jsonify({'error': '仅超级管理员可以管理管理员账号'}), 403
        old_status = user['status']
        now = datetime.now(timezone.utc).isoformat()
        if action == 'delete':
            if data.get('confirm_username') != user['username']:
                return jsonify({'error': '请输入完整用户名确认删除'}), 400
            if old_status == 'deleted':
                return jsonify({'error': '账号已在已删除列表'}), 409
            status, label = 'deleted', '删除账号（数据保留，可恢复）'
        elif action == 'restore':
            if old_status != 'deleted':
                return jsonify({'error': '只有已删除账号可以恢复'}), 409
            status = user['deleted_status']
            if status not in ('pending', 'rejected'):
                status = 'disabled'
            label = '恢复账号，状态：' + status
        else:
            if old_status not in ('approved', 'disabled') or type(data.get('enabled')) is not bool:
                return jsonify({'error': '仅已批准或停用账号支持启用/停用；已删除账号请先恢复'}), 409
            status = 'approved' if data['enabled'] else 'disabled'
            if status == old_status:
                return jsonify({'success': True, 'status': status})
            label = '启用账号' if data['enabled'] else '停用账号'
        try:
            updated = conn.execute(
                'UPDATE users SET status=?,auth_version=auth_version+1,deleted_at=?,deleted_by=?,deleted_status=? '
                'WHERE id=? AND status=? AND auth_version=? AND is_admin=? AND is_super_admin=?',
                (status, now if action == 'delete' else None,
                 actor.get('username', 'admin') if action == 'delete' else None,
                 old_status if action == 'delete' else None, user['id'], old_status,
                 user['auth_version'], user['is_admin'], user['is_super_admin']))
            if updated.rowcount != 1:
                conn.rollback()
                return jsonify({'error': '账号状态已变化，请刷新重试'}), 409
            conn.execute('INSERT INTO approval_logs(username,action,detail,actor,created_at) VALUES(?,?,?,?,?)',
                         (user['username'], action + '_user' if action != 'status' else 'change_status',
                          label, actor.get('username', 'admin'), now))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return jsonify({'success': True, 'status': status, 'message': label})

    @app.post('/api/super-admin/role')
    @super_only
    def set_role():
        data, user, error = target()
        if error:
            return error
        role = data.get('role')
        if role not in ('admin', 'user'):
            return jsonify({'error': '角色必须为 admin 或 user'}), 400
        admin = int(role == 'admin')
        conn = db.get_conn()
        conn.execute("UPDATE users SET is_admin=?,must_change_password=?,status=CASE WHEN ?=1 THEN 'approved' ELSE status END,"
                     "approved_by=?,approved_at=? WHERE id=?",
                     (admin,admin,admin,ctx.get_admin_actor()['username'],datetime.now(timezone.utc).isoformat(),user['id']))
        conn.commit()
        ctx._log_approval(user['username'], 'change_role', '晋升管理员' if admin else '降级为普通用户')
        return jsonify({'success': True})

    @app.post('/api/super-admin/status')
    @super_only
    def set_status():
        data, user, error = target()
        if error:
            return error
        if not user['is_admin'] or not isinstance(data.get('enabled'), bool):
            return jsonify({'error': '仅管理员账号支持启用或禁用'}), 400
        status = 'approved' if data['enabled'] else 'disabled'
        conn = db.get_conn()
        conn.execute('UPDATE users SET status=?,auth_version=auth_version+1 WHERE id=?', (status,user['id']))
        conn.commit()
        ctx._log_approval(user['username'], 'change_status', '启用管理员' if data['enabled'] else '禁用管理员')
        return jsonify({'success': True})

    @app.post('/api/super-admin/reset-password')
    @super_only
    def reset_password():
        data, user, error = target()
        if error:
            return error
        if not user['is_admin']:
            return jsonify({'error': '仅支持重置管理员密码'}), 400
        error = password_error(data.get('password'))
        if error:
            return jsonify({'error': error}), 400
        conn = db.get_conn()
        conn.execute('UPDATE users SET password_hash=?,must_change_password=1 WHERE id=?',
                     (generate_password_hash(data['password']),user['id']))
        conn.commit()
        ctx._log_approval(user['username'], 'reset_password', '重置管理员密码，下次登录需修改')
        return jsonify({'success': True})

    # 隐藏偏好由用户自己通过顶栏按钮自助切换（/api/auth/visibility 正常写入）。
    # /api/admin/visibility 是管理员批量设置入口，UI 已移除，保留仅为兼容旧缓存页面，不再写入字段。
    @app.post('/api/admin/visibility')
    @ctx.admin_only
    def admin_visibility():
        data = request.get_json() or {}
        if not isinstance(data.get('username'), str):
            return jsonify({'error': '需要用户名'}), 400
        conn = db.get_conn()
        user = conn.execute('SELECT is_admin,is_super_admin FROM users WHERE username=?', (data['username'],)).fetchone()
        if not user:
            return jsonify({'error': '账户不存在'}), 404
        if user['is_super_admin'] or (user['is_admin'] and not ctx.get_admin_actor().get('is_super_admin')):
            return jsonify({'error': '该账户只能由超级管理员管理'}), 403
        return jsonify({'success': True, 'auto': True})

    @app.post('/api/auth/visibility')
    @ctx.login_required
    def own_visibility():
        data = request.get_json() or {}
        if not isinstance(data.get('hide_unauthorized'), bool):
            return jsonify({'error': 'hide_unauthorized 必须为布尔值'}), 400
        user = ctx.get_current_user()
        conn = db.get_conn()
        conn.execute('UPDATE users SET hide_unauthorized=? WHERE id=?', (int(data['hide_unauthorized']), user['id']))
        conn.commit()
        return jsonify({'success': True, 'hide_unauthorized': data['hide_unauthorized']})

    app.add_url_rule('/api/super-admin/permissions', 'super_permissions_read',
                     super_only(ctx.api_admin_permissions_def), methods=['GET'])
    app.add_url_rule('/api/super-admin/permissions', 'super_permissions_write',
                     super_only(ctx.api_admin_set_permissions), methods=['POST'])
    app.add_url_rule('/api/super-admin/visibility', 'super_visibility',
                     super_only(admin_visibility), methods=['POST'])
