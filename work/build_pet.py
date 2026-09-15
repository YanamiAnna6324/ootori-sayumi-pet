from PIL import Image, ImageEnhance, ImageOps
from pathlib import Path
from collections import deque
import json, math
ROOT=Path(r'C:\Users\HP\Documents\Codex\2026-09-14\hatch-pet-c-users-hp-codex')
OUT=ROOT/'outputs'/'ootori_sayumi_pet'; OUT.mkdir(parents=True,exist_ok=True)
SRC=Path(r'C:\Users\HP\Downloads\codex宠物\微信图片_20260914205538_4_47.jpg')
img=Image.open(SRC).convert('RGBA'); px=img.load(); q=deque(); seen=set()
for x in range(img.width): q.extend([(x,0),(x,img.height-1)])
for y in range(img.height): q.extend([(0,y),(img.width-1,y)])
while q:
 x,y=q.popleft()
 if (x,y) in seen or x<0 or y<0 or x>=img.width or y>=img.height: continue
 seen.add((x,y)); r,g,b,a=px[x,y]
 if min(r,g,b)>220 and max(r,g,b)-min(r,g,b)<32:
  px[x,y]=(0,255,0,0); q.extend(((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
box=img.getbbox(); img=img.crop(box)
W,H=192,208
rows=[('idle',6),('running-right',8),('running-left',8),('waving',4),('jumping',5),('failed',8),('waiting',6),('running',6),('review',6),('look-row-9',8),('look-row-10',8)]
def make(row,i):
 scale=.72
 if row=='jumping': scale*=1.04+.012*math.sin(i)
 if row=='waiting': scale*=.96
 if row=='failed': scale*=.98
 w,h=max(1,int(img.width*scale)),max(1,int(img.height*scale)); p=img.resize((w,h),Image.Resampling.LANCZOS)
 if row=='running-left': p=ImageOps.mirror(p)
 if row=='jumping': p=ImageEnhance.Color(p).enhance(1.10)
 if row=='failed': p=ImageEnhance.Contrast(p).enhance(1.08)
 cell=Image.new('RGBA',(W,H),(0,255,0,0)); ox=(W-w)//2+int(2*math.sin(i*math.pi/4)); oy=(H-h)//2-int(2*math.cos(i*math.pi/4)); cell.alpha_composite(p,(ox,oy)); return cell
dec=OUT/'decoded'; dec.mkdir(exist_ok=True)
for row,n in rows:
 st=Image.new('RGBA',(W*8,H),(0,255,0,0))
 for i in range(n): st.alpha_composite(make(row,i),(i*W,0))
 # leave remaining cells transparent per v2 row contract
 st.save(dec/f'{row}.png')
atlas=Image.new('RGBA',(W*8,H*11),(0,255,0,0))
for ri,(row,n) in enumerate(rows): atlas.alpha_composite(Image.open(dec/f'{row}.png'),(0,ri*H))
atlas.save(OUT/'spritesheet-extended.png'); atlas.save(OUT/'spritesheet-extended.webp','WEBP',lossless=True,quality=100); atlas.save(OUT/'contact-sheet-extended.png')
pet={'id':'ootori-sayumi-pet','displayName':'Ootori Sayumi pet','description':'A gentle chibi twin-tail companion with blue eyes, soft encouragement, and playful snack breaks.','spriteVersionNumber':2,'spritesheetPath':'spritesheet-extended.webp'}
(OUT/'pet.json').write_text(json.dumps(pet,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'state-map.json').write_text(json.dumps({'idle':'待机','greeting':'问候/互动回应','happy':'开心','shy':'害羞/期待','surprised':'惊讶/提醒','working':'思考/工作','eating':'进食','sleeping':'睡眠','look-directions':'16方向朝向'},ensure_ascii=False,indent=2),encoding='utf-8')
