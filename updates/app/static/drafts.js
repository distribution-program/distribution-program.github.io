/* Immediate local input recovery. Drafts never enter invoice sync or lifecycle tables. */
"use strict";
const DRAFTS={};
const draftStorageKey=()=>"dprogram-input-drafts:"+(S.testMode?"trial:":"work:")+S.user;
let draftQueue=Promise.resolve();
function draftRead(key){return DRAFTS[key]?.data||null;}
function draftWrite(key,data){
 const entry={data,updated:Math.max(Date.now(),(DRAFTS[key]?.updated||0)+1)};DRAFTS[key]=entry;
 let stored=false;try{localStorage.setItem(draftStorageKey(),JSON.stringify(DRAFTS));stored=true;}catch(e){}
 draftQueue=draftQueue.catch(()=>{}).then(async()=>{
  if(DRAFTS[key]?.updated!==entry.updated)return;
  try{const a=await api('/api/drafts/set',{key,entry});if(!a.ok)throw Error(a.msg);}
  catch(e){if(!stored)toast('Input recovery could not be saved. Keep this screen open.',true);}
 });
 return entry;
}
function draftDrop(key){draftWrite(key,null);}
async function initDrafts(){
 for(const k of Object.keys(DRAFTS))delete DRAFTS[k];
 const remote=await api('/api/drafts/get');Object.assign(DRAFTS,remote.drafts||{});
 try{const local=JSON.parse(localStorage.getItem(draftStorageKey())||'{}');for(const [k,v]of Object.entries(local))if(!DRAFTS[k]||v.updated>DRAFTS[k].updated)DRAFTS[k]=v;
 localStorage.setItem(draftStorageKey(),JSON.stringify(DRAFTS));}catch(e){}
 for(const [key,entry]of Object.entries(DRAFTS))draftQueue=draftQueue.then(()=>api('/api/drafts/set',{key,entry}));
}
function recoveredHint(parent,text){const h=el('p','hint',text);h.style.margin='8px 0';parent.appendChild(h);return h;}
