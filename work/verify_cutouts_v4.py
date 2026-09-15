"""Audit extracted PNGs against their original pixels and preview resources."""
from pathlib import Path
from html.parser import HTMLParser
import argparse
import hashlib
import json
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


class LocalLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        self.links.extend(value for key, value in attrs if key in ('src', 'href'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=Path(r'C:\Users\HP\Downloads\codex宠物'))
    args = parser.parse_args()
    folder = ROOT / 'outputs/ootori_sayumi_pet/cutouts-v4'
    report = json.loads((folder / 'extraction-report.json').read_text(encoding='utf-8'))
    results = {}
    for name, info in report.items():
        path = folder / (name + '.png')
        image = Image.open(path)
        data = np.array(image)
        original = np.array(Image.open(args.source_dir / info['source']).convert('RGB'))
        left, top, right, bottom = info['crop_box']
        original = original[top:bottom, left:right]
        visible = data[:, :, 3] > 0
        checks = {
            'rgba': image.mode == 'RGBA',
            'transparent_exterior': bool(np.any(~visible)),
            'nonempty': bool(visible.any()),
            'hidden_rgb_zero': bool(np.all(data[~visible, :3] == 0)),
            'source_pixels_unchanged': bool(np.array_equal(data[visible, :3], original[visible])),
        }
        results[name] = {
            'checks': checks,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'size': list(image.size),
            'native_animation_ready': False,
        }
        if not all(checks.values()):
            raise SystemExit(f'FAIL: {name}: {checks}')
    html = (folder / 'preview.html').read_text(encoding='utf-8')
    links = LocalLinks()
    links.feed(html)
    missing = [link for link in links.links if not (folder / link).is_file()]
    if missing:
        raise SystemExit(f'Missing preview resources: {missing}')
    javascript = html.split('<script>', 1)[1].split('</script>', 1)[0]
    (ROOT / 'work/repair-v4/preview-script.js').write_text(javascript, encoding='utf-8')
    result = {
        'cutout_pixel_checks_ok': True,
        'count': len(results),
        'preview_resource_links_ok': True,
        'preview_browser_qa': 'unavailable: CUA auth token unavailable',
        'native_release_qa': 'blocked: incomplete source silhouettes, overlapping effects, no generated action/gaze rows',
        'assets': results,
    }
    (folder / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'PASS: {len(results)} RGBA cutouts; original visible RGB preserved, hidden RGB zero, preview resources exist.')
    print('Native release remains blocked; this audit does not validate animation or reconstruction.')


if __name__ == '__main__':
    main()
