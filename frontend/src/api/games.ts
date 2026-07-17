import { api } from "./client";

export type Scene = {
  scene_key: string;
  no: string;
  title: string;
  short_desc: string;
  option_a: string;
  option_b: string;
  option_a_text: string;
  option_b_text: string;
  required: boolean;
  completed: boolean;
  best_score: number | null;
};

export type StagProgress = {
  experiment_code: string;
  title: string;
  rounds_per_scene: number;
  unlock_games: boolean;
  done_count: number;
  required_count: number;
  all_done: boolean;
  scenes: Scene[];
  payoff_matrix: Record<string, string>;
};

export type Round = {
  round_no: number;
  my_choice: string;
  opponent_choice: string;
  my_points: number;
  opponent_points: number;
};

export type Session = {
  id: number;
  scene_key: string;
  status: string;
  current_round: number;
  rounds_total: number;
  my_score: number;
  opponent_score: number;
  last_round: Round | null;
  history: Round[];
  experiment_all_done: boolean;
};

export function getScenes() {
  return api<StagProgress>("/api/v1/experiments/stag-hunt/scenes");
}

export function startSession(sceneKey: string) {
  return api<Session>(`/api/v1/experiments/stag-hunt/scenes/${sceneKey}/sessions`, {
    method: "POST",
  });
}

export function playRound(sessionId: number, choice: "A" | "B") {
  return api<Session>(`/api/v1/sessions/${sessionId}/rounds`, {
    method: "POST",
    json: { choice },
  });
}

export function abandonSession(sessionId: number) {
  return api<Session>(`/api/v1/sessions/${sessionId}/abandon`, { method: "POST" });
}
