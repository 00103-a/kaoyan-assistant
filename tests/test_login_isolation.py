"""
测试登录 Token 隔离：验证两个不同用户的 token 不会互相串号。

复现条件：
- 两个用户各自登录 → 各自生成不同 token → 各自 token 只能查到自己的 user_id
- 验证 monkey-patch 移除后 app.py 仍能正常编译
"""
import sys
import os
import unittest
import secrets
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

# 将项目根目录加入 path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class LoginTokenIsolationTests(unittest.TestCase):
    """Token 隔离测试：验证不同用户 token 不会串号"""

    def setUp(self):
        """使用内存数据库模拟 users 表"""
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                password_hash TEXT,
                login_token TEXT
            )
        """)

    def tearDown(self):
        self.conn.close()

    def _hash(self, pw):
        return hashlib.sha256(pw.encode()).hexdigest()

    def _add_user(self, uid, username, password):
        self.conn.execute(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
            (uid, username, self._hash(password)),
        )
        self.conn.commit()

    def _save_token(self, user_id, token):
        self.conn.execute(
            "UPDATE users SET login_token=? WHERE id=?", (token, user_id)
        )
        self.conn.commit()

    def _verify_token(self, token):
        if not token:
            return None
        row = self.conn.execute(
            "SELECT id, username FROM users WHERE login_token=?", (token,)
        ).fetchone()
        if row:
            return {"user_id": row[0], "username": row[1]}
        return None

    def _generate_token(self):
        return secrets.token_hex(32)

    # ── token 操作基础测试 ──

    def test_generated_token_is_64_chars(self):
        """生成的 token 应为 64 字符十六进制字符串"""
        token = self._generate_token()
        self.assertEqual(len(token), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in token))

    def test_two_tokens_are_different(self):
        """两次生成的 token 应不同"""
        t1 = self._generate_token()
        t2 = self._generate_token()
        self.assertNotEqual(t1, t2)

    def test_verify_valid_token_returns_user(self):
        """有效 token 应返回对应用户信息"""
        self._add_user(1, "alice", "pass1")
        token = self._generate_token()
        self._save_token(1, token)
        result = self._verify_token(token)
        self.assertIsNotNone(result)
        self.assertEqual(result["user_id"], 1)
        self.assertEqual(result["username"], "alice")

    def test_verify_invalid_token_returns_none(self):
        """无效 token 应返回 None"""
        result = self._verify_token("nonexistent_token_1234567890abcdef1234567890abcdef1234567890abcdef")
        self.assertIsNone(result)

    def test_verify_none_token_returns_none(self):
        """None token 应返回 None"""
        result = self._verify_token(None)
        self.assertIsNone(result)

    def test_verify_empty_token_returns_none(self):
        """空字符串 token 应返回 None"""
        result = self._verify_token("")
        self.assertIsNone(result)

    # ── 核心：跨用户隔离测试 ──

    def test_two_users_tokens_are_isolated(self):
        """两个用户各自登录后，各自的 token 只映射到自己的账号"""
        # 创建两个用户
        self._add_user(1, "alice", "pass_alice")
        self._add_user(2, "bob", "pass_bob")

        # Alice 登录 → 生成 token_A
        token_alice = self._generate_token()
        self._save_token(1, token_alice)

        # Bob 登录 → 生成 token_B
        token_bob = self._generate_token()
        self._save_token(2, token_bob)

        # 验证 token_A 只返回 Alice
        r = self._verify_token(token_alice)
        self.assertEqual(r["user_id"], 1)
        self.assertEqual(r["username"], "alice")

        # 验证 token_B 只返回 Bob
        r = self._verify_token(token_bob)
        self.assertEqual(r["user_id"], 2)
        self.assertEqual(r["username"], "bob")

    def test_token_a_cannot_find_user_b(self):
        """用 Alice 的 token 不能查到 Bob"""
        self._add_user(1, "alice", "pass")
        self._add_user(2, "bob", "pass")

        token_alice = self._generate_token()
        self._save_token(1, token_alice)

        # Alice 的 token 应返回 alice，而不是 bob
        r = self._verify_token(token_alice)
        self.assertEqual(r["user_id"], 1)

    def test_token_overwrite_isolation(self):
        """用户重新登录（token 被覆盖）后，旧 token 失效，新 token 正确"""
        self._add_user(1, "alice", "pass")

        # 第一次登录
        token_old = self._generate_token()
        self._save_token(1, token_old)

        # 第二次登录（覆盖 token）
        token_new = self._generate_token()
        self._save_token(1, token_new)

        # 旧 token 失效
        self.assertIsNone(self._verify_token(token_old))

        # 新 token 有效
        r = self._verify_token(token_new)
        self.assertEqual(r["user_id"], 1)

    def test_same_token_in_db_returns_some_user(self):
        """验证：如果两个用户被意外写入相同 token（本不该发生），
        查询会返回其中一个用户（取决于 DB 实现），但至少不会返回 None
        这说明同 token 必然导致串号 —— 所以必须保证 token 唯一性"""
        self._add_user(1, "alice", "pass")
        self._add_user(2, "bob", "pass")

        shared_token = self._generate_token()
        self._save_token(1, shared_token)
        self._save_token(2, shared_token)

        # 两个用户都有相同 token（模拟异常场景）
        # 至少应该返回一个有效用户（而不是 None 或 crash）
        r = self._verify_token(shared_token)
        self.assertIsNotNone(r)
        self.assertIn(r["user_id"], [1, 2])
        self.assertIn(r["username"], ["alice", "bob"])

    # ── 编译验证 ──

    def test_app_compiles_without_monkey_patch_error(self):
        """验证 app.py 可以正常编译（无语法错误）"""
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        source = app_path.read_text(encoding="utf-8-sig")

        # 不做 import（会触发 streamlit 运行时），只验证语法编译
        compile(source, str(app_path), "exec")

    def test_cookie_manager_not_using_cache_resource(self):
        """验证 CookieManager 不再使用 @st.cache_resource（防止跨 session 缓存）"""
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        source = app_path.read_text(encoding="utf-8-sig")

        # 检查 get_cookie_manager 函数周围不再有 @st.cache_resource
        import re
        # 找到 get_cookie_manager 函数定义
        func_match = re.search(r'def get_cookie_manager\(\):', source)
        self.assertIsNotNone(func_match, "找不到 get_cookie_manager 函数")

        # 检查函数前 5 行内不应有 @st.cache_resource
        lines_before = source[:func_match.start()].split('\n')
        last_lines = [l.strip() for l in lines_before[-6:]]
        cache_found = '@st.cache_resource' in last_lines
        self.assertFalse(
            cache_found,
            "get_cookie_manager 不应再使用 @st.cache_resource，"
            "请改用 st.session_state 确保跨用户 session 隔离"
        )


if __name__ == "__main__":
    unittest.main()
