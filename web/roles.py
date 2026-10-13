"""Role maintenance and dynamic Nginx authentication, sharing the existing account DB."""
import base64
from datetime import datetime, timezone
from functools import wraps
import json
import re
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
        if user['status'] != 'approved' or not user['is_admin']:
            return make_response('', 403)
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

    @app.get('/api/super-admin/users')
    @super_only
    def super_users():
        rows = db.get_conn().execute(
            'SELECT id,username,email,is_admin,is_super_admin,status,permissions,hide_unauthorized,'
            'must_change_password,created_at FROM users ORDER BY id DESC').fetchall()
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
        return data, dict(row), None

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
        conn.execute('UPDATE users SET status=? WHERE id=?', (status,user['id']))
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

    @app.post('/api/admin/visibility')
    @ctx.admin_only
    def admin_visibility():
        data = request.get_json() or {}
        if not isinstance(data.get('username'), str) or not isinstance(data.get('hide_unauthorized'), bool):
            return jsonify({'error': '需要用户名与隐藏设置'}), 400
        conn = db.get_conn()
        user = conn.execute('SELECT id,is_admin,is_super_admin FROM users WHERE username=?', (data['username'],)).fetchone()
        if not user:
            return jsonify({'error': '账户不存在'}), 404
        if user['is_super_admin'] or (user['is_admin'] and not ctx.get_admin_actor().get('is_super_admin')):
            return jsonify({'error': '该账户只能由超级管理员管理'}), 403
        conn.execute('UPDATE users SET hide_unauthorized=? WHERE id=?', (int(data['hide_unauthorized']),user['id']))
        conn.commit()
        ctx._log_approval(data['username'], 'visibility', '隐藏未授权功能' if data['hide_unauthorized'] else '显示未授权入口')
        return jsonify({'success': True})

    @app.post('/api/auth/visibility')
    @ctx.login_required
    def own_visibility():
        data = request.get_json() or {}
        if not isinstance(data.get('hide_unauthorized'), bool):
            return jsonify({'error': 'hide_unauthorized 必须为布尔值'}), 400
        user = ctx.get_current_user()
        conn = db.get_conn()
        conn.execute('UPDATE users SET hide_unauthorized=? WHERE id=?', (int(data['hide_unauthorized']),user['id']))
        conn.commit()
        return jsonify({'success': True, 'hide_unauthorized': data['hide_unauthorized']})

    app.add_url_rule('/api/super-admin/permissions', 'super_permissions_read',
                     super_only(ctx.api_admin_permissions_def), methods=['GET'])
    app.add_url_rule('/api/super-admin/permissions', 'super_permissions_write',
                     super_only(ctx.api_admin_set_permissions), methods=['POST'])
    app.add_url_rule('/api/super-admin/visibility', 'super_visibility',
                     super_only(admin_visibility), methods=['POST'])
