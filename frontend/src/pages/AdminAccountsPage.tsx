import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import {
  assignInviteCode,
  createInviteCode,
  getAccountEvents,
  getInviteCodes,
  getSubAdmins,
  toggleInviteCode,
  type AccountEvent,
  type InviteCode,
  type SubAdmin,
} from "../api/admin";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { isSuperAdmin } from "../lib/roles";

export function AdminAccountsPage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const superAdmin = isSuperAdmin(user?.role);
  const [invites, setInvites] = useState<InviteCode[]>([]);
  const [events, setEvents] = useState<AccountEvent[]>([]);
  const [subAdmins, setSubAdmins] = useState<SubAdmin[]>([]);
  const [code, setCode] = useState("");
  const [kind, setKind] = useState<"sub_admin" | "participant">("participant");
  const [maxUses, setMaxUses] = useState(0);
  const [note, setNote] = useState("");
  const [ownerId, setOwnerId] = useState<number | "">("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const i = await getInviteCodes();
    setInvites(i);
    if (superAdmin) {
      const [e, s] = await Promise.all([getAccountEvents(), getSubAdmins()]);
      setEvents(e);
      setSubAdmins(s);
    } else {
      setEvents([]);
      setSubAdmins([]);
    }
  }

  useEffect(() => {
    load().catch((err) => toast(err instanceof ApiError ? err.message : "加载失败"));
  }, [toast, superAdmin]);

  async function onCreate() {
    if (!code.trim()) {
      toast("请输入邀请码");
      return;
    }
    setBusy(true);
    try {
      await createInviteCode({
        code: code.trim(),
        kind,
        max_uses: maxUses,
        note,
        owner_id: kind === "participant" && ownerId !== "" ? Number(ownerId) : null,
      });
      setCode("");
      setNote("");
      setMaxUses(0);
      setOwnerId("");
      await load();
      toast("邀请码已创建");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function onAssign(inv: InviteCode, nextOwner: string) {
    const value = nextOwner === "" ? null : Number(nextOwner);
    try {
      await assignInviteCode(inv.id, value);
      await load();
      toast(value == null ? "已取消分配" : "已分配给子管理员");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "分配失败");
    }
  }

  async function copyCode(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast("邀请码已复制");
    } catch {
      toast(`邀请码：${text}`);
    }
  }

  return (
    <div className="page">
      {superAdmin ? (
        <div className="settings">
          <article className="setting card">
            <i>✉</i>
            <h3>注册策略</h3>
            <p>必须填写邀请码才能注册。子管码注册后成为子管理员；员工码须先分配给子管。</p>
          </article>
          <article className="setting card">
            <i>#</i>
            <h3>两层邀请码</h3>
            <p>先发「子管邀请码」给同学注册成子管，再创建「员工邀请码」并分配给他们转发。</p>
          </article>
          <article className="setting card">
            <i>⌁</i>
            <h3>登录安全</h3>
            <p>禁用账号后将无法登录。可在「用户数据」中启用/禁用或重置密码。</p>
          </article>
        </div>
      ) : (
        <div className="settings">
          <article className="setting card">
            <i>#</i>
            <h3>我的员工邀请码</h3>
            <p>总管分配给你的邀请码如下。请复制后发给员工注册；你无法自行创建新码。</p>
          </article>
        </div>
      )}

      {superAdmin ? (
        <section className="card" style={{ marginTop: 18, padding: 22 }}>
          <div className="tablehead" style={{ border: 0, padding: 0, marginBottom: 16 }}>
            <h3>创建邀请码</h3>
          </div>
          <div className="invite-form">
            <label className="field">
              邀请码
              <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="例如 YM-SUB-01" />
            </label>
            <label className="field">
              类型
              <select value={kind} onChange={(e) => setKind(e.target.value as "sub_admin" | "participant")}>
                <option value="participant">员工邀请码（分给子管转发）</option>
                <option value="sub_admin">子管邀请码（注册即成子管理员）</option>
              </select>
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
            {kind === "participant" ? (
              <label className="field">
                分配给子管理员（可稍后分配）
                <select
                  value={ownerId === "" ? "" : String(ownerId)}
                  onChange={(e) => setOwnerId(e.target.value === "" ? "" : Number(e.target.value))}
                >
                  <option value="">暂不分配</option>
                  {subAdmins.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.nickname} · {s.email}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <button className="primary" type="button" disabled={busy} onClick={onCreate}>
              创建
            </button>
          </div>
        </section>
      ) : null}

      <section className="table card" style={{ marginTop: 18 }}>
        <div className="tablehead">
          <h3>{superAdmin ? "邀请码列表" : "可转发的员工邀请码"}</h3>
        </div>
        <div className="row header invite-head" style={{ gridTemplateColumns: superAdmin ? "1.1fr 0.9fr 0.8fr 0.7fr 1fr 1.2fr" : "1.2fr 0.9fr 0.7fr 1fr 0.8fr" }}>
          <span>邀请码</span>
          <span>类型</span>
          <span>用量</span>
          <span>状态</span>
          {superAdmin ? <span>归属子管</span> : null}
          <span>操作</span>
        </div>
        {invites.map((inv) => (
          <div
            className="row invite-row"
            key={inv.id}
            style={{ gridTemplateColumns: superAdmin ? "1.1fr 0.9fr 0.8fr 0.7fr 1fr 1.2fr" : "1.2fr 0.9fr 0.7fr 1fr 0.8fr" }}
          >
            <b>{inv.code}</b>
            <span>{inv.kind === "sub_admin" ? "子管码" : "员工码"}</span>
            <span>
              {inv.used_count}
              {inv.max_uses > 0 ? ` / ${inv.max_uses}` : " / ∞"}
            </span>
            <span className={`badge ${inv.enabled ? "" : "warn"}`}>
              {inv.enabled ? "启用" : "停用"}
            </span>
            {superAdmin ? (
              inv.kind === "participant" ? (
                <select
                  value={inv.owner_id ?? ""}
                  onChange={(e) => onAssign(inv, e.target.value)}
                >
                  <option value="">未分配</option>
                  {subAdmins.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.nickname}
                    </option>
                  ))}
                </select>
              ) : (
                <span>—</span>
              )
            ) : null}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="secondary" type="button" onClick={() => copyCode(inv.code)}>
                复制
              </button>
              {superAdmin ? (
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
              ) : null}
            </div>
          </div>
        ))}
        {invites.length === 0 && (
          <div className="row" style={{ gridTemplateColumns: "1fr" }}>
            <span>{superAdmin ? "暂无邀请码" : "总管尚未给你分配员工邀请码"}</span>
          </div>
        )}
      </section>

      {superAdmin ? (
        <section className="table card" style={{ marginTop: 18 }}>
          <div className="tablehead">
            <h3>账号事件</h3>
          </div>
          <div className="row header event-row">
            <span>事件</span>
            <span>时间</span>
          </div>
          {events.map((ev) => (
            <div className="row event-row" key={ev.id}>
              <span className="event-copy">
                <b>{ev.title || ev.event_type}</b>
                <small>{ev.detail || "无更多说明"}</small>
              </span>
              <span className="event-time">
                {ev.created_at
                  ? new Date(ev.created_at).toLocaleString("zh-CN", {
                      year: "numeric",
                      month: "2-digit",
                      day: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "—"}
              </span>
            </div>
          ))}
          {events.length === 0 && (
            <div className="row" style={{ gridTemplateColumns: "1fr" }}>
              <span>暂无事件</span>
            </div>
          )}
        </section>
      ) : null}
    </div>
  );
}
