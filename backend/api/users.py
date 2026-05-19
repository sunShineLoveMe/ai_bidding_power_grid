from flask import Blueprint, request, jsonify
import sqlite3
import json
import logging
from backend.db.supabase_repo import identify_app_user

# 创建蓝图
bp = Blueprint('users', __name__)

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect('bidding.db')
    conn.row_factory = sqlite3.Row
    return conn

@bp.route('/identify', methods=['POST'])
def identify_user():
    """用户识别"""
    data = request.get_json()
    fingerprint_id = data.get('fingerprintId')
    
    if not fingerprint_id:
        return jsonify({'error': '未获取到当前操作人员身份，请刷新页面后重试。'}), 400
    
    try:
        user_id, is_new = identify_app_user(fingerprint_id)
        return jsonify({'userId': user_id, 'isNew': is_new, 'storage': 'supabase'})
    except Exception:
        logging.exception("Supabase 操作人员身份识别失败，回退 SQLite")

    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # 查找现有用户
        cursor.execute('SELECT * FROM users WHERE fingerprint_id = ?', (fingerprint_id,))
        user = cursor.fetchone()
        
        if user:
            # 用户已存在
            conn.close()
            return jsonify({'userId': user['id'], 'isNew': False, 'storage': 'sqlite_fallback'})
        cursor.execute('INSERT INTO users (fingerprint_id) VALUES (?)', (fingerprint_id,))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return jsonify({'userId': user_id, 'isNew': True, 'storage': 'sqlite_fallback'})
            
    except Exception:
        logging.exception("操作人员身份识别失败")
        return jsonify({'error': '操作人员身份识别失败，请联系系统管理员。'}), 500
