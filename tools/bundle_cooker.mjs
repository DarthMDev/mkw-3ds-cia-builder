import * as esbuild from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';
// Keep upstream parsing code intact. Offline cooker never instantiates browser
// renderers/animation players. Retain the real material optimizer as a slice.
await esbuild.build({entryPoints:['tools/export_brres.ts','tools/export_driver.ts','tools/export_star.ts','tools/export_item_box_uv.ts','tools/export_joints.ts','tools/export_blast.ts'],bundle:true,platform:'node',format:'esm',outdir:'build',outExtension:{'.js':'.mjs'},plugins:[{name:'offline-parser',setup(b){
 b.onLoad({filter:/[\\/]rres[\\/]brres\.ts$/},a=>({contents:fs.readFileSync(a.path,'utf8').replace("import { GXTextureMapping } from '../gx/gx_render.js';", `class GXTextureMapping {
 gfxTexture = null; gfxSampler; width = 0; height = 0; lodBias = 0; flipY = false; lateBinding;
 reset() { this.gfxTexture = null; this.gfxSampler = undefined; this.width = 0; this.height = 0; this.lodBias = 0; this.flipY = false; this.lateBinding = undefined; }
 copy(other) { this.gfxTexture = other.gfxTexture; this.gfxSampler = other.gfxSampler; this.width = other.width; this.height = other.height; this.lodBias = other.lodBias; this.flipY = other.flipY; this.lateBinding = other.lateBinding; }
 }`),loader:'ts',resolveDir:path.dirname(a.path)}));
 b.onResolve({filter:/gx_render\.js$/},a=>({path:path.resolve(a.resolveDir,a.path.replace(/\.js$/,'.ts')),namespace:'optimizer'}));
 b.onLoad({filter:/.*/,namespace:'optimizer'},a=>{const s=fs.readFileSync(a.path,'utf8');return {contents:"import * as GX from './gx_enum.js';\nimport type * as GX_Material from './gx_material.js';\n"+s.slice(s.indexOf('function autoOptimizeMaterialHasPostTexMtxBlock'),s.indexOf('\n}',s.indexOf('export function autoOptimizeMaterial('))+2),loader:'ts',resolveDir:path.dirname(a.path)};});
 b.onResolve({filter:/rustlib\.js$/},()=>({path:'unused-browser-rust',namespace:'shim'}));
 b.onLoad({filter:/.*/,namespace:'shim'},()=>({contents:'export const rust = new Proxy({}, {get(){throw new Error("Unexpected browser-only Rust dependency in offline BRRES parsing");}});'}));
}}]});
