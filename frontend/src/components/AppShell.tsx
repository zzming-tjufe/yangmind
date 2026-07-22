import { useEffect, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import {
  ArrowLeftRight,
  ArrowUpRight,
  ClipboardList,
  FileText,
  FlaskConical,
  KeyRound,
  LayoutList,
  LogOut,
  Megaphone,
  MonitorPlay,
  Trophy,
  User,
  UserCog,
  Users,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useSitePages } from "../hooks/useSite";
import { isStaff, isSubAdmin, isSuperAdmin, type SudoViewAs } from "../lib/roles";
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
  | "invites"
  | "sub_admins"
  | "audit"
  | "pages"
  | "content";

type NavItem = { id: View; icon: LucideIcon; label: string };
type NavGroup = { label: string; items: NavItem[] };

const userNavBase: NavItem[] = [
  { id: "bfi", icon: FileText, label: "BFI-44 问卷" },
  { id: "games", icon: FlaskConical, label: "博弈 PK" },
  { id: "rank", icon: Trophy, label: "排行榜" },
  { id: "profile", icon: User, label: "我的账号" },
];

const superAdminNavGroups: NavGroup[] = [
  {
    label: "实验运营",
    items: [
      { id: "users", icon: Users, label: "参与者数据" },
      { id: "experiments", icon: FlaskConical, label: "博弈实验" },
    ],
  },
  {
    label: "拉人与协作",
    items: [
      { id: "invites", icon: KeyRound, label: "邀请码" },
      { id: "sub_admins", icon: UserCog, label: "子管理员" },
    ],
  },
  {
    label: "站点配置",
    items: [
      { id: "pages", icon: LayoutList, label: "参与端页面" },
      { id: "content", icon: Megaphone, label: "文案与公告" },
    ],
  },
  {
    label: "系统",
    items: [{ id: "audit", icon: ClipboardList, label: "操作记录" }],
  },
  {
    label: "账号",
    items: [{ id: "profile", icon: User, label: "我的账号" }],
  },
];

const subAdminNavGroups: NavGroup[] = [
  {
    label: "我的团队",
    items: [
      { id: "users", icon: Users, label: "我的参与者" },
      { id: "invites", icon: KeyRound, label: "我的邀请码" },
    ],
  },
  {
    label: "账号",
    items: [{ id: "profile", icon: User, label: "我的账号" }],
  },
];

const fallbackTitles: Record<View, [string, string]> = {
  bfi: ["BFI-44 人格问卷", "完成问卷后即可解锁全部博弈实验"],
  games: ["博弈 PK", "选择实验，观察你的合作与决策模式"],
  rank: ["排行榜", "看看本周谁最擅长建立合作"],
  notices: ["公告栏", "测试通告与版本更新日志"],
  profile: ["我的账号", "查看资料并自行修改登录密码"],
  users: ["参与者数据", "查看和管理注册过来的同学"],
  experiments: ["博弈实验", "开关实验、调整场景"],
  accounts: ["邀请码", "创建邀请码，分给子管去拉人"],
  invites: ["邀请码", "创建邀请码，分给子管去拉人"],
  sub_admins: ["子管理员", "查看子管，启用或禁用"],
  audit: ["操作记录", "后台发码、分配、启停等操作的留痕"],
  pages: ["参与端页面", "控制用户侧菜单页显示与标题"],
  content: ["文案与公告", "改说明文字、场景介绍，发公告"],
};

type Props = {
  view: View;
  onNavigate: (v: View) => void;
  demoMode?: boolean;
  onToggleDemo?: () => void;
  onResetDemo?: () => void;
  /** sudo 专用：当前视角；有值才显示切换器 */
  sudoViewAs?: SudoViewAs;
  onSudoViewChange?: (v: SudoViewAs) => void;
  /** 侧栏按此角色渲染（sudo 可切换） */
  effectiveRole?: string;
  children: ReactNode;
};

export type { View };

function NavIcon({ icon: Icon }: { icon: LucideIcon }) {
  return <Icon className="nav-icon" size={18} strokeWidth={2} aria-hidden />;
}

export function AppShell({
  view,
  onNavigate,
  demoMode = false,
  onToggleDemo,
  onResetDemo,
  sudoViewAs,
  onSudoViewChange,
  effectiveRole,
  children,
}: Props) {
  const { user, logout } = useAuth();
  const role = effectiveRole ?? user?.role;
  const superAdmin = isSuperAdmin(role);
  const subAdmin = isSubAdmin(role);
  const staff = isStaff(role);
  const showParticipantUi = !staff || demoMode;
  const { byKey, pages } = useSitePages();

  const staffGroups = superAdmin ? superAdminNavGroups : subAdmin ? subAdminNavGroups : [];
  const participantItems = userNavBase.filter((item) => {
    if (item.id === "profile") return true;
    const cfg = byKey[item.id];
    if (!pages.length) return true;
    return cfg?.status === "published";
  });

  const pageCfg = byKey[view];
  const titles = fallbackTitles[view] ?? fallbackTitles.users;
  let [fallbackTitle, fallbackSub] = titles;
  if (view === "users" && subAdmin && !demoMode) {
    fallbackTitle = "我的参与者";
    fallbackSub = "只能看到用你转发的邀请码注册的人";
  }
  if (view === "invites" && subAdmin && !demoMode) {
    fallbackTitle = "我的邀请码";
    fallbackSub = "复制发给同学注册；不能自己新建";
  }
  const title =
    showParticipantUi && pageCfg?.title
      ? pageCfg.title
      : staff && !demoMode
        ? fallbackTitle
        : pageCfg?.title || fallbackTitle;
  const sub = demoMode
    ? "演示模式 · 操作可完整交互，数据不写入正式库"
    : showParticipantUi
      ? pageCfg?.subtitle || fallbackSub
      : fallbackSub;

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

  const spaceLabel = demoMode
    ? "演示模式"
    : sudoViewAs
      ? sudoViewAs === "super_admin"
        ? "调试 · 总管界面"
        : sudoViewAs === "sub_admin"
          ? "调试 · 子管界面"
          : "调试 · 参与者界面"
      : superAdmin
        ? "运营后台"
        : subAdmin
          ? "子管后台"
          : "参与者空间";

  return (
    <section id="app" className={demoMode ? "demo-mode" : undefined}>
      <aside className="sidebar">
        <div className="brand">
          <i>YM</i>
          <strong>YangMind Lab</strong>
        </div>
        <div className="space" id="space-title">
          {spaceLabel}
        </div>
        <nav className="nav" id="nav">
          {showParticipantUi ? (
            <>
              <small>实验参与</small>
              {participantItems.map((item) => (
                <button
                  key={item.id}
                  data-view={item.id}
                  className={view === item.id ? "active" : ""}
                  onClick={() => onNavigate(item.id)}
                >
                  <span className="nav-icon-wrap">
                    <NavIcon icon={item.icon} />
                  </span>
                  {item.label}
                </button>
              ))}
            </>
          ) : (
            staffGroups.map((group) => (
              <div className="nav-group" key={group.label}>
                <small className="nav-group-label">{group.label}</small>
                {group.items.map((item) => (
                  <button
                    key={item.id}
                    data-view={item.id}
                    className={view === item.id ? "active" : ""}
                    onClick={() => onNavigate(item.id)}
                  >
                    <span className="nav-icon-wrap">
                      <NavIcon icon={item.icon} />
                    </span>
                    {item.label}
                  </button>
                ))}
              </div>
            ))
          )}
          <button
            className="mobile-logout"
            type="button"
            onClick={logout}
            title="切换账号"
            aria-label="切换账号"
          >
            <span className="nav-icon-wrap">
              <LogOut className="nav-icon" size={18} strokeWidth={2} aria-hidden />
            </span>
            切换账号
          </button>
        </nav>
        {staff && onToggleDemo ? (
          <button
            className="switch preview-switch"
            type="button"
            onClick={onToggleDemo}
            title={demoMode ? "返回管理后台" : "进入演示模式"}
            aria-label={demoMode ? "返回管理后台" : "进入演示模式"}
          >
            {demoMode ? (
              <>
                <ArrowLeftRight size={16} strokeWidth={2} aria-hidden />
                返回管理后台
              </>
            ) : (
              <>
                <MonitorPlay size={16} strokeWidth={2} aria-hidden />
                演示模式
              </>
            )}
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
          <button onClick={logout} title="切换账号" aria-label="切换账号">
            <ArrowUpRight size={16} strokeWidth={2} aria-hidden />
          </button>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <div className="crumb">
              YANGMIND LAB <em>/</em>{" "}
              <span id="crumb-role">{spaceLabel}</span>
            </div>
            <h1 id="page-title">{title}</h1>
            <p id="page-sub">{sub}</p>
          </div>
          <div className="topbar-actions">
            {sudoViewAs && onSudoViewChange ? (
              <div className="sudo-view-switch" role="group" aria-label="调试视角">
                {(
                  [
                    ["super_admin", "总管"],
                    ["sub_admin", "子管"],
                    ["participant", "参与者"],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    className={sudoViewAs === id ? "active" : ""}
                    onClick={() => onSudoViewChange(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            ) : null}
            {!demoMode ? <AnnouncementBell /> : null}
            {demoMode ? (
              <div className="preview-status" role="status">
                <span>演示 · 数据不保存</span>
                {onResetDemo ? (
                  <button type="button" onClick={onResetDemo}>
                    重置演示
                  </button>
                ) : null}
                <button type="button" onClick={onToggleDemo}>
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
