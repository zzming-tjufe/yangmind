import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import {
  assignInviteCode,
  createInviteCode,
  getInviteCodes,
  getSubAdmins,
  setUserStatus,
  toggleInviteCode,
  type InviteCode,
  type SubAdmin,
} from "../api/admin";
import { AdminListStatus } from "../components/AdminListStatus";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { copyText } from "../lib/clipboard";
import { isSuperAdmin } from "../lib/roles";

type Props = {
  /** 侧栏入口：邀请码 / 子管理员 */
  section?: "invites" | "sub_admins";
};

export function AdminAccountsPage({ section = "invites" }: Props) {
  const { user } = useAuth();
  const { toast } = useToast();
  const superAdmin = isSuperAdmin(user?.role);
  const showInvites = section === "invites";
  const showSubAdmins = section === "sub_admins" && superAdmin;

  const [invites, setInvites] = useState<InviteCode[]>([]);
  const [subAdmins, setSubAdmins] = useState<SubAdmin[]>([]);
  const [code, setCode] = useState("");
  const [kind, setKind] = useState<"sub_admin" | "participant">("participant");
  const [maxUses, setMaxUses] = useState(0);
  const [note, setNote] = useState("");
  const [ownerId, setOwnerId] = useState<number | "">("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      if (showInvites || showSubAdmins) {
        const i = await getInviteCodes();
        setInvites(i);
      }
      if (superAdmin) {
        setSubAdmins(await getSubAdmins());
      } else {
        setSubAdmins([]);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load().catch((err) => {
      setLoading(false);
      toast(err instanceof ApiError ? err.message : "加载失败");
    });
  }, [toast, superAdmin, section]);

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

  async function toggleSubAdmin(s: SubAdmin) {
    const next = s.status === "active" ? "disabled" : "active";
    setBusy(true);
    try {
      await setUserStatus(s.id, next);
      await load();
      toast(next === "active" ? "已启用子管理员" : "已禁用子管理员");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  async function copyCode(text: string) {
    const ok = await copyText(text);
    if (ok) toast("邀请码已复制");
    else toast(`复制失败，请手动复制：${text}`);
  }

  const activeSubAdmins = subAdmins.filter((s) => s.status === "active");

  return (
    <div className="page">
      {showInvites && superAdmin ? (
        <div className="settings">
          <article className="setting card">
            <i>码</i>
            <h3>怎么注册</h3>
            <p>同学注册必须填邀请码。子管码 → 注册成子管理员；参与者码 → 注册成普通参与者（一般先分给子管再转发）。</p>
          </article>
          <article className="setting card">
            <i>流</i>
            <h3>建议流程</h3>
            <p>先发「子管邀请码」让同学成为子管，再创建「参与者邀请码」分配给他们去拉人。</p>
          </article>
          <article className="setting card">
            <i>协</i>
            <h3>子管去哪管</h3>
            <p>看谁注册成了子管、启停登录，请到左侧「子管理员」。发码相关留痕在「操作记录」。</p>
          </article>
        </div>
      ) : null}

      {showInvites && !superAdmin ? (
        <div className="settings">
          <article className="setting card">
            <i>码</i>
            <h3>我的邀请码</h3>
            <p>总管分给你的码在下面。复制发给同学注册即可；你不能自己新建邀请码。</p>
          </article>
        </div>
      ) : null}

      {showSubAdmins ? (
        <div className="settings">
          <article className="setting card">
            <i>协</i>
            <h3>子管理员是谁</h3>
            <p>用「子管邀请码」注册的同学会出现在这里。可以启用或禁用他们登录。</p>
          </article>
          <article className="setting card">
            <i>码</i>
            <h3>怎么加人</h3>
            <p>去左侧「邀请码」创建子管码，发给对方注册。参与者码也是在邀请码页分配给他们转发。</p>
          </article>
        </div>
      ) : null}

      {showInvites && superAdmin ? (
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
                <option value="participant">参与者邀请码（分给子管转发）</option>
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
                  {activeSubAdmins.map((s) => (
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

      {showSubAdmins ? (
        <section className="table card" style={{ marginTop: 18 }}>
          <div className="tablehead">
            <h3>子管理员列表</h3>
            <span style={{ opacity: 0.65, fontSize: 13 }}>{subAdmins.length} 人</span>
          </div>
          <div
            className="row header sub-admin-head"
            style={{ gridTemplateColumns: "1fr 1.2fr 0.9fr 0.8fr 0.7fr 0.8fr" }}
          >
            <span>昵称 / ID</span>
            <span>邮箱</span>
            <span>注册所用子管码</span>
            <span>名下参与者码</span>
            <span>状态</span>
            <span>操作</span>
          </div>
          {loading ? (
            <AdminListStatus loading />
          ) : subAdmins.length === 0 ? (
            <AdminListStatus
              empty
              emptyText="还没有子管理员。去「邀请码」创建子管码，对方注册后会出现在这里。"
            />
          ) : (
            subAdmins.map((s) => (
              <div
                className="row sub-admin-row"
                key={s.id}
                style={{ gridTemplateColumns: "1fr 1.2fr 0.9fr 0.8fr 0.7fr 0.8fr" }}
              >
                <span>
                  <b>{s.nickname}</b>
                  {s.is_debug ? (
                    <small style={{ display: "block", color: "#8a5a10" }}>调试账号</small>
                  ) : null}
                  <small style={{ display: "block", opacity: 0.7 }}>{s.public_id}</small>
                </span>
                <span>{s.email}</span>
                <span>{s.invite_code || "—"}</span>
                <span>{s.owned_invite_count ?? 0}</span>
                <span className={`badge ${s.status === "active" ? "" : "warn"}`}>
                  {s.status === "active" ? "正常" : "已禁用"}
                </span>
                <div>
                  <button
                    className="secondary"
                    type="button"
                    disabled={busy}
                    onClick={() => toggleSubAdmin(s)}
                  >
                    {s.status === "active" ? "禁用" : "启用"}
                  </button>
                </div>
              </div>
            ))
          )}
        </section>
      ) : null}

      {showInvites ? (
        <section className="table card" style={{ marginTop: 18 }}>
          <div className="tablehead">
            <h3>{superAdmin ? "邀请码列表" : "可转发的邀请码"}</h3>
          </div>
          <div
            className="row header invite-head"
            style={{
              gridTemplateColumns: superAdmin
                ? "1.1fr 0.9fr 0.8fr 0.7fr 1fr 1.2fr"
                : "1.2fr 0.9fr 0.7fr 1fr 0.8fr",
            }}
          >
            <span>邀请码</span>
            <span>类型</span>
            <span>用量</span>
            <span>状态</span>
            {superAdmin ? <span>归属 / 注册人</span> : null}
            <span>操作</span>
          </div>
          {loading ? (
            <AdminListStatus loading />
          ) : invites.length === 0 ? (
            <AdminListStatus
              empty
              emptyText={superAdmin ? "暂无邀请码" : "总管还没给你分配邀请码"}
            />
          ) : (
            invites.map((inv) => (
              <div
                className="row invite-row"
                key={inv.id}
                style={{
                  gridTemplateColumns: superAdmin
                    ? "1.1fr 0.9fr 0.8fr 0.7fr 1fr 1.2fr"
                    : "1.2fr 0.9fr 0.7fr 1fr 0.8fr",
                }}
              >
                <b>{inv.code}</b>
                <span>
                  {inv.kind === "sub_admin" ? "子管码" : "参与者码"}
                  {inv.is_debug ? " · 调试" : ""}
                </span>
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
                          {s.status !== "active" ? "（已禁用）" : ""}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span>
                      {subAdmins
                        .filter((s) => s.invite_code_id === inv.id)
                        .map((s) => s.nickname)
                        .join("、") || "—"}
                    </span>
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
            ))
          )}
        </section>
      ) : null}
    </div>
  );
}
