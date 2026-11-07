"""Prepare source-preserving canvases, edit masks and facial animation prompts."""
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'work/repair-v5/idle-stable-v1'
OUT = ROOT / 'output/imagegen/repair-v5/idle-stable-v1'
SOURCE = ROOT / 'work/repair-v5/references/idle-cutout.png'
if (RUN / 'generation-plan.json').exists():
    raise SystemExit('Existing stable idle plan retained. Use a new version directory to prepare another run.')
RUN.mkdir(parents=True, exist_ok=True)
(RUN / 'prompts').mkdir(exist_ok=True)
(OUT / 'raw').mkdir(parents=True, exist_ok=True)
source = Image.open(SOURCE).convert('RGBA')
# One shared transform from the user's original drawing; never fit individual frames.
scale = 2
offset = ((1024 - source.width * scale) // 2, 980 - source.height * scale)
canonical = Image.new('RGBA', (1024, 1024))
canonical.alpha_composite(source.resize((source.width * scale, source.height * scale), Image.Resampling.LANCZOS), offset)
canonical.save(RUN / 'canonical.png')
edit_target = Image.new('RGBA', canonical.size, '#00ff00')
edit_target.alpha_composite(canonical)
edit_target.save(RUN / 'edit-target.png')
editable = Image.new('L', source.size, 0)
draw = ImageDraw.Draw(editable)
# Preserve hair, cheeks, facial outline and all other original artwork.
draw.polygon([(127,153),(147,151),(168,173),(181,187),(177,208),(145,212),(125,196),(118,175)], fill=255)
draw.polygon([(208,148),(222,136),(244,134),(265,145),(272,167),(265,190),(246,204),(220,204),(209,187)], fill=255)
draw.ellipse((175,211,226,239), fill=255)
editable = editable.resize((source.width * scale, source.height * scale), Image.Resampling.LANCZOS)
weights = Image.new('L', (1024, 1024), 0)
weights.paste(editable, offset)
# Blur only within the original edit region, leaving every exterior pixel locked.
blurred = weights.filter(ImageFilter.GaussianBlur(2.0))
from PIL import ImageChops
weights = ImageChops.multiply(blurred, weights)
mask = Image.new('RGBA', canonical.size, 'white')
mask.putalpha(ImageChops.invert(weights))
mask.save(RUN / 'face-mask.png')
overlay = edit_target.copy()
highlight = Image.new('RGBA', canonical.size, (255,0,120,0))
highlight.putalpha(weights.point(lambda a: int(a * .45)))
overlay.alpha_composite(highlight)
overlay.save(RUN / 'mask-overlay.png')
expressions = [
    'Both eyes fully open, original relaxed blue-eyed gaze; tiny closed gentle smile. Neutral entry pose.',
    'Both upper eyelids lowered by about 10 percent; blue irises remain visible, same gentle closed smile.',
    'Beginning a natural blink: both eyelids half closed; lower eyelids and all eye corners stay anchored.',
    'Blink at its deepest point: both eyes fully closed as soft curved eyelid lines; tiny contented closed smile.',
    'Eyes just reopening: both eyelids about 35 percent open; blue irises partially visible, soft relaxed smile.',
    'Eyes reopened about 85 percent; tiny warm change at the mouth corners, no open talking mouth.',
    'Both eyes fully open again; subtly attentive gaze, original mouth width and relaxed closed smile.',
    'Both eyes fully open, returning to the exact initial relaxed gaze and gentle smile for a quiet loop.',
]
durations = [480,160,120,100,120,160,240,520]
common = (
    'Edit this single original artwork for a quiet desktop-pet idle animation. The attached image is the exact edit target, not a style reference. '
    'Change ONLY the eyes/eyelids and tiny closed mouth expression in the editable face regions. '
    'Preserve the exact camera, canvas, pixel scale, hair, face shape, head position, hair clip, ribbons, skin palette, costume, clasped hands, skirt, original short crossed legs, sock openings and feet. '
    'Do not redraw, resize or move any body part. Both feet, knees and skirt must stay in exactly the same positions. '
    'Preserve the original chibi drawing, not the longer-legged regenerated version. Keep the same blue irises and black ink line style. '
    'Uniform green #00FF00 backdrop. One character only, same framing and complete feet, no text, guides, shadow, outline, props or effects. '
    'Current facial expression: '
)
jobs=[]
for index, expr in enumerate(expressions,1):
    prompt = RUN / 'prompts' / f'frame-{index:02d}.md'
    prompt.write_text(common + expr + '\n', encoding='utf-8')
    jobs.append({'index':index, 'prompt_file':str(prompt), 'output_file':str(OUT/'raw'/f'frame-{index:02d}.png'), 'expression':expr, 'duration_ms':durations[index-1], 'status':'pending'})
plan={'name':'Ootori Sayumi pet','purpose':'source-preserving eight-frame idle repair','source':str(SOURCE),'canonical':str(RUN/'canonical.png'),'edit_target':str(RUN/'edit-target.png'),'mask':str(RUN/'face-mask.png'),'mask_semantics':'alpha0 editable, alpha255 protected; generated face RGB composited locally into canonical alpha','shared_transform':{'scale':scale,'offset':list(offset),'canvas':[1024,1024]},'durations_ms':durations,'sway_px':0,'lower_body_fixed_from_y':700,'packaging_eligible':False,'generation_mode':'official imagegen CLI gpt-image-2 masked edit; each frame is separately model-generated','jobs':jobs}
(RUN/'generation-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'run':str(RUN),'out':str(OUT),'offset':offset,'frames':len(jobs),'canonical_bbox':canonical.getbbox()},ensure_ascii=False))
