import * as THREE from 'three';
import {OrbitControls} from '/vendor/OrbitControls.js';
let catalogPromise,dispose=()=>{},generation=0;
const catalog=()=>catalogPromise??=fetch('/api/visuals').then(r=>r.json());
async function picture(url){if(!url)return null;const i=new Image();i.src=url;try{await i.decode();return i}catch{return null}}
async function mount(slot,preview=false){
 dispose();const gen=++generation,host=document.querySelector('.character-figure');if(!host)return;
 host.innerHTML='<p>Loading client appearance…</p>';
 try{
 const data=await catalog();if(gen!==generation)return;
 const options=data.profiles.filter(p=>p.model),profile=options.find(p=>p.id===slot.appearance)||options.find(p=>p.id==='1-1');
 host.innerHTML='<label>Client appearance<select aria-label="Client appearance"></select></label><div class="model-viewport"></div><small class="model-status">Loading client textures… First extraction can take a minute.</small><small>Client standing pose and armor textures. Equipment shares the character skeleton; animations and some client shaders are not yet supported. Appearance does not change combat stats.</small>';
 const select=host.querySelector('select');for(const p of options){const o=new Option(p.name,p.id);select.add(o)}select.value=profile.id;
 select.onchange=()=>{slot.appearance=select.value;if(!preview)window.save?.();mount(slot,preview)};
 if(!preview)for(const b of document.querySelectorAll('[data-gear]')){const id=slot.gear?.[b.dataset.gear]?.catalog_id,v=data.displays[data.items[id]];if(v?.icon){const im=document.createElement('img');im.src=v.icon;im.alt='';b.querySelector('.gear-icon').replaceChildren(im)}}
 const meshData=await fetch(profile.model).then(r=>r.json());if(gen!==generation)return;
 const canvas=document.createElement('canvas');canvas.width=canvas.height=512;const ctx=canvas.getContext('2d');
 const base=await picture(profile.textures['0']?.[0]);if(!base)throw Error('Base skin texture unavailable');canvas.width=base.width;canvas.height=base.height;ctx.drawImage(base,0,0);
 const regions={armupper:[0,0,128,64],armlower:[0,64,128,64],hand:[0,128,128,32],torsoupper:[128,0,128,64],torsolower:[128,64,128,32],legupper:[128,96,128,64],leglower:[128,160,128,64],foot:[128,224,128,32]};
 async function layer(url,rect){const im=await picture(url);if(!im)return;if(im.width===canvas.width&&im.height===canvas.height)ctx.drawImage(im,0,0);else ctx.drawImage(im,...rect.map((x,i)=>x*(i%2?canvas.height:canvas.width)/256))}
 await layer(profile.textures['1']?.[0],[0,192,128,64]);await layer(profile.textures['1']?.[1],[0,160,128,32]);await layer(profile.textures['4']?.[0],[128,96,128,64]);await layer(profile.textures['4']?.[1],[128,0,128,64]);await layer(profile.textures['3']?.[1],[0,192,128,64]);await layer(profile.textures['3']?.[2],[0,160,128,32]);
 for(const key of ['shirt','legs','feet','chest','tabard','wrists','hands','waist']){const item=slot.gear?.[key],v=data.displays[data.items[item?.catalog_id]];for(const c of v?.components||[])await layer(c[profile.sex?'female':'male'],regions[c.region])}
 const visual=key=>data.displays[data.items[slot.gear?.[key]?.catalog_id]];
 const requested=[];const head=visual('head')?.attachments?.head?.[profile.id];if(head)requested.push({ref:head,point:11});
 for(const [i,ref] of (visual('shoulders')?.attachments?.shoulders||[]).entries())if(ref)requested.push({ref,point:6-i});
 for(const [key,point] of [['main_hand',1],['off_hand',slot.gear?.off_hand?.kind==='shield'?0:2],['ranged',12]]){const ref=visual(key)?.attachments?.[key];if(ref)requested.push({ref,point})}
 let missingModels=0;
 const attachments=(await Promise.all(requested.map(async a=>{try{if(!meshData.attachments?.[a.point])throw Error('Missing attachment point');const r=await fetch('/api/item-model?id='+a.ref.model);if(!r.ok)throw Error('Model unavailable');const model=await r.json(),images=await Promise.all(model.groups.map(g=>picture(g.texture||a.ref.texture)));return {...a,model,images}}catch{missingModels++;return null}}))).filter(Boolean);
 const capeImage=await picture(visual('back')?.cape_texture);
 const hairImage=await picture(profile.textures['3']?.[0]);
 if(gen!==generation)return;
 const viewport=host.querySelector('.model-viewport'),renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));viewport.append(renderer.domElement);
 const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(35,1,.01,100),controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.minDistance=1;controls.maxDistance=12;
 scene.add(new THREE.HemisphereLight(0xffffff,0x59667d,2));const light=new THREE.DirectionalLight(0xffffff,2.5);light.position.set(3,5,4);scene.add(light);
 const texture=new THREE.CanvasTexture(canvas);texture.flipY=false;texture.colorSpace=THREE.SRGBColorSpace;
 const hairTexture=hairImage?new THREE.Texture(hairImage):null;if(hairTexture){hairTexture.flipY=false;hairTexture.colorSpace=THREE.SRGBColorSpace;hairTexture.needsUpdate=true}
 const hairMaterial=new THREE.MeshStandardMaterial({map:hairTexture||texture,side:THREE.DoubleSide,alphaTest:.5,roughness:.85});
 const capeTexture=capeImage?new THREE.Texture(capeImage):null;if(capeTexture){capeTexture.flipY=false;capeTexture.colorSpace=THREE.SRGBColorSpace;capeTexture.needsUpdate=true}
 const capeMaterial=new THREE.MeshStandardMaterial({map:capeTexture,side:THREE.DoubleSide,alphaTest:.5,roughness:.85});
 const material=new THREE.MeshStandardMaterial({map:texture,side:THREE.DoubleSide,roughness:.85});
 const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(meshData.positions,3));geometry.setAttribute('normal',new THREE.Float32BufferAttribute(meshData.normals,3));geometry.setAttribute('uv',new THREE.Float32BufferAttribute(meshData.uv,2));
 const ids=new Set(meshData.groups.map(g=>g.id)),groups=new Map([[4,401],[5,501],[7,702],[8,801],[12,1201],[13,1301],[20,ids.has(2001)?2001:2002]]);
 for(const [key,family,offset] of [['hands',4,0],['feet',5,0],['chest',8,0],['legs',13,0],['chest',13,2]]){const v=data.displays[data.items[slot.gear?.[key]?.catalog_id]],n=v?.geosets?.[offset];if(n&&ids.has(family*100+1+n))groups.set(family,family*100+1+n)}

 if(capeImage)groups.set(15,1501+(visual('back')?.geosets?.[0]||1));
 const masks=attachments.some(a=>a.point===11)?(visual('head')?.helmet_visibility?.[profile.sex]||[]):[];
 const hidden=index=>Boolean((masks[index]||0)&(1<<profile.race));
 const selected=new Set([0,hidden(0)?0:profile.hair_geoset,...(profile.facial_geosets||[]).filter(id=>!hidden(Math.floor(id/100))),...groups.values()]);
 if(hidden(4))selected.delete(groups.get(7));
 const indices=[];for(const g of meshData.groups)if(selected.has(g.id)){const start=indices.length;indices.push(...meshData.indices.slice(g.start,g.start+g.count));geometry.addGroup(start,g.count,g.texture_type===6?1:g.texture_type===2?2:0)}geometry.setIndex(indices);

 const mesh=new THREE.Mesh(geometry,[material,hairMaterial,capeMaterial]);mesh.rotation.x=-Math.PI/2;scene.add(mesh);
 const itemResources=[];
 for(const a of attachments){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(a.model.positions,3));g.setAttribute('normal',new THREE.Float32BufferAttribute(a.model.normals,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(a.model.uv,2));g.setIndex(a.model.indices);
 const mats=a.model.groups.map((group,i)=>{let t=null;if(a.images[i]){t=new THREE.Texture(a.images[i]);t.flipY=false;t.colorSpace=THREE.SRGBColorSpace;t.needsUpdate=true;itemResources.push(t)}const mat=new THREE.MeshStandardMaterial({map:t,side:THREE.DoubleSide,alphaTest:.5,roughness:.75});itemResources.push(mat);g.addGroup(group.start,group.count,i);return mat});
 const attached=new THREE.Mesh(g,mats);attached.matrixAutoUpdate=false;attached.matrix.fromArray(meshData.attachment_matrices[a.point]);mesh.add(attached);itemResources.push(g)}
 const box=new THREE.Box3().setFromObject(mesh),center=box.getCenter(new THREE.Vector3()),height=box.max.y-box.min.y;controls.target.copy(center);camera.position.set(center.x+height*2,center.y+height*.1,center.z+height*.6);controls.update();
 const resize=new ResizeObserver(()=>{const w=viewport.clientWidth,h=viewport.clientHeight;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix()});resize.observe(viewport);
 renderer.setAnimationLoop(()=>{controls.update();renderer.render(scene,camera)});
 dispose=()=>{resize.disconnect();renderer.setAnimationLoop(null);controls.dispose();geometry.dispose();for(const r of itemResources)r.dispose();capeMaterial.dispose();capeTexture?.dispose();material.dispose();hairMaterial.dispose();hairTexture?.dispose();texture.dispose();renderer.dispose();renderer.forceContextLoss()};
 host.querySelector('.model-status').textContent=(preview?'Set appearance preview · gear unchanged':'Client mesh loaded')+` · ${attachments.length} item models loaded${missingModels?' · '+missingModels+' unavailable':''} · drag to orbit · scroll to zoom`;
 }catch(e){if(gen===generation)host.textContent='Appearance unavailable: '+e.message}
}
window.CombatAppearance={mount};window.dispatchEvent(new Event('appearance-ready'));
