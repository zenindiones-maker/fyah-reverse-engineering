#!/usr/bin/env node
// Explicitly authorized REA MCP call, isolated from model authority.
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
const [exe, toolName, argsJson] = process.argv.slice(2);
const allowed = new Set(['inspect_artifact']);
if (!exe || !allowed.has(toolName)) { console.error('REA_MCP_DENIED=tool_not_allowlisted'); process.exit(2); }
let args;
try { args = JSON.parse(argsJson || '{}'); } catch { process.exit(2); }
if (!args || Array.isArray(args) || typeof args !== 'object') process.exit(2);
const child = spawn(exe, ['--mcp'], {stdio:['pipe','pipe','pipe'], env:{...process.env,NO_COLOR:'1'}});
let id=0;const waiting=new Map();
const timer=setTimeout(()=>{console.error('REA_MCP_TIMEOUT');child.kill('SIGKILL');process.exit(1)},25000);
createInterface({input:child.stdout}).on('line',line=>{
  let msg;try{msg=JSON.parse(line)}catch{return}
  const p=waiting.get(msg.id);if(!p)return;
  waiting.delete(msg.id);msg.error?p.reject(Error(JSON.stringify(msg.error))):p.resolve(msg.result);
});
const send=obj=>child.stdin.write(JSON.stringify({jsonrpc:'2.0',...obj})+'\n');
const request=(method,params)=>new Promise((resolve,reject)=>{const key=++id;waiting.set(key,{resolve,reject});send({id:key,method,params})});
try {
  const init=await request('initialize',{protocolVersion:'2025-03-26',capabilities:{},clientInfo:{name:'fyah-re-harness-bridge',version:'1.0.0'}});
  if(!init?.serverInfo?.name)throw Error('invalid MCP server');
  send({method:'notifications/initialized'});
  const listed=await request('tools/list',{});
  const tool=listed?.tools?.find(t=>t.name===toolName);
  if(!tool?.inputSchema)throw Error('allowlisted tool absent');
  const required=tool.inputSchema.required||[];
  if(required.some(k=>!(k in args)))throw Error('required arguments missing: '+required.join(','));
  // No arbitrary paths or URLs accepted from a model: fixture only for now.
  for(const value of Object.values(args)){
    if(typeof value==='string' && (value.startsWith('/')||value.includes('..')||/^https?:/i.test(value)))throw Error('untrusted path or URL');
  }
  const result=await request('tools/call',{name:toolName,arguments:args});
  if(result?.isError)throw Error('MCP tool returned isError');
  if(!Array.isArray(result?.content))throw Error('invalid MCP tool response');
  console.log(JSON.stringify({status:'PASS',server:init.serverInfo.name,tool:toolName,content_blocks:result.content.length}));
}catch(err){console.error('REA_MCP_CALL=FAIL',err.message);process.exitCode=1}
finally{clearTimeout(timer);child.kill('SIGTERM')}
