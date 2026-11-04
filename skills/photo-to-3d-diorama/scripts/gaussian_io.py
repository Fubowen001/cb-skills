"""Read binary little-endian Gaussian PLY by property names, pack SPLAT."""
from pathlib import Path
from common import activate
activate()
import numpy as np
NAMES=['x','y','z']+[f'f_dc_{i}' for i in range(3)]+['opacity']+[f'scale_{i}' for i in range(3)]+[f'rot_{i}' for i in range(4)]
def load_ply(path):
    types={'float':'<f4','float32':'<f4','double':'<f8','uchar':'u1','uint8':'u1','int':'<i4','uint':'<u4','short':'<i2','ushort':'<u2'}
    with Path(path).open('rb') as f:
        if f.readline().strip()!=b'ply':raise ValueError('Not PLY')
        props=[];n=None;vertex=False;fmt=False
        for _ in range(2048):
            line=f.readline()
            if not line:raise ValueError('Truncated PLY header')
            s=line.decode('ascii').strip().split()
            if not s:continue
            if s[0]=='format':fmt=s[1]=='binary_little_endian'
            elif s[0]=='element':
                if n is None and s[1]!='vertex':raise ValueError('Vertex must be first element')
                vertex=s[1]=='vertex'
                if vertex:n=int(s[2])
            elif s[0]=='property' and vertex:
                if s[1] not in types:raise ValueError('Unsupported vertex property')
                props.append((s[2],types[s[1]]))
            elif s[0]=='end_header':break
        else:raise ValueError('Header too large')
        if not fmt or not n or n>10_000_000:raise ValueError('Unsupported PLY format/count')
        if not set(NAMES)<=set(x[0] for x in props):raise ValueError('Missing Gaussian properties')
        dt=np.dtype(props);raw=f.read(n*dt.itemsize)
        if len(raw)!=n*dt.itemsize:raise ValueError('Truncated PLY data')
        data=np.frombuffer(raw,dtype=dt,count=n)
        v=np.column_stack([data[name] for name in NAMES]).astype(np.float32)
    if not np.isfinite(v[:,:6]).all() or not np.isfinite(v[:,7:]).all() or np.isnan(v[:,6]).any():raise ValueError('Nonfinite Gaussian parameter')
    with np.errstate(over='ignore',under='ignore'):sc=np.exp(v[:,7:10])
    if not np.isfinite(sc).all() or (sc<=0).any():raise ValueError('Invalid scale')
    if (np.linalg.norm(v[:,10:14],axis=1)<1e-8).any():raise ValueError('Invalid zero quaternion')
    return v
def pack(path,out):
    v=load_ply(path);n=len(v);a=np.empty((n,32),dtype=np.uint8)
    a[:,:12]=v[:,:3].copy().astype('<f4').view('u1').reshape(n,12)
    a[:,12:24]=np.exp(v[:,7:10]).astype('<f4').view('u1').reshape(n,12)
    a[:,24:27]=np.clip((.5+.28209479177387814*v[:,3:6])*255,0,255).astype('u1')
    a[:,27]=(255/(1+np.exp(-np.clip(v[:,6],-30,30)))).astype('u1')
    q=v[:,10:14];q=q/np.linalg.norm(q,axis=1,keepdims=True)
    a[:,28:]=np.clip(q*127+128,0,255).astype('u1');Path(out).write_bytes(a.tobytes());return n
