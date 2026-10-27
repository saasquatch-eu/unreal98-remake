"""Bounded, read-only v61 P8 texture decoding; no native game code is executed."""
from dataclasses import dataclass
import hashlib
import struct

from .package61 import Package61,PackageError,Reader


def properties(package,export):
    if export.flags&0x02000000:raise PackageError('texture state frames are unsupported')
    reader=Reader(package.data,export.offset,export.offset+export.size)
    result={}
    while True:
        name=package.name(reader.compact())
        if name=='None':return result,reader
        info=reader.unpack('B');kind=info&15;code=(info>>4)&7
        if kind==0:raise PackageError('invalid texture property type')
        structure=package.name(reader.compact()) if kind==10 else None
        size=(1,2,4,12,16)[code] if code<5 else reader.unpack(('B','H','I')[code-5])
        index=0
        if info&128 and kind!=3:
            index=reader.unpack('B')
            if index>=128:raise PackageError('large texture property array indices are unsupported')
        if (name,index) in result:raise PackageError('duplicate texture property tag')
        raw=reader.take(0 if kind==3 else size)
        result[name,index]=(kind,structure,raw,bool(info&128) if kind==3 else None)


def scalar(props,name,kind,default=None):
    value=props.get((name,0))
    if value is None:return default
    if value[0]!=kind:raise PackageError('unexpected property type: '+name)
    raw=value[2]
    if kind==3:return value[3]
    r=Reader(raw)
    value=r.compact() if kind==5 else r.unpack('B' if kind==1 else 'i')
    if r.offset!=r.end:raise PackageError('unconsumed scalar property bytes')
    return value


@dataclass(frozen=True)
class Texture:
    width:int
    height:int
    pixels:bytes
    palette:bytes
    metadata:dict

    def rgba(self,masked=False):
        # Legacy palette alpha is not opacity. P8 masking uses palette index zero.
        colors=[self.palette[i*4:i*4+3]+bytes([0 if masked and i==0 else 255]) for i in range(256)]
        return b''.join(colors[i] for i in self.pixels)


def decode_texture(package,path,package_name):
    matches=[e for e in package.exports if package.object_path(e.index+1,package_name)==path and package.class_name(e)=='Texture']
    if len(matches)!=1:raise PackageError('expected one texture export: '+path)
    export=matches[0]
    if package.class_name(export)!='Texture':raise PackageError('only static Texture objects are decoded')
    props,r=properties(package,export)
    if scalar(props,'Format',1,0)!=0:raise PackageError('only P8 textures are supported')
    width,height=scalar(props,'USize',2),scalar(props,'VSize',2)
    if any(not isinstance(v,int) or not 1<=v<=4096 or v&(v-1) for v in (width,height)):
        raise PackageError('invalid texture dimensions')
    for name,dim in (('UBits',width),('VBits',height)):
        if scalar(props,name,1,dim.bit_length()-1)!=dim.bit_length()-1:raise PackageError('texture bit size mismatch')
    palette_ref=scalar(props,'Palette',5)
    if not isinstance(palette_ref,int) or not 0<palette_ref<=len(package.exports):raise PackageError('palette must be local')
    palette_export=package.exports[palette_ref-1]
    if package.class_name(palette_export)!='Palette':raise PackageError('palette reference has wrong class')
    _,pr=properties(package,palette_export)
    if pr.compact()!=256:raise PackageError('P8 palette must have 256 colors')
    palette=pr.take(1024)
    if pr.offset!=pr.end:raise PackageError('unexplained palette bytes')
    count=r.compact()
    if not 1<=count<=max(width,height).bit_length():raise PackageError('invalid mip count')
    mips=[];top=None
    for level in range(count):
        size=r.compact();offset=r.offset
        data=r.take(size);w,h,ub,vb=r.unpack('iiBB')
        expected=(max(1,width>>level),max(1,height>>level))
        if (w,h)!=expected or size!=w*h or (ub,vb)!=(w.bit_length()-1,h.bit_length()-1):
            raise PackageError('mip dimensions or data size mismatch')
        if level==0:top=data
        mips.append(dict(width=w,height=h,offset=offset,size=size,sha256=hashlib.sha256(data).hexdigest()))
    if r.offset!=r.end:raise PackageError('unexplained texture native bytes')
    metadata=dict(path=path,export_index=export.index,offset=export.offset,size=export.size,
                  export_sha256=hashlib.sha256(package.data[export.offset:export.offset+export.size]).hexdigest(),
                  palette=package.object_path(palette_ref,package_name),palette_sha256=hashlib.sha256(palette).hexdigest(),
                  format='P8',width=width,height=height,mips=mips,
                  anim_next=package.object_path(scalar(props,'AnimNext',5,0),package_name))
    return Texture(width,height,top,palette,metadata)


def tga_bytes(texture,masked=False):
    rgba=texture.rgba(masked)
    bgra=bytearray(rgba)
    bgra[0::4],bgra[2::4]=rgba[2::4],rgba[0::4]
    # Uncompressed BGRA, top-left origin; input row order is not flipped.
    return struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,texture.width,texture.height,32,0x28)+bgra
