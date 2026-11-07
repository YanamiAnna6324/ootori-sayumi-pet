"""Render optional tiny upper-body sway after the eight generated face edits pass.

This renderer does not generate facial artwork or replace missing model frames.
It applies only a time-smooth horizontal displacement field, keeps the original
canvas, and copies the canonical lower body back exactly.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from assemble_stable_idle import (
    DEFAULT_OUTPUT,
    differing_pixels,
    file_hash,
    image_hash,
    inspect_animation,
    native_cell,
    rgba,
)


def resolve_record_path(value: str, baseline_dir: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (baseline_dir / path).resolve()


def taper(y: float) -> float:
    if y <= 430:
        return 1.0
    if y >= 680:
        return 0.0
    position = (y - 430) / 250
    return 1 - position * position * (3 - 2 * position)


def frame_motion(durations: list[int], amplitude: float) -> tuple[list[dict], dict]:
    period = sum(durations)
    centers = []
    elapsed = 0
    for duration in durations:
        centers.append(elapsed + duration / 2)
        elapsed += duration
    # Place the sinusoid's peak halfway across the wrap gap. The first and last
    # displayed displacements then match, while phases remain time-derived.
    wrap_midpoint = (centers[-1] + centers[0] + period) / 2
    phase_offset = math.pi / 2 - 2 * math.pi * wrap_midpoint / period
    samples = [math.sin(2 * math.pi * center / period + phase_offset) for center in centers]
    unit_step = max(abs(samples[(i+1) % len(samples)] - sample) for i, sample in enumerate(samples))
    actual_amplitude = min(amplitude, 1.79 / unit_step) if unit_step else amplitude
    records = [
        {'index': index + 1, 'duration_ms': duration, 'frame_center_ms': center,
         'phase_radians': 2 * math.pi * center / period + phase_offset,
         'horizontal_displacement_px': actual_amplitude * sample,
         'vertical_displacement_px': 0}
        for index, (duration, center, sample) in enumerate(zip(durations, centers, samples))
    ]
    deltas = [abs(records[(i+1) % len(records)]['horizontal_displacement_px'] - record['horizontal_displacement_px'])
              for i, record in enumerate(records)]
    return records, {
        'period_ms': period, 'phase_offset_radians': phase_offset,
        'requested_amplitude_px': amplitude, 'analytic_maximum_displacement_px': actual_amplitude,
        'maximum_sampled_displacement_px': max(abs(record['horizontal_displacement_px']) for record in records),
        'neighbor_displacement_deltas_px_including_loop': deltas,
        'maximum_neighbor_displacement_delta_px': max(deltas),
        'last_to_first_displacement_delta_px': deltas[-1],
        'time_function': 'A*sin(2*pi*t/period+phase_offset), sampled at cumulative frame centers',
    }


def horizontal_sway(frame: Image.Image, canonical: Image.Image, displacement: float) -> Image.Image:
    mesh = []
    width = frame.width
    # Every scanline keeps its horizontal scale exactly 1. Only its offset
    # changes. Premultiplied RGBa makes fractional silhouette sampling safe.
    for y in range(680):
        top_shift, bottom_shift = displacement * taper(y), displacement * taper(y + 1)
        mesh.append(((0, y, width, y + 1),
                     (-top_shift, y, -bottom_shift, y + 1,
                      width - bottom_shift, y + 1, width - top_shift, y)))
    result = frame.convert('RGBa').transform(
        frame.size, Image.Transform.MESH, mesh,
        resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0, 0),
    ).convert('RGBA')
    # Avoid any premultiplication roundoff in the zero-displacement region.
    result.paste(frame.crop((0, 680, 1024, 700)), (0, 680))
    result.paste(canonical.crop((0, 700, 1024, 1024)), (0, 700))
    return result


def make_contact(frames: list[Image.Image], motion: list[dict], path: Path) -> None:
    sheet = Image.new('RGB', (1024, 560), (239, 241, 245))
    draw = ImageDraw.Draw(sheet)
    for index, (frame, record) in enumerate(zip(frames, motion)):
        left, top = (index % 4) * 256, (index // 4) * 280
        for y in range(top + 32, top + 240, 16):
            for x in range(left + 32, left + 224, 16):
                alternate = ((x-left-32)//16 + (y-top-32)//16) % 2
                draw.rectangle((x, y, min(x+15, left+223), min(y+15, top+239)),
                               fill=(215, 218, 225) if alternate else (245, 246, 248))
        sheet.paste(frame, (left + 32, top + 32), frame)
        draw.text((left + 12, top + 10), f'{index+1:02d}  {record["duration_ms"]} ms', fill=(22, 25, 31))
        draw.text((left + 12, top + 252), f'upper dx={record["horizontal_displacement_px"]:+.2f}px / legs fixed', fill=(60, 65, 74))
    sheet.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-dir', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--baseline-qa', type=Path, help='Defaults to baseline-dir/qa.json')
    parser.add_argument('--output-dir', type=Path, help='Defaults to baseline-dir/gentle-sway')
    parser.add_argument('--amplitude', type=float, default=1.5, help='Maximum horizontal motion at 1024px, within 0..1.5px')
    args = parser.parse_args()
    if not 0 < args.amplitude <= 1.5:
        parser.error('Amplitude must be greater than 0 and no more than 1.5px at the 1024px canvas')
    baseline_dir = args.baseline_dir.expanduser().resolve()
    qa_path = args.baseline_qa.expanduser().resolve() if args.baseline_qa else baseline_dir / 'qa.json'
    if not qa_path.is_file():
        raise SystemExit(f'Complete the no-sway baseline first; missing {qa_path}. No outputs written.')
    baseline = json.loads(qa_path.read_text(encoding='utf-8-sig'))
    if baseline.get('ok') is not True or baseline.get('errors'):
        raise SystemExit('No-sway baseline QA must pass before optional sway; no outputs written.')
    records = sorted(baseline.get('frames', []), key=lambda record: record['index'])
    if len(records) != 8 or [record['index'] for record in records] != list(range(1, 9)):
        raise SystemExit('Exactly eight completed no-sway frames are required; sway cannot fill missing artwork.')
    if baseline.get('assembly', {}).get('sway_px') != 0:
        raise SystemExit('The input must be the original no-sway baseline, not a previously warped preview.')
    face_hashes = [record.get('face_sha256') for record in records]
    source_hashes = [record.get('generated_source_sha256') for record in records]
    if None in face_hashes or len(set(face_hashes)) != 8 or None in source_hashes or len(set(source_hashes)) != 8:
        raise SystemExit('Eight distinct generated source hashes and facial artwork hashes are required before adding sway.')
    durations = baseline.get('durations_ms')
    if not durations or len(durations) != 8 or any(not isinstance(value, int) or value <= 0 for value in durations):
        raise SystemExit('The baseline must contain all eight positive frame durations.')
    canonical_path = resolve_record_path(baseline['canonical'], baseline_dir)
    input_paths = [resolve_record_path(record['processed'], baseline_dir) for record in records]
    source_paths = [resolve_record_path(record['generated_source'], baseline_dir) for record in records]
    missing = [str(path) for path in [canonical_path, *input_paths, *source_paths] if not path.is_file()]
    if missing:
        raise SystemExit('Missing baseline or generated artwork; no outputs written:\n' + '\n'.join(missing))
    if file_hash(canonical_path) != baseline.get('canonical_sha256'):
        raise SystemExit('Canonical image differs from passing baseline QA; rerun baseline first.')
    for record, processed, source in zip(records, input_paths, source_paths):
        if file_hash(processed) != record.get('processed_sha256') or file_hash(source) != record.get('generated_source_sha256'):
            raise SystemExit(f'Frame {record["index"]} differs from passing baseline provenance; rerun baseline first.')
    canonical = rgba(canonical_path)
    inputs = [rgba(path) for path in input_paths]
    canonical_lower = canonical.crop((0, 700, 1024, 1024))
    if any(differing_pixels(frame.crop((0, 700, 1024, 1024)), canonical_lower) for frame in inputs):
        raise SystemExit('No-sway baseline lower body differs from canonical; sway was not applied.')
    motion, motion_summary = frame_motion(durations, args.amplitude)
    frames = [horizontal_sway(frame, canonical, record['horizontal_displacement_px']) for frame, record in zip(inputs, motion)]
    native = [native_cell(frame) for frame in frames]
    native_original = native_cell(canonical)
    native_lower_y = math.ceil(8 + 700 * 192 / 1024)
    output = args.output_dir.expanduser().resolve() if args.output_dir else baseline_dir / 'gentle-sway'
    if output == baseline_dir or any(path.is_relative_to(output) for path in [qa_path, canonical_path, *input_paths, *source_paths]):
        raise SystemExit('Output must be a separate directory that does not contain baseline or generated inputs.')
    full_dir, native_dir = output / 'processed', output / 'frames-192'
    full_dir.mkdir(parents=True, exist_ok=True)
    native_dir.mkdir(parents=True, exist_ok=True)
    frame_qa = []
    for index, (frame, small, source, record, movement) in enumerate(zip(frames, native, input_paths, records, motion), 1):
        full_path, native_path = full_dir / f'frame-{index:02d}.png', native_dir / f'frame-{index:02d}.png'
        frame.save(full_path)
        small.save(native_path)
        bbox = frame.getchannel('A').getbbox()
        frame_qa.append({
            **movement, 'source_processed': str(source), 'source_processed_sha256': record['processed_sha256'],
            'source_face_sha256': record['face_sha256'], 'generated_source': record['generated_source'],
            'generated_source_sha256': record['generated_source_sha256'], 'expression': record.get('expression'),
            'processed': str(full_path), 'processed_sha256': file_hash(full_path),
            'native_frame': str(native_path), 'native_sha256': file_hash(native_path),
            'lower_body_changed_pixels': differing_pixels(frame.crop((0, 700, 1024, 1024)), canonical_lower),
            'native_lower_body_changed_pixels': differing_pixels(small.crop((0, native_lower_y, 192, 208)), native_original.crop((0, native_lower_y, 192, 208))),
            'zero_displacement_band_changed_pixels': differing_pixels(frame.crop((0, 680, 1024, 700)), inputs[index-1].crop((0, 680, 1024, 700))),
            'bbox': bbox, 'foot_baseline': bbox[3]-1 if bbox else None,
        })
    large_preview = [frame.resize((512, 512), Image.Resampling.LANCZOS) for frame in frames]
    large_path, native_path = output / 'idle-gentle-sway.webp', output / 'idle-gentle-sway-192.webp'
    for sequence, path in [(large_preview, large_path), (native, native_path)]:
        sequence[0].save(path, save_all=True, append_images=sequence[1:], duration=durations,
                         loop=0, lossless=True, quality=100, method=6, exact=True)
    animations = {'preview_512': inspect_animation(large_path), 'native_192x208': inspect_animation(native_path)}
    contact_path = output / 'idle-gentle-sway-contact.png'
    make_contact(native, motion, contact_path)
    errors = []
    if motion_summary['analytic_maximum_displacement_px'] > 1.5:
        errors.append('Horizontal displacement exceeds 1.5px')
    if motion_summary['maximum_neighbor_displacement_delta_px'] >= 1.8:
        errors.append('Neighbor displacement change reaches or exceeds 1.8px')
    for record in frame_qa:
        if record['lower_body_changed_pixels'] or record['native_lower_body_changed_pixels'] or record['zero_displacement_band_changed_pixels']:
            errors.append(f'Frame {record["index"]} changed fixed lower-body pixels')
    canonical_bbox = canonical.getchannel('A').getbbox()
    if any(record['foot_baseline'] != canonical_bbox[3]-1 for record in frame_qa):
        errors.append('Foot baseline changed')
    for name, animation in animations.items():
        if animation['frames'] != 8 or animation['durations_ms'] != durations:
            errors.append(f'{name}: encoded frame count or timings differ from the eight-frame baseline')
    qa = {
        'ok': not errors, 'kind': 'optional_gentle_sway_preview', 'native_pet_package': False,
        'created_at': datetime.now(timezone.utc).isoformat(), 'errors': errors,
        'visual_qa': 'pending independent comparison against the passing no-sway baseline',
        'baseline_qa': str(qa_path), 'baseline_qa_sha256': file_hash(qa_path),
        'canonical': str(canonical_path), 'canonical_sha256': file_hash(canonical_path),
        'generated_facial_artwork_hashes': face_hashes, 'generated_source_hashes': source_hashes,
        'generated_facial_artwork_distinct_count': len(set(face_hashes)),
        'facial_artwork_drawn_by_renderer': False, 'missing_frame_synthesis': False,
        'renderer': {'script': str(Path(__file__).resolve()), 'script_sha256': file_hash(Path(__file__)),
                     'method': 'premultiplied-alpha horizontal scanline MESH displacement',
                     'full_canvas': [1024,1024], 'upper_full_amplitude_through_y': 430,
                     'smoothstep_taper_to_zero_at_y': 680, 'canonical_lower_exact_from_y': 700,
                     'vertical_displacement_px': 0, 'rotation_degrees': 0, 'horizontal_scale': 1,
                     'vertical_scale': 1, 'body_or_leg_resizing': False, 'bbox_fit': False,
                     'native_transform': {'scale':192/1024, 'offset':[0,8], 'shared_across_frames':True},
                     'resampling': 'RGBa premultiplied BICUBIC for subpixel sway; shared LANCZOS output size'},
        'motion': motion_summary, 'durations_ms': durations, 'total_duration_ms': sum(durations),
        'checks': {'eight_generated_expression_sources_required': True,
                   'distinct_source_face_hashes': len(set(face_hashes)),
                   'lower_body_exact_in_all_frames': all(record['lower_body_changed_pixels'] == 0 for record in frame_qa),
                   'native_lower_body_exact_in_all_frames': all(record['native_lower_body_changed_pixels'] == 0 for record in frame_qa),
                   'foot_baseline_equal_in_all_frames': all(record['foot_baseline'] == canonical_bbox[3]-1 for record in frame_qa),
                   'maximum_displacement_bounded': motion_summary['analytic_maximum_displacement_px'] <= 1.5,
                   'neighbor_motion_bounded_including_loop': motion_summary['maximum_neighbor_displacement_delta_px'] < 1.8},
        'frames': frame_qa, 'animations': animations, 'contact_sheet': str(contact_path),
    }
    output_qa = output / 'qa.json'
    output_qa.write_text(json.dumps(qa, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'ok': qa['ok'], 'qa': str(output_qa), 'webp':str(large_path),
                      'native_webp': str(native_path), 'contact_sheet': str(contact_path),
                      'motion': motion_summary, 'checks':qa['checks'], 'errors':errors}, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
