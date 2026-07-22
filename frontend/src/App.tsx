import { useLayoutEffect, useState } from "react";
import { ApiError } from "./api/client";
import { AppShell, type View } from "./components/AppShell";
import { useAuth } from "./context/AuthContext";
import { useDemo } from "./context/DemoContext";
import { useSudoView } from "./context/SudoViewContext";
import { useToast } from "./context/ToastContext";
import { isStaff, isSuperAdmin } from "./lib/roles";
import { AuthPage } from "./pages/AuthPage";
import { AdminAccountsPage } from "./pages/AdminAccountsPage";
import { AdminAuditPage } from "./pages/AdminAuditPage";
import { AdminContentPage } from "./pages/AdminContentPage";
import { AdminExperimentsPage } from "./pages/AdminExperimentsPage";
import { AdminPagesPage } from "./pages/AdminPagesPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { BfiPage } from "./pages/BfiPage";
import { GamesPage } from "./pages/GamesPage";
import { NoticesPage } from "./pages/NoticesPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RankPage } from "./pages/RankPage";

const staffViews = new Set<View>([
  "users",
  "experiments",
  "accounts",
  "invites",
  "sub_admins",
  "audit",
  "pages",
  "content",
]);

const superOnlyViews = new Set<View>([
  "experiments",
  "pages",
  "content",
  "sub_admins",
  "audit",
]);

function homeViewFor(role: string | undefined): View {
  return isStaff(role) ? "users" : "bfi";
}

function normalizeView(view: View): View {
  return view === "accounts" ? "invites" : view;
}

export default function App() {
  const { user, loading } = useAuth();
  const { demoMode, enterDemo, exitDemo, resetDemo } = useDemo();
  const { isSudoUser, viewAs, setViewAs, effectiveRole } = useSudoView();
  const { toast } = useToast();
  const [view, setView] = useState<View>("bfi");
  const [demoEpoch, setDemoEpoch] = useState(0);

  useLayoutEffect(() => {
    if (!user) {
      exitDemo();
      setView("bfi");
      return;
    }
    exitDemo();
    setView(homeViewFor(isSudoUser ? viewAs : user.role));
  }, [user, exitDemo, isSudoUser, viewAs]);

  async function toggleDemo() {
    if (!isStaff(effectiveRole)) return;
    if (demoMode) {
      exitDemo();
      setView("users");
      return;
    }
    try {
      await enterDemo();
      setView("bfi");
      toast("已进入演示模式：操作完整可交互，数据不写入正式库");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "进入演示模式失败");
    }
  }

  async function onResetDemo() {
    try {
      await resetDemo();
      setDemoEpoch((n) => n + 1);
      toast("演示数据已重置");
      setView("bfi");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "重置失败");
    }
  }

  function onSudoViewChange(next: typeof viewAs) {
    setViewAs(next);
    exitDemo();
    setView(homeViewFor(next));
    toast(
      next === "super_admin"
        ? "已切换到总管界面"
        : next === "sub_admin"
          ? "已切换到子管界面"
          : "已切换到参与者界面",
    );
  }

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: "center" }}>
        正在恢复登录状态…
      </div>
    );
  }

  if (!user) return <AuthPage />;

  const staff = isStaff(effectiveRole);
  const superAdmin = isSuperAdmin(effectiveRole);
  const showParticipantUi = !staff || demoMode;

  let safeView = normalizeView(view);
  if (showParticipantUi) {
    if (staffViews.has(safeView)) safeView = "bfi";
  } else if (!staff) {
    safeView = "bfi";
  } else if (superOnlyViews.has(safeView) && !superAdmin) {
    safeView = "users";
  }

  let content = null;
  switch (safeView) {
    case "bfi":
      content = <BfiPage />;
      break;
    case "games":
      content = <GamesPage />;
      break;
    case "rank":
      content = <RankPage />;
      break;
    case "notices":
      content = <NoticesPage />;
      break;
    case "profile":
      content = <ProfilePage />;
      break;
    case "users":
      content = staff && !demoMode ? <AdminUsersPage /> : <BfiPage />;
      break;
    case "experiments":
      content = superAdmin && !demoMode ? <AdminExperimentsPage /> : <BfiPage />;
      break;
    case "accounts":
    case "invites":
      content =
        staff && !demoMode ? <AdminAccountsPage section="invites" /> : <BfiPage />;
      break;
    case "sub_admins":
      content =
        superAdmin && !demoMode ? (
          <AdminAccountsPage section="sub_admins" />
        ) : (
          <BfiPage />
        );
      break;
    case "audit":
      content = superAdmin && !demoMode ? <AdminAuditPage /> : <BfiPage />;
      break;
    case "pages":
      content = superAdmin && !demoMode ? <AdminPagesPage /> : <BfiPage />;
      break;
    case "content":
      content = superAdmin && !demoMode ? <AdminContentPage /> : <BfiPage />;
      break;
  }

  return (
    <AppShell
      view={safeView}
      onNavigate={setView}
      demoMode={demoMode}
      onToggleDemo={staff && !isSudoUser ? toggleDemo : undefined}
      onResetDemo={demoMode ? onResetDemo : undefined}
      sudoViewAs={isSudoUser ? viewAs : undefined}
      onSudoViewChange={isSudoUser ? onSudoViewChange : undefined}
      effectiveRole={effectiveRole}
    >
      <div
        key={`${safeView}-${demoMode ? "demo" : "live"}-${viewAs}-${demoEpoch}`}
        className="page-soft-in"
      >
        {content}
      </div>
    </AppShell>
  );
}
