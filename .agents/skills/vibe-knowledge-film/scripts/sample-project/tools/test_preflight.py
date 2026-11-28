"""Regression checks that intentionally run without third-party site packages."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parent


class PrerequisiteTests(unittest.TestCase):
    def run_tool(self, script, *args):
        return subprocess.run([sys.executable, '-S', str(TOOLS / script), *args],
                              capture_output=True, text=True)

    def test_help_without_dependencies(self):
        for script in ('render.py', 'analyze_music.py', 'encode.py', 'verify.py',
                       'check_dependencies.py'):
            with self.subTest(script=script):
                result = self.run_tool(script, '--help')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('usage:', result.stdout)

    def test_missing_dependencies_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            track = Path(temp) / 'provided-track.wav'
            track.touch()  # Only existence is checked before the dependency failure.
            output = Path(temp) / 'not-created'
            commands = (
                ('render.py', 'frames', '--out', str(output)),
                ('analyze_music.py', str(track), str(output)),
                ('encode.py', '--track', str(track), '--out', str(output)),
                ('verify.py', str(output), '--track', str(track)),
                ('check_dependencies.py',),
            )
            for command in commands:
                with self.subTest(command=command[0]):
                    result = self.run_tool(*command)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('pip install -r requirements.txt', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
                    self.assertFalse(output.exists())

    def test_missing_track_is_actionable(self):
        with tempfile.TemporaryDirectory() as temp:
            missing = str(Path(temp) / 'missing.m4a')
            for command in (
                ('analyze_music.py', missing, str(Path(temp) / 'map.json')),
                ('encode.py', '--track', missing),
                ('verify.py', 'unused.mp4', '--track', missing),
                ('check_dependencies.py', '--track', missing),
            ):
                with self.subTest(command=command[0]):
                    result = self.run_tool(*command)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('Approved audio file not found', result.stderr)
                    self.assertIn('not bundled audio', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
