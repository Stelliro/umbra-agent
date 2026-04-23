"""Tests for simplified JSON auth"""
import sys, json, tempfile, shutil
sys.path.insert(0, '/home/claude')
from auth import AuthManager

def test_default_creds():
    tmp = tempfile.mkdtemp()
    mgr = AuthManager(tmp)
    creds = json.loads((mgr.path).read_text())
    assert creds["username"] == "admin"
    assert creds["password"] == "umbra"
    print("✓ Default login.json created")
    shutil.rmtree(tmp)

def test_login():
    tmp = tempfile.mkdtemp()
    mgr = AuthManager(tmp)
    assert mgr.login("admin", "umbra") is not None
    assert mgr.login("admin", "wrong") is None
    assert mgr.login("nobody", "umbra") is None
    print("✓ Login works")
    shutil.rmtree(tmp)

def test_session():
    tmp = tempfile.mkdtemp()
    mgr = AuthManager(tmp)
    token = mgr.login("admin", "umbra")
    assert mgr.validate_session(token) == "admin"
    assert mgr.validate_session("bogus") is None
    assert mgr.validate_session(None) is None
    print("✓ Sessions work")
    shutil.rmtree(tmp)

def test_logout():
    tmp = tempfile.mkdtemp()
    mgr = AuthManager(tmp)
    token = mgr.login("admin", "umbra")
    mgr.logout(token)
    assert mgr.validate_session(token) is None
    print("✓ Logout works")
    shutil.rmtree(tmp)

def test_change_password():
    tmp = tempfile.mkdtemp()
    mgr = AuthManager(tmp)
    r = mgr.change_password("admin", "umbra", "newpass")
    assert r["success"] == True
    assert mgr.login("admin", "umbra") is None
    assert mgr.login("admin", "newpass") is not None
    creds = json.loads(mgr.path.read_text())
    assert creds["password"] == "newpass"
    print("✓ Change password")
    shutil.rmtree(tmp)

def test_change_password_wrong():
    tmp = tempfile.mkdtemp()
    mgr = AuthManager(tmp)
    r = mgr.change_password("admin", "wrong", "newpass")
    assert r["success"] == False
    assert mgr.login("admin", "umbra") is not None
    print("✓ Change password rejects wrong current")
    shutil.rmtree(tmp)

def test_change_username():
    tmp = tempfile.mkdtemp()
    mgr = AuthManager(tmp)
    r = mgr.change_username("admin", "umbra", "stelliro")
    assert r["success"] == True
    assert mgr.login("admin", "umbra") is None
    assert mgr.login("stelliro", "umbra") is not None
    creds = json.loads(mgr.path.read_text())
    assert creds["username"] == "stelliro"
    print("✓ Change username")
    shutil.rmtree(tmp)

def test_change_username_wrong():
    tmp = tempfile.mkdtemp()
    mgr = AuthManager(tmp)
    r = mgr.change_username("admin", "wrong", "stelliro")
    assert r["success"] == False
    assert mgr.login("admin", "umbra") is not None
    print("✓ Change username rejects wrong password")
    shutil.rmtree(tmp)

def test_sessions_cleared_on_change():
    tmp = tempfile.mkdtemp()
    mgr = AuthManager(tmp)
    token = mgr.login("admin", "umbra")
    assert mgr.validate_session(token) == "admin"
    mgr.change_password("admin", "umbra", "new")
    assert mgr.validate_session(token) is None
    print("✓ Sessions cleared after credential change")
    shutil.rmtree(tmp)

def test_compat_stubs():
    tmp = tempfile.mkdtemp()
    mgr = AuthManager(tmp)
    assert mgr.has_admin() == True
    assert mgr.create_admin("x", "y") == "ok"
    token = mgr.login("x", "y")
    assert mgr.check_permission(token, "anything") == True
    assert mgr.check_token_limit(token, 9999) == True
    print("✓ Compat stubs work")
    shutil.rmtree(tmp)

if __name__ == "__main__":
    print("=" * 50)
    print("AUTH (SIMPLE JSON) TESTS")
    print("=" * 50)
    tests = [
        test_default_creds, test_login, test_session, test_logout,
        test_change_password, test_change_password_wrong,
        test_change_username, test_change_username_wrong,
        test_sessions_cleared_on_change, test_compat_stubs,
    ]
    for t in tests:
        t()
    print(f"\n{'='*50}\nALL {len(tests)} TESTS PASSED ✓\n{'='*50}")
