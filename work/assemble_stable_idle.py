"""Assemble model-generated facial edits over one unchanged idle body.

This is a preview pipeline. It never draws facial art, generates motion, fits
individual frames to a bounding box, or modifies a native pet atlas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / 'work/repair-v5/idle-stable-v1/generation-plan.json'
DEFAULT_OUTPUT = ROOT / 'output/imagegen/repair-v5/idle-stable-v1'
EXPECTED_SIZE = (1024, 1024)
DEFAULT_DURATIONS = [480, 160, 120, 100, 120, 160, 240, 520]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_hash(image: Image.Image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()


def resolve_input(value: str, plan_path: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (plan_path.parent / path).resolve()


def rgba(path: Path) -> Image.Image:
    with Image.open(path) as source:
        image = source.convert('RGBA')
    if image.size != EXPECTED_SIZE:
        raise ValueError(f'{path}: expected fixed 1024x1024 input, got {image.size}; no automatic resize is allowed')
    return image


def generated_face_source(path: Path) -> tuple[Image.Image, tuple[int, int]]:
    """Register a service-returned square canvas, never the character bbox.

    Some provider responses ignore size=1024x1024 and return 1254x1254.
    Preserve that original file. Only its facial RGB is sampled at the requested
    canvas coordinates; canonical body pixels are never scaled per frame.
    """
    with Image.open(path) as source:
        image = source.convert('RGBA')
    original_size = image.size
    if image.width != image.height or not 768 <= image.width <= 2048:
        raise ValueError(f'{path}: unsupported generated canvas {image.size}')
    if image.size != EXPECTED_SIZE:
        image = image.resize(EXPECTED_SIZE, Image.Resampling.LANCZOS)
    return image, original_size


def differing_pixels(first: Image.Image, second: Image.Image) -> int:
    diff = ImageChops.difference(first, second).convert('RGB')
    channels = diff.split()
    maximum = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
    if first.mode == 'RGBA' and second.mode == 'RGBA':
        maximum = ImageChops.lighter(maximum, ImageChops.difference(first.getchannel('A'), second.getchannel('A')))
    return sum(maximum.histogram()[1:])


def masked_face(image: Image.Image, support: Image.Image) -> Image.Image:
    return Image.composite(image, Image.new('RGBA', image.size, (0, 0, 0, 0)), support)


def native_cell(image: Image.Image) -> Image.Image:
    # One constant transform for every input, including the canonical image.
    # The entire 1024px canvas becomes 192px; no bbox is inspected here.
    scaled = image.resize((192, 192), Image.Resampling.LANCZOS)
    result = Image.new('RGBA', (192, 208), (0, 0, 0, 0))
    result.paste(scaled, (0, 8))
    return result


def gif_palette_frames(frames: list[Image.Image]) -> list[Image.Image]:
    # A single palette prevents the unchanged body from flickering between
    # independent quantizers. Index 255 is explicitly reserved for transparency.
    sample = Image.new('RGB', (512 * 4, 512 * 2), 'white')
    for index, frame in enumerate(frames):
        flat = Image.new('RGBA', frame.size, 'white')
        flat.alpha_composite(frame)
        sample.paste(flat.convert('RGB'), ((index % 4) * 512, (index // 4) * 512))
    palette = sample.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    colours = palette.getpalette()
    # Pillow may use any palette index, including an otherwise unused 255.
    # Make it duplicate index 0 while quantizing, then map opaque uses back
    # to 0 before reserving 255 for actual transparent pixels.
    colours[765:768] = colours[:3]
    palette.putpalette(colours)
    result = []
    for frame in frames:
        flat = Image.new('RGBA', frame.size, 'white')
        flat.alpha_composite(frame)
        indexed = flat.convert('RGB').quantize(palette=palette, dither=Image.Dither.NONE)
        indexed = indexed.point(lambda value: 0 if value == 255 else value)
        transparent = frame.getchannel('A').point(lambda value: 255 if value < 128 else 0)
        indexed.paste(255, mask=transparent)
        indexed.info['transparency'] = 255
        result.append(indexed)
    return result


def inspect_animation(path: Path) -> dict:
    durations = []
    with Image.open(path) as image:
        frame_count = image.n_frames
        for index in range(frame_count):
            image.seek(index)
            image.load()
            durations.append(image.info.get('duration'))
        return {'path': str(path), 'format': image.format, 'frames': frame_count,
                'durations_ms': durations, 'total_duration_ms': sum(d or 0 for d in durations),
                'loop': image.info.get('loop'), 'sha256': file_hash(path)}


def contact_sheet(frames: list[Image.Image], durations: list[int], output: Path) -> None:
    sheet = Image.new('RGB', (1024, 560), (239, 241, 245))
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(frames):
        left, top = (index % 4) * 256, (index // 4) * 280
        # All eight native-size sprites have exactly the same display transform.
        for y in range(top + 32, top + 240, 16):
            for x in range(left + 32, left + 224, 16):
                colour = (215, 218, 225) if ((x-left-32)//16 + (y-top-32)//16) % 2 else (245, 246, 248)
                draw.rectangle((x, y, min(x+15, left+223), min(y+15, top+239)), fill=colour)
        sheet.paste(frame, (left + 32, top + 32), frame)
        draw.text((left + 12, top + 10), f'{index+1:02d}  {durations[index]} ms', fill=(22, 25, 31))
        draw.text((left + 12, top + 252), '192x208 / fixed body', fill=(60, 65, 74))
    sheet.save(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=DEFAULT_PLAN)
    parser.add_argument('--raw-dir', type=Path, help='Override job output_file locations with frame-01.png through frame-08.png')
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--expected-frames', type=int, default=8)
    parser.add_argument('--feather-radius', type=float, default=0, help='Only 0 is accepted: the supplied mask is already feathered')
    args = parser.parse_args()
    if args.expected_frames != 8:
        parser.error('This stable idle preview requires exactly 8 genuinely generated frames')
    if args.feather_radius != 0:
        parser.error('The supplied mask owns feathering; this assembler must not feather it again')
    plan_path = args.plan.expanduser().resolve()
    plan = json.loads(plan_path.read_text(encoding='utf-8-sig'))
    if plan.get('sway_px', 0) != 0:
        parser.error('This first QA preview supports sway_px=0 only; body pixels must be exact')
    canonical_path = resolve_input(plan['canonical'], plan_path)
    mask_path = resolve_input(plan['mask'], plan_path)
    jobs = sorted(plan.get('jobs', []), key=lambda job: job['index'])
    if len(jobs) != 8 or [job['index'] for job in jobs] != list(range(1, 9)):
        raise ValueError('The generation plan must contain exactly indexed jobs 1 through 8')
    durations = plan.get('durations_ms') or [job.get('duration_ms', DEFAULT_DURATIONS[index]) for index, job in enumerate(jobs)]
    if len(durations) != 8 or any(not isinstance(d, int) or d <= 0 or d % 10 for d in durations):
        raise ValueError('Eight positive integer durations in multiples of 10ms are required for exact GIF timing')
    lower_y = int(plan.get('lower_body_fixed_from_y', 700))
    if lower_y != 700:
        raise ValueError('Stable idle QA requires lower_body_fixed_from_y=700')
    raw_paths = [(args.raw_dir.expanduser().resolve() / f'frame-{index:02d}.png') if args.raw_dir else resolve_input(job['output_file'], plan_path)
                 for index, job in enumerate(jobs, 1)]
    missing = [str(path) for path in [canonical_path, mask_path, *raw_paths] if not path.is_file()]
    if missing:
        raise SystemExit('Missing inputs; no partial preview written:\n' + '\n'.join(missing))
    canonical = rgba(canonical_path)
    mask = rgba(mask_path)
    weight = ImageChops.invert(mask.getchannel('A'))
    if weight.crop((0, lower_y, 1024, 1024)).getbbox() is not None:
        raise ValueError('Mask allows lower-body editing at y>=700; repair the mask before assembly')
    # The generated image supplies RGB only. Original alpha remains authoritative
    # so model background edits cannot change the character silhouette.
    canonical_support = canonical.getchannel('A').point(lambda value: 255 if value else 0)
    weight = ImageChops.multiply(weight, canonical_support)
    face_support = weight.point(lambda value: 255 if value else 0)
    face_bbox = face_support.getbbox()
    if face_bbox is None:
        raise ValueError('The face mask has no editable character pixels')
    registered_sources = [generated_face_source(path) for path in raw_paths]
    raw_images = [item[0] for item in registered_sources]
    for path, generated in zip(raw_paths, raw_images):
        transparent_face = generated.getchannel('A').point(lambda a: 255 if a < 250 else 0)
        strong_edit = weight.point(lambda a: 255 if a >= 128 else 0)
        if ImageChops.multiply(transparent_face, strong_edit).getbbox() is not None:
            raise ValueError(f'{path}: generated editable face contains transparent holes')
    frames = []
    for generated in raw_images:
        frame = Image.composite(generated, canonical, weight)
        frame.putalpha(canonical.getchannel('A'))
        frames.append(frame)
    output = args.output_dir.expanduser().resolve()
    if output == args.raw_dir or output in raw_paths:
        raise ValueError('Output directory cannot replace raw generated inputs')
    full_dir, native_dir = output / 'processed', output / 'frames-192'
    full_dir.mkdir(parents=True, exist_ok=True)
    native_dir.mkdir(parents=True, exist_ok=True)
    native = [native_cell(frame) for frame in frames]
    native_canonical = native_cell(canonical)
    native_canonical.save(output / 'canonical-192.png')
    protected = ImageChops.invert(face_support)
    canonical_bbox = canonical.getchannel('A').getbbox()
    native_bbox = native_canonical.getchannel('A').getbbox()
    canonical_lower = canonical.crop((0, lower_y, 1024, 1024))
    native_lower_y = math.ceil(8 + lower_y * 192 / 1024)
    records = []
    faces = []
    raw_hashes = []
    for index, (frame, small, path, job, generated) in enumerate(zip(frames, native, raw_paths, jobs, raw_images), 1):
        full_path, native_path = full_dir / f'frame-{index:02d}.png', native_dir / f'frame-{index:02d}.png'
        frame.save(full_path)
        small.save(native_path)
        face = masked_face(frame, face_support)
        faces.append(face)
        source_hash = file_hash(path)
        raw_hashes.append(source_hash)
        record = {
            'index': index, 'expression': job.get('expression', ''), 'duration_ms': durations[index-1],
            'generated_source': str(path), 'generated_source_sha256': source_hash,
            'generated_canvas_size': list(registered_sources[index-1][1]),
            'generated_face_canvas_registration': {'output_size': [1024, 1024], 'method': 'uniform full-canvas resampling only; no character bbox fitting'},
            'generation_status_in_plan': job.get('status'),
            'prompt_file': job.get('prompt_file'),
            'processed': str(full_path), 'processed_sha256': file_hash(full_path),
            'native_frame': str(native_path), 'native_sha256': file_hash(native_path),
            'face_sha256': image_hash(face),
            'generated_face_sha256': image_hash(masked_face(generated, face_support)),
            'face_changed_pixels_from_canonical': differing_pixels(face, masked_face(canonical, face_support)),
            'outside_face_changed_pixels': differing_pixels(masked_face(frame, protected), masked_face(canonical, protected)),
            'lower_body_changed_pixels': differing_pixels(frame.crop((0, lower_y, 1024, 1024)), canonical_lower),
            'native_lower_body_changed_pixels': differing_pixels(small.crop((0, native_lower_y, 192, 208)), native_canonical.crop((0, native_lower_y, 192, 208))),
            'alpha_exact': ImageChops.difference(frame.getchannel('A'), canonical.getchannel('A')).getbbox() is None,
            'bbox': frame.getchannel('A').getbbox(), 'native_bbox': small.getchannel('A').getbbox(),
            'foot_baseline': (frame.getchannel('A').getbbox() or (0,0,0,0))[3] - 1,
            'native_foot_baseline': (small.getchannel('A').getbbox() or (0,0,0,0))[3] - 1,
        }
        prompt_path = resolve_input(job['prompt_file'], plan_path) if job.get('prompt_file') else None
        if prompt_path and prompt_path.is_file():
            record['prompt_sha256'] = file_hash(prompt_path)
        records.append(record)
    adjacent = []
    for index, face in enumerate(faces):
        next_face = faces[(index + 1) % len(faces)]
        diff = ImageChops.difference(face, next_face).convert('RGB').crop(face_bbox)
        adjacent.append({'from': index + 1, 'to': (index+1) % 8 + 1,
                         'changed_face_pixels': differing_pixels(face, next_face),
                         'face_bbox_mean_absolute_rgb_difference': sum(ImageStat.Stat(diff).mean)/3})
    previews = [frame.resize((512, 512), Image.Resampling.LANCZOS) for frame in frames]
    webp = output / 'idle-stable-preview.webp'
    previews[0].save(webp, save_all=True, append_images=previews[1:], duration=durations, loop=0, lossless=True, quality=100, method=6, exact=True)
    gif = output / 'idle-stable-preview.gif'
    gif_frames = gif_palette_frames(previews)
    gif_frames[0].save(gif, save_all=True, append_images=gif_frames[1:], duration=durations, loop=0,
                       transparency=255, disposal=2, optimize=False)
    contact_path = output / 'idle-stable-contact.png'
    contact_sheet(native, durations, contact_path)
    animations = {'webp': inspect_animation(webp), 'gif': inspect_animation(gif)}
    errors = []
    for record in records:
        for field in ['outside_face_changed_pixels', 'lower_body_changed_pixels', 'native_lower_body_changed_pixels']:
            if record[field] != 0:
                errors.append(f"Frame {record['index']}: {field}={record[field]}")
        if not record['alpha_exact'] or record['bbox'] != canonical_bbox or record['native_bbox'] != native_bbox:
            errors.append(f"Frame {record['index']}: silhouette or bbox changed")
    unique_faces = len({record['face_sha256'] for record in records})
    if unique_faces != 8:
        errors.append(f'Only {unique_faces}/8 distinct assembled facial hashes')
    if len(set(raw_hashes)) != 8:
        errors.append(f'Only {len(set(raw_hashes))}/8 distinct generated input file hashes')
    for kind, animation in animations.items():
        if animation['frames'] != 8:
            errors.append(f'{kind} stores {animation["frames"]} frames instead of 8; no artificial frame differences were added')
        if animation['durations_ms'] != durations:
            errors.append(f'{kind} encoded timing differs from generation plan')
    qa = {
        'ok': not errors, 'kind': 'stable_idle_facial_preview', 'created_at': datetime.now(timezone.utc).isoformat(),
        'native_pet_package': False, 'visual_qa': 'pending independent review; hashes cannot verify correct eyelids or natural expression',
        'errors': errors, 'warnings': ['First preview intentionally has no sway; complete body and hair retain original pixels.'],
        'canonical': str(canonical_path), 'canonical_sha256': file_hash(canonical_path),
        'mask': str(mask_path), 'mask_sha256': file_hash(mask_path), 'editable_bbox': face_bbox,
        'mask_semantics': 'weight=255-mask_alpha; supplied feathering used unchanged; generated RGB only; canonical alpha exact',
        'generation_plan': str(plan_path), 'generation_plan_sha256': file_hash(plan_path),
        'source_art': plan.get('source'), 'source_shared_transform': plan.get('shared_transform'),
        'assembly': {'method': 'canonical body preserved pixel-for-pixel, genuine generated expression RGB composited only through supplied face mask',
                     'face_art_drawn_by_script': False, 'per_frame_registration': False, 'per_frame_bbox_fit': False,
                     'per_frame_full_resolution_resize': False, 'extra_mask_feathering': False, 'sway_px': 0,
                     'full_size': [1024,1024], 'native_size': [192,208],
                     'native_transform': {'scale': 192/1024, 'offset': [0,8], 'resampler': 'LANCZOS'},
                     'preview_transform': {'scale': 0.5, 'resampler': 'LANCZOS'},
                     'lower_body_fixed_from_y': lower_y, 'native_lower_body_fixed_from_y': native_lower_y,
                     'script': str(Path(__file__).resolve()), 'script_sha256': file_hash(Path(__file__))},
        'checks': {'eight_input_files': True, 'distinct_generated_input_hashes': len(set(raw_hashes)),
                   'distinct_facial_frame_hashes': unique_faces,
                   'outside_face_exact_in_all_frames': all(r['outside_face_changed_pixels'] == 0 for r in records),
                   'lower_body_exact_in_all_frames': all(r['lower_body_changed_pixels'] == 0 for r in records),
                   'native_lower_body_exact_in_all_frames': all(r['native_lower_body_changed_pixels'] == 0 for r in records),
                   'silhouette_and_bbox_equal_in_all_frames': all(r['bbox'] == canonical_bbox and r['alpha_exact'] for r in records),
                   'foot_baseline_equal_in_all_frames': len({r['foot_baseline'] for r in records}) == 1,
                   'native_bbox_equal_in_all_frames': all(r['native_bbox'] == native_bbox for r in records)},
        'durations_ms': durations, 'total_duration_ms': sum(durations), 'frames': records,
        'adjacent_face_differences_including_loop': adjacent, 'animations': animations, 'contact_sheet': str(contact_path),
    }
    qa_path = output / 'qa.json'
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'ok': qa['ok'], 'qa': str(qa_path), 'contact_sheet': str(contact_path),
                      'webp': str(webp), 'gif': str(gif), 'checks': qa['checks'], 'errors': errors}, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
