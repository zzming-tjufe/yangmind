import { useLayoutEffect, useState } from "react";
import { AppShell, type View } from "./components/AppShell";
import { useAuth } from "./context/AuthContext";
import { isStaff, isSuperAdmin } from "./lib/roles";
import { AuthPage } from "./pages/AuthPage";
import { AdminAccountsPage } from "./pages/AdminAccountsPage";
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
  "pages",
  "content",
]);

const superOnlyViews = new Set<View>(["experiments", "pages", "content"]);

function homeViewFor(role: string | undefined): View {
  return isStaff(role) ? "users" : "bfi";
}

export default function App() {
  const { user, loading } = useAuth();
  const [view, setView] = useState<View>("bfi");
  const [previewingUserUi, setPreviewingUserUi] = useState(false);

  // 必须在绘制前切回角色对应首页，否则会短暂渲染上一账号的管理页并弹出「需要管理员权限」
  useLayoutEffect(() => {
    if (!user) {
      setPreviewingUserUi(false);
      setView("bfi");
      return;
    }
    setPreviewingUserUi(false);
    setView(homeViewFor(user.role));
  }, [user]);

  function toggleUserPreview() {
    if (!isSuperAdmin(user?.role)) return;
    setPreviewingUserUi((current) => {
      setView(current ? "users" : "bfi");
      return !current;
    });
  }

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: "center" }}>
        正在恢复登录状态…
      </div>
    );
  }

  if (!user) return <AuthPage />;

  const staff = isStaff(user.role);
  const superAdmin = isSuperAdmin(user.role);
  const showParticipantUi = !staff || previewingUserUi;

  // 按角色校正当前 view，避免错误页面发起管理端请求
  let safeView = view;
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
      content = staff && !previewingUserUi ? <AdminUsersPage /> : <BfiPage />;
      break;
    case "experiments":
      content = superAdmin && !previewingUserUi ? <AdminExperimentsPage /> : <BfiPage />;
      break;
    case "accounts":
      content = staff && !previewingUserUi ? <AdminAccountsPage /> : <BfiPage />;
      break;
    case "pages":
      content = superAdmin && !previewingUserUi ? <AdminPagesPage /> : <BfiPage />;
      break;
    case "content":
      content = superAdmin && !previewingUserUi ? <AdminContentPage /> : <BfiPage />;
      break;
  }

  return (
    <AppShell
      view={safeView}
      onNavigate={setView}
      previewingUserUi={previewingUserUi}
      onToggleUserPreview={toggleUserPreview}
    >
      <div
        key={safeView}
        className={`page-soft-in${previewingUserUi ? " user-preview-content" : ""}`}
      >
        {content}
      </div>
    </AppShell>
  );
}
