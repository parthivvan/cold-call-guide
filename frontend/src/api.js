const BASE=(import.meta.env.VITE_API_BASE_URL||'http://localhost:8000').replace(/\/+$/,'');
async function request(path,options={}) {
 const response=await fetch(BASE+path,{...options,headers:{...(options.body?{'Content-Type':'application/json'}:{}),...(options.headers||{})}});
 const text=await response.text(); let data; try{data=text?JSON.parse(text):null}catch{data=text}
 if(!response.ok){const detail=data&&data.detail;throw new Error(typeof detail==='string'?detail:detail?.message||('Request failed ('+response.status+')'))}
 return data;
}
const post=body=>({method:'POST',body:JSON.stringify(body)});
export const api={health:()=>request('/'),stages:()=>request('/stages'),calls:()=>request('/calls'),createCall:b=>request('/calls',post(b)),saveStage:(id,b)=>request('/calls/'+encodeURIComponent(id)+'/stages',post(b)),suggest:id=>request('/calls/'+encodeURIComponent(id)+'/suggest-outcome',{method:'POST'}),close:(id,b)=>request('/calls/'+encodeURIComponent(id)+'/close',post(b))};
