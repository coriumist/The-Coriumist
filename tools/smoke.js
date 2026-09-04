// THE CORIUMIST . SMOKE TEST. Loads every page type in jsdom with the network mocked and fails the build on any JS error.
const {JSDOM,VirtualConsole}=require("jsdom");const fs=require("fs");const path=require("path");
const SITE=path.join(__dirname,"..","site");
const content=[{id:"11111111-1111-1111-1111-111111111111",format:"Dispatch",title:"Test dispatch",body:"Para one.\n\nPara two.",publish_at:"2026-09-01T10:00:00Z",media_urls:[]}];
async function test(rel,url){
  let html=fs.readFileSync(path.join(SITE,rel),"utf8");
  html=html.replace(/<script src="https:\/\/cdnjs[^"]*leaflet[^"]*"><\/script>/,`<script>${fs.readFileSync(require.resolve("leaflet/dist/leaflet.js"),"utf8")}</script>`).replace(/<link rel="stylesheet" href="https:\/\/cdnjs[^"]*leaflet[^"]*">/,"").replace(/<link href="https:\/\/fonts[^"]*"[^>]*>/g,"");
  const errors=[];const vc=new VirtualConsole();vc.on("jsdomError",e=>errors.push("jsdomError: "+e.message.split("\n")[0]));vc.on("error",m=>errors.push("console.error: "+m));
  const dom=new JSDOM(html,{url,runScripts:"dangerously",pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){
  w.IntersectionObserver=class{constructor(cb){this.cb=cb}observe(el){this.cb([{isIntersecting:true,target:el}])}unobserve(){}};
  w.matchMedia=q=>({matches:false,addListener(){},removeListener(){}});
  w.fetch=async(u,o)=>{u=String(u);
    if(u.startsWith("/data/read.json"))return {ok:true,json:async()=>JSON.parse(fs.readFileSync(SITE+"/data/read.json","utf8"))};
    if(u.includes("supabase.co/rest/v1/content"))return {ok:true,json:async()=>content};
    if(u.includes("supabase.co/rest/v1/venues"))return {ok:true,json:async()=>[{city_slug:"monaco",slug:"le-louis-xv"}]};
    errors.push("unexpected fetch "+u);return {ok:false,json:async()=>[]}};
  w.addEventListener("error",e=>errors.push("window.error: "+(e.error&&e.error.message||e.message)));
  w.onerror=(m)=>errors.push("onerror: "+m);
  }});const w=dom.window;
  await new Promise(r=>setTimeout(r,1200));
  const d=w.document;
  const out={rel,errors,dispatchCards:d.querySelectorAll("#drail .card, #feed .card").length,markers:d.querySelectorAll(".leaflet-marker-icon").length,panel:(d.querySelector("#panel h3")||{}).textContent,title:(d.querySelector("#a-title")||{}).textContent,body:(d.querySelector("#a-body")||{}).innerHTML,approved:[...d.querySelectorAll("[data-v]")].filter(e=>e.textContent).length,menu:!!d.querySelector(".hnav .menu")};
  console.log(rel, JSON.stringify(out));
  if(errors.length){console.error("SMOKE FAIL",rel,errors);process.exitCode=1}
  if(rel==="index.html"&&(out.markers!==40||out.dispatchCards<1)){console.error("SMOKE FAIL home",out);process.exitCode=1}
  if(rel.startsWith("read/")&&out.title!=="Test dispatch"){console.error("SMOKE FAIL article",out);process.exitCode=1}
  try{w.close()}catch(e){}
}
(async()=>{
 await test("index.html","https://coriumist.com/");
 await test("map/index.html","https://coriumist.com/map/");
 await test("read/index.html","https://coriumist.com/read/?id=11111111-1111-1111-1111-111111111111");
 await test("latest/index.html","https://coriumist.com/latest/");
 await test("circuit/monaco/index.html","https://coriumist.com/circuit/monaco/");
 await test("places/monaco/le-louis-xv/index.html","https://coriumist.com/places/monaco/le-louis-xv/");
})();
