"""Version policy boundaries are independent of wall time and live APIs."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import check_dependencies as dep

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


class RuntimePolicyTests(unittest.TestCase):
    def releases(self, date: datetime) -> list[dict]:
        return [
            {"name": "Python 3.12.14", "release_date": "2026-01-01T00:00:00Z", "is_published": True, "pre_release": False},
            {"name": "Python 3.12.15", "release_date": date.isoformat(), "is_published": True, "pre_release": False},
            {"name": "Python 3.13.9", "release_date": "2026-01-01T00:00:00Z", "is_published": True, "pre_release": False},
        ]

    def test_grace_before_at_and_after_72_hours(self) -> None:
        published = NOW - timedelta(hours=72)
        for offset, expected in ((-1, "3.12.14"), (0, "3.12.15"), (1, "3.12.15")):
            with self.subTest(offset=offset):
                self.assertEqual(dep.required_runtime("python", self.releases(published), "3.12", NOW + timedelta(seconds=offset), 72), expected)

    def test_new_grace_release_does_not_hide_an_older_overdue_update(self) -> None:
        data = self.releases(NOW - timedelta(days=4))
        data.append({"name": "Python 3.12.16", "release_date": NOW.isoformat(), "is_published": True, "pre_release": False})
        self.assertEqual(dep.required_runtime("python", data, "3.12", NOW, 72), "3.12.15")
        with self.assertRaisesRegex(dep.PolicyViolation, "expired"):
            dep.check_runtime("python", "3.12.14", "3.12.15", "3.12")

    def test_prerelease_and_future_release_do_not_force_updates(self) -> None:
        data = self.releases(NOW + timedelta(days=1))
        data.append({"name": "Python 3.12.99rc1", "pre_release": True, "is_published": True})
        self.assertEqual(dep.required_runtime("python", data, "3.12", NOW, 72), "3.12.14")

    def test_node_published_at_has_an_exact_72_hour_boundary(self) -> None:
        data = [{"tag_name": "v24.1.0", "published_at": "2026-01-01T00:00:00Z"}, {"tag_name": "v24.2.0", "published_at": "2026-10-17T15:12:46Z"}, {"tag_name": "v26.0.0", "published_at": "2026-01-01T00:00:00Z"}]
        boundary = datetime(2026, 10, 20, 15, 12, 46, tzinfo=timezone.utc)
        self.assertEqual(dep.required_runtime("node", data, "24", boundary - timedelta(seconds=1), 72), "24.1.0")
        self.assertEqual(dep.required_runtime("node", data, "24", boundary, 72), "24.2.0")

    def test_series_migration_is_not_allowed(self) -> None:
        dep.check_runtime("python", "3.12.15", "3.12.14", "3.12")
        dep.check_runtime("node", "v24.22.0", "24.21.0", "24")
        for kind, actual, required, series in (("python", "3.13.1", "3.12.15", "3.12"), ("node", "26.0.0", "24.22.0", "24")):
            with self.assertRaisesRegex(dep.PolicyViolation, "outside"):
                dep.check_runtime(kind, actual, required, series)

    def test_official_source_failures_are_distinct(self) -> None:
        with patch.object(dep, "urlopen", side_effect=URLError("offline")):
            with self.assertRaises(dep.ReleaseSourceError):
                dep.fetch_releases("https://www.python.org/api/v2/downloads/release/")
        for data in ([], [{"name": "Python 3.12.15", "is_published": True, "release_date": "bad"}]):
            with self.assertRaises(dep.ReleaseSourceError):
                dep.required_runtime("python", data, "3.12", NOW, 72)

    def test_source_success_uses_mock_response(self) -> None:
        with patch.object(dep, "urlopen") as request:
            request.return_value.__enter__.return_value.read.return_value = json.dumps(self.releases(NOW)).encode()
            self.assertEqual(len(dep.fetch_releases("https://www.python.org/api/v2/downloads/release/")), 3)


class FixedPolicyTests(unittest.TestCase):
    def test_python_manifest_lock_and_installed_versions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest, lock = Path(directory) / "requirements.txt", Path(directory) / "requirements.lock"
            manifest.write_text("pytest==8.4.2\n")
            lock.write_text("pytest==8.4.2\npluggy==1.7.0\n")
            installed = {"pytest": "8.4.2", "pluggy": "1.7.0"}
            dep.check_python_lock(manifest, lock, installed)
            with self.assertRaisesRegex(dep.PolicyViolation, "installed"):
                dep.check_python_lock(manifest, lock, {**installed, "pytest": "9.0.0"})
            manifest.write_text("pytest==8.4.1\n")
            with self.assertRaisesRegex(dep.PolicyViolation, "manifest/lock"):
                dep.check_python_lock(manifest, lock, installed)
            manifest.write_text("pytest>=8\n")
            with self.assertRaisesRegex(dep.PolicyViolation, "exact"):
                dep.pins(manifest)

    def test_node_manifest_and_resolved_lock_versions(self) -> None:
        package = {"dependencies": {"example": "1.2.3"}}
        lock = {"lockfileVersion": 3, "packages": {"": package, "node_modules/example": {"version": "1.2.3"}}}
        dep.check_node_lock(package, lock)
        lock["packages"]["node_modules/example"]["version"] = "1.2.4"
        with self.assertRaisesRegex(dep.PolicyViolation, "resolved"):
            dep.check_node_lock(package, lock)
        with self.assertRaisesRegex(dep.PolicyViolation, "declarations"):
            dep.check_node_lock({"dependencies": {"example": "2.0.0"}}, lock)
        with self.assertRaises(dep.PolicyViolation):
            dep.check_node_lock(package, {})
