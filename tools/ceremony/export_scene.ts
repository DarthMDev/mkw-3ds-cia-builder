// Ceremony camera moves: every SCN0 camera of a BRRES sampled at each 60 Hz
// frame (award 123dai.brres demowin01-03, Lose demolos01). Output: one .scam
// file per SCN0 ("SCAM", version, frame count, then per frame 13 floats:
// position, rotation (degrees), aim, twist, vertical FOV, near, far) and a
// JSON summary on stdout. Rotation-type cameras leave aim zero.
import fs from 'node:fs';
import path from 'node:path';
import * as BRRES from '../../vendor/noclip/src/rres/brres.js';
import ArrayBufferSlice from '../../vendor/noclip/src/ArrayBufferSlice.js';
const [source, outputDir] = process.argv.slice(2);
if (!source || !outputDir) throw new Error('usage: export_scene.mjs <file.brres> <output dir>');
const data = fs.readFileSync(source);
const rres = BRRES.parse(new ArrayBufferSlice(data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength)));
fs.mkdirSync(outputDir, { recursive: true });
const summary: any[] = [];
for (const scene of rres.scn0) {
  if (scene.cameras.length !== 1) throw new Error(`${scene.name}: expected one camera, found ${scene.cameras.length}`);
  const camera = scene.cameras[0];
  const frames = Math.max(1, scene.duration);
  const sample = (track: any, frame: number) => track ? BRRES.sampleFloatAnimationTrack(track, frame) : 0;
  const values = new Float32Array(frames * 13);
  for (let f = 0; f < frames; ++f) {
    const row = [camera.posX, camera.posY, camera.posZ, camera.rotX, camera.rotY, camera.rotZ,
      camera.aimX, camera.aimY, camera.aimZ, camera.twist, camera.perspFovy, camera.near, camera.far].map(t => sample(t, f));
    if (row.some(v => !Number.isFinite(v))) throw new Error(`${scene.name}: non-finite camera value at frame ${f}`);
    values.set(row, f * 13);
  }
  const header = Buffer.alloc(12);
  header.write('SCAM', 0, 'ascii'); header.writeUInt32LE(1, 4); header.writeUInt32LE(frames, 8);
  const file = path.join(outputDir, scene.name + '.scam');
  fs.writeFileSync(file, Buffer.concat([header, Buffer.from(values.buffer)]));
  summary.push({ name: scene.name, frames, cameraType: camera.cameraType, camera: camera.name, file: path.basename(file) });
}
console.log(JSON.stringify(summary));
