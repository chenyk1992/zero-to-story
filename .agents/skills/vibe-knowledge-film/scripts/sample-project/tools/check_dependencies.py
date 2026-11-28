"""Check sample-project prerequisites without installing or rendering anything."""
import argparse
import importlib
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = {
    'playwright.async_api': 'playwright',
    'PIL.Image': 'Pillow',
    'numpy': 'numpy',
    'scipy.signal': 'scipy',
    'imageio_ffmpeg': 'imageio-ffmpeg',
}
PROFILES = {
    'render': ('playwright.async_api', 'PIL.Image'),
    'analyze_music': ('numpy', 'scipy.signal', 'imageio_ffmpeg'),
    'encode': ('imageio_ffmpeg',),
    'verify': ('numpy', 'imageio_ffmpeg'),
    'all': tuple(PACKAGES),
}


def require_dependencies(parser, profile):
    """Run after argparse so --help works with the standard library alone."""
    if sys.version_info < (3, 9):
        parser.error('Python 3.9 or newer is required.')
    errors = []
    modules = {}
    for name in PROFILES[profile]:
        try:
            modules[name] = importlib.import_module(name)
        except (ImportError, OSError) as exc:
            errors.append(f'{PACKAGES[name]}: {exc}')
    if errors:
        parser.error('Missing or unusable dependencies: ' + '; '.join(errors)
                     + '\nIn sample-project, activate your virtual environment and run: '
                     'python -m pip install -r requirements.txt')
    if 'imageio_ffmpeg' in modules:
        try:
            ffmpeg = modules['imageio_ffmpeg'].get_ffmpeg_exe()
            subprocess.run([ffmpeg, '-version'], check=True, capture_output=True, timeout=15)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            parser.error(f'FFmpeg is unavailable: {exc}. Reinstall imageio-ffmpeg '
                         'or configure IMAGEIO_FFMPEG_EXE to a working executable.')


def require_chromium(parser, executable):
    if not os.path.isfile(executable) or not os.access(executable, os.X_OK):
        parser.error('Playwright Chromium is missing or not executable. '
                     'Run: python -m playwright install chromium')


def require_track(parser, track):
    path = ROOT / track
    if not path.is_file():
        parser.error(f'Approved audio file not found: {path}. '
                     'Provide a real track approved for this project; '
                     'music/approved-track.m4a is an example path, not bundled audio.')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=PROFILES, default='all')
    parser.add_argument('--track', help='Optional real, project-approved audio file to check')
    args = parser.parse_args()
    if args.track:
        require_track(parser, args.track)
    require_dependencies(parser, args.profile)
    if args.profile in ('render', 'all'):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            require_chromium(parser, playwright.chromium.executable_path)
    print(f'Prerequisites passed: {args.profile}. No media was generated; '
          'track rights, duration, browser system libraries and playback still need verification.')


if __name__ == '__main__':
    main()
