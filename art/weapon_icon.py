# Draws the Hangball Mk.II weapon icon: 512x256 side profile, white outline on black, nose to the left,
# in the same style and scale as the game's other weapon icons. Dimensions match build_hangball.py.
# Usage: python3 weapon_icon.py <output png>
import math, sys
from PIL import Image, ImageDraw

OUT = sys.argv[1] if len(sys.argv) > 1 else 'weaponIcon_HangballMkII.png'
SS = 4                      # supersampling
W, H = 512, 256
PX = 232                    # pixels per metre
CX = 256 + 0.0 * PX         # z = 0 sits at the centre
LW = 2 * SS
WHITE, BLACK = (225, 225, 225), (0, 0, 0)

img = Image.new('RGB', (W * SS, H * SS), BLACK)
d = ImageDraw.Draw(img)


def p(z, y):
    return ((CX - z * PX) * SS, (H / 2 - y * PX) * SS)


def poly(pts, fill=BLACK):
    d.polygon([p(z, y) for z, y in pts], fill=fill, outline=WHITE, width=LW)


def line(pts, w=LW):
    d.line([p(z, y) for z, y in pts], fill=WHITE, width=w)


def mirrored(pts):
    return [(z, -y) for z, y in pts]


def fin(stations, r0=0.086):
    """Fin seen flat-on, as the other icons draw them: leading edge, tip, trailing edge."""
    up = [(stations[0][1], r0)] + [(zl, r) for r, zl, _ in stations[1:]] + \
         [(zt, r) for r, _, zt in reversed(stations[1:])] + [(stations[0][2], r0)]
    poly(up)
    poly(mirrored(up))


R = 0.090
# fins behind the body
fin([(0.086, -0.455, -0.766), (0.150, -0.565, -0.766), (0.172, -0.605, -0.718)])
fin([(0.086, -0.340, -0.470), (0.106, -0.440, -0.470)])
fin([(0.086, 0.590, 0.330), (0.138, 0.515, 0.345)])
# tube and tail
poly([(0.70, R), (-0.700, R), (-0.703, 0.094), (-0.742, 0.094), (-0.745, R), (-0.766, 0.084),
      (-0.766, -0.084), (-0.745, -R), (-0.742, -0.094), (-0.703, -0.094), (-0.700, -R), (0.70, -R)])
line([(-0.703, 0.094), (-0.703, -0.094)], SS)
line([(-0.742, 0.094), (-0.742, -0.094)], SS)
# chute pack: octagon with flats up and down (top flat at y = R_PACK * cos 22.5), collars and chamfers
RP, RC = 0.120, 0.128
top_p, top_c = RP * math.cos(math.pi / 8), RC * math.cos(math.pi / 8)
pack = [(0.255, R), (0.225, top_c), (0.190, top_c), (0.190, top_p), (-0.260, top_p), (-0.260, top_c),
        (-0.295, top_c), (-0.325, R)]
poly(pack + mirrored(pack[::-1]))
for z in (0.225, 0.190, -0.260, -0.295):
    line([(z, top_c if z in (0.225, -0.295) else top_p), (z, -(top_c if z in (0.225, -0.295) else top_p))], SS)
# octagon corner edges
for y in (RP * math.sin(math.pi / 8), -RP * math.sin(math.pi / 8)):
    line([(0.190, y), (-0.260, y)], SS)
# antenna channel and the stowed wire along it, hinge at the rear
line([(0.190, 0.012), (-0.260, 0.012)], SS)
line([(0.190, -0.012), (-0.260, -0.012)], SS)
line([(-0.278, 0.0), (0.772, 0.0)], SS + 2)
cz, cy = p(-0.278, 0.0)
d.ellipse((cz - 4 * SS, cy - 4 * SS, cz + 4 * SS, cy + 4 * SS), outline=WHITE, width=SS, fill=BLACK)
# band and sensor dome
line([(0.60, R), (0.60, -R)], SS)
DZ, DR, ST = 0.700, 0.093, 1.10
dome = [(DZ + DR * ST * math.cos(a), DR * math.sin(a)) for a in [math.pi / 2 - i * math.pi / 32 for i in range(33)]]
poly([(0.70, R)] + dome + [(0.70, -R)])
line([(0.70, DR), (0.70, -DR)], SS)
# lens apertures on the visible side of the dome
for th, ph, r in ((math.radians(42), math.radians(30), 0.013), (math.radians(42), math.radians(-30), 0.013),
                  (math.radians(74), math.radians(60), 0.012), (math.radians(74), math.radians(-60), 0.012)):
    z = DZ + DR * ST * math.cos(th)
    y = DR * math.sin(th) * math.sin(ph)
    zz, yy = p(z, y)
    rr = r * PX * SS
    d.ellipse((zz - rr * 0.6, yy - rr, zz + rr * 0.6, yy + rr), outline=WHITE, width=SS)

small = img.resize((W, H), Image.LANCZOS)
out = small.convert('RGBA')
out.putalpha(small.convert('L').point(lambda v: min(255, v * 255 // 225)))   # lines opaque, background clear
out.save(OUT)
print('icon written', OUT)
