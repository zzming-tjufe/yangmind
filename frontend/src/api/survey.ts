import { api } from "./client";

export type SurveyItem = { item_no: number; stem: string; sort_order: number };

export type SurveyInstrument = {
  code: string;
  version: string;
  title: string;
  item_count: number;
  scale_hint: string;
  items: SurveyItem[];
};

export type Personality = {
  e: number;
  a: number;
  c: number;
  n: number;
  o: number;
  summary_label: string;
};

export type MyResponse = {
  status: "none" | "in_progress" | "submitted";
  answered_count: number;
  answers: Record<string, number>;
  personality: Personality | null;
  quality_passed: boolean | null;
  unlock_games: boolean;
};

export function getBfi() {
  return api<SurveyInstrument>("/api/v1/surveys/bfi-44");
}

export function getMyResponse() {
  return api<MyResponse>("/api/v1/surveys/bfi-44/my-response");
}

export function saveAnswers(answers: { item_no: number; value: number }[]) {
  return api<MyResponse>("/api/v1/surveys/bfi-44/answers", {
    method: "PUT",
    json: { answers },
  });
}

export function submitSurvey() {
  return api<MyResponse>("/api/v1/surveys/bfi-44/submit", { method: "POST" });
}

export function retakeSurvey() {
  return api<MyResponse>("/api/v1/surveys/bfi-44/retake", { method: "POST" });
}
