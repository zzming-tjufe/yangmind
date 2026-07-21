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
  survey_done: boolean;
  survey_quality_failed?: boolean;
  comprehension_passed: boolean;
  experiment_status: string;
  done_count: number;
  required_count: number;
  all_done: boolean;
  participation_locked: boolean;
  active_match_id: number | null;
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

export type ComprehensionQuestion = {
  question_id: string;
  prompt: string;
  options: { value: string; label: string }[];
};

export type Comprehension = {
  passed: boolean;
  attempts: number;
  incorrect_ids: string[];
  questions: ComprehensionQuestion[];
};

export function getComprehension() {
  return api<Comprehension>("/api/v1/experiments/stag-hunt/comprehension");
}

export function submitComprehension(answers: Record<string, string>) {
  return api<Comprehension>("/api/v1/experiments/stag-hunt/comprehension", {
    method: "POST",
    json: { answers },
  });
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

export type PvpRound = {
  round_no: number;
  status: string;
  my_choice: string | null;
  opponent_choice: string | null;
  my_points: number | null;
  opponent_points: number | null;
  my_timed_out: boolean;
  opponent_timed_out: boolean;
};

export type PvpMatch = {
  id: number;
  status: string;
  scene_key: string;
  scene_title: string;
  rounds_total: number;
  current_round: number;
  round_timeout_sec: number;
  round_deadline: string | null;
  seconds_left: number | null;
  my_score: number;
  opponent_score: number;
  opponent_nickname: string | null;
  my_seat: string;
  waiting: boolean;
  resumed?: boolean;
  i_have_chosen: boolean;
  opponent_has_chosen: boolean;
  history: PvpRound[];
};

export function joinPvpQueue(sceneKey: string) {
  return api<PvpMatch>(`/api/v1/pvp/stag-hunt/scenes/${sceneKey}/queue`, {
    method: "POST",
  });
}

export function cancelPvpQueue() {
  return api<{
    ok: boolean;
    cancelled: boolean;
    status?: string | null;
    match_id?: number | null;
    detail?: string;
  }>("/api/v1/pvp/queue/cancel", {
    method: "POST",
  });
}

export function getPvpMatch(matchId: number) {
  return api<PvpMatch>(`/api/v1/pvp/matches/${matchId}`);
}

export function submitPvpChoice(matchId: number, choice: "A" | "B", roundNo?: number) {
  return api<PvpMatch>(`/api/v1/pvp/matches/${matchId}/choice`, {
    method: "POST",
    json: { choice, round_no: roundNo },
  });
}
