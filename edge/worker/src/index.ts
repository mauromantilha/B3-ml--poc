export interface Env {
  CLOUD_RUN_BASE_URL: string;
  EDGE_SHARED_SECRET: string;
}

const routeMap: Record<string, string> = {
  "/webhooks/qstash/eod": "/v1/jobs/eod-reconcile",
  "/webhooks/qstash/analytics-mirror": "/v1/jobs/analytics-mirror",
  "/webhooks/qstash/train-model": "/v1/jobs/train-model",
};

function buildRequestId(): string {
  return crypto.randomUUID();
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const targetPath = routeMap[url.pathname];

    if (!targetPath) {
      return new Response(JSON.stringify({ error: "Route not found" }), {
        status: 404,
        headers: { "content-type": "application/json" },
      });
    }

    const body = await request.text();
    const requestId = buildRequestId();
    const idempotencyKey = request.headers.get("Upstash-Message-Id") ?? requestId;
    const targetUrl = `${env.CLOUD_RUN_BASE_URL.replace(/\/$/, "")}${targetPath}`;

    const response = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-edge-shared-secret": env.EDGE_SHARED_SECRET,
        "x-request-id": requestId,
        "idempotency-key": idempotencyKey,
      },
      body,
    });

    return new Response(response.body, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") ?? "application/json",
        "x-request-id": requestId,
      },
    });
  },
};
