from flask import Blueprint, request, jsonify
import json
import logging
import os
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from backend.core.security import create_session_token, decode_session_token, env_bool, is_production_mode
from backend.db.postgres_compat import _database_url
from backend.db.postgres_pool import pooled_connection
from backend.db.supabase_repo import identify_app_user

# 创建蓝图
bp = Blueprint('users', __name__)


def _normalize_username(value: str | None) -> str:
    return (value or "").strip().lower()


def _public_user(user: dict) -> dict:
    return {
        "id": str(user.get("id")),
        "username": user.get("username"),
        "displayName": user.get("display_name") or user.get("username"),
        "companyName": user.get("company_name") or "",
        "role": user.get("role") or "member",
        "status": user.get("status") or "active",
    }


def _find_login_user(username: str) -> dict | None:
    with pooled_connection(_database_url()) as conn:
        return conn.execute(
            """
            select id, username, password_hash, display_name, company_name, role, status
            from public.app_users
            where lower(username) = lower(%s)
            limit 1
            """,
            (username,),
        ).fetchone()


def _create_login_user(username: str, password: str, display_name: str, company_name: str) -> dict:
    with pooled_connection(_database_url()) as conn:
        existing_count = conn.execute(
            "select count(*)::int as count from public.app_users where username is not null"
        ).fetchone()["count"]
        role = "admin" if existing_count == 0 else "member"
        row = conn.execute(
            """
            insert into public.app_users (username, password_hash, display_name, company_name, role, status)
            values (%s, %s, %s, %s, %s, 'active')
            returning id, username, display_name, company_name, role, status
            """,
            (username, generate_password_hash(password), display_name, company_name, role),
        ).fetchone()
        conn.commit()
        return row


def _touch_login(user_id: str) -> None:
    with pooled_connection(_database_url()) as conn:
        conn.execute(
            "update public.app_users set last_login_at = %s where id = %s",
            (datetime.now(timezone.utc), user_id),
        )
        conn.commit()


def _auth_response(user: dict):
    token = create_session_token(user)
    max_age = int(os.getenv("APP_SESSION_EXPIRES_HOURS", "72") or 72) * 3600
    response = jsonify({"token": token, "user": _public_user(user)})
    response.set_cookie(
        "app_session",
        token,
        httponly=True,
        samesite="Lax",
        secure=env_bool("APP_COOKIE_SECURE", is_production_mode()),
        max_age=max_age,
    )
    return response


@bp.route('/register', methods=['POST'])
def register_user():
    data = request.get_json(silent=True) or {}
    username = _normalize_username(data.get("username"))
    password = data.get("password") or ""
    display_name = (data.get("displayName") or data.get("display_name") or username).strip()
    company_name = (data.get("companyName") or data.get("company_name") or "").strip()

    if len(username) < 3:
        return jsonify({"error": "账号至少需要 3 个字符。"}), 400
    if len(password) < 8:
        return jsonify({"error": "密码至少需要 8 位。"}), 400

    try:
        if _find_login_user(username):
            return jsonify({"error": "该账号已存在，请直接登录。"}), 409
        user = _create_login_user(username, password, display_name, company_name)
        return _auth_response(user), 201
    except Exception as exc:
        logging.exception("用户注册失败")
        return jsonify({"error": f"注册失败: {exc}"}), 500


@bp.route('/login', methods=['POST'])
def login_user():
    data = request.get_json(silent=True) or {}
    username = _normalize_username(data.get("username"))
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "请输入账号和密码。"}), 400

    try:
        user = _find_login_user(username)
        if not user or not user.get("password_hash") or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "账号或密码不正确。"}), 401
        if user.get("status") != "active":
            return jsonify({"error": "账号已停用，请联系管理员。"}), 403
        _touch_login(str(user["id"]))
        return _auth_response(user)
    except Exception as exc:
        logging.exception("用户登录失败")
        return jsonify({"error": f"登录失败: {exc}"}), 500


@bp.route('/me', methods=['GET'])
def current_user():
    auth = request.headers.get("Authorization", "").strip()
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else request.cookies.get("app_session", "")
    payload = decode_session_token(token)
    if not payload:
        return jsonify({"error": "请先登录。"}), 401
    return jsonify({
        "user": {
            "id": payload.get("sub"),
            "username": payload.get("username"),
            "displayName": payload.get("display_name") or payload.get("username"),
            "role": payload.get("role") or "member",
        }
    })


@bp.route('/logout', methods=['POST'])
def logout_user():
    response = jsonify({"ok": True})
    response.delete_cookie("app_session")
    return response

@bp.route('/identify', methods=['POST'])
def identify_user():
    """用户识别"""
    data = request.get_json()
    fingerprint_id = data.get('fingerprintId')
    
    if not fingerprint_id:
        return jsonify({'error': '未获取到当前操作人员身份，请刷新页面后重试。'}), 400
    
    try:
        user_id, is_new = identify_app_user(fingerprint_id)
        return jsonify({'userId': user_id, 'isNew': is_new, 'storage': 'postgres'})
    except Exception:
        logging.exception("操作人员身份识别失败")
        return jsonify({'error': '操作人员身份识别失败，请联系系统管理员。'}), 500
