#!/usr/bin/env python3
"""Integration tests for the tccs CLI.

Tests run the `./tccs` script in a temporary HOME directory so they never
touch the user's real ~/.tccs or ~/.claude directories.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TCCS = ROOT / "tccs"


def run_tccs(args, home, env_extra=None, input=None):
    """Run tccs with the given args and HOME directory."""
    env = os.environ.copy()
    env["HOME"] = str(home)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(TCCS)] + list(args),
        env=env,
        capture_output=True,
        text=True,
        input=input,
    )


class TestList(unittest.TestCase):
    def test_list_no_profiles(self):
        """tccs -l in a fresh home reports no active profile and hints."""
        home = tempfile.mkdtemp()
        try:
            result = run_tccs(["-l"], home)
            self.assertEqual(result.returncode, 0)
            self.assertIn("No active profile.", result.stdout)
            self.assertIn("Tip: create a JSON file", result.stderr)
        finally:
            shutil.rmtree(home)

    def test_list_active_profile(self):
        """tccs -l shows the active profile and its variables."""
        home = tempfile.mkdtemp()
        try:
            tccs_dir = Path(home) / ".tccs"
            tccs_dir.mkdir(mode=0o700)
            (tccs_dir / "llm_foo.json").write_text('{"KEY": "value"}\n')
            (tccs_dir / "llm.json").symlink_to("llm_foo.json")
            result = run_tccs(["-l"], home)
            self.assertEqual(result.returncode, 0)
            self.assertIn("Active profile: foo", result.stdout)
            self.assertIn("KEY=value", result.stdout)
        finally:
            shutil.rmtree(home)

class TestAddEdit(unittest.TestCase):
    def _fake_editor(self, home, content_json):
        """Create a fake editor script that overwrites the target file."""
        editor = Path(home) / "fake_editor.py"
        editor.write_text(
            '#!/usr/bin/env python3\n'
            'import sys\n'
            'with open(sys.argv[1], "w") as f:\n'
            '    f.write({!r})\n'.format(content_json)
        )
        editor.chmod(0o755)
        return editor

    def test_add_profile_with_editor(self):
        """tccs -a creates a profile from the edited JSON."""
        home = tempfile.mkdtemp()
        try:
            editor = self._fake_editor(home, '{"API_KEY": "secret"}\n')
            result = run_tccs(
                ["-a"], home,
                env_extra={"EDITOR": str(editor)},
                input="myprofile\nn\n",
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("Saved profile", result.stderr)
            profile = Path(home) / ".tccs" / "llm_myprofile.json"
            self.assertTrue(profile.exists())
            self.assertEqual(json.loads(profile.read_text()), {"API_KEY": "secret"})
        finally:
            shutil.rmtree(home)

    def test_add_profile_invalid_json(self):
        """tccs -a rejects invalid JSON and does not save."""
        home = tempfile.mkdtemp()
        try:
            editor = self._fake_editor(home, "not json")
            result = run_tccs(
                ["-a"], home,
                env_extra={"EDITOR": str(editor)},
                input="badprofile\nn\n",
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("Invalid JSON", result.stderr)
            profile = Path(home) / ".tccs" / "llm_badprofile.json"
            self.assertFalse(profile.exists())
        finally:
            shutil.rmtree(home)

    def test_edit_profile_with_editor(self):
        """tccs -e updates an existing profile."""
        home = tempfile.mkdtemp()
        try:
            tccs_dir = Path(home) / ".tccs"
            tccs_dir.mkdir(mode=0o700)
            (tccs_dir / "llm_myprofile.json").write_text('{"OLD": "value"}\n')
            editor = self._fake_editor(home, '{"NEW": "value"}\n')
            result = run_tccs(
                ["-e", "myprofile"], home,
                env_extra={"EDITOR": str(editor)},
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("Saved profile", result.stderr)
            profile = tccs_dir / "llm_myprofile.json"
            self.assertEqual(json.loads(profile.read_text()), {"NEW": "value"})
        finally:
            shutil.rmtree(home)

class TestSetup(unittest.TestCase):
    def test_setup_injects_shell_block(self):
        """tccs (no args) injects shell functions and creates the example profile."""
        home = tempfile.mkdtemp()
        try:
            result = run_tccs([], home, input="\n\n")
            self.assertEqual(result.returncode, 0)
            bashrc = Path(home) / ".bashrc"
            self.assertTrue(bashrc.exists())
            content = bashrc.read_text()
            self.assertIn("tccs-switch", content)
            self.assertIn("tccs-refresh", content)
            self.assertIn("# >>> tccs initialized v2 >>>", content)
            self.assertIn("# <<< tccs initialized v2 <<<", content)
            self.assertIn("tccs-env()", content)
            self.assertTrue((Path(home) / ".tccs" / "llm_example.json").exists())
        finally:
            shutil.rmtree(home)

    def test_setup_detects_outdated_block(self):
        """tccs warns when the shell block uses old flags and refuses to run."""
        home = tempfile.mkdtemp()
        try:
            bashrc = Path(home) / ".bashrc"
            old_block = (
                "# >>> tccs initialized >>>\n"
                'tccs-switch() { eval "$(tccs -s \"$1\")"; }\n'
                "# <<< tccs initialized <<<\n"
            )
            bashrc.write_text(old_block)
            result = run_tccs([], home, input="\n\n")
            self.assertEqual(result.returncode, 1)
            self.assertIn("outdated", result.stderr)
        finally:
            shutil.rmtree(home)

    def test_reinit_updates_outdated_block(self):
        """tccs -r replaces an outdated shell block with the current one."""
        home = tempfile.mkdtemp()
        try:
            bashrc = Path(home) / ".bashrc"
            old_block = (
                "# >>> tccs initialized >>>\n"
                'tccs-switch() { eval "$(tccs -s \"$1\")"; }\n'
                "# <<< tccs initialized <<<\n"
            )
            bashrc.write_text(old_block)
            result = run_tccs(["-r"], home, input="\n\n")
            self.assertEqual(result.returncode, 0)
            content = bashrc.read_text()
            self.assertIn("tccs-switch", content)
            self.assertNotIn('tccs -s "', content)
        finally:
            shutil.rmtree(home)

class TestConfig(unittest.TestCase):
    def test_list_reads_config_values(self):
        """tccs -l reads claude_path and sync_env from config.json."""
        home = tempfile.mkdtemp()
        try:
            tccs_dir = Path(home) / ".tccs"
            tccs_dir.mkdir(mode=0o700)
            config = {
                "claude_path": "/custom/.claude",
                "sync_env": False,
            }
            (tccs_dir / "config.json").write_text(json.dumps(config) + "\n")
            result = run_tccs(["-l"], home)
            self.assertEqual(result.returncode, 0)
            self.assertIn("Claude path: /custom/.claude", result.stdout)
            self.assertIn("Sync to settings.json: No", result.stdout)
        finally:
            shutil.rmtree(home)

    def test_setup_persists_config(self):
        """Interactive setup persists the chosen claude_path and sync_env."""
        home = tempfile.mkdtemp()
        try:
            result = run_tccs([], home, input="/custom\nn\n")
            self.assertEqual(result.returncode, 0)
            result = run_tccs(["-l"], home)
            self.assertIn("Claude path: /custom", result.stdout)
            self.assertIn("Sync to settings.json: No", result.stdout)
        finally:
            shutil.rmtree(home)

class TestCommands(unittest.TestCase):
    def _create_profile(self, home, name, data):
        """Create a profile file under the temp HOME."""
        tccs_dir = Path(home) / ".tccs"
        tccs_dir.mkdir(mode=0o700, exist_ok=True)
        (tccs_dir / "llm_{}.json".format(name)).write_text(json.dumps(data) + "\n")

    def test_show_profiles(self):
        """tccs -s lists profiles and marks the active one."""
        home = tempfile.mkdtemp()
        try:
            self._create_profile(home, "foo", {"A": "1"})
            self._create_profile(home, "bar", {"B": "2"})
            tccs_dir = Path(home) / ".tccs"
            (tccs_dir / "llm.json").symlink_to("llm_foo.json")
            result = run_tccs(["-s"], home)
            self.assertEqual(result.returncode, 0)
            self.assertIn("* foo", result.stdout)
            self.assertIn("  bar", result.stdout)
        finally:
            shutil.rmtree(home)

    def test_switch_profile(self):
        """tccs -w name activates the profile and prints exports."""
        home = tempfile.mkdtemp()
        try:
            self._create_profile(home, "foo", {"API": "secret"})
            result = run_tccs(["-w", "foo"], home)
            self.assertEqual(result.returncode, 0)
            self.assertIn("export API=secret", result.stdout)
            link = Path(home) / ".tccs" / "llm.json"
            self.assertTrue(link.is_symlink())
            self.assertEqual(os.readlink(str(link)), "llm_foo.json")
        finally:
            shutil.rmtree(home)

    def test_switch_invalid_name(self):
        """tccs -w rejects invalid profile names."""
        home = tempfile.mkdtemp()
        try:
            result = run_tccs(["-w", "bad name!"], home)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Invalid profile name", result.stderr)
        finally:
            shutil.rmtree(home)

    def test_switch_profile_not_found(self):
        """tccs -w reports missing profiles."""
        home = tempfile.mkdtemp()
        try:
            result = run_tccs(["-w", "missing"], home)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Profile not found", result.stderr)
        finally:
            shutil.rmtree(home)

    def test_delete_profile(self):
        """tccs -d removes a profile file."""
        home = tempfile.mkdtemp()
        try:
            self._create_profile(home, "foo", {"A": "1"})
            result = run_tccs(["-d", "foo"], home)
            self.assertEqual(result.returncode, 0)
            self.assertIn("Deleted profile: foo", result.stdout)
            self.assertFalse((Path(home) / ".tccs" / "llm_foo.json").exists())
        finally:
            shutil.rmtree(home)

    def test_delete_example_refused(self):
        """tccs -d example is not allowed."""
        home = tempfile.mkdtemp()
        try:
            result = run_tccs(["-d", "example"], home)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Cannot delete the example profile", result.stderr)
        finally:
            shutil.rmtree(home)


class TestSettingsJsonSync(unittest.TestCase):
    def _create_profile(self, home, name, data):
        """Create a profile file under the temp HOME."""
        tccs_dir = Path(home) / ".tccs"
        tccs_dir.mkdir(mode=0o700, exist_ok=True)
        (tccs_dir / "llm_{}.json".format(name)).write_text(json.dumps(data) + "\n")

    def _fake_editor(self, home, content_json):
        """Create a fake editor script that overwrites the target file."""
        editor = Path(home) / "fake_editor.py"
        editor.write_text(
            '#!/usr/bin/env python3\n'
            'import sys\n'
            'with open(sys.argv[1], "w") as f:\n'
            '    f.write({!r})\n'.format(content_json)
        )
        editor.chmod(0o755)
        return editor

    def test_switch_syncs_env_to_settings_json(self):
        """tccs -w writes profile env to ~/.claude/settings.json when sync_env=True."""
        home = tempfile.mkdtemp()
        try:
            claude_dir = Path(home) / ".claude"
            claude_dir.mkdir()
            settings = claude_dir / "settings.json"
            settings.write_text('{"enabledPlugins": ["foo"]}\n')

            self._create_profile(home, "foo", {"API": "secret", "URL": "http://x"})
            result = run_tccs(["-w", "foo"], home)
            self.assertEqual(result.returncode, 0)

            data = json.loads(settings.read_text())
            self.assertEqual(data["env"], {"API": "secret", "URL": "http://x"})
            self.assertEqual(data["enabledPlugins"], ["foo"])
        finally:
            shutil.rmtree(home)

    def test_switch_creates_settings_json_if_missing(self):
        """tccs -w creates settings.json if it doesn't exist."""
        home = tempfile.mkdtemp()
        try:
            self._create_profile(home, "foo", {"API": "secret"})
            result = run_tccs(["-w", "foo"], home)
            self.assertEqual(result.returncode, 0)

            settings = Path(home) / ".claude" / "settings.json"
            self.assertTrue(settings.exists())
            self.assertEqual(json.loads(settings.read_text())["env"], {"API": "secret"})
        finally:
            shutil.rmtree(home)

    def test_switch_does_not_touch_settings_when_sync_false(self):
        """tccs -w leaves settings.json alone when sync_env=False."""
        home = tempfile.mkdtemp()
        try:
            tccs_dir = Path(home) / ".tccs"
            tccs_dir.mkdir(mode=0o700)
            (tccs_dir / "config.json").write_text('{"sync_env": false}\n')

            claude_dir = Path(home) / ".claude"
            claude_dir.mkdir()
            settings = claude_dir / "settings.json"
            settings.write_text('{"env": {"OLD": "val"}, "other": 1}\n')

            self._create_profile(home, "foo", {"API": "secret"})
            result = run_tccs(["-w", "foo"], home)
            self.assertEqual(result.returncode, 0)

            data = json.loads(settings.read_text())
            self.assertEqual(data["env"], {"OLD": "val"})
            self.assertEqual(data["other"], 1)
        finally:
            shutil.rmtree(home)

    def test_delete_active_clears_settings_env(self):
        """tccs -d on active profile clears settings.json env when sync_env=True."""
        home = tempfile.mkdtemp()
        try:
            claude_dir = Path(home) / ".claude"
            claude_dir.mkdir()
            settings = claude_dir / "settings.json"
            settings.write_text('{"env": {"API": "secret"}, "other": 1}\n')

            self._create_profile(home, "foo", {"API": "secret"})
            tccs_dir = Path(home) / ".tccs"
            (tccs_dir / "llm.json").symlink_to("llm_foo.json")

            result = run_tccs(["-d", "foo"], home)
            self.assertEqual(result.returncode, 0)

            data = json.loads(settings.read_text())
            self.assertEqual(data["env"], {})
            self.assertEqual(data["other"], 1)
        finally:
            shutil.rmtree(home)

    def test_delete_active_no_touch_when_sync_false(self):
        """tccs -d on active profile leaves settings.json alone when sync_env=False."""
        home = tempfile.mkdtemp()
        try:
            tccs_dir = Path(home) / ".tccs"
            tccs_dir.mkdir(mode=0o700)
            (tccs_dir / "config.json").write_text('{"sync_env": false}\n')

            claude_dir = Path(home) / ".claude"
            claude_dir.mkdir()
            settings = claude_dir / "settings.json"
            settings.write_text('{"env": {"API": "secret"}, "other": 1}\n')

            self._create_profile(home, "foo", {"API": "secret"})
            (tccs_dir / "llm.json").symlink_to("llm_foo.json")

            result = run_tccs(["-d", "foo"], home)
            self.assertEqual(result.returncode, 0)

            data = json.loads(settings.read_text())
            self.assertEqual(data["env"], {"API": "secret"})
        finally:
            shutil.rmtree(home)

    def test_edit_active_syncs_to_settings(self):
        """tccs -e on active profile updates settings.json env when sync_env=True."""
        home = tempfile.mkdtemp()
        try:
            claude_dir = Path(home) / ".claude"
            claude_dir.mkdir()
            settings = claude_dir / "settings.json"
            settings.write_text('{"env": {"OLD": "val"}, "other": 1}\n')

            tccs_dir = Path(home) / ".tccs"
            tccs_dir.mkdir(mode=0o700)
            (tccs_dir / "llm_foo.json").write_text('{"OLD": "val"}\n')
            (tccs_dir / "llm.json").symlink_to("llm_foo.json")

            editor = self._fake_editor(home, '{"NEW": "val"}\n')
            result = run_tccs(
                ["-e", "foo"], home,
                env_extra={"EDITOR": str(editor)},
            )
            self.assertEqual(result.returncode, 0)

            data = json.loads(settings.read_text())
            self.assertEqual(data["env"], {"NEW": "val"})
            self.assertEqual(data["other"], 1)
        finally:
            shutil.rmtree(home)

    def test_edit_inactive_does_not_touch_settings(self):
        """tccs -e on inactive profile does not modify settings.json."""
        home = tempfile.mkdtemp()
        try:
            claude_dir = Path(home) / ".claude"
            claude_dir.mkdir()
            settings = claude_dir / "settings.json"
            settings.write_text('{"env": {"OLD": "val"}, "other": 1}\n')

            tccs_dir = Path(home) / ".tccs"
            tccs_dir.mkdir(mode=0o700)
            (tccs_dir / "llm_foo.json").write_text('{"OLD": "val"}\n')
            (tccs_dir / "llm_bar.json").write_text('{"OTHER": "val"}\n')
            (tccs_dir / "llm.json").symlink_to("llm_bar.json")

            editor = self._fake_editor(home, '{"NEW": "val"}\n')
            result = run_tccs(
                ["-e", "foo"], home,
                env_extra={"EDITOR": str(editor)},
            )
            self.assertEqual(result.returncode, 0)

            data = json.loads(settings.read_text())
            self.assertEqual(data["env"], {"OLD": "val"})
        finally:
            shutil.rmtree(home)


class TestEnv(unittest.TestCase):
    def _create_profile(self, home, name, data):
        """Create a profile file under the temp HOME."""
        tccs_dir = Path(home) / ".tccs"
        tccs_dir.mkdir(mode=0o700, exist_ok=True)
        (tccs_dir / "llm_{}.json".format(name)).write_text(json.dumps(data) + "\n")

    def test_env_prints_exports(self):
        """tccs -E prints export statements for the profile."""
        home = tempfile.mkdtemp()
        try:
            self._create_profile(home, "foo", {"API": "secret", "URL": "http://x"})
            result = run_tccs(["-E", "foo"], home)
            self.assertEqual(result.returncode, 0)
            self.assertIn("export API=secret", result.stdout)
            self.assertIn("export URL=http://x", result.stdout)
        finally:
            shutil.rmtree(home)

    def test_env_invalid_name(self):
        """tccs -E rejects invalid profile names."""
        home = tempfile.mkdtemp()
        try:
            result = run_tccs(["-E", "bad name!"], home)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Invalid profile name", result.stderr)
        finally:
            shutil.rmtree(home)

    def test_env_profile_not_found(self):
        """tccs -E reports missing profiles."""
        home = tempfile.mkdtemp()
        try:
            result = run_tccs(["-E", "missing"], home)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Profile not found", result.stderr)
        finally:
            shutil.rmtree(home)

    def test_env_does_not_update_symlink(self):
        """tccs -E does not create or change the active symlink."""
        home = tempfile.mkdtemp()
        try:
            self._create_profile(home, "foo", {"A": "1"})
            self._create_profile(home, "bar", {"B": "2"})
            tccs_dir = Path(home) / ".tccs"
            # Set active to foo first via -w
            run_tccs(["-w", "foo"], home)
            # Now env-source bar - should not change symlink
            result = run_tccs(["-E", "bar"], home)
            self.assertEqual(result.returncode, 0)
            link = tccs_dir / "llm.json"
            self.assertTrue(link.is_symlink())
            self.assertEqual(os.readlink(str(link)), "llm_foo.json")
        finally:
            shutil.rmtree(home)

    def test_env_does_not_create_symlink(self):
        """tccs -E does not create an active symlink if none exists."""
        home = tempfile.mkdtemp()
        try:
            self._create_profile(home, "foo", {"A": "1"})
            result = run_tccs(["-E", "foo"], home)
            self.assertEqual(result.returncode, 0)
            link = Path(home) / ".tccs" / "llm.json"
            self.assertFalse(link.exists())
        finally:
            shutil.rmtree(home)

    def test_env_does_not_touch_settings_json(self):
        """tccs -E leaves settings.json alone even when sync_env=True."""
        home = tempfile.mkdtemp()
        try:
            self._create_profile(home, "foo", {"API": "secret"})
            claude_dir = Path(home) / ".claude"
            claude_dir.mkdir()
            settings = claude_dir / "settings.json"
            settings.write_text('{"env": {"OLD": "val"}, "other": 1}\n')
            result = run_tccs(["-E", "foo"], home)
            self.assertEqual(result.returncode, 0)
            data = json.loads(settings.read_text())
            self.assertEqual(data["env"], {"OLD": "val"})
            self.assertEqual(data["other"], 1)
        finally:
            shutil.rmtree(home)

    def test_env_does_not_create_settings_json(self):
        """tccs -E does not create settings.json if it doesn't exist."""
        home = tempfile.mkdtemp()
        try:
            self._create_profile(home, "foo", {"API": "secret"})
            result = run_tccs(["-E", "foo"], home)
            self.assertEqual(result.returncode, 0)
            settings = Path(home) / ".claude" / "settings.json"
            self.assertFalse(settings.exists())
        finally:
            shutil.rmtree(home)


if __name__ == "__main__":
    unittest.main()
