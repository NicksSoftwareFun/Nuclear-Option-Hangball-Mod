# Builds the Hangball Mk.II model in Blender (bpy / Blender 5.2) from the stock Eyeball mesh and the concept art.
# File space = Unity local space with X negated (z = forward/nose, y = up). Units are meters.
# Inputs:  <ART>/agm_scanner1.obj (exported from Unity, X negated)
# Outputs: hangball.blend, hangball_body.obj (materials Missiles1, Weapons5, Hangball),
#          hangball_antenna.obj (origin at hinge, wire along +Z = stowed pointing at the nose)
# Usage:   blender -b -P build_hangball.py -- <ART folder>
import bpy, bmesh, math, sys
from mathutils import Vector, Matrix

ART = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else '.'

R_BODY = 0.090
R_PACK = 0.120          # octagon corner radius
R_COLLAR = 0.128
Z_FRONT_CHAMFER, Z_FRONT_COLLAR, Z_PANEL_FRONT = 0.255, 0.225, 0.190
Z_PANEL_REAR, Z_REAR_COLLAR, Z_REAR_CHAMFER = -0.260, -0.295, -0.325
DOME_CENTER_Z, DOME_R, DOME_STRETCH = 0.700, 0.093, 1.10
BAND_Z0, BAND_Z1, BAND_R = 0.600, 0.700, 0.0915
WIRE_HINGE_Z = -0.278
WIRE_LEN = 1.05         # ~70% of the 1.57 m body
WIRE_OFFSET = 0.103     # stowed distance from the centreline (inside the pack channel)

PACK = (0.0, 0.5, 0.5, 1.0)
COLLAR = (0.5, 0.75, 0.75, 1.0)
DOME = (0.75, 0.75, 1.0, 1.0)
BAND = (0.5, 0.5, 0.75, 0.75)
WIRE = (0.75, 0.5, 1.0, 0.75)

OCT = 8
OCT_ROT = math.pi / 8   # flats face up/down/left/right, like the concept


def remap(region, u, v):
    u0, v0, u1, v1 = region
    return (u0 + (u1 - u0) * u, v0 + (v1 - v0) * v)


def get_mat(name):
    return bpy.data.materials.get(name) or bpy.data.materials.new(name)


def new_obj(name, bm, mats, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for m in mats:
        me.materials.append(get_mat(m))
    return ob


def read_obj(path):
    V, VT, F, mat = [], [], [], None
    for line in open(path):
        p = line.split()
        if not p:
            continue
        if p[0] == 'v':
            V.append(tuple(map(float, p[1:4])))
        elif p[0] == 'vt':
            VT.append(tuple(map(float, p[1:3])))
        elif p[0] == 'usemtl':
            mat = p[1]
        elif p[0] == 'f':
            F.append((mat, [tuple(int(a) - 1 for a in c.split('/')[:2]) for c in p[1:]]))
    return V, VT, F


bpy.ops.wm.read_factory_settings(use_empty=True)

# ---- stock body, original UVs and game materials
V, VT, F = read_obj(f'{ART}/agm_scanner1.obj')
# Flatten the two stock side fairings (z 0.44-0.56, out to r 0.115 on the +/-X sides) onto the body
# skin so the stowed HF wires (x = +/-WIRE_OFFSET) pass clear of them.
FAIR_Z0, FAIR_Z1 = 0.44, 0.56
for i, (x, y, z) in enumerate(V):
    r = math.hypot(x, y)
    if FAIR_Z0 <= z <= FAIR_Z1 and r > R_BODY and abs(y) <= 0.5 * abs(x):
        V[i] = (x * R_BODY / r, y * R_BODY / r, z)
bm = bmesh.new()
uvl = bm.loops.layers.uv.new('UVMap')
verts = [bm.verts.new(v) for v in V]
mat_index = {'Missiles1': 0, 'Weapons5': 1}
for m, face in F:
    try:
        f = bm.faces.new([verts[i] for i, _ in face])
    except ValueError:
        continue
    f.material_index = mat_index[m]
    for loop, (_, t) in zip(f.loops, face):
        loop[uvl].uv = VT[t]
body = new_obj('Body', bm, ['Missiles1', 'Weapons5'], smooth=True)


def ring(bm, r, z, n=OCT, rot=OCT_ROT):
    return [bm.verts.new((r * math.cos(rot + 2 * math.pi * s / n), r * math.sin(rot + 2 * math.pi * s / n), z)) for s in range(n + 1)]


def skin(bm, uvl, ra, rb, region, va, vb, n=OCT):
    """Quads between two rings (ra at front, rb behind). u runs around, v from vb..va."""
    for s in range(n):
        f = bm.faces.new([ra[s], rb[s], rb[s + 1], ra[s + 1]])
        uvs = [(s / n, va), (s / n, vb), ((s + 1) / n, vb), ((s + 1) / n, va)]
        for loop, (u, v) in zip(f.loops, uvs):
            loop[uvl].uv = remap(region, u, v)


# ---- octagonal chute pack with a recessed antenna channel down each side flat (+X and -X)
GROOVE_HALF = 0.012     # channel half-width
GROOVE_FLOOR = 0.092    # channel floor distance from the centreline


def pack_profile(R):
    """Octagon (flats up/down/left/right) with a channel notched into the +X and -X flats.
    Returns [(x, y, u)] closed (first point repeated), u = 0..1 around the octagon as before."""
    ry = R * math.sin(math.pi / 8)
    xf = R * math.cos(math.pi / 8)
    xn = min(GROOVE_FLOOR, xf - 0.001)
    pts = []
    for s in range(8):
        a = OCT_ROT + 2 * math.pi * s / 8
        pts.append((R * math.cos(a), R * math.sin(a), s / 8))
        if s == 3:   # face 3 = -X flat, running from +y to -y
            for (x, y) in ((-xf, GROOVE_HALF), (-xn, GROOVE_HALF), (-xn, -GROOVE_HALF), (-xf, -GROOVE_HALF)):
                pts.append((x, y, (3 + (ry - y) / (2 * ry)) / 8))
        if s == 7:   # face 7 = +X flat, running from -y to +y
            for (x, y) in ((xf, -GROOVE_HALF), (xn, -GROOVE_HALF), (xn, GROOVE_HALF), (xf, GROOVE_HALF)):
                pts.append((x, y, (7 + (y + ry) / (2 * ry)) / 8))
    pts.append((pts[0][0], pts[0][1], 1.0))
    return pts


def loft(bm, uvl, stations, region):
    """stations: [(R, z, v)] front to back; quads between consecutive profiles."""
    rings = [[(bm.verts.new((x, y, z)), u) for x, y, u in pack_profile(R)] + [v] for R, z, v in stations]
    for ra, rb in zip(rings, rings[1:]):
        va, vb = ra[-1], rb[-1]
        for s in range(len(ra) - 2):
            f = bm.faces.new([ra[s][0], rb[s][0], rb[s + 1][0], ra[s + 1][0]])
            uvs = [(ra[s][1], va), (rb[s][1], vb), (rb[s + 1][1], vb), (ra[s + 1][1], va)]
            for loop, (u, v) in zip(f.loops, uvs):
                loop[uvl].uv = remap(region, u, v)


def box(bm, uvl, lo, hi, region_uv):
    res = bmesh.ops.create_cube(bm, size=1.0)
    for v in res['verts']:
        v.co = Vector(((lo[i] + hi[i]) / 2 + v.co[i] * (hi[i] - lo[i]) for i in range(3)))
    for f in {f for v in res['verts'] for f in v.link_faces}:
        for loop in f.loops:
            loop[uvl].uv = region_uv


bm = bmesh.new()
uvl = bm.loops.layers.uv.new('UVMap')
loft(bm, uvl, [(R_BODY, Z_FRONT_CHAMFER, 1.0), (R_COLLAR, Z_FRONT_COLLAR, 0.85), (R_COLLAR, Z_PANEL_FRONT, 0.55)], COLLAR)
loft(bm, uvl, [(R_COLLAR, Z_PANEL_FRONT, 0.55), (R_PACK, Z_PANEL_FRONT, 0.5)], COLLAR)
loft(bm, uvl, [(R_PACK, Z_PANEL_FRONT, 1.0), (R_PACK, Z_PANEL_REAR, 0.0)], PACK)
loft(bm, uvl, [(R_PACK, Z_PANEL_REAR, 0.5), (R_COLLAR, Z_PANEL_REAR, 0.45), (R_COLLAR, Z_REAR_COLLAR, 0.15), (R_BODY, Z_REAR_CHAMFER, 0.0)], COLLAR)
# hinge clevis in the rear end of each channel: two cheeks above and below the antenna barrel, a pin cap on each
steel = remap(WIRE, 0.5, 0.5)
for sx in (1, -1):
    x0, x1 = sorted((sx * GROOVE_FLOOR, sx * (WIRE_OFFSET + 0.011)))
    for sy in (1, -1):
        y0, y1 = sorted((sy * 0.0115, sy * 0.0165))
        box(bm, uvl, (x0, y0, WIRE_HINGE_Z - 0.016), (x1, y1, WIRE_HINGE_Z + 0.016), steel)
        y0, y1 = sorted((sy * 0.0165, sy * 0.0195))
        box(bm, uvl, (sx * WIRE_OFFSET - 0.005, y0, WIRE_HINGE_Z - 0.005), (sx * WIRE_OFFSET + 0.005, y1, WIRE_HINGE_Z + 0.005), steel)
    # front clip that holds the stowed wire at the forward end of the channel
    box(bm, uvl, (min(sx * GROOVE_FLOOR, sx * (WIRE_OFFSET + 0.006)), -0.0115, Z_PANEL_FRONT - 0.012),
        (max(sx * GROOVE_FLOOR, sx * (WIRE_OFFSET + 0.006)), -0.0045, Z_PANEL_FRONT + 0.004), steel)
pack = new_obj('ChutePack', bm, ['Hangball'])

# ---- glass dome over the stock nose, black/yellow band behind it
bm = bmesh.new()
uvl = bm.loops.layers.uv.new('UVMap')
SEG, ROWS = 32, 10
rings = []
for j in range(ROWS + 1):
    a = j / ROWS * math.pi / 2
    r = DOME_R * math.cos(a)
    z = DOME_CENTER_Z + DOME_R * DOME_STRETCH * math.sin(a)
    rings.append(ring(bm, max(r, 1e-5), z, SEG, 0.0))
for j in range(ROWS):
    for s in range(SEG):
        f = bm.faces.new([rings[j][s], rings[j][s + 1], rings[j + 1][s + 1], rings[j + 1][s]])
        for loop in f.loops:
            co = loop.vert.co
            # azimuthal-equidistant map: texture radius grows with the angle from the nose axis,
            # so lenses near the dome's edge are not squashed the way a flat projection squashes them
            rxy = math.hypot(co.x, co.y)
            th = math.asin(min(rxy / DOME_R, 1.0))
            k = 0.5 * th / (math.pi / 2) / rxy if rxy > 1e-6 else 0.0
            loop[uvl].uv = remap(DOME, 0.5 + k * co.x, 0.5 + k * co.y)
rb0 = ring(bm, BAND_R, BAND_Z0, SEG, 0.0)
rb1 = ring(bm, BAND_R, BAND_Z1, SEG, 0.0)
skin(bm, uvl, rb1, rb0, BAND, 1.0, 0.0, SEG)
nose = new_obj('GlassNose', bm, ['Hangball'], smooth=True)

# ---- HF wire antenna: origin at hinge, wire along +Z (stowed pointing at the nose)
# hinge barrel (axis = Y, the fold axis), a thick root sleeve tapering into the wire, small tip ball
bm = bmesh.new()
uvl = bm.loops.layers.uv.new('UVMap')
seg = 10
# barrel
rb0 = ring(bm, 0.0085, 0.0, seg, 0.0)
rb1 = ring(bm, 0.0085, 0.0, seg, 0.0)
for r, y in ((rb0, -0.011), (rb1, 0.011)):
    for v in r:
        v.co = Vector((v.co.x, y, v.co.y))   # rotate the ring into the XZ plane at height y
skin(bm, uvl, rb1, rb0, WIRE, 1.0, 0.0, seg)
for r in (rb0, rb1):
    bm.faces.new(r[:-1])
# sleeve: r 6.5 mm for 7 cm, then taper to the 3.5 mm wire over 4 cm
prof = [(0.0065, 0.0), (0.0065, 0.07), (0.0075, 0.075), (0.0065, 0.08), (0.0035, 0.12), (0.0035, WIRE_LEN), (0.0, WIRE_LEN + 0.002)]
rings_w = [ring(bm, max(r, 1e-4), z, seg, 0.0) for r, z in prof]
for a, b in zip(rings_w[1:], rings_w[:-1]):
    skin(bm, uvl, a, b, WIRE, 1.0, 0.0, seg)
res = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.006)
for v in res['verts']:
    v.co += Vector((0, 0, WIRE_LEN))
for f in {f for v in res['verts'] for f in v.link_faces}:
    for loop in f.loops:
        loop[uvl].uv = remap(WIRE, 0.5, 0.5)
ant = new_obj('Antenna', bm, ['Hangball'], smooth=True)
ant_l = bpy.data.objects.new('Antenna_L', ant.data)
ant_r = bpy.data.objects.new('Antenna_R', ant.data)
for ob, x in ((ant_l, WIRE_OFFSET), (ant_r, -WIRE_OFFSET)):
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (x, 0, WIRE_HINGE_Z)
bpy.data.objects.remove(ant)

bpy.ops.wm.save_as_mainfile(filepath=f'{ART}/hangball.blend')


def write_obj(path, objects, mat_order, at_origin=False):
    out = ['# Hangball Mk.II (file X = -Unity X)']
    vi = 1
    groups = {m: [] for m in mat_order}
    for ob in objects:
        me = ob.data
        me.calc_loop_triangles()
        cn = me.corner_normals
        uv = me.uv_layers.active.data
        mw = Matrix.Identity(4) if at_origin else ob.matrix_world
        nm = mw.to_3x3().inverted().transposed()
        for tri in me.loop_triangles:
            mname = me.materials[tri.material_index].name
            idx = []
            for li in tri.loops:
                co = mw @ me.vertices[me.loops[li].vertex_index].co
                n = (nm @ cn[li].vector).normalized()
                u = uv[li].uv
                out.append(f'v {co.x:.6f} {co.y:.6f} {co.z:.6f}')
                out.append(f'vt {u.x:.6f} {u.y:.6f}')
                out.append(f'vn {n.x:.6f} {n.y:.6f} {n.z:.6f}')
                idx.append(vi)
                vi += 1
            groups[mname].append(idx)
    for m in mat_order:
        out.append(f'usemtl {m}')
        for a, b, c in groups[m]:
            out.append(f'f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}')
    open(path, 'w').write('\n'.join(out) + '\n')


write_obj(f'{ART}/hangball_body.obj', [body, pack, nose], ['Missiles1', 'Weapons5', 'Hangball'])
write_obj(f'{ART}/hangball_antenna.obj', [ant_l], ['Hangball'], at_origin=True)
print('built')
