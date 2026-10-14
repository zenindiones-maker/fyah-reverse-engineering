#!/usr/bin/env node
// Isolated MCP protocol proof; no application target or credentials.
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';

const executable = process.argv[2];
if (!executable) throw new Error('REA executable path required');
const child = spawn(executable, ['--mcp'], { stdio: ['pipe', 'pipe', 'pipe'], env: { ...process.env, NO_COLOR: '1' } });
let nextId = 1;
const pending = new Map();
const errors = [];
child.stderr.on('data', chunk => { if (errors.join('').length < 2000) errors.push(String(chunk)); });
const lines = createInterface({ input: child.stdout });
lines.on('line', line => {
  if (!line.trim()) return;
  let msg;
  try { msg = JSON.parse(line); } catch { return; }
  if (msg.id != null && pending.has(msg.id)) {
    const p = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) p.reject(new Error(JSON.stringify(msg.error)));
    else p.resolve(msg.result);
  }
});
const send = obj => child.stdin.write(JSON.stringify(obj) + '\n');
const request = (method, params = {}) => new Promise((resolve, reject) => {
  const id = nextId++;
  pending.set(id, { resolve, reject });
  send({ jsonrpc: '2.0', id, method, params });
});
const timeout = setTimeout(() => {
  console.error('MCP_HANDSHAKE=TIMEOUT', errors.join('').slice(0, 1000));
  child.kill('SIGKILL');
  process.exit(1);
}, 25000);
try {
  const init = await request('initialize', { protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 'fyah-re-smoke', version: '1.0.0' } });
  if (!init?.serverInfo?.name) throw new Error('Missing server identity');
  send({ jsonrpc: '2.0', method: 'notifications/initialized' });
  const tools = await request('tools/list');
  if (!Array.isArray(tools?.tools) || tools.tools.length === 0) throw new Error('No MCP tools enumerated');
  if (!tools.tools.every(t => typeof t.name === 'string' && t.inputSchema)) throw new Error('Invalid tool contracts');
  console.log('MCP_INITIALIZE=PASS');
  console.log('MCP_SERVER=' + init.serverInfo.name);
  console.log('MCP_TOOLS_LIST=PASS');
  console.log('MCP_TOOL_COUNT=' + tools.tools.length);
  console.log('MCP_SAMPLE_TOOLS=' + tools.tools.slice(0, 5).map(t => t.name).join(','));
} catch (e) {
  console.error('MCP_E2E=FAIL', e.message, errors.join('').slice(0, 1000));
  process.exitCode = 1;
} finally {
  clearTimeout(timeout);
  child.kill('SIGTERM');
}
