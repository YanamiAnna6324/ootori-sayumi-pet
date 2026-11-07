"""Close the approved blink by replaying the same generated poses in reverse.

This changes playback order only. No facial artwork is drawn or regenerated.
Eight logical cells are retained; encoders may merge equal adjacent holds.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops

from assemble_stable_idle import (
    ROOT, contact_sheet, differing_pixels, file_hash, gif_palette_frames,
    inspect_animation, native_cell, rgba,
)
from render_stable_idle_sway import frame_motion, horizontal_sway, make_contact


FRAME_MAP = [1, 2, 3, 4, 3, 2, 1, 1]
DURATIONS = [480, 100, 70, 100, 70, 100, 460, 520]


def save_webp(frames: list[Image.Image], path: Path) -> dict:
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=DURATIONS, loop=0, lossless=True,
                   quality=100, method=4, exact=True)
    return inspect_animation(path)


def pixel_difference_report(first: Image.Image, second: Image.Image) -> dict:
    """Compare alpha and visible RGB exactly; report invisible RGB separately."""
    first, second = first.convert('RGBA'), second.convert('RGBA')
    alpha_first, alpha_second = first.getchannel('A'), second.getchannel('A')
    alpha_diff = ImageChops.difference(alpha_first, alpha_second)
    channels = ImageChops.difference(first.convert('RGB'), second.convert('RGB')).split()
    rgb_diff = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
    visible = ImageChops.lighter(alpha_first, alpha_second).point(lambda value: 255 if value else 0)
    visible_rgb_diff = ImageChops.multiply(rgb_diff, visible)
    visible_count = sum(visible_rgb_diff.histogram()[1:])
    return {'alpha_changed_pixels': sum(alpha_diff.histogram()[1:]),
            'visible_rgb_changed_pixels': visible_count,
            'hidden_rgb_changed_pixels': sum(rgb_diff.histogram()[1:]) - visible_count}


def audit_timeline(path: Path, expected: list[Image.Image]) -> dict:
    """Compare every displayed interval, allowing equal adjacent hold merging."""
    with Image.open(path) as encoded:
        decoded, durations = [], []
        for index in range(encoded.n_frames):
            encoded.seek(index)
            encoded.load()
            decoded.append(encoded.convert('RGBA'))
            durations.append(encoded.info['duration'])
    elapsed, errors, comparisons = 0, [], []
    for index, (frame, duration) in enumerate(zip(expected, DURATIONS), 1):
        end, covered = 0, 0
        for encoded_index, (candidate, encoded_duration) in enumerate(zip(decoded, durations), 1):
            overlap = max(0, min(elapsed + duration, end + encoded_duration) - max(elapsed, end))
            if overlap:
                delta = pixel_difference_report(frame, candidate)
                comparisons.append({'logical_slot': index, 'encoded_frame': encoded_index,
                                    'overlap_ms': overlap, **delta})
                if delta['alpha_changed_pixels'] or delta['visible_rgb_changed_pixels']:
                    errors.append(f'Logical slot {index} differs visibly from encoded frame {encoded_index}')
                covered += overlap
            end += encoded_duration
        if covered != duration:
            errors.append(f'Logical slot {index} is not fully covered by encoded time')
        elapsed += duration
    endpoint = pixel_difference_report(decoded[0], decoded[-1])
    if endpoint['alpha_changed_pixels'] or endpoint['visible_rgb_changed_pixels']:
        errors.append('Encoded first/last visible pixels differ')
    return {'ok': not errors, 'errors': errors,
            'logical_slots_checked': len(expected),
            'comparisons': comparisons, 'encoded_endpoint_difference': endpoint,
            'first_last_encoded_visible_pixels_equal': not endpoint['alpha_changed_pixels'] and not endpoint['visible_rgb_changed_pixels'],
            'total_duration_matches': sum(durations) == sum(DURATIONS)}


def write_frames(frames: list[Image.Image], canonical: Image.Image, directory: Path) -> tuple[list[Image.Image], list[dict]]:
    full_dir, native_dir = directory / 'processed', directory / 'frames-192'
    full_dir.mkdir(parents=True)
    native_dir.mkdir()
    native = [native_cell(frame) for frame in frames]
    canonical_native = native_cell(canonical)
    records = []
    for index, (frame, small, source_index, duration) in enumerate(zip(frames, native, FRAME_MAP, DURATIONS), 1):
        full_path, native_path = full_dir / f'frame-{index:02d}.png', native_dir / f'frame-{index:02d}.png'
        frame.save(full_path)
        small.save(native_path)
        bbox = small.getchannel('A').getbbox()
        records.append({'index': index, 'source_frame': source_index,
                        'duration_ms': duration, 'processed': str(full_path),
                        'processed_sha256': file_hash(full_path),
                        'native_frame': str(native_path), 'native_sha256': file_hash(native_path),
                        'lower_body_changed_pixels': differing_pixels(frame.crop((0,700,1024,1024)), canonical.crop((0,700,1024,1024))),
                        'native_lower_body_changed_pixels': differing_pixels(small.crop((0,140,192,208)), canonical_native.crop((0,140,192,208))),
                        'native_bbox': bbox, 'native_foot_baseline': bbox[3]-1})
    return native, records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-dir', type=Path, default=ROOT / 'output/imagegen/repair-v5/idle-stable-v2')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'output/imagegen/repair-v5/idle-stable-v5')
    args = parser.parse_args()
    source_dir, output = args.baseline_dir.resolve(), args.output_dir.resolve()
    qa_path = source_dir / 'qa.json'
    qa = json.loads(qa_path.read_text(encoding='utf-8-sig'))
    if not qa.get('ok') or qa.get('errors'):
        raise SystemExit('The approved fixed-body input must pass QA.')
    if output.exists():
        raise SystemExit(f'Preserve the previous output; select a new output directory: {output}')
    canonical_path = Path(qa['canonical'])
    if file_hash(canonical_path) != qa['canonical_sha256']:
        raise SystemExit('Canonical differs from the approved input.')
    source_records = sorted(qa['frames'], key=lambda item: item['index'])
    if [record['index'] for record in source_records] != list(range(1,9)):
        raise SystemExit('The existing eight generated source cells are required.')
    for record in source_records:
        if file_hash(Path(record['processed'])) != record['processed_sha256']:
            raise SystemExit(f'Input frame {record["index"]} changed since approved QA.')
    canonical = rgba(canonical_path)
    originals = [rgba(Path(record['processed'])) for record in source_records]
    frames = [originals[source_index-1].copy() for source_index in FRAME_MAP]
    motion, motion_summary = frame_motion(DURATIONS, 1.5)
    # Guarantee exact loop closure, including subpixel transform parameters.
    motion[-1]['horizontal_displacement_px'] = motion[0]['horizontal_displacement_px']
    motion_summary['neighbor_displacement_deltas_px_including_loop'] = [
        abs(motion[(index+1) % len(motion)]['horizontal_displacement_px'] - record['horizontal_displacement_px'])
        for index, record in enumerate(motion)]
    motion_summary['maximum_neighbor_displacement_delta_px'] = max(motion_summary['neighbor_displacement_deltas_px_including_loop'])
    motion_summary['last_to_first_displacement_delta_px'] = 0.0
    swayed = [horizontal_sway(frame, canonical, record['horizontal_displacement_px'])
              for frame, record in zip(frames, motion)]
    output.mkdir(parents=True)
    native, records = write_frames(frames, canonical, output)
    sway_dir = output / 'gentle-sway'
    sway_native, sway_records = write_frames(swayed, canonical, sway_dir)
    large = [frame.resize((512,512), Image.Resampling.LANCZOS) for frame in frames]
    sway_large = [frame.resize((512,512), Image.Resampling.LANCZOS) for frame in swayed]
    animations = {}
    for name, sequence, path in [
        ('fixed_512', large, output / 'idle-stable-preview.webp'),
        ('sway_512', sway_large, sway_dir / 'idle-gentle-sway.webp'),
        ('sway_native', sway_native, sway_dir / 'idle-gentle-sway-192.webp'),
    ]:
        animations[name] = {**save_webp(sequence, path), 'timeline': audit_timeline(path, sequence)}
    palette = gif_palette_frames(large)
    gif = output / 'idle-stable-preview.gif'
    palette[0].save(gif, save_all=True, append_images=palette[1:], duration=DURATIONS,
                    loop=0, transparency=255, disposal=2, optimize=False)
    animations['fixed_gif'] = {**inspect_animation(gif), 'timeline': audit_timeline(gif, palette)}
    contact_sheet(native, DURATIONS, output / 'idle-stable-contact.png')
    make_contact(sway_native, motion, sway_dir / 'idle-gentle-sway-contact.png')
    checks = {
        'logical_slots': len(frames), 'intentional_pose_reuse': True,
        'source_frame_map': FRAME_MAP, 'distinct_source_poses_used': len(set(FRAME_MAP)),
        'fixed_endpoint_changed_pixels': differing_pixels(frames[0], frames[-1]),
        'sway_endpoint_changed_pixels': differing_pixels(swayed[0], swayed[-1]),
        'native_sway_endpoint_changed_pixels': differing_pixels(sway_native[0], sway_native[-1]),
        'fixed_blink_retrace_pairs_changed_pixels': [differing_pixels(frames[a], frames[b]) for a,b in [(0,6),(1,5),(2,4)]],
        'all_legs_fixed': all(not record['lower_body_changed_pixels'] and not record['native_lower_body_changed_pixels'] for record in records+sway_records),
        'native_foot_baselines': sorted({record['native_foot_baseline'] for record in records+sway_records}),
        'all_encoded_timelines_match': all(value.get('timeline',{}).get('ok',True) and value.get('timeline',{}).get('total_duration_matches',True) for value in animations.values()),
        'all_animations_loop_forever': all(value['loop'] == 0 for value in animations.values()),
        'all_durations_match': all(value['total_duration_ms'] == sum(DURATIONS) for value in animations.values()),
    }
    errors = []
    for key in ['fixed_endpoint_changed_pixels','sway_endpoint_changed_pixels','native_sway_endpoint_changed_pixels']:
        if checks[key]:
            errors.append(f'{key}: {checks[key]}')
    if any(checks['fixed_blink_retrace_pairs_changed_pixels']):
        errors.append('Reopening does not retrace the closing poses')
    for key in ['all_legs_fixed','all_encoded_timelines_match','all_animations_loop_forever','all_durations_match']:
        if not checks[key]:
            errors.append(key)
    if len(checks['native_foot_baselines']) != 1:
        errors.append('Foot baseline drift')
    report = {'ok': not errors, 'kind': 'seamless_blink_playback_repair', 'native_pet_package': False,
              'errors': errors, 'input_qa': str(qa_path), 'input_qa_sha256': file_hash(qa_path),
              'canonical': str(canonical_path), 'canonical_sha256': file_hash(canonical_path),
              'script': str(Path(__file__).resolve()), 'script_sha256': file_hash(Path(__file__)),
              'new_artwork_generated': False, 'source_frame_map': FRAME_MAP,
              'durations_ms': DURATIONS, 'total_duration_ms': sum(DURATIONS),
              'checks': checks, 'motion': motion_summary, 'motion_records': motion,
              'fixed_frames': records, 'sway_frames': sway_records,
              'animations': animations,
              'notes': ['User requested identical start/end eyes and a seamless repeating loop.',
                        'Closing poses are replayed in reverse for reopening; generated candidates 05..08 remain preserved in the previous version.',
                        'Equal adjacent holds may be merged by the encoder; eight logical PNG cells remain available.',
                        'Encoded playback requires exact alpha and RGB at every visible pixel; RGB changes under zero alpha are reported separately.',
                        'Independent visual acceptance is recorded separately in visual-review.json.']}
    (output / 'qa.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'ok': report['ok'], 'output': str(output), 'checks': checks,
                      'encoded_frames': {key:value['frames'] for key,value in animations.items()},
                      'errors': errors}, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
