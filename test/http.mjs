// Hosted endpoint check: api/mcp.mjs behind a plain node http server (mimics Vercel req/res).  node test/http.mjs
import http from "node:http";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import handler from "../api/mcp.mjs";
const srv = http.createServer(async (req, res) => {
  let b = ""; for await (const c of req) b += c;
  req.body = b ? JSON.parse(b) : undefined;
  res.status = c => { res.statusCode = c; return res; };
  res.json = o => res.end(JSON.stringify(o));
  await handler(req, res);
}).listen(8787);
const client = new Client({ name: "t", version: "0" });
await client.connect(new StreamableHTTPClientTransport(new URL("http://localhost:8787/mcp")));
const { tools } = await client.listTools();
const r = await client.callTool({ name: "search_sfx", arguments: { query: "paper", limit: 1 } });
const g = await client.callTool({ name: "get_style", arguments: { style: "comic-teardown" } });
console.log(tools.length, "tools;", client.getInstructions()?.slice(0, 40), ";", JSON.parse(r.content[0].text)[0].url, "; style chars", g.content[0].text.length);
await client.close(); srv.close();
