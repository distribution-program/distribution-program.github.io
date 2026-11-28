/* Driver Deliveries: confirm what drivers marked delivered on the phone. */
function drvdelTile(g){
 const b=el("button","nav-main","Driver Deliveries");b.id="t-drvdel";b.style.setProperty("--tile-color","#0f766e");g.appendChild(b);
 if((S.trialLimit||S.testMode)&&!window.__licFull){b.disabled=true;b.style.opacity=".5";b.style.cursor="not-allowed";b.title="Not available in the trial";b.onclick=()=>toast("Not available in the trial",true);return b}
 b.onclick=openDrvDel;
 setTimeout(async()=>{try{if(!document.body.contains(b)||b.disabled)return;const r=await api("/api/drvdel/list",{});if(!r.ok||!document.body.contains(b))return;
  const old=b.querySelector(".drvdel-count");if(old)old.remove();const c=el("span","drvdel-count",r.to_check+" to check");c.style.cssText="display:inline-block;margin-top:8px;background:#fff;color:#0b4a82;border-radius:12px;padding:2px 10px;font-weight:700;font-size:14px;"+(r.to_check?"":"opacity:.7");b.appendChild(c)}catch(e){}},400);
 return b;
}
async function openDrvDel(){
 if((S.trialLimit||S.testMode)&&!window.__licFull)return toast("Not available in the trial",true);
 if(!canOpen("drvdel"))return msgBox("Access denied","Driver Deliveries is not allowed for your user.",true);
 const c=el("div");c.appendChild(el("h2",null,"Driver Deliveries"));
 c.appendChild(el("p","hint","Only drivers who have In Process invoices are listed. Press a driver to see what he marked delivered on the phone."));
 const holder=el("div");c.appendChild(holder);const bar=el("div","toolbar");const closeB=el("button","btn","Close");bar.appendChild(closeB);c.appendChild(bar);
 const {close}=modal(c,"900px");closeB.onclick=close;
 let last="";
 async function load(){
  const r=await api("/api/drvdel/list",{});if(!r.ok){holder.textContent=r.msg||"Failed";return}
  const sig=JSON.stringify(r);if(sig===last)return;last=sig;
  if(!r.drivers.length){holder.appendChild(el("p","hint","No driver has In Process invoices."));return}
  holder.innerHTML="";const t=el("table","gtab");t.style.cssText="width:100%;border-collapse:collapse;font-size:14px";
  const h=el("tr");for(const x of ["Driver","Car / Line","In Process","Marked delivered, waiting for check"])h.appendChild(el("th",null,x));t.appendChild(h);
  for(const d of r.drivers){const tr=el("tr");tr.style.cursor="pointer";tr.append(el("td",null,d.driver),el("td",null,(d.car||"-")+" / "+(d.line||"-")),el("td",null,String(d.inprocess)));const m=el("td",null,String(d.marked));m.style.cssText="font-weight:700;"+(d.marked?"color:#b45309":"");tr.appendChild(m);tr.firstChild.style.fontWeight="700";tr.onclick=()=>{close();driverScreen(d.driver)};t.appendChild(tr)}
  holder.appendChild(t)}
 load();const iv=setInterval(()=>{if(!document.body.contains(holder)){clearInterval(iv);return}load()},2000);
}
async function driverScreen(name){
 const c=el("div");c.appendChild(el("h2",null,name+": marked delivered, waiting for your check"));
 const row=el("div");row.style.cssText="display:flex;gap:8px;align-items:center;background:#f1f5f9;padding:10px;border-radius:8px;margin:6px 0";
 const lab=el("label",null,"Check");lab.style.fontWeight="700";const inp=el("input","in");inp.placeholder="Type invoice number and press Enter";inp.style.cssText="flex:1;padding:9px;border:2px solid #0b4a82;border-radius:6px;font-size:15px";
 const go=el("button","btn accent","Check");row.append(lab,inp,go);c.appendChild(row);
 const msg=el("p","hint","After you type the number of the signed invoice, it leaves this list and its status changes from In Process to Delivered.");msg.style.margin="0 0 6px";c.appendChild(msg);
 const holder=el("div");c.appendChild(holder);const bar=el("div","toolbar");const back=el("button","btn","Back to drivers"),closeB=el("button","btn","Close");bar.append(back,closeB);c.appendChild(bar);
 const {close}=modal(c,"1100px");closeB.onclick=close;back.onclick=()=>{close();openDrvDel()};
 let last="";
 async function load(){
  const r=await api("/api/drvdel/driver",{driver:name});
  if(!r.ok){holder.innerHTML="";holder.textContent=r.msg||"Failed";return}
  const sig=JSON.stringify(r);if(sig===last)return;last=sig;holder.innerHTML="";
  if(!r.items.length){holder.appendChild(el("p","hint","Nothing is waiting for check for this driver."));return}
  const t=el("table","gtab");t.style.cssText="width:100%;border-collapse:collapse;font-size:13px";const h=el("tr");for(const x of ["Invoice Number","Customer","District","Delivered By / At (phone)","Status"])h.appendChild(el("th",null,x));t.appendChild(h);
  for(const i of r.items){const tr=el("tr");tr.append(el("td",null,i.invoice),el("td",null,i.customer),el("td",null,i.district),el("td",null,i.by+" "+i.at),el("td",null,i.status));tr.lastChild.style.color="#b45309";t.appendChild(tr)}
  holder.appendChild(t)}
 async function doCheck(){
  const v=inp.value.trim();if(!v)return;go.disabled=true;
  const r=await api("/api/drvdel/check",{driver:name,number:v});go.disabled=false;
  msg.textContent=r.msg||"";msg.style.color=r.ok?"#15803d":"#b91c1c";msg.style.fontWeight="700";
  inp.style.borderColor=r.ok?"#15803d":"#b91c1c";inp.value="";inp.focus();if(r.ok)load()}
 go.onclick=doCheck;inp.onkeydown=e=>{if(e.key==="Enter"){e.preventDefault();doCheck()}};
 load();const iv=setInterval(()=>{if(!document.body.contains(holder)){clearInterval(iv);return}load()},2000);setTimeout(()=>inp.focus(),100);
}
