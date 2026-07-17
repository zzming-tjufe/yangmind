import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import {
  createInviteCode,
  getAccountEvents,
  getInviteCodes,
  toggleInviteCode,
  type AccountEvent,
  type InviteCode,
} from "../api/admin";
import { useToast } from "../context/ToastContext";

export function AdminAccountsPage() {
  const { toast } = useToast();
  const [invites, setInvites] = useState<InviteCode[]>([]);
  const [events, setEvents] = useState<AccountEvent[]>([]);
  const [code, setCode] = useState("");
  const [maxUses, setMaxUses] = useState(0);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const [i, e] = await Promise.all([getInviteCodes(), getAccountEvents()]);
    setInvites(i);
    setEvents(e);
  }

  useEffect(() => {
    load().catch((err) => toast(err instanceof ApiError ? err.message : "加载失败"));
  }, [toast]);

  async function onCreate() {
    if (!code.trim()) {
      toast("请输入邀请码");
      return;
    }
    setBusy(true);
    try {
      await createInviteCode({ code: code.trim(), max_uses: maxUses, note });
      setCode("");
      setNote("");
      setMaxUses(0);
      await load();
      toast("邀请码已创建");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "创建失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <div className="settings">
        <article className="setting card">
          <i>✉</i>
          <h3>注册策略</h3>
          <p>开放邮箱注册。可选填写邀请码；若填写则必须有效且未用尽。</p>
        </article>
        <article className="setting card">
          <i>⌁</i>
          <h3>登录安全</h3>
          <p>禁用账号后将无法登录。可在「用户数据」中启用/禁用或重置密码。</p>
        </article>
        <article className="setting card">
          <i>#</i>
          <h3>实验邀请码</h3>
          <p>用于定向招募。最大次数为 0 表示不限次数。</p>
        </article>
      </div>

      <section className="card" style={{ marginTop: 18, padding: 22 }}>
        <div className="tablehead" style={{ border: 0, padding: 0, marginBottom: 16 }}>
          <h3>创建邀请码</h3>
        </div>
        <div className="invite-form">
          <label className="field">
            邀请码
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="例如 YM2026" />
          </label>
          <label className="field">
            最大使用次数（0=不限）
            <input
              type="number"
              min={0}
              value={maxUses}
              onChange={(e) => setMaxUses(Number(e.target.value) || 0)}
            />
          </label>
          <label className="field">
            备注
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="班级 / 批次" />
          </label>
          <button className="primary" type="button" disabled={busy} onClick={onCreate}>
            创建
          </button>
        </div>
      </section>

      <section className="table card" style={{ marginTop: 18 }}>
        <div className="tablehead">
          <h3>邀请码列表</h3>
        </div>
        <div className="row header invite-head">
          <span>邀请码</span>
          <span>用量</span>
          <span>状态</span>
          <span>备注</span>
          <span>操作</span>
        </div>
        {invites.map((inv) => (
          <div className="row invite-row" key={inv.id}>
            <b>{inv.code}</b>
            <span>
              {inv.used_count}
              {inv.max_uses > 0 ? ` / ${inv.max_uses}` : " / ∞"}
            </span>
            <span className={`badge ${inv.enabled ? "" : "warn"}`}>
              {inv.enabled ? "启用" : "停用"}
            </span>
            <span>{inv.note || "—"}</span>
            <button
              className="secondary"
              type="button"
              onClick={async () => {
                try {
                  await toggleInviteCode(inv.id, !inv.enabled);
                  await load();
                  toast(inv.enabled ? "已停用" : "已启用");
                } catch (e) {
                  toast(e instanceof ApiError ? e.message : "失败");
                }
              }}
            >
              {inv.enabled ? "停用" : "启用"}
            </button>
          </div>
        ))}
        {invites.length === 0 && (
          <div className="row" style={{ gridTemplateColumns: "1fr" }}>
            <span>暂无邀请码</span>
          </div>
        )}
      </section>

      <section className="table card" style={{ marginTop: 18 }}>
        <div className="tablehead">
          <h3>账号事件</h3>
        </div>
        {events.map((ev) => (
          <div className="row event-row" key={ev.id}>
            <span>
              <b>{ev.event_type}</b>
              {ev.detail ? ` · ${ev.detail}` : ""}
            </span>
            <span>{ev.created_at ? new Date(ev.created_at).toLocaleString() : ""}</span>
          </div>
        ))}
        {events.length === 0 && (
          <div className="row" style={{ gridTemplateColumns: "1fr" }}>
            <span>暂无事件</span>
          </div>
        )}
      </section>
    </div>
  );
}
