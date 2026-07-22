import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { MyResponse } from "../api/survey";
import type { PvpMatch, StagProgress } from "../api/games";

type DemoContextValue = {
  demoMode: boolean;
  enterDemo: () => Promise<void>;
  exitDemo: () => void;
  resetDemo: () => Promise<void>;
  getMyResponse: () => Promise<MyResponse>;
  saveAnswers: (answers: { item_no: number; value: number }[]) => Promise<MyResponse>;
  submitSurvey: (
    attentionAnswers: Record<string, number>,
    telemetry: {
      diligence_answers: Record<string, number>;
      page_timings_seconds: Record<string, number>;
      blur_count: number;
    },
    allAnswers: Record<number, number>,
  ) => Promise<MyResponse>;
  getScenes: () => Promise<StagProgress>;
  startBotSession: (sceneKey: string) => Promise<PvpMatch>;
  playRound: (sessionId: number, choice: "A" | "B") => Promise<PvpMatch>;
};

const DemoContext = createContext<DemoContextValue | null>(null);

export function DemoProvider({ children }: { children: ReactNode }) {
  const [demoMode, setDemoMode] = useState(false);

  const resetDemo = useCallback(async () => {
    await api<{ ok: boolean }>("/api/v1/demo/reset", { method: "POST" });
  }, []);

  const enterDemo = useCallback(async () => {
    await api<{ ok: boolean }>("/api/v1/demo/reset", { method: "POST" });
    setDemoMode(true);
  }, []);

  const exitDemo = useCallback(() => {
    setDemoMode(false);
  }, []);

  const getMyResponse = useCallback(() => {
    return api<MyResponse>("/api/v1/demo/surveys/bfi-44/my-response");
  }, []);

  const saveAnswers = useCallback((answers: { item_no: number; value: number }[]) => {
    return api<MyResponse>("/api/v1/demo/surveys/bfi-44/answers", {
      method: "PUT",
      json: { answers },
    });
  }, []);

  const submitSurvey = useCallback(
    async (
      attentionAnswers: Record<string, number>,
      _telemetry: {
        diligence_answers: Record<string, number>;
        page_timings_seconds: Record<string, number>;
        blur_count: number;
      },
      allAnswers: Record<number, number>,
    ) => {
      return api<MyResponse>("/api/v1/demo/surveys/bfi-44/submit", {
        method: "POST",
        json: {
          answers: Object.entries(allAnswers).map(([item_no, value]) => ({
            item_no: Number(item_no),
            value,
          })),
          attention_answers: Object.entries(attentionAnswers).map(([check_id, value]) => ({
            check_id,
            value,
          })),
          diligence_answers: Object.entries(_telemetry.diligence_answers).map(
            ([check_id, value]) => ({ check_id, value }),
          ),
        },
      });
    },
    [],
  );

  const getScenes = useCallback(() => {
    return api<StagProgress>("/api/v1/demo/stag-hunt/scenes");
  }, []);

  const startBotSession = useCallback((sceneKey: string) => {
    return api<PvpMatch>(`/api/v1/demo/stag-hunt/scenes/${sceneKey}/sessions`, {
      method: "POST",
    });
  }, []);

  const playRound = useCallback((sessionId: number, choice: "A" | "B") => {
    return api<PvpMatch>(`/api/v1/demo/sessions/${sessionId}/rounds`, {
      method: "POST",
      json: { choice },
    });
  }, []);

  const value = useMemo(
    () => ({
      demoMode,
      enterDemo,
      exitDemo,
      resetDemo,
      getMyResponse,
      saveAnswers,
      submitSurvey,
      getScenes,
      startBotSession,
      playRound,
    }),
    [
      demoMode,
      enterDemo,
      exitDemo,
      resetDemo,
      getMyResponse,
      saveAnswers,
      submitSurvey,
      getScenes,
      startBotSession,
      playRound,
    ],
  );

  return <DemoContext.Provider value={value}>{children}</DemoContext.Provider>;
}

export function useDemo() {
  const ctx = useContext(DemoContext);
  if (!ctx) throw new Error("useDemo must be used within DemoProvider");
  return ctx;
}

/** 可选：非 DemoProvider 下返回 null */
export function useDemoOptional() {
  return useContext(DemoContext);
}
