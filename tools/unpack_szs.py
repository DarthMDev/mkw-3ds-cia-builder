#!/usr/bin/env python3
"""Unpack local Yaz0/U8 archives with strict bounds and safe paths."""
import argparse,io,struct
from pathlib import Path
try:
    from gclib.yaz0_yay0 import Yaz0
    def decompress_yaz0(b):
        return Yaz0.decompress(io.BytesIO(b)).getvalue()
except ImportError:
    def decompress_yaz0(b):
        if b[:4] != b'Yaz0': return b
        size = struct.unpack_from('>I', b, 4)[0]
        out = bytearray()
        i = 16
        while len(out) < size:
            code = b[i]; i += 1
            for k in range(8):
                if len(out) >= size: break
                if code & (0x80 >> k):
                    out.append(b[i]); i += 1
                else:
                    b1, b2 = b[i], b[i + 1]; i += 2
                    dist = ((b1 & 15) << 8 | b2) + 1
                    n = b1 >> 4
                    if n == 0: n = b[i] + 0x12; i += 1
                    else: n += 2
                    start = len(out) - dist
                    for j in range(n): out.append(out[start + j])
        return bytes(out)

def unpack(source,output):
 b=source.read_bytes()
 if b[:4]==b'Yaz0':b=decompress_yaz0(b)
 if b[:4]!=b'U\xaa8-':raise ValueError('not a U8 archive')
 root=struct.unpack_from('>I',b,4)[0];count=struct.unpack_from('>I',b,root+8)[0];strings=root+count*12
 stack=[(Path(),count)];output.mkdir(parents=True,exist_ok=True)
 for i in range(1,count):
  while i>=stack[-1][1]:stack.pop()
  info,offset,size=struct.unpack_from('>III',b,root+i*12);start=strings+(info&0xffffff);name=b[start:b.index(0,start)].decode()
  if '/' in name or '\\' in name or name == '..' or (name == '.' and not info>>24):raise ValueError('unsafe archive path')
  relative=stack[-1][0]/name;target=output/relative
  if info>>24:stack.append((relative,size));target.mkdir(exist_ok=True,parents=True)
  else:
   if offset+size>len(b):raise ValueError('truncated archive')
   target.parent.mkdir(exist_ok=True,parents=True);target.write_bytes(b[offset:offset+size])
 print(source,'->',output,count-1,'entries')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();unpack(a.source,a.output)
