# Renders preview images of the Hangball Mk.II model.
# Usage: blender -b -P render_previews.py -- <ART folder with hangball.blend and textures> <output folder>
import bpy, math, sys
from mathutils import Vector
ART, OUT = sys.argv[sys.argv.index('--') + 1:][:2] if '--' in sys.argv else sys.argv[1:3]
bpy.ops.wm.open_mainfile(filepath=f'{ART}/hangball.blend')
sc = bpy.context.scene
TEX = {'Missiles1': 'missiles1', 'Weapons5': 'weapons5', 'Hangball': 'hangball'}
for name, t in TEX.items():
    m = bpy.data.materials[name]; m.use_nodes = True
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    img = nt.nodes.new('ShaderNodeTexImage'); img.image = bpy.data.images.load(f'{ART}/{t}_b.png')
    nt.links.new(img.outputs['Color'], b.inputs['Base Color'])
    try:
        mi = nt.nodes.new('ShaderNodeTexImage'); mi.image = bpy.data.images.load(f'{ART}/{t}_m.png'); mi.image.colorspace_settings.name = 'Non-Color'
        sep = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(mi.outputs['Color'], sep.inputs[0])
        nt.links.new(sep.outputs[0], b.inputs['Metallic'])
        inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1
        nt.links.new(mi.outputs['Alpha'], inv.inputs[1]); nt.links.new(inv.outputs[0], b.inputs['Roughness'])
    except Exception as e: print(e)
# group everything under a pivot so we can orient: file z = nose
piv = bpy.data.objects.new('Pivot', None); sc.collection.objects.link(piv)
for ob in list(sc.objects):
    if ob.type == 'MESH': ob.parent = piv
piv.rotation_euler = (math.radians(90), 0, math.radians(180))
# lighting
w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.55, 0.6, 0.68, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.6
for rot, e in (((50, 0, 40), 4.0), ((-30, 0, 220), 1.5)):
    l = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')); l.data.energy = e
    l.rotation_euler = [math.radians(a) for a in rot]; sc.collection.objects.link(l)
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, -0.35))
g = bpy.data.materials.new('G'); g.use_nodes = True; g.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.08, 0.08, 0.085, 1)
bpy.context.object.data.materials.append(g)
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 50
sc.render.engine = 'CYCLES'; sc.cycles.samples = 48; sc.cycles.device = 'CPU'
sc.render.resolution_x, sc.render.resolution_y = 1400, 800
sc.view_settings.view_transform = 'AgX'
def look(loc, tgt=(0, 0.0, 0)):
    cam.location = loc; d = Vector(tgt) - Vector(loc); cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
ants = [o for o in sc.objects if o.name.startswith('Antenna')]
def deploy(on):
    for a in ants:
        sgn = 1 if a.location.x > 0 else -1
        a.rotation_euler = (0, math.radians(90 * sgn) if on else 0, 0)
shots = [('1_stowed_3q', False, (1.7, 1.9, 0.9)), ('2_deployed_3q', True, (1.9, 1.6, 1.4)),
         ('3_side', False, (2.6, 0, 0.05)), ('3b_other_side', False, (-2.6, 0, 0.05)), ('4_top_deployed', True, (0, -0.02, 3.4)),
         ('5_nose_closeup', False, (0.55, 1.35, 0.3)), ('6_pack_closeup', False, (-0.75, 0.25, 0.35)), ('7_hinge_stowed', False, (0.42, -0.62, 0.16)), ('8_hinge_deployed', True, (0.42, -0.62, 0.16))]
for name, dep, loc in shots:
    deploy(dep)
    tgt = (0, 0.75, 0) if 'nose' in name else ((0, -0.05, 0) if 'pack' in name else ((0.11, -0.28, 0) if 'hinge' in name else (0, 0, 0)))
    look(loc, tgt)
    sc.render.filepath = f'{OUT}/{name}.png'
    bpy.ops.render.render(write_still=True)
print('done')
