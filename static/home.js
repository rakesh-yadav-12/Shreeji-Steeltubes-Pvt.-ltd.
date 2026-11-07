/* Home tab logic (Ashoka Buildcon style home) */
(function(){
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const app=$('#app'),home=$('#home');
const H=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');

/* ---------- tabs: Home / Chat (the whole tab bar is hidden by CSS once the user says Hi) ---------- */
window.setTab=function(t){
  app.classList.toggle('m-home',t==='home');
  $$('#tabs button').forEach(b=>{const on=b.dataset.t===t;b.classList.toggle('on',on);b.setAttribute('aria-selected',on)});
  const sp=$('#hsub');if(sp)sp.textContent=t==='home'?'House of Quality Steel Tubes\u2122':'online';
  if(t==='home')heroPlay();else{heroStop();closeProd();if(window.revealOpts)revealOpts();requestAnimationFrame(()=>{if(typeof down==='function')down()})}
};
window.openChat=function(){closeProd();setTab('chat');if(!window.__hi){window.__hi=1;go('hi',false,'\uD83D\uDC4B Hi')}};
$$('#tabs button').forEach(b=>b.onclick=()=>setTab(b.dataset.t));

/* ---------- menu scroll ---------- */
window.homeGo=function(id){closeProd();if(id==='top'){home.scrollTo({top:0,behavior:'smooth'});return}
  const el=$('#s-'+id);if(!el)return;const nav=null;
  home.scrollTo({top:el.getBoundingClientRect().top-home.getBoundingClientRect().top+home.scrollTop-(nav?nav.offsetHeight:0),behavior:'smooth'})};

/* ---------- banner slider ---------- */
const slides=$$('#s-top .hs'),dots=$('#hdots');let hi=0,timer=null;
slides.forEach((_,i)=>{const b=document.createElement('button');b.type='button';b.setAttribute('aria-label','Slide '+(i+1));b.onclick=()=>{heroShow(i);heroPlay()};dots.appendChild(b)});
function heroShow(i){hi=(i+slides.length)%slides.length;slides.forEach((s,k)=>s.classList.toggle('on',k===hi));$$('button',dots).forEach((d,k)=>d.classList.toggle('on',k===hi))}
function heroStop(){clearInterval(timer);timer=null}
function heroPlay(){heroStop();if(matchMedia('(prefers-reduced-motion:reduce)').matches)return;timer=setInterval(()=>heroShow(hi+1),5000)}
window.heroGo=d=>{heroShow(hi+d);heroPlay()};
heroShow(0);
const hero=$('#s-top');let sx=null;
hero.addEventListener('touchstart',e=>{sx=e.touches[0].clientX;heroStop()},{passive:true});
hero.addEventListener('touchend',e=>{if(sx!=null){const dx=e.changedTouches[0].clientX-sx;if(Math.abs(dx)>40)heroShow(hi+(dx<0?1:-1));sx=null}heroPlay()});
document.addEventListener('visibilitychange',()=>{if(document.hidden)heroStop();else if(app.classList.contains('m-home'))heroPlay()});

/* ---------- products: cards (image + title + MORE INFO) -> details popup ---------- */
const PRODUCTS=[
 {n:'GI Pipe',sub:'Hot Dipped Galvanized Pipe',img:'p-gi.jpg',tag:'IS 1239 / IS 3589',
  d:'GI Pipe (Hot Dip Galvanized Pipe): steel pipes coated with a layer of zinc through the hot-dip process to prevent corrosion. These pipes offer high strength, durability, and resistance to rust, making them ideal for construction, water, gas, and industrial applications in both indoor and outdoor environments.',
  spec:[['Size','15NB \u2013 500NB (21.70 mm OD \u2013 508.00 mm OD)'],['Thickness','2.00 mm \u2013 12.70 mm'],['Class','Light / Medium / Heavy'],['Length','4.00 \u2013 12.00 metre'],
        ['Indian Standard','Water, gas, sewage, fire: IS 1239 (Part 1 \u2013 2004) / IS 3589 \u2013 Fe330 / Fe410'],['','Mechanical, structural (CHS) & general engineering: IS 1161 \u2013 YST210, YST240, YST310, YST355 / IS 3601'],['American Standard','ASTM A53 / 1993'],['British Standard','BS 1387 / 1985']],
  apps:['Water Supply','Agriculture & Irrigation','Construction & Structural Use','Fencing & Railing','Firefighting Lines','Oil, Gas & Industrial Pipelines','Electrical Conduits']},
 {n:'MS Pipe',sub:'Black Pipe / ERW Pipe',img:'p-ms.jpg',tag:'IS 1239 / IS 1161 / IS 3589',
  d:'Manufactured from high-quality mild steel under the supervision of skilled engineers, these pipes are available in various sizes and lengths. Known for their strength, durability, and smooth finish, MS Black Pipes are widely used for water, gas, and fuel transportation, construction, and diverse industrial applications.',
  spec:[['Size','15NB \u2013 600NB (21.70 mm OD \u2013 610.00 mm OD)'],['Thickness','1.00 mm \u2013 16.00 mm'],['Class','Light / Medium / Heavy'],['Length','4.00 \u2013 12.00 metre'],['Grade','IS 1239, IS 3589 Fe330\u2013Fe410, IS 1161 YST210 / YST240 / YST310 / YST355, IS 3601, IS 9295']],
  feat:['Hold superior corrosion resistance strength','Can be installed indoors as well as outdoors','Longer working life','Economical in operation','Uniform design','Available in various length, thickness and size'],
  apps:['Liquid Transmission','Conveyor Idlers','Structural','Fire Protection','Mechanical & General Engg.','Fencing','Electrical Conduit','Fabrication','Electric Poles','Water & Sewage','Water Wells']},
 {n:'Large Diameter Pipes',sub:'ERW / H-SAW / L-SAW',img:'p-largedia.jpg',tag:'IS 3589 / API 5L',
  d:'Manufactured as per IS 3589:2001, these steel pipes are used for water and sewage applications. They come in ERW (Electric Resistance Welded), H-SAW (Helically Submerged Arc Welded \u2013 Spiral), and L-SAW (Longitudinal Submerged Arc Welded) forms. Widely used in collieries for water extraction, thermal power plants, transport systems, industrial pipelines, and agriculture & irrigation.',
  spec:[['MS ERW Pipe','168.30 mm \u2013 610.00 mm OD (6\u201d \u2013 24\u201d NB) | 4.00 \u2013 16.00 mm | 4.00 \u2013 12.00 m'],['H-SAW / L-SAW','457.00 mm \u2013 3048.00 mm OD (18\u201d \u2013 120\u201d NB) | 5.00 \u2013 16.00 mm | 6.00 \u2013 12.00 m'],['Standard','IS 3589 Fe330 or Fe410, API 5L Gr up to X80, ASTM A252, ASTM A139, IS 5504']],
  coat:['3LPE Coating','Fusion Bond Epoxy','External Coal Tar Tape Coating','External Cement Mortar Lining','Internal Liquid Epoxy Coating','Internal Cement Mortar Lining','3 Layer PE Coating'],
  apps:['Water Mains (Domestic & Industrial)','Industrial Water Lines, Plant Piping','Agriculture & Irrigation','Oil Pipe Lines','Oil Refinery & Crude Oil Piping','Cross Country Pipe Line','Gas Supply']},
 {n:'Hollow Sections',sub:'Square (SHS) / Rectangle (RHS) / Circular (CHS)',img:'p-hollow.jpg',tag:'IS 4923 / IS 1161',
  d:'SHS: made from high-grade steel as per international standards, with excellent tensile strength, rust resistance and long service life. RHS: valued for strength, durability, precise dimensions and manufacturing accuracy. CHS: precisely designed using prime-grade steel for superior rigidity, corrosion resistance, high impact strength and better weldability.',
  spec:[['CHS','21.70 mm OD \u2013 610.00 mm OD | 1.20 \u2013 16.00 mm | 4.00 \u2013 12.00 m | IS 1161 / IS 3589 | YST210 / YST240 / YST310 / YST355 & Fe330 / Fe410'],['SHS','12 \u00d7 12 mm \u2013 600 \u00d7 600 mm | 1.20 \u2013 25.00 mm | 4.00 \u2013 12.00 m | IS 4923 | YST210 / YST240 / YST310 / YST355'],['RHS','26 \u00d7 13 mm \u2013 600 \u00d7 550 mm | 1.20 \u2013 25.00 mm | 4.00 \u2013 12.00 m | IS 4923 | YST210 / YST240 / YST310 / YST355'],['Hot-dipped GI','All sections are also available in hot dip galvanized form depending on your requirement & quantity.']],
  apps:['Machinery Manufacturing','Transmission Tower Plants','Automotive Industry','Construction Industry','Furniture','Heavy Machine Equipment','Agricultural Equipment','Earth Moving Equipment','Solar Panel & Systems','Electric Poles']},
 {n:'High Grade YST310 / YST355',sub:'IS 4923 & IS 1161 \u2013 SHS / RHS / CHS',img:'p-highgrade.jpg',tag:'Exclusive High Quality',
  d:'YST310 or YST355 high strength steel hollow sections (CHS/SHS/RHS) are manufactured using best-grade raw materials (HR coils) from a world-class hot strip mill. Yield strength of 355 MPa and UTS of 490 MPa give a better strength-to-weight ratio, helping save up to 40% steel compared to conventional angles or channels and up to 20% compared to local steel hollow sections.',
  spec:[['Grades','YST240 / YST310 / YST355 (IS 4923 & IS 1161)'],['Yield strength','355 MPa'],['UTS','490 MPa'],['Steel savings','Up to 40% vs angles / channels, up to 20% vs local hollow sections']],
  feat:['Architectural: smooth profile, high quality surface finish, best suited for exposed steel, easy to bend, clutter-free fabrication','Structural: better use of material, lighter weight of structural system, high torsional rigidity, long unsupported lengths for columns and beams','Fabrication & maintenance: lower fabrication and erection cost, no dust accumulation unlike open sections']},
 {n:'Seamless Pipe',sub:'Carbon Seamless Pipes',img:'p-seamless.jpg',tag:'ASTM A106 Gr B / A53',
  d:'A seamless tube has no welding seam, so it has uniform structure and strength all over the pipe body. Seamless steel pipe has better pressure capacity and strength than ERW welded pipe, and is widely used in high pressure equipment, thermal boiler industries and corrosive atmospheres.',
  spec:[['Size','21.70 mm OD \u2013 610 mm OD'],['Thickness','SCH 20 / 30 / STD / 40 / XS / 60 / 80 / 100 / 120 / 140 / 160 / XXS'],['Grade','ASTM A106 Gr B / ASTM A53 (other grades offered on requirement)'],['Length','5.00 \u2013 7.00 metre']],
  apps:['Oil & Gas Refinery','Petrochemicals','Hydro Carbon Process','Chemical & Fertilizer Industries','Automotive','General Engineering','Bearing','Boilers & Heat Exchanger','Mechanical & Structural Application']},
 {n:'Pre-Galvanized Tube (GP Pipe)',sub:'GP Pipe \u2013 Round / Square / Rectangle',img:'p-gp.jpg',tag:'60 / 90 / 120 GSM',
  d:'Pre-Galvanised Tubes (GP Tubes) are made from high-quality MS galvanized sheets pre-coated with zinc, ensuring durability, stability, and long-term resistance to atmospheric and corrosive conditions. The zinc coating strengthens the metal and prevents rust, with a uniform coating that withstands mechanical stress without damage.',
  spec:[['Round tube (CHS)','21.30 mm OD \u2013 76.30 mm OD | 0.80 \u2013 3.00 mm | 4.00 \u2013 6.00 m | IS 3601'],['Square (SHS)','15 \u00d7 15 mm \u2013 100 \u00d7 100 mm | 0.80 \u2013 3.00 mm | 4.00 \u2013 6.00 m | IS 4923'],['Rectangle (RHS)','40 \u00d7 20 mm \u2013 100 \u00d7 50 mm | 0.80 \u2013 3.00 mm | 4.00 \u2013 6.00 m | IS 4923'],['Zinc coating','60 / 90 / 120 GSM']],
  apps:['Gates & Grills','Electrical Conduits','Advertisement Hoardings','Scaffolding','Fence Framework','Cabling & Ducting','Automotive Industries (Bus Body)','Green House Structures']}];

window.PRODUCTS=PRODUCTS;
$('#pgrid').innerHTML=PRODUCTS.map((p,i)=>'<div class="pc"><img loading="lazy" src="/static/home/'+p.img+'" alt="'+H(p.n)+'"><h3>'+H(p.n)+'</h3><button type="button" class="h-btn l" onclick="openProd('+i+')">More Info</button></div>').join('');
function prodHtml(p){
 const list=(t,a)=>a?'<h4>'+t+'</h4><ul>'+a.map(x=>'<li>'+H(x)+'</li>').join('')+'</ul>':'',chips=(t,a)=>a?'<h4>'+t+'</h4><div class="h-chips">'+a.map(x=>'<span>'+H(x)+'</span>').join('')+'</div>':'';
 return '<div class="h-pp"><div class="im"><img src="/static/home/'+p.img+'" alt="'+H(p.n)+'"><span>'+H(p.tag)+'</span></div><div class="bd"><h3>'+H(p.n)+'</h3><div class="sb">'+H(p.sub)+'</div><p class="ds">'+H(p.d)+'</p>'
  +'<h4>Size Range &amp; Specifications</h4><table>'+p.spec.map(r=>'<tr><td>'+H(r[0])+'</td><td>'+H(r[1])+'</td></tr>').join('')+'</table>'
  +list('Features & Advantages',p.feat)+chips('Pipe Coating Available',p.coat)+chips('Applications',p.apps)
  +'<div class="ac"><button class="h-btn o" onclick="openChat()">Enquire About This</button><a class="h-btn l" href="/static/home/Shreeji_SteelTubes_Catalogue.pdf" target="_blank" rel="noopener">Catalogue PDF</a></div></div></div>'}
window.openProd=i=>{$('#ppanel').innerHTML=prodHtml(PRODUCTS[i]);const m=$('#pm');m.hidden=false;m.scrollTop=0};
window.closeProd=()=>{const m=$('#pm');if(m)m.hidden=true};
$('#pm').addEventListener('click',e=>{if(e.target.id==='pm')closeProd()});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeProd()});

/* ---------- brands ---------- */
const BR=[['tata-structura','Tata Structura'],['tata-pipes','Tata Pipes'],['msl','Maharashtra Seamless Limited'],['jindal-star','Jindal Star'],['jindal-panther','Jindal Panther'],['hitech-saw','Hi-Tech SAW'],['hitech-steel-pipes','Hi-Tech Steel Pipes'],['narmada','Narmada'],['rama','Rama'],['khanna','Khanna'],['asian','Asian'],['srj','SRJ']];
$('#brands').innerHTML=BR.map(b=>'<div><img loading="lazy" src="/static/home/logos/'+b[0]+'.png" alt="'+H(b[1])+'"></div>').join('');
if(app.classList.contains('m-home'))heroPlay();
})();
