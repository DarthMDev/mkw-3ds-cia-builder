// Bundles the ceremony exporters like tools/bundle_cooker.mjs, into build/ceremony/.
// noclip's track sampler is module-private upstream; the bundle exports it.
import * as esbuild from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';
await esbuild.build({entryPoints:['tools/ceremony/export_scene.ts'],bundle:true,platform:'node',format:'esm',outdir:'build/ceremony',outExtension:{'.js':'.mjs'},plugins:[{name:'offline-parser',setup(b){
 b.onLoad({filter:/[\\/]rres[\\/]brres\.ts$/},a=>({contents:fs.readFileSync(a.path,'utf8').replace("import { GXTextureMapping }", "import type { GXTextureMapping }").replace('\nfunction sampleFloatAnimationTrack(','\nexport function sampleFloatAnimationTrack('),loader:'ts',resolveDir:path.dirname(a.path)}));
 b.onResolve({filter:/gx_render\.js$/},a=>({path:path.resolve(a.resolveDir,a.path.replace(/\.js$/,'.ts')),namespace:'optimizer'}));
 b.onLoad({filter:/.*/,namespace:'optimizer'},a=>{const s=fs.readFileSync(a.path,'utf8');return {contents:"import * as GX from './gx_enum.js';\nimport type * as GX_Material from './gx_material.js';\n"+s.slice(s.indexOf('function autoOptimizeMaterialHasPostTexMtxBlock'),s.indexOf('\n}',s.indexOf('export function autoOptimizeMaterial('))+2),loader:'ts',resolveDir:path.dirname(a.path)};});
 b.onResolve({filter:/rustlib\.js$/},()=>({path:'unused-browser-rust',namespace:'shim'}));
 b.onLoad({filter:/.*/,namespace:'shim'},()=>({contents:'export const rust = new Proxy({}, {get(){throw new Error("Unexpected browser-only Rust dependency in offline BRRES parsing");}});'}));
}}]});
