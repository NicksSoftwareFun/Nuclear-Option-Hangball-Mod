# Paints the Hangball Mk.II texture atlas (1024x1024). Everything is generated here; no game textures are used.
# Regions (u0, v0, u1, v1), v up; must match build_hangball.py.
# Usage: python3 paint_hangball.py <output folder>
import math, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ART = sys.argv[1] if len(sys.argv) > 1 else '.'
S = 1024
random.seed(7)

rng = np.random.default_rng(7)


def noise(w, h, cell, cell_y=None):
    """Smooth value noise in -1..1 with features about `cell` pixels across (`cell_y` tall, for streaks)."""
    cy = cell_y or cell
    g = rng.uniform(-1, 1, (h // cy + 3, w // cell + 3)).astype(np.float32)
    img = Image.fromarray(((g + 1) * 127.5).astype(np.uint8)).resize(((w // cell + 3) * cell, (h // cy + 3) * cy), Image.BICUBIC)
    return np.asarray(img, np.float32)[cy:cy + h, cell:cell + w] / 127.5 - 1


def gunmetal(w, h, level=52):
    """Matte mid-grey missile paint in the house style of the game's standard missile bodies: very even tone,
    faint mottling, and sparse small light-grey scuffs where the paint is worn."""
    a = level + 2.5 * noise(w, h, 48) + 1.5 * noise(w, h, 8) + 1.2 * rng.normal(0, 1, (h, w))
    img = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert('RGB')
    d = ImageDraw.Draw(img)
    for _ in range(w * h // 1400):                    # scuffs: little flecks and short scrapes
        x, y = random.uniform(0, w), random.uniform(0, h)
        c = random.randint(level + 18, level + 48)
        if random.random() < 0.6:
            r = random.uniform(0.6, 1.8)
            d.ellipse((x - r, y - r * random.uniform(0.5, 1.5), x + r, y + r), fill=(c, c, c))
        else:
            ang, ln = random.uniform(0, math.pi), random.uniform(3, 10)
            d.line((x, y, x + ln * math.cos(ang), y + ln * math.sin(ang)), fill=(c, c, c), width=1)
    return img.filter(ImageFilter.GaussianBlur(0.5))

albedo = Image.new('RGB', (S, S), (40, 40, 40))
metal = Image.new('RGBA', (S, S), (20, 20, 20, 110))   # R metallic, A smoothness
draw = ImageDraw.Draw(albedo)
mdraw = ImageDraw.Draw(metal)


def box(region):
    u0, v0, u1, v1 = region
    return (int(u0 * S), int((1 - v1) * S), int(u1 * S), int((1 - v0) * S))


PACK = (0.0, 0.5, 0.5, 1.0)
COLLAR = (0.5, 0.75, 0.75, 1.0)
DOME = (0.75, 0.75, 1.0, 1.0)
BAND = (0.5, 0.5, 0.75, 0.75)
WIRE = (0.75, 0.5, 1.0, 0.75)
BODY = (0.0, 0.0, 0.5, 0.5)
FIN = (0.5, 0.0, 0.75, 0.5)
TAIL = (0.75, 0.0, 1.0, 0.5)
TUBE_V = [(-0.700, 0.0), (-0.325, 0.42), (0.255, 0.44), (0.700, 1.0)]   # body tube z -> v, as in build_hangball.py
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def fill_grunge(rect, tiles_x=1, darken=1.0):
    x0, y0, x1, y1 = rect
    albedo.paste(gunmetal(x1 - x0, y1 - y0, int(55 * darken)), (x0, y0))


def rivet(d, x, y, r=3, col=(95, 95, 95)):
    d.ellipse((x - r, y - r, x + r, y + r), fill=(25, 25, 25))
    d.ellipse((x - r + 1, y - r + 1, x + r - 1, y + r - 1), fill=col)


# ---- pack: 8 faces side by side (u), length along v (v=1 is the front of the pack)
x0, y0, x1, y1 = box(PACK)
fill_grunge((x0, y0, x1, y1), 8)
fw = (x1 - x0) // 8
for k in range(8):
    fx = x0 + k * fw
    draw.line((fx, y0, fx, y1), fill=(14, 14, 14), width=3)
    draw.line((fx + 3, y0, fx + 3, y1), fill=(72, 72, 72), width=1)
    for yy in range(y0 + 16, y1, 40):
        rivet(draw, fx + 9, yy)
        rivet(draw, fx + fw - 9, yy)
    for yy in (y0 + 120, y1 - 120):
        draw.line((fx, yy, fx + fw, yy), fill=(18, 18, 18), width=2)
    cx = fx + fw // 2
    if k in (0, 2):   # upper side flats, just above the antenna channels (0 = +X side, 2 = -X side)
        # HANG along the length; text baseline runs along v
        font = ImageFont.truetype(FONT, 46)
        txt = Image.new('RGBA', (300, 60), (0, 0, 0, 0))
        ImageDraw.Draw(txt).text((150, 30), 'HANG', font=font, fill=(205, 205, 200, 255), anchor='mm')
        txt = txt.rotate(-90 if k == 0 else 90, expand=True)  # reads upright, nose to the right on the +X side
        albedo.paste(txt, (cx - txt.width // 2, (y0 + y1) // 2 - txt.height // 2), txt)
    if k in (3, 7):   # side flats carry the recessed antenna channel in their middle quarter
        gx0, gx1 = fx + int(fw * 0.37), fx + int(fw * 0.63)
        draw.rectangle((gx0, y0, gx1, y1), fill=(24, 24, 24))
        draw.line((gx0, y0, gx0, y1), fill=(8, 8, 8), width=2)
        draw.line((gx1, y0, gx1, y1), fill=(8, 8, 8), width=2)
        mdraw.rectangle((gx0, y0, gx1, y1), fill=(40, 40, 40, 70))

# ---- collars: darker grunge, bolt heads at the octagon corners
x0, y0, x1, y1 = box(COLLAR)
fill_grunge((x0, y0, x1, y1), 8, 0.75)
fw = (x1 - x0) // 8
for k in range(8):
    fx = x0 + k * fw
    draw.line((fx, y0, fx, y1), fill=(10, 10, 10), width=2)
    for yy in (y0 + 40, y1 - 40):
        rivet(draw, fx + fw // 2, yy, 6, (110, 110, 110))
draw.line((x0, y0 + 4, x1, y0 + 4), fill=(80, 80, 80), width=3)
draw.line((x0, y1 - 4, x1, y1 - 4), fill=(80, 80, 80), width=3)

# ---- sensor dome: azimuthal-equidistant map (radius = angle from the nose axis), centre = nose tip.
# Same metal as the body, with plain violet lens apertures spread over it like the stock Eyeball.
x0, y0, x1, y1 = box(DOME)
cx, cy, R = (x0 + x1) // 2, (y0 + y1) // 2, (x1 - x0) // 2
fill_grunge((x0, y0, x1, y1), 4)
PX_PER_RAD = R / (math.pi / 2)


def aperture(theta, phi, alpha=0.20):
    """Round lens of angular radius alpha centred theta (rad from the nose axis), phi (around)."""
    px, py = cx + PX_PER_RAD * theta * math.cos(phi), cy - PX_PER_RAD * theta * math.sin(phi)
    rad, tan = (math.cos(phi), -math.sin(phi)), (math.sin(phi), math.cos(phi))
    stretch = theta / math.sin(theta) if theta > 1e-6 else 1.0
    def ell(scale):
        a_r = PX_PER_RAD * alpha * scale
        a_t = a_r * stretch
        return [(px + a_r * math.cos(t) * rad[0] + a_t * math.sin(t) * tan[0],
                 py + a_r * math.cos(t) * rad[1] + a_t * math.sin(t) * tan[1]) for t in [i * math.pi / 24 for i in range(48)]]
    draw.polygon(ell(1.22), fill=(16, 16, 17))        # recessed bezel
    draw.polygon(ell(1.0), fill=(84, 48, 92))         # plain violet coated window, like the stock seeker windows
    mdraw.polygon(ell(1.22), fill=(30, 30, 30, 120))
    mdraw.polygon(ell(1.0), fill=(10, 10, 10, 235))


aperture(0.0, 0.0, 0.22)
for i in range(6):
    aperture(math.radians(42), math.radians(30 + 60 * i), 0.19)
for i in range(6):
    aperture(math.radians(74), math.radians(60 * i), 0.17)

# ---- bands: v=0 rear .. v=1 front: yellow stripe, then a black ring up to the dome
x0, y0, x1, y1 = box(BAND)
h = y1 - y0
yb = y0 + int(h * 0.42)
draw.rectangle((x0, y0, x1, yb), fill=(22, 22, 22))   # black ring up to the dome
draw.rectangle((x0, yb, x1, y1), fill=(226, 178, 58))
for i in range(50):
    xx, yy = random.randint(x0, x1), random.randint(yb, y1)
    r = random.uniform(0.6, 1.4)
    draw.ellipse((xx - r, yy - r, xx + r, yy + r), fill=(158, 125, 40))
mdraw.rectangle((x0, yb, x1, y1), fill=(0, 0, 0, 90))

# ---- body tube: u around (0 = +X side, counter-clockwise looking from the nose's back), v along z
x0, y0, x1, y1 = box(BODY)
fill_grunge((x0, y0, x1, y1))
bw, bh = x1 - x0, y1 - y0


def zy(z):
    v = 1.0
    for (za, va), (zb, vb) in zip(TUBE_V, TUBE_V[1:]):
        if z <= zb + 1e-9:
            v = va + (vb - va) * (z - za) / (zb - za)
            break
    return y1 - int(v * bh)




# thin section joints, no rivets
for z in (-0.47, 0.56):
    yy = zy(z)
    draw.line((x0, yy, x1, yy), fill=(30, 30, 30), width=2)


def band(za, zb, col, wear=40):
    ya, yb = zy(za), zy(zb)
    draw.rectangle((x0, ya, x1, yb), fill=col)
    for i in range(wear):   # worn spots showing the grey underneath
        xx, yy = random.randint(x0, x1), random.randint(ya, yb)
        r = random.uniform(0.6, 1.4)
        draw.ellipse((xx - r, yy - r, xx + r, yy + r), fill=tuple(int(c * 0.7) for c in col))
    mdraw.rectangle((x0, ya, x1, yb), fill=(0, 0, 0, 100))


band(-0.400, -0.425, (205, 100, 22))          # orange band behind the pack, ahead of the tail fins
band(0.300, 0.282, (178, 180, 182), 60)       # light-grey ring at the forward joint
# a lifting-lug plate on top (u = 0.25)
cxp = x0 + bw // 4
for z in (-0.53, 0.42):
    draw.rectangle((cxp - 10, zy(z) - 14, cxp + 10, zy(z) + 14), fill=(40, 40, 40))

# ---- fins: u = span (0 root .. 1 tip), v = chord; slightly lighter metal, a darker root fillet and edge wear
x0, y0, x1, y1 = box(FIN)
albedo.paste(gunmetal(x1 - x0, y1 - y0, 78), (x0, y0))
fw, fh = x1 - x0, y1 - y0
draw.rectangle((x0, y0, x0 + 10, y1), fill=(52, 52, 52))
for fx in (0.35, 0.7):
    draw.line((x0 + int(fw * fx), y0, x0 + int(fw * fx), y1), fill=(58, 58, 58), width=2)
for fy in (0.3, 0.65):
    draw.line((x0, y0 + int(fh * fy), x1, y0 + int(fh * fy)), fill=(58, 58, 58), width=2)
mdraw.rectangle((x0, y0, x1, y1), fill=(90, 90, 90, 120))

# ---- tail: boat tail into the nozzle, v = 1 at the tube joint down to the nozzle throat; heat-darkened at the end
x0, y0, x1, y1 = box(TAIL)
t = gunmetal(x1 - x0, y1 - y0, 52)
fade = np.linspace(1.0, 0.35, y1 - y0)[:, None, None] ** 1.5
albedo.paste(Image.fromarray((np.asarray(t, np.float32) * fade).astype(np.uint8)), (x0, y0))
th = y1 - y0
draw.line((x0, y0 + int(th * 0.30), x1, y0 + int(th * 0.30)), fill=(16, 16, 16), width=2)
mdraw.rectangle((x0, y0 + int(th * 0.4), x1, y1), fill=(60, 60, 60, 60))

# ---- wire: plain steel
x0, y0, x1, y1 = box(WIRE)
draw.rectangle((x0, y0, x1, y1), fill=(150, 152, 155))
mdraw.rectangle((x0, y0, x1, y1), fill=(220, 220, 220, 160))

# ---- light weathering over the paint: faint grime, a few scratches and very shallow dents. Strength per region; the wire and the dome lenses get little or none.
A = np.asarray(albedo, np.float32).copy()
M = np.asarray(metal, np.float32).copy()
H = np.zeros((S, S), np.float32)          # height for the normal map, 0 = painted surface
WEATHER = [(PACK, 0.25), (COLLAR, 0.2), (BODY, 0.25), (FIN, 0.15), (TAIL, 0.4), (BAND, 0.1), (DOME, 0.1)]
for region, k in WEATHER:
    x0, y0, x1, y1 = box(region)
    w, h = x1 - x0, y1 - y0
    a, m, hh = A[y0:y1, x0:x1], M[y0:y1, x0:x1], H[y0:y1, x0:x1]
    # grime: dark patches and streaks running along v (image y is along the length on every region but the dome)
    grime = np.clip(0.55 * noise(w, h, 40) + 0.3 * noise(w, h, 10) + 0.45 * noise(w, h, 6, 70) - 0.05, 0, 1)
    a *= (1 - 0.45 * k * grime)[..., None]
    m[..., 3] -= 60 * k * grime                     # grime is rougher
    # scratches: thin bright lines through the paint
    scr = Image.new('L', (w, h), 0)
    sd = ImageDraw.Draw(scr)
    for _ in range(int(w * h / 5000 * k)):
        x, y = random.uniform(0, w), random.uniform(0, h)
        ang = random.gauss(math.pi / 2, 0.5) if random.random() < 0.6 else random.uniform(0, math.pi)
        ln = random.uniform(6, 60)
        sd.line((x, y, x + ln * math.cos(ang), y + ln * math.sin(ang)), fill=random.randint(60, 160), width=1)
    sv = np.asarray(scr, np.float32) / 255
    a += (sv * 30)[..., None]
    m[..., 0] += sv * 60
    hh -= sv * 0.25
    # dents: broad, shallow
    hh += 0.3 * k * noise(w, h, 28)
A = np.clip(A, 0, 255)
M = np.clip(M, 0, 255)
albedo = Image.fromarray(A.astype(np.uint8))
metal = Image.fromarray(M.astype(np.uint8), 'RGBA')

# normal map (OpenGL / Unity convention, green = +v) from the height field plus the painted detail
# (seams, rivets and bolt heads read as raised or sunk from their brightness against the local average)
lum = A.mean(axis=2)
blur = np.asarray(Image.fromarray(lum.astype(np.uint8)).filter(ImageFilter.GaussianBlur(5)), np.float32)
H += (lum - blur) / 90.0
H = np.asarray(Image.fromarray(((H + 8) * 16).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7)), np.float32) / 16
dx = (np.roll(H, -1, 1) - np.roll(H, 1, 1)) * 0.9
dy = (np.roll(H, -1, 0) - np.roll(H, 1, 0)) * 0.9
n = np.stack([-dx, dy, np.ones_like(H)], -1)
n /= np.linalg.norm(n, axis=-1, keepdims=True)
wx0, wy0, wx1, wy1 = box(WIRE)
n[wy0:wy1, wx0:wx1] = (0, 0, 1)
normal = Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8))

albedo.save(f'{ART}/hangball_b.png')
metal.save(f'{ART}/hangball_m.png')
normal.save(f'{ART}/hangball_n.png')
Image.new('RGBA', (S, S), (255, 255, 255, 255)).save(f'{ART}/hangball_ao.png')
Image.new('RGBA', (S, S), (0, 0, 0, 255)).save(f'{ART}/hangball_c.png')
print('painted')
