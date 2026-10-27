"""Bounded ear clipping of source polygon boundaries, with area checks."""

import math

from .brush_math import cross, dot


def triangulate(points, normal):
    if not 3 <= len(points) <= 256 or len(normal) != 3 or not all(math.isfinite(v) for p in points for v in p):
        raise ValueError("invalid polygon coordinates")
    if not all(math.isfinite(v) for v in normal) or dot(normal,normal) == 0:
        raise ValueError("invalid polygon normal")
    axis = max(range(3), key=lambda i: abs(normal[i]))
    axes = [i for i in range(3) if i != axis]
    projected = [(p[axes[0]],p[axes[1]]) for p in points]
    extent = max(max(p[i] for p in projected)-min(p[i] for p in projected) for i in range(2))
    epsilon = max(1.0,extent*extent) * 1e-12

    def orient(a,b,c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

    remaining = []
    for i,p in enumerate(projected):
        if not remaining or p != projected[remaining[-1]]:
            remaining.append(i)
    if len(remaining)>1 and projected[remaining[0]]==projected[remaining[-1]]:
        remaining.pop()
    # Legacy BSP can contain collinear, backtracking zero-area spurs. Keep the
    # original boundary in the caller's data; canonicalize its projected footprint.
    changed=True
    while changed and len(remaining)>3:
        changed=False
        for j,b in enumerate(remaining):
            a,c=remaining[j-1],remaining[(j+1)%len(remaining)]
            pa,pb,pc=projected[a],projected[b],projected[c]
            ab=(pb[0]-pa[0],pb[1]-pa[1]);bc=(pc[0]-pb[0],pc[1]-pb[1])
            if abs(orient(pa,pb,pc))<=epsilon and dot(ab,bc)<0:
                remaining.pop(j);changed=True;break
    for j,a in enumerate(remaining):
        b=remaining[(j+1)%len(remaining)]
        for k in range(j+2,len(remaining)):
            c,d=remaining[k],remaining[(k+1)%len(remaining)]
            if a==d:continue
            if (orient(projected[a],projected[b],projected[c])*orient(projected[a],projected[b],projected[d]) < -epsilon**2 and
                    orient(projected[c],projected[d],projected[a])*orient(projected[c],projected[d],projected[b]) < -epsilon**2):
                raise ValueError("self-intersecting polygon boundary")
    area = sum(projected[a][0]*projected[b][1]-projected[b][0]*projected[a][1]
               for a,b in zip(remaining,remaining[1:]+remaining[:1])) / 2
    if abs(area) <= epsilon:
        raise ValueError("polygon has no stable projected area")
    sign = 1 if area>0 else -1
    triangles = []
    while len(remaining)>3:
        found = False
        for j,b in enumerate(remaining):
            a,c = remaining[j-1],remaining[(j+1)%len(remaining)]
            pa,pb,pc = projected[a],projected[b],projected[c]
            turn = sign*orient(pa,pb,pc)
            if turn <= epsilon:
                continue
            inside = any(k not in (a,b,c) and
                         min(sign*orient(pa,pb,projected[k]),sign*orient(pb,pc,projected[k]),
                             sign*orient(pc,pa,projected[k])) >= -epsilon for k in remaining)
            if inside:
                continue
            if len(remaining)==4:
                tail=[k for k in remaining if k!=b]
                if abs(orient(*(projected[k] for k in tail)))<=epsilon:
                    continue
            triangles.append((a,b,c));remaining.pop(j);found=True;break
        if not found:
            raise ValueError("polygon is self-intersecting or cannot be triangulated safely")
    if len(remaining)==3 and abs(orient(*(projected[k] for k in remaining)))>epsilon:
        triangles.append(tuple(remaining))
    triangle_area = sum(abs(orient(*(projected[k] for k in triangle)))/2 for triangle in triangles)
    if abs(triangle_area-abs(area)) > epsilon*max(10,len(points)):
        raise ValueError("triangulation did not preserve projected area")
    oriented = []
    for a,b,c in triangles:
        ab=tuple(y-x for x,y in zip(points[a],points[b],strict=True))
        ac=tuple(y-x for x,y in zip(points[a],points[c],strict=True))
        alignment=dot(cross(ab,ac),normal)
        if alignment == 0:
            raise ValueError("triangle is degenerate in source space")
        oriented.append((a,b,c) if alignment>0 else (a,c,b))
    return tuple(oriented)
