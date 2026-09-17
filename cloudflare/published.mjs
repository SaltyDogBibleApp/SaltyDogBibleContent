const REPOSITORY="SaltyDogBibleApp/SaltyDogBibleContent";
const REPOSITORY_NAME="SaltyDogBibleContent";
const FEED_PATH="reserve-content-feed.json";
const API="https://api.github.com";
const REVIEW_PREFIX="reserve-intel-review/";

export const CHECKS=[
  "I opened the official source.",
  "I verified the facts against the official source.",
  "I verified the status and effective date.",
  "I verified the intended audience.",
  "I reviewed the title, summary, Why It Matters, and details.",
  "I approve this update to the published article.",
];
const PUBLISH_CHECKS=[
  "I opened the official source.",
  "I verified the facts against the official source.",
  "I verified the status and effective date.",
  "I verified the intended audience.",
  "I reviewed the title, summary, Why It Matters, and details.",
  "I approve publication to Reserve Intel.",
];

class UpdateError extends Error{constructor(message,status=400){super(message);this.status=status;}}
function exactKeys(v,keys,label){if(!v||typeof v!=="object"||Array.isArray(v)||Object.keys(v).length!==keys.length||keys.some(k=>!Object.hasOwn(v,k)))throw new UpdateError(`${label} contains missing or unexpected fields.`);}
function validId(v){return typeof v==="string"&&/^[a-zA-Z0-9_-]{1,200}$/.test(v);}
function same(a,b){return JSON.stringify(a)===JSON.stringify(b);}
function nowIso(){return new Date().toISOString().replace(/\.\d{3}Z$/,"Z");}
function encode(text){let b="";for(const x of new TextEncoder().encode(text))b+=String.fromCharCode(x);return btoa(b);}
function decode(text){return new TextDecoder().decode(Uint8Array.from(atob(text.replace(/\s/g,"")),c=>c.charCodeAt(0)));}

export function validatePatch(v){
  exactKeys(v,["title","summary","whyItMatters","details","category","status","priority","effectiveDate","audience","isPinned"],"Article update");
  const out={};
  for(const [k,max] of Object.entries({title:300,summary:4000,whyItMatters:6000,details:20000})){
    if(typeof v[k]!=="string"||!v[k].trim()||v[k].length>max)throw new UpdateError(`${k} must contain 1–${max} characters.`);
    out[k]=v[k].trim();
  }
  const choices={
    category:["Legislation / NDAA","Policy","Pay & Benefits","Retirement","VA / Veteran Benefits","Training & Readiness","Admin","Other"],
    status:["TRACKING","PROPOSED","INTRODUCED","COMMITTEE","PASSED HOUSE","PASSED SENATE","SIGNED","EFFECTIVE","SUPERSEDED"],
    priority:["NORMAL","HIGH"],
  };
  for(const [k,a] of Object.entries(choices)){if(!a.includes(v[k]))throw new UpdateError(`Unsupported ${k}.`);out[k]=v[k];}
  const d=v.effectiveDate;
  if(d!==null&&(typeof d!=="string"||!/^\d{4}-\d{2}-\d{2}T00:00:00Z$/.test(d)||!Number.isFinite(Date.parse(d))||new Date(d).toISOString().replace(".000Z","Z")!==d))throw new UpdateError("Effective date must be a valid calendar date.");
  out.effectiveDate=d;
  exactKeys(v.audience,["service","reserveStatus","trainingWing","squadron"],"Audience");
  if(!["ALL","USN","USMC"].includes(v.audience.service)||!["ALL","SELRES","VTU"].includes(v.audience.reserveStatus))throw new UpdateError("Unsupported audience.");
  out.audience={...v.audience};
  for(const k of ["trainingWing","squadron"]){const t=v.audience[k];if(t!==null&&(typeof t!=="string"||t.length>120))throw new UpdateError(`Invalid ${k}.`);out.audience[k]=t?.trim()||null;}
  if(typeof v.isPinned!=="boolean")throw new UpdateError("Pinned must be true or false.");
  out.isPinned=v.isPinned;return out;
}

async function readJson(request,limit){let text;try{text=await request.text();}catch{throw new UpdateError("Could not read the request body.");}if(!text)throw new UpdateError("Empty request body.");if(new TextEncoder().encode(text).byteLength>limit)throw new UpdateError("Payload is too large.",413);try{return JSON.parse(text);}catch{throw new UpdateError("Invalid JSON request.");}}

async function github(path,token,method="GET",body){
  let r;try{r=await fetch(`${API}${path}`,{method,headers:{Accept:"application/vnd.github+json",Authorization:`Bearer ${token}`,"X-GitHub-Api-Version":"2026-03-10","User-Agent":"Salty-Dog-Reserve-Intel","Content-Type":"application/json"},...(body===undefined?{}:{body:JSON.stringify(body)})});}
  catch(e){console.error("GitHub fetch failed",{path,method,name:e?.name||"Error",message:e?.message||String(e)});throw new UpdateError(`GitHub request failed before receiving a response (${method} ${path}).`,502);}
  let p=null,t=await r.text();if(t){try{p=JSON.parse(t);}catch{if(r.ok)throw new UpdateError("GitHub returned an invalid response.",502);}}
  if(!r.ok){if(path.includes("/access_tokens")&&(r.status===403||r.status===422))throw new UpdateError("The GitHub App needs Contents and Pull requests permissions set to Read and write.",502);const detail=typeof p?.message==="string"&&p.message.length<=300?` ${p.message}`:"";throw new UpdateError(`GitHub could not complete the request (HTTP ${r.status}).${detail}`,r.status===409||r.status===422?409:502);}
  return p;
}

async function installationToken(env,deps){const jwt=await deps.createGitHubAppJwt(env);const i=await github(`/repos/${REPOSITORY}/installation`,jwt);if(!Number.isSafeInteger(i?.id))throw new UpdateError("GitHub App installation was not found.",502);const d=await github(`/app/installations/${i.id}/access_tokens`,jwt,"POST",{repositories:[REPOSITORY_NAME],permissions:{contents:"write",pull_requests:"write"}});if(typeof d?.token!=="string"||!d.token)throw new UpdateError("GitHub App token was not available.",502);return d.token;}

function checklist(){return{sourceOpenedAndRead:true,factsVerifiedAgainstSource:true,statusVerified:true,effectiveDateVerified:true,audienceVerified:true,summaryRewrittenFromSource:true,whyItMattersRewrittenFromSource:true,detailsRewrittenFromSource:true,approvedForPublication:true};}
function correctionId(articleId,now){const stamp=now.replace(/\D/g,"").slice(0,14);const rand=crypto.getRandomValues(new Uint32Array(1))[0].toString(36).padStart(6,"0").slice(-6);return `correction-${articleId.replace(/[^a-zA-Z0-9_-]/g,"-").slice(0,120)}-${stamp}-${rand}`;}
function safeFence(v){const t=typeof v==="object"&&v!==null?JSON.stringify(v,null,2):String(v??"Not specified");return `\`\`\`text\n${t.replaceAll("```","`` `")}\n\`\`\``;}

function makeDraft(current,patch,id,session,now){
  if(typeof current.sourceName!=="string"||!current.sourceName.trim()||typeof current.sourceURL!=="string"||!current.sourceURL.startsWith("https://")||typeof current.publishedAt!=="string"||!current.publishedAt)throw new UpdateError("This published article is missing immutable source or publication metadata and cannot be corrected through the dashboard.",409);
  const articleDraft={id,publishedAt:current.publishedAt,updatedAt:current.updatedAt||null,...patch,sourceName:current.sourceName,sourceURL:current.sourceURL,isActive:false};
  return{draftSchemaVersion:1,draftStatus:"PENDING_HUMAN_REVIEW",requiresHumanReview:true,publishReady:false,detectedAt:now,sourceEvidence:{sourceName:current.sourceName,sourceType:"manual_correction",sourceURL:current.sourceURL,listedDate:typeof current.effectiveDate==="string"?current.effectiveDate.slice(0,10):now.slice(0,10),reserveSignals:["ADMIN_CORRECTION"],categoryHints:[patch.category],officialHostVerified:true,verificationMethod:"authenticated-admin-correction-confirmation",correctionOfArticleId:current.id},reviewChecklist:checklist(),articleDraft,correction:{liveArticleId:current.id,submittedBy:session.sub,submittedAt:now,baseUpdatedAt:current.updatedAt||null}};
}

function renderReview(current,patch,id,session,now){
  const labels={title:"Title",summary:"Summary",whyItMatters:"Why It Matters",details:"Details",category:"Category",status:"Status",priority:"Priority",effectiveDate:"Effective Date",audience:"Audience",isPinned:"Pinned"};
  const changed=Object.keys(patch).filter(k=>!same(patch[k],current[k]));
  const l=["# Reserve Intel Published Article Correction","","> **Human-approved dashboard correction.** The currently published article remains live until this pull request is merged and the existing publication workflow succeeds.","",`- Live article ID: \`${current.id}\``,`- Correction draft ID: \`${id}\``,`- Submitted by: \`${session.sub}\``,`- Submitted at: ${now}`,`- Official source: ${current.sourceURL}`,"- Source identity is immutable in the dashboard correction flow.","","## Proposed Changes",""];
  for(const k of changed)l.push(`### ${labels[k]||k}`,"","**Currently published**","",safeFence(current[k]),"","**Proposed correction**","",safeFence(patch[k]),"");
  l.push("## Publication Approval","","> These confirmations were completed in the authenticated Reserve Intel dashboard before this correction PR was created. Merging this PR is the final publication action.","");
  for(const c of PUBLISH_CHECKS)l.push(`- [x] ${c}`);l.push("");return l.join("\n");
}

async function fetchFeed(token){const f=await github(`/repos/${REPOSITORY}/contents/${FEED_PATH}?ref=main`,token);if(f?.encoding!=="base64"||typeof f.content!=="string")throw new UpdateError("The published feed could not be read.",502);let feed;try{feed=JSON.parse(decode(f.content));}catch{throw new UpdateError("The published feed could not be decoded.",502);}if(!Array.isArray(feed.intelArticles))throw new UpdateError("Invalid published feed.",502);return feed;}
async function liveArticle(token,id){const feed=await fetchFeed(token);const m=feed.intelArticles.filter(a=>a?.id===id);if(m.length!==1||m[0].isActive!==true)throw new UpdateError("This article is missing, inactive, or has a duplicate ID.",409);return m[0];}
function marker(id){return `- Live article ID: \`${id}\``;}
function summary(pr){return{prNumber:pr.number,prUrl:pr.html_url,title:pr.title,branch:pr.head?.ref||null,draft:pr.draft===true};}

async function openReview(token,id){
  const pulls=await github(`/repos/${REPOSITORY}/pulls?state=open&base=main&per_page=100`,token);if(!Array.isArray(pulls))throw new UpdateError("GitHub returned an invalid pull-request list.",502);
  const prefix=`${REVIEW_PREFIX}correction-${id}-`,mk=marker(id);
  const m=pulls.filter(pr=>pr?.state==="open"&&pr?.base?.ref==="main"&&pr?.head?.repo?.full_name===REPOSITORY&&typeof pr?.head?.ref==="string"&&pr.head.ref.startsWith(prefix)&&typeof pr?.body==="string"&&pr.body.includes(mk));
  if(m.length>1)throw new UpdateError("More than one open correction PR exists for this article. Resolve the duplicates in GitHub before continuing.",409);return m[0]||null;
}

async function validatedReview(token,id,n){
  if(!Number.isSafeInteger(n)||n<1)throw new UpdateError("Invalid review PR number.");
  const pr=await github(`/repos/${REPOSITORY}/pulls/${n}`,token),prefix=`${REVIEW_PREFIX}correction-${id}-`;
  if(pr?.number!==n||pr?.state!=="open"||pr?.merged_at||pr?.base?.ref!=="main"||pr?.head?.repo?.full_name!==REPOSITORY||typeof pr?.head?.ref!=="string"||!pr.head.ref.startsWith(prefix)||typeof pr?.body!=="string"||!pr.body.includes(marker(id)))throw new UpdateError("This review PR does not match the selected published article.",409);
  for(const c of PUBLISH_CHECKS)if(!pr.body.includes(`- [x] ${c}`))throw new UpdateError("The review PR no longer contains all six publication approvals.",409);
  const cid=pr.head.ref.slice(REVIEW_PREFIX.length);if(!/^correction-[a-zA-Z0-9_-]{1,220}$/.test(cid))throw new UpdateError("The correction branch name is invalid.",409);
  const dp=`drafts/pending/${cid}.json`,rp=`reviews/pending/${cid}.md`,files=await github(`/repos/${REPOSITORY}/pulls/${n}/files?per_page=100`,token),names=Array.isArray(files)?files.map(f=>f?.filename):[];
  if(names.length!==2||!names.includes(dp)||!names.includes(rp))throw new UpdateError("The correction PR contains unexpected file changes and cannot be managed from the dashboard.",409);
  const df=await github(`/repos/${REPOSITORY}/contents/${dp}?ref=${encodeURIComponent(pr.head.ref)}`,token);if(df?.encoding!=="base64"||typeof df.content!=="string")throw new UpdateError("The correction draft could not be read.",502);
  let draft;try{draft=JSON.parse(decode(df.content));}catch{throw new UpdateError("The correction draft is invalid JSON.",409);}
  if(draft?.draftStatus!=="PENDING_HUMAN_REVIEW"||draft?.requiresHumanReview!==true||draft?.publishReady!==false||draft?.sourceEvidence?.officialHostVerified!==true||draft?.correction?.liveArticleId!==id||draft?.articleDraft?.id!==cid||draft?.articleDraft?.isActive!==false)throw new UpdateError("The correction draft no longer matches the dashboard review contract.",409);
  return{pr,draft};
}

async function reviewAction(body,token,respond){
  if(body.action==="review-status"){exactKeys(body,["action","articleId"],"Review status request");if(!validId(body.articleId))throw new UpdateError("Invalid article ID.");const pr=await openReview(token,body.articleId);return respond({ok:true,articleId:body.articleId,review:pr?summary(pr):null});}
  if(body.action!=="approve-review"&&body.action!=="reject-review")return null;
  exactKeys(body,["action","articleId","prNumber"],"Review action request");if(!validId(body.articleId))throw new UpdateError("Invalid article ID.");const{pr,draft}=await validatedReview(token,body.articleId,body.prNumber);
  if(body.action==="approve-review"){
    if(pr.draft===true)throw new UpdateError("This correction is still a draft PR and cannot be published from the dashboard.",409);
    const current=await liveArticle(token,body.articleId);if((current.updatedAt||null)!==(draft.correction?.baseUpdatedAt||null))throw new UpdateError("The live article changed after this correction was created. Reject this correction, refresh the dashboard, and create a new one.",409);if(current.sourceURL!==draft.articleDraft?.sourceURL)throw new UpdateError("The live article source identity changed.",409);
    const m=await github(`/repos/${REPOSITORY}/pulls/${body.prNumber}/merge`,token,"PUT",{merge_method:"merge",commit_title:`Approve Reserve Intel correction for ${body.articleId}`});if(m?.merged!==true)throw new UpdateError(m?.message||"GitHub did not merge the correction PR.",409);return respond({ok:true,action:"approved",articleId:body.articleId,prNumber:body.prNumber,message:m.message||"Correction PR merged."});
  }
  const c=await github(`/repos/${REPOSITORY}/pulls/${body.prNumber}`,token,"PATCH",{state:"closed"});if(c?.state!=="closed")throw new UpdateError("GitHub did not close the correction PR.",409);return respond({ok:true,action:"rejected",articleId:body.articleId,prNumber:body.prNumber});
}

async function createCorrection(body,token,session,respond){
  exactKeys(body,["articleId","baseUpdatedAt","patch","confirmations"],"Correction request");if(!validId(body.articleId))throw new UpdateError("Invalid article ID.");if(body.baseUpdatedAt!==null&&(typeof body.baseUpdatedAt!=="string"||body.baseUpdatedAt.length>80))throw new UpdateError("Invalid article version.");if(!Array.isArray(body.confirmations)||body.confirmations.length!==CHECKS.length||body.confirmations.some((c,i)=>c!==CHECKS[i]))throw new UpdateError("Complete all six update confirmations.");
  const existing=await openReview(token,body.articleId);if(existing)throw new UpdateError(`Review PR #${existing.number} is already open for this article. Approve or reject it before creating another correction.`,409);
  const patch=validatePatch(body.patch),current=await liveArticle(token,body.articleId);if((current.updatedAt||null)!==body.baseUpdatedAt)throw new UpdateError("This article changed after your dashboard snapshot was generated. Cancel editing, refresh the dashboard, and reopen the article before submitting the correction.",409);if(Object.keys(patch).every(k=>same(patch[k],current[k])))throw new UpdateError("No changes to submit.");
  const now=nowIso(),cid=correctionId(current.id,now),branch=`${REVIEW_PREFIX}${cid}`,dp=`drafts/pending/${cid}.json`,rp=`reviews/pending/${cid}.md`,draft=makeDraft(current,patch,cid,session,now),review=renderReview(current,patch,cid,session,now);
  const ref=await github(`/repos/${REPOSITORY}/git/ref/heads/main`,token),sha=ref?.object?.sha;if(typeof sha!=="string"||!/^[a-f0-9]{40}$/.test(sha))throw new UpdateError("GitHub main branch could not be resolved.",502);
  await github(`/repos/${REPOSITORY}/git/refs`,token,"POST",{ref:`refs/heads/${branch}`,sha});
  await github(`/repos/${REPOSITORY}/contents/${dp}`,token,"PUT",{branch,message:`Create Reserve Intel correction draft for ${current.id}`,content:encode(JSON.stringify(draft,null,2)+"\n")});
  await github(`/repos/${REPOSITORY}/contents/${rp}`,token,"PUT",{branch,message:`Add Reserve Intel correction review for ${current.id}`,content:encode(review+"\n")});
  const pr=await github(`/repos/${REPOSITORY}/pulls`,token,"POST",{title:`Reserve Intel Correction: ${current.title}`.slice(0,250),head:branch,base:"main",body:review,draft:false,maintainer_can_modify:false});
  if(!Number.isSafeInteger(pr?.number)||typeof pr?.html_url!=="string"||!pr.html_url.startsWith("https://github.com/"))throw new UpdateError("GitHub created the correction branch but did not return a valid review PR.",502);
  return respond({ok:true,articleId:current.id,correctionId:cid,branch,prNumber:pr.number,prUrl:pr.html_url,draft:false});
}

export async function handlePublished(request,env,deps){
  const respond=(p,s=200)=>deps.jsonResponse(p,s,env,request);let stage="request-validation";
  try{
    if(request.method!=="POST")throw new UpdateError("Method not allowed.",405);if(request.headers.get("Origin")!==env.FRONTEND_ORIGIN)throw new UpdateError("Origin is not authorized.",403);
    const m=(request.headers.get("Authorization")||"").match(/^Bearer\s+(.+)$/i);if(!m)throw new UpdateError("GitHub sign-in is required.",401);
    let session;try{session=await deps.verifySession(m[1],env.SESSION_SECRET);}catch{throw new UpdateError("Your session expired. Sign in again; your edits are still in this tab.",401);}if(session.sub?.toLowerCase()!=="saltydogbibleapp"||session.repository!==REPOSITORY||env.GITHUB_REPOSITORY!==REPOSITORY)throw new UpdateError("Session is not authorized.",403);
    if(request.headers.get("Content-Type")?.split(";")[0].trim()!=="application/json")throw new UpdateError("JSON content type is required.",415);
    stage="request-parse";const body=await readJson(request,128*1024);stage="installation-token";const token=await installationToken(env,deps);
    if(typeof body?.action==="string"){stage=`review-${body.action}`;const r=await reviewAction(body,token,respond);if(r)return r;throw new UpdateError("Unsupported review action.");}
    stage="correction-create";return await createCorrection(body,token,session,respond);
  }catch(error){if(!(error instanceof UpdateError))console.error("Published correction failed",{stage,name:error?.name||"Error",message:error?.message||String(error)});return respond({ok:false,error:error instanceof UpdateError?error.message:"The GitHub review action could not be completed. No live content was changed."},error instanceof UpdateError?error.status:502);}
}
