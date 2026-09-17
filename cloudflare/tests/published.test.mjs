import test from 'node:test';
import assert from 'node:assert/strict';
import {handlePublished, CHECKS} from '../published.mjs';
const env = {GITHUB_REPOSITORY:'SaltyDogBibleApp/SaltyDogBibleContent',FRONTEND_ORIGIN:'https://saltydogbibleapp.github.io',SESSION_SECRET:'test'};
const article = {id:'intel-test',title:'Original',summary:'Summary',whyItMatters:'Why',details:'Details',category:'Policy',status:'EFFECTIVE',priority:'NORMAL',effectiveDate:null,audience:{service:'USN',reserveStatus:'ALL',trainingWing:null,squadron:null},isPinned:false,isActive:true,publishedAt:'2026-01-01T00:00:00Z',updatedAt:'2026-02-01T00:00:00Z',sourceName:'Official source',sourceURL:'https://example.mil/policy'};
const {id,isActive,publishedAt,updatedAt,sourceName,sourceURL,...editable} = article;
const sha = 'a'.repeat(40);
const deps = {verifySession:async()=>({sub:'SaltyDogBibleApp',repository:env.GITHUB_REPOSITORY}),createGitHubAppJwt:async()=>'jwt',jsonResponse:(p,status)=>Response.json(p,{status})};
async function run({body, method='POST', origin=env.FRONTEND_ORIGIN, auth='Bearer test', currentSha=sha, commitStatus=200, sessionDeps=deps}={}) {
 const calls=[];
 const originalFetch=globalThis.fetch;
 const feed={generatedAt:'old',intelArticles:[article,{...article,id:'other'}],tipperMessages:[{id:'keep'}]};
 globalThis.fetch=async(url, options)=>{
  calls.push({url,options});
  if(url.endsWith('/installation')) return Response.json({id:123});
  if(url.endsWith('/access_tokens')) return Response.json({token:'installation-test'});
  if(options.method==='PUT') return Response.json(commitStatus===200?{content:{sha:'b'.repeat(40)},commit:{sha:'c'.repeat(40)}}:{error:'conflict'},{status:commitStatus});
  return Response.json({sha:currentSha,encoding:'base64',content:Buffer.from(JSON.stringify(feed)).toString('base64')});
 };
 try {
  const request = new Request('https://worker.example/api/published-article?id=intel-test',{method,headers:{Origin:origin,Authorization:auth,'Content-Type':'application/json'},...(method==='GET'?{}:{body:JSON.stringify(body ?? {articleId:id,baseSha:sha,patch:{...editable,title:'Updated — café'},confirmations:CHECKS})})});
  const response = await handlePublished(request,env,sessionDeps);
  return {status:response.status,data:await response.json(),calls,feed};
 } finally {globalThis.fetch=originalFetch;}
}
test('read returns current article and version without modifying GitHub',async()=>{
 const r=await run({method:'GET'}); assert.equal(r.status,200);assert.equal(r.data.baseSha,sha);assert.deepEqual(r.data.article,article);assert.ok(!r.calls.some(c=>c.options.method==='PUT'));assert.deepEqual(JSON.parse(r.calls[1].options.body).permissions,{contents:'read'});
});
test('approved update changes only editable fields and timestamps, preserves feed and audit',async()=>{
 const r=await run();assert.equal(r.status,200);
 const put=r.calls.find(c=>c.options.method==='PUT');const payload=JSON.parse(put.options.body);const written=JSON.parse(Buffer.from(payload.content,'base64').toString('utf8'));
 assert.equal(payload.sha,sha);assert.equal(payload.branch,'main');assert.equal(written.intelArticles[0].title,'Updated — café');
 for(const key of ['id','publishedAt','sourceName','sourceURL','isActive']) assert.equal(written.intelArticles[0][key],article[key]);
 assert.deepEqual(written.intelArticles[1],r.feed.intelArticles[1]);assert.deepEqual(written.tipperMessages,r.feed.tipperMessages);assert.equal(written.intelArticles.length,2);assert.match(payload.message,/Approved by SaltyDogBibleApp/);for(const c of CHECKS) assert.ok(payload.message.includes(c));
 assert.deepEqual(JSON.parse(r.calls[1].options.body).permissions,{contents:'write'});
});
test('missing/expired authentication and foreign origins fail before GitHub',async()=>{
 for(const args of [{auth:''},{origin:'https://attacker.example'},{sessionDeps:{...deps,verifySession:async()=>{throw Error();}}},{sessionDeps:{...deps,verifySession:async()=>({sub:'another-user',repository:env.GITHUB_REPOSITORY})}}]){
  const r=await run(args);assert.ok([401,403].includes(r.status));assert.equal(r.calls.length,0);
 }
});
test('reject incomplete approvals, immutable fields, invalid calendar dates, invalid audience',async()=>{
 const base={articleId:id,baseSha:sha,patch:editable,confirmations:CHECKS};
 for(const body of [{...base,confirmations:CHECKS.slice(0,5)},{...base,patch:{...editable,id:'hijack'}},{...base,patch:{...editable,effectiveDate:'2026-02-30T00:00:00Z'}},{...base,patch:{...editable,audience:{...editable.audience,service:'invalid'}}}]){
  const r=await run({body});assert.equal(r.status,400);assert.equal(r.calls.length,0);
 }
});
test('stale edit does not write; concurrent update returns conflict',async()=>{
 const stale=await run({currentSha:'d'.repeat(40)});assert.equal(stale.status,409);assert.ok(!stale.calls.some(c=>c.options.method==='PUT'));
 const race=await run({commitStatus:409});assert.equal(race.status,409);
});
test('no-op update does not write',async()=>{
 const r=await run({body:{articleId:id,baseSha:sha,patch:editable,confirmations:CHECKS}});assert.equal(r.status,400);assert.ok(!r.calls.some(c=>c.options.method==='PUT'));
});
