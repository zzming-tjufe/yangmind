import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useAuth } from "./AuthContext";
import { isSudo, type SudoViewAs } from "../lib/roles";

type SudoViewContextValue = {
  isSudoUser: boolean;
  viewAs: SudoViewAs;
  setViewAs: (v: SudoViewAs) => void;
  /** 侧栏 / 路由用的有效角色（sudo 可切换，其他人用真实 role） */
  effectiveRole: string;
};

const SudoViewContext = createContext<SudoViewContextValue | null>(null);

const STORAGE_KEY = "yangmind_sudo_view_as";

function readStoredViewAs(): SudoViewAs {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (raw === "super_admin" || raw === "sub_admin" || raw === "participant") return raw;
  } catch {
    /* ignore */
  }
  return "super_admin";
}

export function SudoViewProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const isSudoUser = isSudo(user?.role, user?.is_sudo);
  const [viewAs, setViewAsState] = useState<SudoViewAs>(readStoredViewAs);

  useEffect(() => {
    if (!isSudoUser) {
      setViewAsState("super_admin");
    }
  }, [isSudoUser, user?.id]);

  const setViewAs = useCallback((v: SudoViewAs) => {
    setViewAsState(v);
    try {
      sessionStorage.setItem(STORAGE_KEY, v);
    } catch {
      /* ignore */
    }
  }, []);

  const effectiveRole = useMemo(() => {
    if (!user) return "participant";
    if (!isSudoUser) return user.role;
    return viewAs;
  }, [user, isSudoUser, viewAs]);

  const value = useMemo(
    () => ({ isSudoUser, viewAs, setViewAs, effectiveRole }),
    [isSudoUser, viewAs, setViewAs, effectiveRole],
  );

  return <SudoViewContext.Provider value={value}>{children}</SudoViewContext.Provider>;
}

export function useSudoView() {
  const ctx = useContext(SudoViewContext);
  if (!ctx) throw new Error("useSudoView must be used within SudoViewProvider");
  return ctx;
}
