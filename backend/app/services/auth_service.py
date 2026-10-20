import os
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "auth.db")

class AuthService:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        os.makedirs(DB_DIR, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _hash_password(self, password: str, salt: str) -> str:
        return hashlib.sha256((salt + password + "DAIKIN_SECRET_PEPPER_2026").encode("utf-8")).hexdigest()

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'engineer',
                    status TEXT NOT NULL DEFAULT 'approved',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)

            # 檢查並確保舊資料表具有 email 與 status 欄位
            cursor.execute("PRAGMA table_info(users)")
            cols = [col[1] for col in cursor.fetchall()]
            if "email" not in cols:
                cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
            if "status" not in cols:
                cursor.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'approved'")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    email TEXT,
                    display_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    user_agent TEXT NOT NULL,
                    details TEXT,
                    timestamp TEXT NOT NULL
                )
            """)

            cursor.execute("PRAGMA table_info(audit_logs)")
            audit_cols = [col[1] for col in cursor.fetchall()]
            if "email" not in audit_cols:
                cursor.execute("ALTER TABLE audit_logs ADD COLUMN email TEXT")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    role TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            # 建立或更新預設種子帳號 (含完整 email，且均為已核准 approved)
            default_users = [
                ("admin", "admin@daikin.com.tw", "daikin2026", "系統管理員", "admin"),
                ("engineer", "engineer@daikin.com.tw", "daikin888", "空調工程師 (測試)", "engineer"),
                ("sales", "sales@daikin.com.tw", "daikin666", "專案業務部", "sales")
            ]
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for u, em, p, name, role in default_users:
                cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (u, em))
                row = cursor.fetchone()
                if not row:
                    salt = secrets.token_hex(8)
                    pwd_hash = self._hash_password(p, salt)
                    cursor.execute(
                        "INSERT INTO users (username, email, password_hash, salt, display_name, role, status, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, 'approved', 1, ?)",
                        (u, em, pwd_hash, salt, name, role, now_str)
                    )
                else:
                    cursor.execute("UPDATE users SET email = ?, status = 'approved', is_active = 1 WHERE id = ?", (em, row[0]))

            conn.commit()

    def register_user(self, email_or_username: str, password: str, display_name: str, role: str, ip: str = "", user_agent: str = "") -> Dict[str, Any]:
        identifier = email_or_username.strip()
        if not identifier or not password:
            return {"success": False, "message": "Email 與密碼不能為空"}
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(COALESCE(email, '')) = LOWER(?)", (identifier, identifier))
            if cursor.fetchone():
                return {"success": False, "message": "此 Email 已經註冊過，若尚未開通請聯繫管理員審核"}
            salt = secrets.token_hex(8)
            pwd_hash = self._hash_password(password, salt)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 新申請註冊的帳號，預設 status='pending', is_active=0，需等管理員核通
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, salt, display_name, role, status, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', 0, ?)",
                (identifier, identifier, pwd_hash, salt, display_name or identifier, role or "engineer", now_str)
            )
            # 寫入日誌通報管理員
            cursor.execute(
                "INSERT INTO audit_logs (username, email, display_name, action, ip_address, user_agent, details, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (identifier, identifier, display_name or identifier, "USER_APPLY", ip, user_agent, f"提出帳號開通申請 (身分: {role})，等待核通", now_str)
            )
            conn.commit()
            return {"success": True, "message": "帳號申請已送出！系統管理員已收到通知，請靜候後台核准開通。"}

    def get_pending_users(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, COALESCE(email, username) as email, display_name, role, status, is_active, created_at 
                FROM users 
                WHERE status = 'pending' OR is_active = 0
                ORDER BY id DESC
            """)
            return [dict(r) for r in cursor.fetchall()]

    def approve_user(self, identifier_or_id: Any, action: str, admin_name: str, ip: str = "", user_agent: str = "") -> Dict[str, Any]:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, email, display_name, role FROM users 
                WHERE id = ? OR LOWER(username) = LOWER(?) OR LOWER(COALESCE(email, '')) = LOWER(?)
            """, (identifier_or_id, str(identifier_or_id), str(identifier_or_id)))
            target_user = cursor.fetchone()
            if not target_user:
                return {"success": False, "message": "查無此待審核使用者"}

            user_email = target_user["email"] or target_user["username"]
            if action == "approve":
                cursor.execute("UPDATE users SET is_active = 1, status = 'approved' WHERE id = ?", (target_user["id"],))
                cursor.execute(
                    "INSERT INTO audit_logs (username, email, display_name, action, ip_address, user_agent, details, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_email, user_email, target_user["display_name"], "USER_APPROVED", ip, user_agent, f"管理員 {admin_name} 已審核通過並開通使用權限", now_str)
                )
                conn.commit()
                return {"success": True, "message": f"已成功核准開通帳號：{user_email}"}
            else:
                cursor.execute("UPDATE users SET is_active = 0, status = 'rejected' WHERE id = ?", (target_user["id"],))
                cursor.execute(
                    "INSERT INTO audit_logs (username, email, display_name, action, ip_address, user_agent, details, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_email, user_email, target_user["display_name"], "USER_REJECTED", ip, user_agent, f"管理員 {admin_name} 駁回此帳號申請", now_str)
                )
                conn.commit()
                return {"success": True, "message": f"已駁回帳號申請：{user_email}"}

    def login(self, identifier: str, password: str, ip: str, user_agent: str) -> Dict[str, Any]:
        identifier = identifier.strip()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM users 
                WHERE LOWER(username) = LOWER(?) OR LOWER(COALESCE(email, '')) = LOWER(?)
            """, (identifier, identifier))
            user = cursor.fetchone()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if not user:
                cursor.execute(
                    "INSERT INTO audit_logs (username, email, display_name, action, ip_address, user_agent, details, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (identifier or "未知Email", identifier or "未知Email", "未知人員", "LOGIN_FAILED", ip, user_agent, "帳號不存在", now_str)
                )
                conn.commit()
                return {"success": False, "message": "Email 或密碼錯誤，請確認後重試"}

            # 驗證密碼
            expected_hash = self._hash_password(password, user["salt"])
            user_email = user["email"] or user["username"]
            if user["password_hash"] != expected_hash:
                cursor.execute(
                    "INSERT INTO audit_logs (username, email, display_name, action, ip_address, user_agent, details, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_email, user_email, user["display_name"], "LOGIN_FAILED", ip, user_agent, "密碼比對失敗", now_str)
                )
                conn.commit()
                return {"success": False, "message": "Email 或密碼錯誤，請確認後重試"}

            # 檢查審核狀態 (核通機制)
            user_status = user["status"] if "status" in user.keys() else ("approved" if user["is_active"] == 1 else "pending")
            if user_status == "pending" or user["is_active"] == 0:
                cursor.execute(
                    "INSERT INTO audit_logs (username, email, display_name, action, ip_address, user_agent, details, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_email, user_email, user["display_name"], "LOGIN_BLOCKED", ip, user_agent, "帳號待管理員審核中", now_str)
                )
                conn.commit()
                return {
                    "success": False,
                    "message": "⚠️ 您的帳號已提出申請，目前正處於【待管理員審核】狀態。管理員後台已收到通知，請靜候核准開通後方可登入！"
                }

            if user_status == "rejected":
                return {
                    "success": False,
                    "message": "❌ 該帳號已被管理員駁回或停用。如有疑問請洽系統管理員。"
                }

            # 登入成功 -> 簽發 Session Token (有效期 7 天)
            token = secrets.token_urlsafe(32)
            expires_at = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO sessions (token, username, role, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (token, user["username"], user["role"], expires_at, now_str)
            )

            # 記錄登入日誌 (使用者欄位優先寫入 Email)
            cursor.execute(
                "INSERT INTO audit_logs (username, email, display_name, action, ip_address, user_agent, details, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_email, user_email, user["display_name"], "LOGIN_SUCCESS", ip, user_agent, f"角色: {user['role']}", now_str)
            )
            conn.commit()

            return {
                "success": True,
                "token": token,
                "user": {
                    "username": user["username"],
                    "email": user_email,
                    "display_name": user["display_name"],
                    "role": user["role"]
                }
            }

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                SELECT s.token, s.username, s.role, u.display_name, COALESCE(u.email, u.username) as email, s.expires_at 
                FROM sessions s
                JOIN users u ON s.username = u.username
                WHERE s.token = ? AND s.expires_at > ? AND u.is_active = 1
            """, (token, now_str))
            row = cursor.fetchone()
            if row:
                return {
                    "token": row["token"],
                    "username": row["username"],
                    "email": row["email"],
                    "display_name": row["display_name"],
                    "role": row["role"]
                }
        return None

    def logout(self, token: str, ip: str = "", user_agent: str = ""):
        if not token:
            return
        user_info = self.verify_token(token)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
            if user_info:
                user_email = user_info.get("email") or user_info.get("username")
                cursor.execute(
                    "INSERT INTO audit_logs (username, email, display_name, action, ip_address, user_agent, details, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_email, user_email, user_info["display_name"], "LOGOUT", ip, user_agent, "主動登出", now_str)
                )
            conn.commit()

    def log_action(self, username: str, display_name: str, action: str, ip: str, user_agent: str, details: str = "", email: str = ""):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_email = email or username or "未知Email"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO audit_logs (username, email, display_name, action, ip_address, user_agent, details, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (log_email, log_email, display_name or "未具名", action, ip, user_agent, details, now_str)
            )
            conn.commit()

    def get_audit_logs(self, limit: int = 150) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, COALESCE(email, username) as email, display_name, action, ip_address, user_agent, details, timestamp
                FROM audit_logs
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def list_users(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, COALESCE(email, username) as email, display_name, role, is_active, created_at FROM users ORDER BY id ASC")
            return [dict(r) for r in cursor.fetchall()]

    def create_user(self, email_or_username: str, password: str, display_name: str, role: str) -> Dict[str, Any]:
        identifier = email_or_username.strip()
        if not identifier or not password:
            return {"success": False, "message": "Email 與密碼不能為空"}
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(COALESCE(email, '')) = LOWER(?)", (identifier, identifier))
            if cursor.fetchone():
                return {"success": False, "message": "此 Email / 帳號已存在，請使用其他電子郵件"}
            salt = secrets.token_hex(8)
            pwd_hash = self._hash_password(password, salt)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, salt, display_name, role, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                (identifier, identifier, pwd_hash, salt, display_name or identifier, role or "engineer", now_str)
            )
            conn.commit()
            return {"success": True, "message": f"成功建立帳號：{identifier}"}
