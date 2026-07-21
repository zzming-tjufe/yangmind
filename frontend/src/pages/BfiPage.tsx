import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "../api/client";
import * as surveyApi from "../api/survey";
import type { MyResponse, SurveyInstrument } from "../api/survey";
import { useToast } from "../context/ToastContext";
import { useSiteContent } from "../hooks/useSite";

const PAGE_SIZE = 11;

function focusQuestion(itemNo: number, flash = true) {
  const el = document.querySelector(`[data-item-no="${itemNo}"]`);
  if (!(el instanceof HTMLElement)) return;
  el.scrollIntoView({ behavior: "smooth", block: "start" });
  if (!flash) return;
  el.classList.remove("qrow-flash");
  // 强制重启动画
  void el.offsetWidth;
  el.classList.add("qrow-flash");
  window.setTimeout(() => el.classList.remove("qrow-flash"), 900);
}

export function BfiPage() {
  const { toast } = useToast();
  const { byKey: content } = useSiteContent();
  const [introDone, setIntroDone] = useState(false);
  const [instrument, setInstrument] = useState<SurveyInstrument | null>(null);
  const [mine, setMine] = useState<MyResponse | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [attentionAnswers, setAttentionAnswers] = useState<Record<string, number>>({});
  const [qpage, setQpage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  /** 翻页后定位到某题；null 表示不处理 */
  const pendingFocusItem = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [inst, resp] = await Promise.all([surveyApi.getBfi(), surveyApi.getMyResponse()]);
        if (cancelled) return;
        setInstrument(inst);
        setMine(resp);
        const map: Record<number, number> = {};
        Object.entries(resp.answers).forEach(([k, v]) => {
          map[Number(k)] = v;
        });
        setAnswers(map);
        if (resp.status === "submitted" || resp.answered_count > 0) setIntroDone(true);
      } catch (e) {
        toast(e instanceof ApiError ? e.message : "加载问卷失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [toast]);

  const answered = Object.keys(answers).length;
  const progress = Math.round((answered / 44) * 100);
  const start = (qpage - 1) * PAGE_SIZE;
  const pageItems = useMemo(
    () => instrument?.items.slice(start, start + PAGE_SIZE) ?? [],
    [instrument, start],
  );

  async function onAnswer(itemNo: number, value: number) {
    setAnswers((prev) => ({ ...prev, [itemNo]: value }));
    try {
      const resp = await surveyApi.saveAnswers([{ item_no: itemNo, value }]);
      setMine(resp);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "保存失败");
    }
  }

  function goPage(next: number, opts?: { skipCheck?: boolean; focusItemNo?: number }) {
    if (!opts?.skipCheck && next > qpage) {
      const unanswered = pageItems.find((item) => !answers[item.item_no]);
      if (unanswered) {
        toast(`本组还有未作答题目（第 ${unanswered.item_no} 题）`);
        focusQuestion(unanswered.item_no);
        return;
      }
    }
    // 等新一组题目渲染后再滚到目标题（默认本组第一题）
    const startNo = (next - 1) * PAGE_SIZE + 1;
    const focusNo = opts?.focusItemNo ?? startNo;
    if (next === qpage) {
      window.setTimeout(() => focusQuestion(focusNo), 40);
      return;
    }
    pendingFocusItem.current = focusNo;
    setQpage(next);
  }

  useEffect(() => {
    const itemNo = pendingFocusItem.current;
    if (itemNo == null) return;
    const timer = window.setTimeout(() => {
      pendingFocusItem.current = null;
      focusQuestion(itemNo);
    }, 60);
    return () => window.clearTimeout(timer);
  }, [qpage, pageItems]);

  async function onSubmit() {
    if (answered < 44) {
      const allItems = instrument?.items ?? [];
      const first = allItems.find((item) => !answers[item.item_no]);
      if (first) {
        const targetPage = Math.ceil(first.item_no / PAGE_SIZE);
        toast(`还有 ${44 - answered} 题未完成，已定位到第 ${first.item_no} 题`);
        goPage(targetPage, { skipCheck: true, focusItemNo: first.item_no });
      } else {
        toast(`还有 ${44 - answered} 题未完成，请检查后提交`);
      }
      return;
    }
    const qualityChecks = instrument?.quality_checks ?? [];
    const missingCheck = qualityChecks.find((check) => !attentionAnswers[check.check_id]);
    if (missingCheck) {
      toast("请先完成页面下方的作答确认题");
      document
        .querySelector(`[data-quality-check="${missingCheck.check_id}"]`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    setBusy(true);
    try {
      const resp = await surveyApi.submitSurvey(attentionAnswers);
      setMine(resp);
      toast("问卷已提交，博弈入口已解锁");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "提交失败");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <div className="page"><p>加载中…</p></div>;

  if (mine?.status === "submitted" && mine.feedback_unlocked && mine.personality) {
    const p = mine.personality;
    const dims = [
      `开放性 ${Math.round(p.o * 20)}`,
      `尽责性 ${Math.round(p.c * 20)}`,
      `外向性 ${Math.round(p.e * 20)}`,
      `宜人性 ${Math.round(p.a * 20)}`,
      `情绪敏感 ${Math.round(p.n * 20)}`,
    ];
    return (
      <div className="page">
        <section className="hero card">
          <div>
            <div className="eyebrow">
              实验已完成 · 人格反馈
            </div>
            <h2>你的人格轮廓已生成</h2>
            <p>{p.summary_label}。结果用于解释博弈中的决策倾向，不代表能力高低。</p>
          </div>
          <div className="ring" style={{ ["--p" as string]: "360deg" }}>
            <b>100%</b>
          </div>
        </section>
        <div className="statgrid" style={{ marginTop: 18 }}>
          {dims.map((x) => (
            <div className="stat card" key={x}>
              <span>人格维度</span>
              <b>{x}</b>
              <em>已生成</em>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (mine?.status === "submitted") {
    return (
      <div className="page">
        <section className="hero card">
          <div>
            <div className="eyebrow">问卷已提交 · 等待实验完成</div>
            <h2>人格反馈将在博弈结束后展示</h2>
            <p>
              你的答案已经安全记录。为避免人格标签影响后续决策，请先完成全部必做博弈场景；完成后回到这里即可查看结果。
            </p>
          </div>
          <div className="ring" style={{ ["--p" as string]: "360deg" }}>
            <b>✓</b>
          </div>
        </section>
        <div className="quality">
          <i>→</i>
          <div>
            <b>下一步：进入博弈实验</b>
            <small>质量指标仅用于研究数据筛选，不会在实验过程中提示或改变你的作答。</small>
          </div>
        </div>
      </div>
    );
  }

  if (!introDone) {
    const intro = content["bfi.intro"];
    const introTitle = intro?.title?.trim() || "BFI-44 人格问卷";
    const introParts = (intro?.body || "").split("\n\n").map((p) => p.trim()).filter(Boolean);
    // CMS 里若仍是「请先阅读以下介绍」这类空话，改用内置说明
    const vague =
      !introParts.length ||
      introParts.some((p) => p.includes("请先阅读以下") && introParts.length <= 2);
    const introLead = vague
      ? "本问卷共 44 题，用于了解你在五个方面的稳定倾向。作答约需 6–8 分钟，请按真实、日常的自己选择，而不是理想中的自己。"
      : introParts[0];
    const introNote =
      introParts.length > 1 && !vague
        ? introParts[introParts.length - 1]
        : "人格没有好坏之分。结果仅用于本次实验中的行为分析，不作为临床诊断。";
    const announcement = content["announcement.banner"];
    const dimensions = [
      { code: "O", name: "开放性", en: "Openness", desc: "好奇、想象与接受新想法的程度" },
      { code: "C", name: "尽责性", en: "Conscientiousness", desc: "条理、可靠与坚持完成任务的程度" },
      { code: "E", name: "外向性", en: "Extraversion", desc: "活力、社交与主动表达的程度" },
      { code: "A", name: "宜人性", en: "Agreeableness", desc: "信任、合作与体谅他人的程度" },
      { code: "N", name: "情绪敏感", en: "Neuroticism", desc: "紧张、忧虑与情绪起伏的敏感程度" },
    ];

    return (
      <div className="page theory-page">
        {announcement?.body?.trim() && (
          <div className="alert" style={{ marginBottom: 16 }}>
            <i>!</i>
            <div>
              <b>{announcement.title || "平台公告"}</b>
              <small>{announcement.body}</small>
            </div>
          </div>
        )}
        <section className="theory-hero card">
          <div>
            <div className="eyebrow">BFI-44 · 问卷入口</div>
            <h2>{introTitle}</h2>
            <p>{introLead}</p>
          </div>
        </section>

        <div className="dimension-grid">
          {dimensions.map((d, i) => (
            <article
              className="dimension-card card"
              key={d.code}
              style={{ animationDelay: `${i * 55}ms` }}
            >
              <i>{d.code}</i>
              <h3>{d.name}</h3>
              <span>{d.en}</span>
              <p>{d.desc}</p>
            </article>
          ))}
        </div>

        <div className="theory-note">
          <b>作答说明</b>
          <span>{introNote}</span>
        </div>
        <div className="theory-action card">
          <div>
            <small>预计用时</small>
            <b>6–8 分钟 · 共 44 题</b>
          </div>
          <button className="primary" type="button" onClick={() => setIntroDone(true)}>
            开始作答 →
          </button>
        </div>
      </div>
    );
  }

  const surveyHero = content["bfi.survey_hero"];

  return (
    <div className="page bfi-survey-page">
      <section className="hero card">
        <div>
          <div className="eyebrow">问卷进行中 · 已答 {answered} / 44</div>
          <h2>{surveyHero?.title || "BFI-44 问卷作答"}</h2>
          <p>
            {surveyHero?.body ||
              "请根据真实、稳定的自己作答。1 = 非常不同意，5 = 非常同意。"}
          </p>
        </div>
        <div className="ring" style={{ ["--p" as string]: `${progress * 3.6}deg` }}>
          <b>{progress}%</b>
        </div>
      </section>
      <div className="quality">
        <i>✓</i>
        <div>
          <b>答案已自动保存</b>
          <small>第 {qpage} / 4 组 · 已作答 {answered} / 44</small>
        </div>
      </div>
      <section className="question-card card">
        <div className="qhead">
          <div>
            <span>
              第 {qpage} / 4 组
            </span>
            <br />
            <b>请判断以下描述与你的符合程度</b>
          </div>
          <span>
            {answered} / 44 已作答
          </span>
        </div>
        <div key={qpage} className="qpage-anim">
          {pageItems.map((item) => (
            <div
              className={`qrow${answers[item.item_no] ? " answered" : ""}`}
              key={item.item_no}
              data-item-no={item.item_no}
            >
              <div className="qtext">
                <b>{String(item.item_no).padStart(2, "0")}</b>
                我认为自己是一个{item.stem}的人。
              </div>
              <div className="scale">
                {[1, 2, 3, 4, 5].map((v) => (
                  <label key={v} className={answers[item.item_no] === v ? "picked" : undefined}>
                    <input
                      type="radio"
                      name={`q${item.item_no}`}
                      checked={answers[item.item_no] === v}
                      onChange={() => onAnswer(item.item_no, v)}
                    />
                    <i />
                    {v}
                  </label>
                ))}
              </div>
            </div>
          ))}
          {qpage === 4 && (instrument?.quality_checks.length ?? 0) > 0 ? (
            <div className="quality-check-block">
              <div className="quality-check-heading">
                <b>作答确认</b>
                <span>以下题目不计入人格得分，请按题目中的要求选择。</span>
              </div>
              {instrument?.quality_checks.map((check, index) => (
                <div
                  className={`qrow${attentionAnswers[check.check_id] ? " answered" : ""}`}
                  key={check.check_id}
                  data-quality-check={check.check_id}
                >
                  <div className="qtext">
                    <b>C{index + 1}</b>
                    {check.stem}
                  </div>
                  <div className="scale">
                    {[1, 2, 3, 4, 5].map((value) => (
                      <label
                        key={value}
                        className={
                          attentionAnswers[check.check_id] === value ? "picked" : undefined
                        }
                      >
                        <input
                          type="radio"
                          name={check.check_id}
                          checked={attentionAnswers[check.check_id] === value}
                          onChange={() =>
                            setAttentionAnswers((previous) => ({
                              ...previous,
                              [check.check_id]: value,
                            }))
                          }
                        />
                        <i />
                        {value}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
        <div className="qfoot">
          <button
            className="secondary"
            type="button"
            disabled={qpage === 1}
            onClick={() => goPage(Math.max(1, qpage - 1))}
          >
            ← 上一组
          </button>
          <span>答案已同步</span>
          {qpage < 4 ? (
            <button className="primary" type="button" onClick={() => goPage(qpage + 1)}>
              下一组 →
            </button>
          ) : (
            <button className="primary" type="button" disabled={busy} onClick={onSubmit}>
              {busy ? "提交中…" : answered < 44 ? `还差 ${44 - answered} 题` : "提交问卷 →"}
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
