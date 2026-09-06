export interface LocalNarrativeEvent {
  stage: "idle" | "downloading" | "loading" | "generating" | "done" | "error";
  detail?: string;
  narrative?: string;
}

export interface LocalNarrativeAnswer {
  template: string;
  query: string;
  confidence: "high" | "medium" | "low";
  explanation: string;
  results: { label: string; detail: string }[];
}

const MODEL_ID = "onnx-community/Qwen2.5-0.5B-Instruct";
const MAX_NEW_TOKENS = 96;
const GENERATION_TIMEOUT_MS = 120000;

const SYSTEM_PROMPT =
  "You are a precise security analyst for a SIEM demo. " +
  "Summarize ONLY the JSON rows below. If the rows are empty, say there are no matches. " +
  "Never invent metrics, entity names, or claims not present in the rows. " +
  "Answer in 1-3 short sentences. Do not mention that you are an AI.";

let pipelinePromise: Promise<unknown> | null = null;

function extractGenerated(text: unknown): string {
  if (Array.isArray(text)) {
    for (const item of text) {
      const v = item && (item.generated_text ?? item.output_text);
      if (typeof v === "string") return v;
    }
    return "";
  }
  const obj = text as { generated_text?: unknown; output_text?: unknown } | null;
  const v = obj?.generated_text ?? obj?.output_text;
  return typeof v === "string" ? v : String(text ?? "");
}

async function loadPipeline(
  push: (stage: LocalNarrativeEvent["stage"], detail?: string) => void,
) {
  if (!pipelinePromise) {
    pipelinePromise = (async () => {
      push("downloading", "downloading model (~480 MB, one time; cached afterwards)");
      const mod = await import("@huggingface/transformers");
      const env = mod.env;
      env.allowLocalModels = false;
      return mod.pipeline("text-generation", MODEL_ID, {
        device: "wasm",
        dtype: "q4",
        subfolder: "onnx",
        progress_callback: (p: { status: string; file?: string; progress?: number }) => {
          if (!p) return;
          if (p.status === "progress" && typeof p.progress === "number") {
            push("downloading", `${Math.round(p.progress)}% downloaded`);
          } else if (p.status === "done") {
            push("loading", "loading model into memory…");
          }
        },
      });
    })();
  }
  return pipelinePromise;
}

export async function generateLocalNarrative(
  answer: LocalNarrativeAnswer,
  onEvent: (event: LocalNarrativeEvent) => void,
): Promise<string | null> {
  const push = (stage: LocalNarrativeEvent["stage"], detail?: string) =>
    onEvent({ stage, detail });

  if (answer.results.length === 0) {
    return null;
  }

  try {
    push("loading", "preparing model…");
    const generator = await loadPipeline(push);

    const context = JSON.stringify({
      question: answer.query,
      template: answer.template,
      confidence: answer.confidence,
      rows: answer.results.map((r) => ({ label: r.label, detail: r.detail })),
    });

    push("generating");
    const output = (generator as (messages: unknown, opts: Record<string, unknown>) => Promise<unknown>)(
      [{ role: "system", content: SYSTEM_PROMPT }, { role: "user", content: context }],
      {
        max_new_tokens: MAX_NEW_TOKENS,
        do_sample: false,
        temperature: 0.2,
        repetition_penalty: 1.1,
      },
    );

    const racer = Promise.race([
      output,
      new Promise<null>((_, reject) =>
        setTimeout(() => reject(new Error("generation timed out")), GENERATION_TIMEOUT_MS),
      ),
    ]);

    const raw = await racer;
    const narrative = extractGenerated(raw).trim();

    if (!narrative) return null;

    push("done", undefined);
    return narrative;
  } catch {
    push("error", "in-browser model unavailable in this browser");
    return null;
  }
}