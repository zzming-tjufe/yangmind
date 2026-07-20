import { useEffect, type ReactNode } from "react";
import { useAuth } from "../context/AuthContext";
import { useSitePages } from "../hooks/useSite";
import { isStaff, isSubAdmin, isSuperAdmin } from "../lib/roles";
import { AnnouncementBell } from "./AnnouncementBell";

type View =
  | "bfi"
  | "games"
  | "rank"
  | "notices"
  | "profile"
  | "users"
  | "experiments"
  | "accounts"
  | "pages"
  | "content";

const userNavBase: { id: View; icon: string; label: string }[] = [
  { id: "bfi", icon: "◇", label: "BFI-44 问卷" },
  { id: "games", icon: "◎", label: "博弈 PK" },
  { id: "rank", icon: "↗", label: "排行榜" },
  { id: "profile", icon: "◌", label: "我的账号" },
];

const superAdminNav: { id: View; icon: string; label: string }[] = [
  { id: "users", icon: "◉", label: "用户数据" },
  { id: "experiments", icon: "⌁", label: "博弈实验" },
  { id: "accounts", icon: "⊕", label: "注册与登录" },
  { id: "pages", icon: "▤", label: "页面管理" },
  { id: "content", icon: "✦", label: "内容管理" },
  { id: "profile", icon: "◌", label: "我的账号" },
];

const subAdminNav: { id: View; icon: string; label: string }[] = [
  { id: "users", icon: "◉", label: "用户数据" },
  { id: "accounts", icon: "⊕", label: "我的邀请码" },
  { id: "profile", icon: "◌", label: "我的账号" },
];

const fallbackTitles: Record<View, [string, string]> = {
  bfi: ["BFI-44 人格问卷", "完成问卷后即可解锁全部博弈实验"],
  games: ["博弈 PK", "选择实验，观察你的合作与决策模式"],
  rank: ["排行榜", "看看本周谁最擅长建立合作"],
  notices: ["公告栏", "测试通告与版本更新日志"],
  profile: ["我的账号", "查看资料并自行修改登录密码"],
  users: ["用户数据", "掌握参与情况、得分与人格结果"],
  experiments: ["博弈实验", "配置、排序并维护实验项目"],
  accounts: ["注册与登录管理", "管理访问策略、账号事件与登录安全"],
  pages: ["页面管理", "维护页面结构、状态与访问范围"],
  content: ["内容管理", "编辑问卷说明、实验场景和平台内容"],
};

type Props = {
  view: View;
  onNavigate: (v: View) => void;
  previewingUserUi?: boolean;
  onToggleUserPreview?: () => void;
  children: ReactNode;
};

export type { View };

export function AppShell({
  view,
  onNavigate,
  previewingUserUi = false,
  onToggleUserPreview,
  children,
}: Props) {
  const { user, logout } = useAuth();
  const superAdmin = isSuperAdmin(user?.role);
  const subAdmin = isSubAdmin(user?.role);
  const staff = isStaff(user?.role);
  const showParticipantUi = !staff || previewingUserUi;
  const { byKey, pages } = useSitePages();

  const staffNav = superAdmin ? superAdminNav : subAdmin ? subAdminNav : [];
  const items = showParticipantUi
    ? [
        ...userNavBase.filter((item) => {
          if (item.id === "profile") return true;
          const cfg = byKey[item.id];
          if (!pages.length) return true;
          return cfg?.status === "published";
        }),
      ]
    : staffNav;

  const pageCfg = byKey[view];
  const [fallbackTitle, fallbackSub] = fallbackTitles[view];
  const title = pageCfg?.title || fallbackTitle;
  const sub = pageCfg?.subtitle || fallbackSub;

  useEffect(() => {
    if (!showParticipantUi || !pages.length) return;
    const allowed = new Set(
      pages.filter((p) => p.status === "published").map((p) => p.page_key),
    );
    if (
      !allowed.has(view) &&
      (view === "bfi" || view === "games" || view === "rank" || view === "notices")
    ) {
      const first = userNavBase.find((n) => allowed.has(n.id));
      if (first) onNavigate(first.id);
    }
  }, [showParticipantUi, pages, view, onNavigate]);

  return (
    <section id="app" className={previewingUserUi ? "user-preview-mode" : undefined}>
      <aside className="sidebar">
        <div className="brand">
          <i>YM</i>
          <strong>YangMind Lab</strong>
        </div>
        <div className="space" id="space-title">
          {previewingUserUi
            ? "用户界面预览"
            : superAdmin
              ? "管理控制台"
              : subAdmin
                ? "子管理空间"
                : "参与者空间"}
        </div>
        <nav className="nav" id="nav">
          <small>{showParticipantUi ? "实验参与" : subAdmin ? "团队管理" : "实验管理"}</small>
          {items.map((item) => (
            <button
              key={item.id}
              data-view={item.id}
              className={view === item.id ? "active" : ""}
              onClick={() => onNavigate(item.id)}
            >
              <span>{item.icon}</span>
              {item.label}
            </button>
          ))}
          <button
            className="mobile-logout"
            type="button"
            onClick={logout}
            title="退出登录"
            aria-label="退出登录"
          >
            <span>↗</span>
            退出登录
          </button>
        </nav>
        {superAdmin && onToggleUserPreview ? (
          <button
            className="switch preview-switch"
            type="button"
            onClick={onToggleUserPreview}
            title={previewingUserUi ? "返回管理后台" : "预览用户界面"}
            aria-label={previewingUserUi ? "返回管理后台" : "预览用户界面"}
          >
            {previewingUserUi ? "← 返回管理后台" : "◎ 预览用户界面"}
          </button>
        ) : null}
        <div className="profile">
          <div className="avatar" id="avatar">
            {(user?.nickname || "?").slice(0, 1)}
          </div>
          <div>
            <b id="profile-name">{user?.nickname}</b>
            <small id="profile-id">
              {staff ? user?.email : `ID · ${user?.public_id}`}
            </small>
          </div>
          <button onClick={logout} title="退出">
            ↗
          </button>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <div className="crumb">
              YANGMIND LAB <em>/</em>{" "}
              <span id="crumb-role">
                {previewingUserUi
                  ? "用户界面预览"
                  : superAdmin
                    ? "管理控制台"
                    : subAdmin
                      ? "子管理空间"
                      : "参与者空间"}
              </span>
            </div>
            <h1 id="page-title">{title}</h1>
            <p id="page-sub">{sub}</p>
          </div>
          <div className="topbar-actions">
            {!previewingUserUi ? <AnnouncementBell /> : null}
            {previewingUserUi ? (
              <div className="preview-status" role="status">
                <span>只读预览</span>
                <button type="button" onClick={onToggleUserPreview}>
                  返回管理后台
                </button>
              </div>
            ) : null}
          </div>
        </header>
        <div className="content" id="content">
          {children}
        </div>
      </main>
    </section>
  );
}
