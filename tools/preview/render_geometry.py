"""Optional CPU preview using already available Pillow/NumPy; no UE editor calls."""

import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np
from PIL import Image,ImageDraw,ImageFont

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from ue1_converter.brush_math import rotation_matrix


def unit(value):
    value=np.asarray(value,dtype=float)
    return value/np.linalg.norm(value)


def render(geometry,*,sample=None,width=1200,height=900):
    bounds=geometry["diagnostics"]["bounds"]
    if sample:
        chosen=next(s for s in geometry["zone_samples"] if s["actor"]==sample)
        camera=np.asarray(chosen["position"],dtype=float)
        import re
        values=dict((k,int(v)) for k,v in re.findall(r"(Pitch|Yaw|Roll)=(-?\d+)",chosen["rotation"] or ""))
        rotation=np.asarray(rotation_matrix(tuple(values.get(k,0) for k in ("Pitch","Yaw","Roll"))))
        forward,right,up=rotation[:,0],rotation[:,1],rotation[:,2]
        title=f"Source camera point: {sample}"
    else:
        center=(np.asarray(bounds["minimum"])+np.asarray(bounds["maximum"]))/2
        camera=center+np.array([8450,-12025,8125])
        forward=unit(center-camera);right=unit(np.cross([0,0,1],forward));up=unit(np.cross(forward,right))
        title="Castle intro / original evaluated BSP"
    axes=np.stack((right,up,forward))
    points=np.asarray(geometry["points"])
    transformed=(points-camera)@axes.T
    color=np.zeros((height,width,3),dtype=np.uint8);color[:]=[21,28,39]
    depth=np.zeros((height,width),dtype=float)
    focal=width/(2*math.tan(math.radians(75)/2))
    light=unit([-0.4,-0.65,1.0])

    def raster(tri,shade):
        screen=np.column_stack((width/2+focal*tri[:,0]/tri[:,2],height/2-focal*tri[:,1]/tri[:,2]))
        x0,y0=screen[0];x1,y1=screen[1];x2,y2=screen[2]
        denominator=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
        if abs(denominator)<1e-10:return
        left=max(0,int(math.floor(screen[:,0].min())));right_edge=min(width-1,int(math.ceil(screen[:,0].max())))
        top=max(78,int(math.floor(screen[:,1].min())));bottom=min(height-1,int(math.ceil(screen[:,1].max())))
        if left>right_edge or top>bottom:return
        ys,xs=np.mgrid[top:bottom+1,left:right_edge+1];xs=xs+0.5;ys=ys+0.5
        a=((y1-y2)*(xs-x2)+(x2-x1)*(ys-y2))/denominator
        b=((y2-y0)*(xs-x2)+(x0-x2)*(ys-y2))/denominator;c=1-a-b
        z=a/tri[0,2]+b/tri[1,2]+c/tri[2,2]
        patch=depth[top:bottom+1,left:right_edge+1]
        mask=(a>=-1e-9)&(b>=-1e-9)&(c>=-1e-9)&(z>patch)
        patch[mask]=z[mask];color[top:bottom+1,left:right_edge+1][mask]=shade

    for face in geometry["faces"]:
        if face["role"] not in {"world","mover"}:continue
        surface=geometry["surfaces"][face["surface"]]
        normal=unit(surface["normal"])
        centroid=points[face["points"]].mean(axis=0)
        if np.dot(normal,camera-centroid)<=0 and not surface["flags"]&256:continue
        intensity=0.30+0.70*max(0,float(np.dot(normal,light)))
        base=np.array([160,166,174]) if face["role"]=="world" else np.array([143,169,184])
        shade=np.asarray(base*intensity,dtype=np.uint8)
        for indices in face["triangles"]:
            polygon=list(transformed[indices])
            clipped=[]
            for a,b in zip(polygon,polygon[1:]+polygon[:1]):
                ia,ib=a[2]>=1,b[2]>=1
                if ia:clipped.append(a)
                if ia!=ib:clipped.append(a+(b-a)*((1-a[2])/(b[2]-a[2])))
            for j in range(1,len(clipped)-1):raster(np.array([clipped[0],clipped[j],clipped[j+1]]),shade)
    image=Image.fromarray(color)
    draw=ImageDraw.Draw(image)
    draw.rectangle((0,0,width,77),fill=(13,19,29))
    draw.text((24,17),title,fill=(235,240,245),font=ImageFont.load_default(size=23))
    draw.text((24,49),"Geometry preview | no original textures, lighting, collision or UE5 rendering",fill=(157,174,191),font=ImageFont.load_default(size=15))
    return image


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geometry",type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--sample",help="source camera actor name; default is overview")
    args=parser.parse_args()
    if args.output.exists():parser.error("choose a new preview output path")
    geometry=json.loads(args.geometry.read_text())
    render(geometry,sample=args.sample).save(args.output)


if __name__=="__main__":main()
