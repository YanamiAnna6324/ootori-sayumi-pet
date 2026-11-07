"""Encode idle timing inside a WebP without altering the desktop client.

The currently installed client multiplies its static idle cell delays by six.
Its loader preserves animated WebP bytes. Each animation instant repeats the
same idle pose across columns 0..5, so the client's column changes cannot slow
or interrupt the encoded animation. Every other cell remains pixel-identical.
This is a client-specific draft, not a general static-atlas release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops

CELL = (192, 208)
SIZE = (1536, 2288)
CLIENT_BASE_DURATIONS = (280, 110, 110, 140, 140, 320)
CLIENT_MULTIPLIER = 6
ANIMATION_DURATIONS = (800, 80, 80, 120, 120, 800)
EXPECTED_SOURCE_SHA256 = '92cef3febf1e35e537ce106f6bc82212f0ce71a0efe109c0669c13e8f1a894f5'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def differences(a: Image.Image, b: Image.Image, *, visible_only: bool = False) -> int:
    channels = ImageChops.difference(a.convert('RGBA'), b.convert('RGBA')).split()
    merged = channels[0]
    for channel in channels[1:3]:
        merged = ImageChops.lighter(merged, channel)
    if visible_only:
        visible = ImageChops.lighter(a.getchannel('A'), b.getchannel('A'))
        visible = visible.point(lambda value: 255 if value else 0)
        merged = ImageChops.multiply(merged, visible)
    merged = ImageChops.lighter(merged, channels[3])
    return sum(merged.histogram()[1:])


def hidden_rgb_changes(a: Image.Image, b: Image.Image) -> int:
    rgb = ImageChops.difference(a.convert('RGB'), b.convert('RGB')).split()
    merged = ImageChops.lighter(ImageChops.lighter(rgb[0], rgb[1]), rgb[2])
    transparent_a = a.getchannel('A').point(lambda value: 255 if value == 0 else 0)
    transparent_b = b.getchannel('A').point(lambda value: 255 if value == 0 else 0)
    merged = ImageChops.multiply(merged, ImageChops.multiply(transparent_a, transparent_b))
    return sum(merged.histogram()[1:])


def box(column: int, row: int = 0) -> tuple[int, int, int, int]:
    return (column * CELL[0], row * CELL[1],
            (column + 1) * CELL[0], (row + 1) * CELL[1])


def encoded(path: Path) -> tuple[list[Image.Image], list[int], int]:
    frames, durations = [], []
    with Image.open(path) as source:
        loop = source.info.get('loop')
        for index in range(source.n_frames):
            source.seek(index)
            source.load()
            frames.append(source.convert('RGBA').copy())
            durations.append(source.info['duration'])
    return frames, durations, loop


def save_animation(frames: list[Image.Image], path: Path,
                   durations: tuple[int, ...]) -> None:
    frames[0].save(path, format='WEBP', save_all=True,
                   append_images=frames[1:], duration=durations, loop=0,
                   lossless=True, quality=100, method=6, exact=True,
                   minimize_size=False, kmin=1, kmax=1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--atlas', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    source_path, output = args.atlas.resolve(), args.output_dir.resolve()
    repo_root = Path(__file__).resolve().parents[1]
    if digest(source_path) != EXPECTED_SOURCE_SHA256:
        raise SystemExit('Source atlas differs from the approved installed idle.')
    if output.exists():
        raise SystemExit('Choose a new output folder; previous artifacts are preserved.')
    with Image.open(source_path) as source:
        if source.size != SIZE or source.n_frames != 1 or source.format != 'WEBP':
            raise SystemExit('Expected the approved static v2 atlas.')
        original = source.convert('RGBA')
    cells = [original.crop(box(column)) for column in range(6)]
    if differences(cells[0], cells[-1]):
        raise SystemExit('Source idle endpoints do not match.')
    if original.getchannel('A').crop(box(7)).getbbox():
        raise SystemExit('Reserved idle column 7 must be empty.')
    frames = []
    for cell in cells:
        frame = original.copy()
        for column in range(6):
            frame.paste(cell, (column * CELL[0], 0))
        frames.append(frame)
    output.mkdir(parents=True)
    atlas_path = output / 'spritesheet.webp'
    preview_path = output / 'native-idle-preview.webp'
    save_animation(frames, atlas_path, ANIMATION_DURATIONS)
    save_animation(cells, preview_path, ANIMATION_DURATIONS)

    decoded, delays, loop = encoded(atlas_path)
    preview_frames, preview_delays, preview_loop = encoded(preview_path)
    if delays != list(ANIMATION_DURATIONS) or loop != 0 or len(decoded) != 6:
        raise SystemExit('Atlas encoding changed the intended six-slot timeline.')
    if preview_delays != delays or preview_loop != 0:
        raise SystemExit('Preview timing differs from the animated atlas.')
    checked = 0
    non_idle_hidden_rgb_changes = []
    hidden_rgb_change_counts = []
    for index, actual in enumerate(decoded):
        if actual.size != SIZE or differences(actual, frames[index], visible_only=True):
            raise SystemExit(f'Lossless encoding changed animation instant {index}.')
        hidden_rgb_change_counts.append(differences(actual, frames[index]))
        if differences(preview_frames[index], actual.crop(box(0)), visible_only=True):
            raise SystemExit('Preview differs from decoded atlas.')
        hidden_changes_this_frame = 0
        for row in range(11):
            for column in range(8):
                cell = actual.crop(box(column, row))
                if row == 0 and column < 6:
                    if differences(cell, cells[index], visible_only=True):
                        raise SystemExit('Native idle columns are not synchronized.')
                else:
                    source_cell = original.crop(box(column, row))
                    if differences(cell, source_cell, visible_only=True):
                        raise SystemExit('A non-idle cell changed.')
                    hidden_changes_this_frame += hidden_rgb_changes(cell, source_cell)
                    checked += 1
        non_idle_hidden_rgb_changes.append(hidden_changes_this_frame)
    if differences(decoded[0], decoded[-1], visible_only=True):
        raise SystemExit('Loop endpoints do not match.')
    report = {
        'ok': True,
        'kind': 'encoded_native_idle_timing_draft',
        'installable': False,
        'source_atlas': 'installed-pet/spritesheet.webp',
        'source_atlas_sha256': digest(source_path),
        'output_atlas': report_path(atlas_path, repo_root),
        'output_atlas_sha256': digest(atlas_path),
        'script_sha256': digest(Path(__file__)),
        'dimensions': list(SIZE),
        'temporal_frames': len(decoded),
        'durations_ms': delays,
        'total_duration_ms': sum(delays),
        'previous_client_idle_duration_ms': sum(CLIENT_BASE_DURATIONS) * CLIENT_MULTIPLIER,
        'native_client_base_durations_ms': list(CLIENT_BASE_DURATIONS),
        'native_client_timing_multiplier': CLIENT_MULTIPLIER,
        'speedup_vs_client_static_idle': round(
            sum(CLIENT_BASE_DURATIONS) * CLIENT_MULTIPLIER
            / sum(ANIMATION_DURATIONS), 2),
        'client_program_or_configuration_modified': False,
        'all_idle_columns_show_the_same_phase': True,
        'all_other_cells_alpha_and_visible_rgb_identical': True,
        'hidden_rgb_changed_pixels_in_non_idle_cells_by_frame': non_idle_hidden_rgb_changes,
        'non_idle_cell_comparisons': checked,
        'neutral_frame_unchanged': True,
        'reserved_column_7_transparent': True,
        'loop_endpoints_pixel_identical': True,
        'alpha_and_all_visible_rgb_preserved': True,
        'hidden_rgb_changes_under_zero_alpha_by_frame': hidden_rgb_change_counts,
        'new_artwork_generated': False,
        'preview': report_path(preview_path, repo_root),
        'preview_sha256': digest(preview_path),
        'preview_matches_decoded_atlas': True,
        'runtime_visual_validation': 'pending',
        'limitations': [
            'Client-specific animated WebP draft, not an officially documented timing option.',
            'Animated images keep playing when a client selects a static idle cell; reduced-motion stillness is not preserved.',
            'Other pet states are retained from the existing unfinished draft.',
        ],
    }
    (output / 'qa.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
