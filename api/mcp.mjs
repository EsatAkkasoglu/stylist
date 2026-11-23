// Hosted Stylist router: the same tools as server/index.mjs over Streamable HTTP (stateless, read-only).
// Vercel serves this at /api/mcp (rewritten to /mcp). Claude connects to https://<host>/mcp.
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { makeServer } from "../server/index.mjs";

export default async function handler(req, res) {
  if (req.method !== "POST") {   // stateless: no SSE stream, no sessions
    res.status(405).setHeader("Allow", "POST").json({ jsonrpc: "2.0", error: { code: -32000, message: "Method not allowed" }, id: null });
    return;
  }
  const base = `https://${req.headers["x-forwarded-host"] || req.headers.host}`;
  const server = makeServer({ sfxBase: base });
  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined, enableJsonResponse: true });
  res.on("close", () => { transport.close(); server.close(); });
  await server.connect(transport);
  await transport.handleRequest(req, res, req.body);
}
