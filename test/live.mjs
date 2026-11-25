// Live check of the hosted router.  node test/live.mjs [https://host]
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
const host = process.argv[2] || "https://stylist-bay.vercel.app";
const client = new Client({ name: "live", version: "0" });
await client.connect(new StreamableHTTPClientTransport(new URL(`${host}/mcp`)));
const { tools } = await client.listTools();
const sfx = JSON.parse((await client.callTool({ name: "search_sfx", arguments: { query: "paper", limit: 1 } })).content[0].text)[0];
const style = await client.callTool({ name: "get_style", arguments: { style: "comic-teardown" } });
const kit = await client.callTool({ name: "get_kit", arguments: {} });
const bl = await client.callTool({ name: "get_guide", arguments: { topic: "blender" } });
const ck = await client.callTool({ name: "get_kit", arguments: { file: "blender/character_check.py" } });
if (bl.isError || ck.isError || !ck.content[0].text.includes("def inside(")) throw new Error("blender guide or checker missing on the live router");
const head = await fetch(sfx.url, { method: "HEAD" });
console.log(`${tools.length} tools | licence note: ${!!client.getInstructions()?.includes("NONCOMMERCIAL")} | style ${style.content[0].text.length} chars | kit err ${!!kit.isError} | blender guide+checker ok | sfx ${head.status} ${head.headers.get("content-type")}`);
await client.close();
