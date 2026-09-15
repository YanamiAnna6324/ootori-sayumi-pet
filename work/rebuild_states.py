from PIL import Image
from pathlib import Path
import json
ROOT=Path(r'C:\Users\HP\Documents\Codex\2026-09-14\hatch-pet-c-users-hp-codex'); SRC=Path(r'C:\Users\HP\Downloads\codex宠物'); OUT=ROOT/'outputs'/'ootori_sayumi_pet'/'states_v2'; OUT.mkdir(parents=True,exist_ok=True)
W,H=192,208
refs={'eating':['微信图片_20260914205822_9_47.jpg','微信图片_20260914205826_12_47.jpg'],'surprised':['微信图片_20260914205823_10_47.jpg'],'working':['微信图片_20260914205825_11_47.jpg'],'happy':['微信图片_20260914205827_13_47.jpg'],'gift':['微信图片_20260914205828_14_47.jpg']}
for state,names in refs.items():
 strip=Image.new('RGBA',(W*6,H),(0,255,0,0))
 for i in range(6):
  im=Image.open(SRC/names[i%len(names)]).convert('RGBA'); im.thumbnail((180,196),Image.Resampling.LANCZOS); cell=Image.new('RGBA',(W,H),(0,255,0,0)); cell.alpha_composite(im,((W-im.width)//2,(H-im.height)//2)); strip.alpha_composite(cell,(i*W,0))
 strip.save(OUT/f'{state}.png')
mp=ROOT/'outputs'/'ootori_sayumi_pet'/'state-map.json'; data=json.loads(mp.read_text(encoding='utf-8')); data.update({k:f'states_v2/{k}.png' for k in refs}); mp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
