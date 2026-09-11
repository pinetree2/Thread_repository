export default {
  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(runDailyAnalysis(env));
  },

  async fetch(request, env) {
    if (new URL(request.url).pathname !== "/run") {
      return new Response("Trend2Threads scheduler", { status: 200 });
    }
    return runDailyAnalysis(env);
  },
};

async function runDailyAnalysis(env) {
  const response = await fetch(`${env.BACKEND_API_URL}/api/scheduled/analyze`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-cron-secret": env.CRON_SECRET,
    },
    body: JSON.stringify({
      region: "GLOBAL",
      language: "ko",
      category: "AI",
      period: "14d",
      min_trend_score: 0,
      content_style: "threads_casual",
      auto_publish: false,
      demo_mode: false,
    }),
  });
  const body = await response.text();
  if (!response.ok) throw new Error(`Backend ${response.status}: ${body.slice(0, 300)}`);
  return new Response(body, { status: 200, headers: { "content-type": "application/json" } });
}
