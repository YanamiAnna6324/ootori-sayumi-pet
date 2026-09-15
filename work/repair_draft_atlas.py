"""Repair an existing draft's neutral slot and hidden RGB without generating art."""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'outputs/ootori_sayumi_pet'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=PACKAGE / 'spritesheet-extended.webp')
    parser.add_argument('--output-dir', type=Path, default=PACKAGE / 'draft')
    args = parser.parse_args()
    with Image.open(args.source) as image:
        if image.size != (1536, 2288) or image.mode != 'RGBA':
            raise SystemExit('Expected an existing 1536x2288 RGBA v2 draft.')
        before = np.array(image)
    repaired = before.copy()
    neutral = repaired[:208, 1152:1344]
    neutral_added = not np.any(neutral[:, :, 3])
    if neutral_added:
        neutral[:] = repaired[:208, :192]
    transparent = repaired[:, :, 3] == 0
    repaired[transparent, :3] = 0
    counts = [6, 8, 8, 4, 5, 8, 6, 6, 6, 8, 8]
    for row, count in enumerate(counts):
        for col in range(8):
            alpha = repaired[row*208:(row+1)*208, col*192:(col+1)*192, 3]
            used = col < count or (row, col) == (0, 6)
            if bool(np.any(alpha)) != used:
                raise SystemExit(f'Unexpected content in row {row}, col {col}: used={used}')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / 'spritesheet.webp'
    Image.fromarray(repaired).save(target, lossless=True, exact=True, quality=100, method=6)
    decoded = np.array(Image.open(target).convert('RGBA'))
    if not np.array_equal(decoded, repaired):
        raise SystemExit('Lossless WebP roundtrip mismatch.')
    existing_visible = before[:, :, 3] > 0
    preserved = np.array_equal(before[existing_visible], repaired[existing_visible])
    if not preserved:
        raise SystemExit('Existing visible sprite pixels changed.')
    report = {
        'kind': 'legacy_preview_draft',
        'structural_checks_ok': True,
        'size': [1536, 2288],
        'mode': 'RGBA',
        'used_cells_nonempty': True,
        'unused_cells_transparent': True,
        'neutral_added_from_idle': neutral_added,
        'hidden_rgb_pixels': 0,
        'existing_visible_pixels_preserved': bool(preserved),
        'lossless_roundtrip': True,
        'source_sha256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
        'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'visual_qa': 'unfinished: static rows, cropped figures, overlapping decorations and incorrect gaze poses remain',
        'final_release_ready': False,
    }
    (args.output_dir / 'structure-check.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Draft structure repaired and verified. Full visual acceptance is still pending.')


if __name__ == '__main__':
    main()
