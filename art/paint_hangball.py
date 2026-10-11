# Paints the Hangball Mk.II texture atlas (1024x1024) from the stock Eyeball body texture.
# Regions (u0, v0, u1, v1), v up; must match build_hangball.py.
# Usage: python3 paint_hangball.py <folder with missiles1_b.png>
import math, random, sys
from PIL import Image, ImageDraw, ImageFont

ART = sys.argv[1] if len(sys.argv) > 1 else '.'
S = 1024
random.seed(7)

base = Image.open(f'{ART}/missiles1_b.png').convert('RGB')
# Stock body mid-section lives at u .67-.909, v .001-.267; this strip has no lettering.
grunge = base.crop((343, 375, 368, 512))

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
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def fill_grunge(rect, tiles_x, darken=1.0):
    x0, y0, x1, y1 = rect
    w = (x1 - x0) // tiles_x
    for i in range(tiles_x):
        tile = grunge.transpose(Image.FLIP_LEFT_RIGHT) if i % 2 else grunge
        tile = tile.resize((w, y1 - y0), Image.BILINEAR)
        if darken != 1.0:
            tile = tile.point(lambda p: int(p * darken))
        albedo.paste(tile, (x0 + i * w, y0))


def rivet(d, x, y, r=3, col=(95, 95, 95)):
    d.ellipse((x - r, y - r, x + r, y + r), fill=(25, 25, 25))
    d.ellipse((x - r + 1, y - r + 1, x + r - 1, y + r - 1), fill=col)


def camera_pod(x, y, r):
    # bezel ring, dark lens with blue tint, glint
    draw.ellipse((x - r - 4, y - r - 4, x + r + 4, y + r + 4), fill=(22, 22, 22))
    draw.ellipse((x - r - 2, y - r - 2, x + r + 2, y + r + 2), fill=(120, 122, 124))
    draw.ellipse((x - r, y - r, x + r, y + r), fill=(18, 26, 34))
    for k in range(r, 0, -1):
        t = k / r
        c = (int(18 + 30 * (1 - t)), int(30 + 50 * (1 - t)), int(42 + 70 * (1 - t)))
        draw.ellipse((x - k, y - k, x + k, y + k), fill=c)
    draw.ellipse((x - r * 0.35, y - r * 0.35, x + r * 0.35, y + r * 0.35), fill=(8, 10, 14))
    draw.ellipse((x - r * 0.55, y - r * 0.65, x - r * 0.15, y - r * 0.3), fill=(200, 220, 235))
    for ang in (45, 135, 225, 315):
        a = math.radians(ang)
        rivet(draw, x + (r + 7) * math.cos(a), y + (r + 7) * math.sin(a), 2)
    mdraw.ellipse((x - r - 2, y - r - 2, x + r + 2, y + r + 2), fill=(180, 180, 180, 150))
    mdraw.ellipse((x - r, y - r, x + r, y + r), fill=(0, 0, 0, 245))


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

# ---- bands: v=0 rear .. v=1 front: yellow stripe, then a body-metal ring up to the dome
x0, y0, x1, y1 = box(BAND)
h = y1 - y0
yb = y0 + int(h * 0.42)
fill_grunge((x0, y0, x1, yb), 4)
draw.line((x0, yb - 2, x1, yb - 2), fill=(20, 20, 20), width=3)   # seam where the stripe meets the ring
draw.rectangle((x0, yb, x1, y1), fill=(222, 175, 30))
for i in range(400):
    xx, yy = random.randint(x0, x1), random.randint(yb, y1)
    draw.point((xx, yy), fill=(90, 90, 90))
mdraw.rectangle((x0, yb, x1, y1), fill=(0, 0, 0, 90))

# ---- wire: plain steel
x0, y0, x1, y1 = box(WIRE)
draw.rectangle((x0, y0, x1, y1), fill=(150, 152, 155))
mdraw.rectangle((x0, y0, x1, y1), fill=(220, 220, 220, 160))

albedo.save(f'{ART}/hangball_b.png')
metal.save(f'{ART}/hangball_m.png')
Image.new('RGBA', (S, S), (128, 128, 255, 255)).save(f'{ART}/hangball_n.png')
Image.new('RGBA', (S, S), (255, 255, 255, 255)).save(f'{ART}/hangball_ao.png')
Image.new('RGBA', (S, S), (0, 0, 0, 255)).save(f'{ART}/hangball_c.png')
print('painted')
