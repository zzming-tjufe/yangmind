import { useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import * as authApi from "../api/auth";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

export function ProfilePage() {
  const { user, logout } = useAuth();
  const { toast } = useToast();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (newPassword.length < 6) {
      toast("新密码至少需要 6 个字符");
      return;
    }
    if (newPassword !== confirmPassword) {
      toast("两次输入的新密码不一致");
      return;
    }
    setBusy(true);
    try {
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      toast("密码已更新，请使用新密码重新登录");
      logout();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "修改失败");
    } finally {
      setBusy(false);
    }
  }

  const passwordType = show ? "text" : "password";

  return (
    <div className="page">
      <section className="hero card">
        <div>
          <div className="eyebrow">ACCOUNT</div>
          <h2>我的账号</h2>
          <p>查看基本信息，并在需要时自行修改登录密码。</p>
        </div>
      </section>

      <section className="card" style={{ marginTop: 18, padding: 22 }}>
        <div className="tablehead" style={{ border: 0, padding: 0, marginBottom: 16 }}>
          <h3>账号信息</h3>
        </div>
        <div className="profile-info-grid">
          <div>
            <small>昵称</small>
            <b>{user?.nickname}</b>
          </div>
          <div>
            <small>ID</small>
            <b>{user?.public_id}</b>
          </div>
          <div>
            <small>邮箱</small>
            <b>{user?.email}</b>
          </div>
        </div>
      </section>

      <section className="card" style={{ marginTop: 18, padding: 22 }}>
        <div className="tablehead" style={{ border: 0, padding: 0, marginBottom: 16 }}>
          <h3>修改密码</h3>
          <button className="secondary" type="button" onClick={() => setShow((v) => !v)}>
            {show ? "隐藏" : "显示"}密码
          </button>
        </div>
        <form className="cms-form" style={{ padding: 0 }} onSubmit={onSubmit}>
          <label className="field">
            当前密码
            <input
              type={passwordType}
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          <label className="field">
            新密码
            <input
              type={passwordType}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              required
              minLength={6}
            />
          </label>
          <label className="field">
            确认新密码
            <input
              type={passwordType}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              required
              minLength={6}
            />
          </label>
          <div className="cms-form-actions">
            <button className="primary" type="submit" disabled={busy}>
              {busy ? "保存中…" : "更新密码"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
