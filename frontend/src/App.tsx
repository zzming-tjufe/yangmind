import { useEffect, useState } from "react";
import { AppShell, type View } from "./components/AppShell";
import { useAuth } from "./context/AuthContext";
import { AuthPage } from "./pages/AuthPage";
import { AdminAccountsPage } from "./pages/AdminAccountsPage";
import { AdminContentPage } from "./pages/AdminContentPage";
import { AdminExperimentsPage } from "./pages/AdminExperimentsPage";
import { AdminPagesPage } from "./pages/AdminPagesPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { BfiPage } from "./pages/BfiPage";
import { GamesPage } from "./pages/GamesPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RankPage } from "./pages/RankPage";

export default function App() {
  const { user, loading } = useAuth();
  const [view, setView] = useState<View>("bfi");
  const [previewingUserUi, setPreviewingUserUi] = useState(false);

  useEffect(() => {
    if (!user) return;
    setPreviewingUserUi(false);
    setView(user.role === "admin" ? "users" : "bfi");
  }, [user]);

  function toggleUserPreview() {
    if (user?.role !== "admin") return;
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

  let content = null;
  switch (view) {
    case "bfi":
      content = <BfiPage />;
      break;
    case "games":
      content = <GamesPage />;
      break;
    case "rank":
      content = <RankPage />;
      break;
    case "profile":
      content = <ProfilePage />;
      break;
    case "users":
      content = <AdminUsersPage />;
      break;
    case "experiments":
      content = <AdminExperimentsPage />;
      break;
    case "accounts":
      content = <AdminAccountsPage />;
      break;
    case "pages":
      content = <AdminPagesPage />;
      break;
    case "content":
      content = <AdminContentPage />;
      break;
  }

  return (
    <AppShell
      view={view}
      onNavigate={setView}
      previewingUserUi={previewingUserUi}
      onToggleUserPreview={toggleUserPreview}
    >
      <div className={previewingUserUi ? "user-preview-content" : undefined}>
        {content}
      </div>
    </AppShell>
  );
}
