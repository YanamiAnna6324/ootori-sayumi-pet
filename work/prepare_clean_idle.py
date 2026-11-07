"""Prepare a separate idle preview from an independently reviewed edge cleanup.

Reuses the eight genuine generated face edits and the existing face mask. This
does not generate artwork, crop, resize, or change individual frame geometry.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from PIL import Image, ImageChops

from assemble_stable_idle import DEFAULT_PLAN, file_hash


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--cleanup-report', type=Path, required=True)
    parser.add_argument('--source-plan', type=Path, default=DEFAULT_PLAN)
    parser.add_argument('--run-dir', type=Path, required=True)
    args = parser.parse_args()
    source_plan = args.source_plan.resolve()
    plan = json.loads(source_plan.read_text(encoding='utf-8-sig'))
    report = json.loads(args.cleanup_report.read_text(encoding='utf-8-sig'))
    canonical = Path(plan['canonical'])
    candidate = args.candidate.resolve()
    if report['source_sha256'] != file_hash(canonical):
        raise SystemExit('Cleanup source hash does not match the original canonical.')
    if Path(report['candidate']).resolve() != candidate:
        raise SystemExit('Cleanup report identifies a different candidate.')
    original = Image.open(canonical).convert('RGBA')
    cleaned = Image.open(candidate).convert('RGBA')
    mask = Image.open(plan['mask']).convert('RGBA')
    if original.size != cleaned.size or original.size != (1024, 1024):
        raise SystemExit('Cleanup must preserve the entire 1024x1024 canvas.')
    # Prohibit edge cleanup from changing any facial editing support.
    support = ImageChops.invert(mask.getchannel('A')).point(lambda v: 255 if v else 0)
    differences = ImageChops.difference(original, cleaned)
    for channel in differences.split():
        if ImageChops.multiply(channel, support).getbbox():
            raise SystemExit('Edge cleanup changes facial artwork; candidate rejected.')
    run = args.run_dir.resolve()
    if run.exists():
        raise SystemExit(f'Output already exists; retain it and use a new run directory: {run}')
    run.mkdir(parents=True)
    shutil.copyfile(candidate, run / 'canonical.png')
    shutil.copyfile(plan['mask'], run / 'face-mask.png')
    shutil.copyfile(args.cleanup_report, run / 'edge-cleanup.json')
    plan['canonical'] = str(run / 'canonical.png')
    plan['mask'] = str(run / 'face-mask.png')
    plan['purpose'] = 'eight generated expression frames with one shared reviewed edge cleanup'
    plan['status'] = 'eight source frames generated; edge candidate reviewed; ready for deterministic assembly'
    plan['parent_generation_plan'] = str(source_plan)
    plan['parent_generation_plan_sha256'] = file_hash(source_plan)
    plan['edge_cleanup_report'] = str(run / 'edge-cleanup.json')
    plan['edge_cleanup_report_sha256'] = file_hash(run / 'edge-cleanup.json')
    plan['edge_cleaned_canonical_sha256'] = file_hash(run / 'canonical.png')
    plan['packaging_eligible'] = False
    plan['review_status_file'] = 'See output preview visual-review.json for completed visual acceptance.'
    target = run / 'generation-plan.json'
    target.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'plan': str(target), 'canonical': plan['canonical'],
                      'face_edit_support_unchanged': True,
                      'alpha_unchanged': original.getchannel('A').tobytes() == cleaned.getchannel('A').tobytes(),
                      'native_pet_package': False}, indent=2))


if __name__ == '__main__':
    main()
