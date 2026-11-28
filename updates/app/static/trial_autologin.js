// Temporary trial convenience only. Existing login, users and Firebase security stay unchanged.
(async()=>{
 const endpoint=async(path,body={})=>(await fetch('/api/trial-autologin/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
 if((typeof S!=="undefined"&&S.trialLimit))return;
 const state=await endpoint('status');
 if(state.enabled){const r=await endpoint('start');if(r.ok&&!r.already_logged_in)await boot();}
 let button;
 setInterval(()=>{
  const app=document.querySelector('#app');if((typeof S!=="undefined"&&S.trialLimit))return;if(!app||app.classList.contains('hidden')||button)return;
  button=document.createElement('button');button.className='btn';button.textContent='Trial auto-login';button.title='Temporary Windows user mapping. Off by default. Not Firebase security.';
  const target=document.querySelector('#t-settings');target.parentNode.insertBefore(button,target);
  button.onclick=async()=>{
   const st=await endpoint('status');
   const c=el('div');c.appendChild(el('h2',null,'Temporary trial auto-login'));
   c.appendChild(el('p',null,'Convenience only, not security. Anyone using this unlocked computer can act as the selected user. Firebase access is separate.'));
   c.appendChild(el('p',null,'Windows user: '+st.windows_user+' | Program user: '+S.user));
   c.appendChild(el('p',null,st.enabled?'Enabled until '+new Date(st.expires_at*1000).toLocaleTimeString():'Off by default. Expires after 60 minutes; normal sign-in remains available.'));
   const row=el('div','mrow'),on=el('button','btn accent','Enable for this user, 60 min'),off=el('button','btn','Disable'),sw=el('button','btn','Switch user'),cl=el('button','btn','Close');row.append(on,off,sw,cl);c.appendChild(row);const {close}=modal(c,'560px');
   on.disabled=S.user==='ADMIN';on.title=on.disabled?'Sign in as the intended non-ADMIN user first':'';
   on.onclick=async()=>{const r=await endpoint('enable',{minutes:60});close();msgBox('Trial auto-login',r.ok?'Enabled temporarily for '+S.user+' on Windows user '+r.windows_user+'.':r.msg,!r.ok);};
   off.onclick=async()=>{await endpoint('disable');close();msgBox('Trial auto-login','Disabled. Normal sign-in is preserved.');};
   sw.onclick=async()=>{await api('/api/logout');location.reload();};cl.onclick=close;
  };
 },500);
})();
