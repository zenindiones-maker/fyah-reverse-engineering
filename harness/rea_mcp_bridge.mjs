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
  console.error('REA_MCP_TOOL_SCHEMA='+JSON.stringify(tool.inputSchema).slice(0,2500));
  const required=tool.inputSchema.required||[];
  if(required.some(k=>!(k in args)))throw Error('required arguments missing: '+required.join(','));
  // No arbitrary paths or URLs accepted from a model: fixture only for now.
  for(const value of Object.values(args)){
    if(typeof value==='string' && (value.startsWith('/')||value.includes('..')||/^https?:/i.test(value)))throw Error('untrusted path or URL');
  }
  const open=listed.tools.find(t=>t.name==='open_binary');
  if(!open?.inputSchema)throw Error('open_binary unavailable');
  console.error('REA_MCP_OPEN_SCHEMA='+JSON.stringify(open.inputSchema).slice(0,2200));
  const fixture=process.env.REA_MCP_FIXTURE;
  if(!fixture || !fixture.startsWith(process.cwd()+'/'))throw Error('fixture must be inside current workspace');
  const openArgs={path:fixture};
  const opened=await request('tools/call',{name:'open_binary',arguments:openArgs});
  if(opened?.isError)throw Error('open_binary failed: '+JSON.stringify(opened.content).slice(0,1200));
  const result=await request('tools/call',{name:toolName,arguments:args});
  if(result?.isError)throw Error('MCP tool returned isError: '+JSON.stringify(result.content).slice(0,1500));
  if(!Array.isArray(result?.content))throw Error('invalid MCP tool response');
  const reports=result.content.filter(b=>b.type==='text'&&typeof b.text==='string'&&b.text.trim());
  if(!reports.length)throw Error('REA returned no nonempty report');
  const report=reports.map(b=>b.text).join('\n');
  if(report.length<40)throw Error('REA report unexpectedly short');
  console.log(JSON.stringify({status:'PASS',server:init.serverInfo.name,tool:toolName,content_blocks:result.content.length,fixture_opened:true,report_length:report.length,report_preview:report.slice(0,1200)}));
}catch(err){console.error('REA_MCP_CALL=FAIL',err.message);process.exitCode=1}
finally{clearTimeout(timer);child.kill('SIGTERM')}
