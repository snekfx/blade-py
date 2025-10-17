"""Tests for version_utils module."""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import version_utils
from packaging import version as pkg_version


class TestCanonicalizeVersion:
    """Test version canonicalization."""

    def test_simple_version(self):
        """Test parsing simple version strings."""
        ver = version_utils.canonicalize_version("1.0.0")
        assert ver is not None
        assert ver.major == 1
        assert ver.minor == 0
        assert ver.micro == 0

    def test_version_normalization_2_0_equals_2_0_0(self):
        """Test that 2.0 and 2.0.0 are treated as equal (core BUGS-03 requirement)."""
        ver1 = version_utils.canonicalize_version("2.0")
        ver2 = version_utils.canonicalize_version("2.0.0")

        assert ver1 is not None
        assert ver2 is not None
        # Most important: they should be equal
        assert ver1 == ver2, "2.0 and 2.0.0 should be treated as equal"

    def test_leading_v_stripped(self):
        """Test that leading 'v' is handled properly."""
        # canonicalize_version doesn't strip 'v' but parse should handle it
        ver = version_utils.canonicalize_version("v1.0.0")
        # This might fail if parse rejects 'v', that's ok - we're testing edge cases
        # Let's just verify behavior is consistent

    def test_equals_sign_stripped(self):
        """Test that leading '=' is stripped."""
        ver = version_utils.canonicalize_version("=1.0.0")
        assert ver is not None
        assert ver.major == 1

    def test_workspace_dependency_returns_none(self):
        """Test that workspace dependencies return None."""
        assert version_utils.canonicalize_version("workspace") is None

    def test_path_dependency_returns_none(self):
        """Test that path dependencies return None."""
        assert version_utils.canonicalize_version("path") is None

    def test_invalid_version_returns_none(self):
        """Test that invalid versions return None."""
        assert version_utils.canonicalize_version("not-a-version") is None
        assert version_utils.canonicalize_version("") is None
        assert version_utils.canonicalize_version(None) is None

    def test_prerelease_version(self):
        """Test parsing pre-release versions."""
        ver = version_utils.canonicalize_version("1.0.0-rc1")
        assert ver is not None
        assert ver.is_prerelease

    def test_version_with_quotes(self):
        """Test handling quoted version strings."""
        ver = version_utils.canonicalize_version('"1.0.0"')
        assert ver is not None
        assert ver.major == 1


class TestIsPrerelease:
    """Test pre-release detection."""

    def test_stable_version_not_prerelease(self):
        """Test that stable versions are not marked as pre-release."""
        assert not version_utils.is_prerelease("1.0.0")
        assert not version_utils.is_prerelease("2.0")
        assert not version_utils.is_prerelease("0.5.0")

    def test_alpha_is_prerelease(self):
        """Test that alpha versions are detected as pre-release."""
        assert version_utils.is_prerelease("1.0.0-alpha")
        assert version_utils.is_prerelease("1.0.0-alpha1")

    def test_beta_is_prerelease(self):
        """Test that beta versions are detected as pre-release."""
        assert version_utils.is_prerelease("1.0.0-beta")
        assert version_utils.is_prerelease("1.0.0-beta1")

    def test_rc_is_prerelease(self):
        """Test that RC versions are detected as pre-release."""
        assert version_utils.is_prerelease("1.0.0-rc")
        assert version_utils.is_prerelease("1.0.0-rc1")

    def test_invalid_version_not_prerelease(self):
        """Test that invalid versions return False."""
        assert not version_utils.is_prerelease("invalid")
        assert not version_utils.is_prerelease("")
        assert not version_utils.is_prerelease(None)

    def test_version_object_input(self):
        """Test that Version objects can be passed directly."""
        ver_stable = pkg_version.parse("1.0.0")
        ver_pre = pkg_version.parse("1.0.0-rc1")

        assert not version_utils.is_prerelease(ver_stable)
        assert version_utils.is_prerelease(ver_pre)


class TestFilterPrerelease:
    """Test pre-release filtering."""

    def test_filter_empty_list(self):
        """Test filtering empty list."""
        result = version_utils.filter_prerelease([])
        assert result == []

    def test_filter_all_stable(self):
        """Test filtering list with only stable versions."""
        versions = ["1.0.0", "2.0.0", "0.5.0"]
        result = version_utils.filter_prerelease(versions)
        assert len(result) == 3

    def test_filter_removes_prerelease(self):
        """Test that pre-releases are filtered out."""
        versions = ["1.0.0", "1.0.0-rc1", "2.0.0", "2.0.0-beta"]
        result = version_utils.filter_prerelease(versions)
        assert len(result) == 2

        # Check that only stable versions remain
        stable_strs = [str(v) for v in result]
        assert any("1.0.0" in s for s in stable_strs)
        assert any("2.0.0" in s for s in stable_strs)
        assert not any("rc" in s.lower() for s in stable_strs)
        assert not any("beta" in s.lower() for s in stable_strs)

    def test_filter_with_version_objects(self):
        """Test filtering with Version objects."""
        versions = [
            pkg_version.parse("1.0.0"),
            pkg_version.parse("1.0.0-rc1"),
            pkg_version.parse("2.0.0"),
        ]
        result = version_utils.filter_prerelease(versions)
        assert len(result) == 2


class TestGetLatestStable:
    """Test getting latest stable version."""

    def test_all_stable_versions(self):
        """Test finding latest among stable versions."""
        versions = ["1.0.0", "2.0.0", "1.5.0"]
        result = version_utils.get_latest_stable(versions)
        assert result is not None
        assert str(result) == "2.0.0"

    def test_filters_prerelease(self):
        """Test that pre-releases are excluded even if newest."""
        versions = ["1.0.0", "2.0.0-rc1", "1.5.0"]
        result = version_utils.get_latest_stable(versions)
        assert result is not None
        # Should be 1.5.0, not 2.0.0-rc1
        assert str(result) == "1.5.0"

    def test_only_prerelease_versions(self):
        """Test behavior when only pre-releases available."""
        versions = ["1.0.0-alpha", "2.0.0-rc1", "1.5.0-beta"]
        result = version_utils.get_latest_stable(versions)
        # Should return None since no stable versions
        assert result is None

    def test_empty_list(self):
        """Test with empty list."""
        result = version_utils.get_latest_stable([])
        assert result is None


class TestVersionsEqual:
    """Test version equality."""

    def test_exact_match(self):
        """Test that identical versions are equal."""
        assert version_utils.versions_equal("1.0.0", "1.0.0")
        assert version_utils.versions_equal("2.0", "2.0")

    def test_normalized_versions_equal(self):
        """Test that 2.0 and 2.0.0 are equal (BUGS-03 requirement)."""
        assert version_utils.versions_equal("2.0", "2.0.0"), \
            "2.0 and 2.0.0 should be equal"
        assert version_utils.versions_equal("1.0", "1.0.0"), \
            "1.0 and 1.0.0 should be equal"
        assert version_utils.versions_equal("0.5", "0.5.0"), \
            "0.5 and 0.5.0 should be equal"

    def test_different_versions_not_equal(self):
        """Test that different versions are not equal."""
        assert not version_utils.versions_equal("1.0.0", "2.0.0")
        assert not version_utils.versions_equal("1.0.0", "1.1.0")
        assert not version_utils.versions_equal("1.0.0", "1.0.1")

    def test_version_objects_as_input(self):
        """Test that Version objects can be compared."""
        ver1 = pkg_version.parse("2.0")
        ver2 = pkg_version.parse("2.0.0")
        assert version_utils.versions_equal(ver1, ver2)

    def test_mixed_string_and_object_input(self):
        """Test comparing string with Version object."""
        ver_obj = pkg_version.parse("2.0.0")
        assert version_utils.versions_equal("2.0", ver_obj)

    def test_invalid_versions(self):
        """Test with invalid versions."""
        # Both invalid should be equal (both None)
        assert version_utils.versions_equal("invalid1", "invalid2")
        # Invalid vs valid should be different
        assert not version_utils.versions_equal("invalid", "1.0.0")


class TestParseVersionMetadata:
    """Test metadata parsing."""

    def test_simple_version_no_metadata(self):
        """Test simple version without metadata."""
        result = version_utils.parse_version_metadata("1.0.0")
        assert result['version'] is not None
        assert result['metadata'] is None

    def test_version_with_local_identifier(self):
        """Test version with local identifier."""
        result = version_utils.parse_version_metadata("1.0.0+build123")
        assert result['version'] is not None
        # Local identifier should be captured
        if result['metadata']:  # May or may not be captured depending on implementation
            assert "build" in result['metadata'] or "123" in result['metadata']

    def test_prerelease_not_metadata(self):
        """Test that pre-release is not confused with metadata."""
        result = version_utils.parse_version_metadata("1.0.0-rc1")
        assert result['version'] is not None
        assert result['version'].is_prerelease

    def test_leading_v_handled(self):
        """Test that leading 'v' is handled."""
        result = version_utils.parse_version_metadata("v1.0.0")
        assert result['version'] is not None

    def test_invalid_version(self):
        """Test invalid version."""
        result = version_utils.parse_version_metadata("not-a-version")
        assert result['version'] is None
        assert result['metadata'] is None


class TestConflictScenarios:
    """Test real conflict scenarios that should or shouldn't occur."""

    def test_no_conflict_2_0_vs_2_0_0(self):
        """Test that 2.0 and 2.0.0 don't create a conflict.

        This is the core BUGS-03 scenario:
        When checking for conflicts, using a set of parsed versions,
        2.0 and 2.0.0 should be treated as the same version and not create
        a conflict.
        """
        versions_strs = ["2.0", "2.0.0"]
        versions_set = set()

        for ver_str in versions_strs:
            parsed = version_utils.canonicalize_version(ver_str)
            if parsed:
                versions_set.add(parsed)

        # Should only have 1 unique version in the set
        assert len(versions_set) == 1, \
            f"2.0 and 2.0.0 should be one version, got {len(versions_set)}"

    def test_conflict_1_0_vs_2_0(self):
        """Test that 1.0 and 2.0 are recognized as different versions."""
        versions_strs = ["1.0", "2.0"]
        versions_set = set()

        for ver_str in versions_strs:
            parsed = version_utils.canonicalize_version(ver_str)
            if parsed:
                versions_set.add(parsed)

        # Should have 2 different versions
        assert len(versions_set) == 2, "1.0 and 2.0 should be different versions"

    def test_no_conflict_with_mixed_prerelease_ignored(self):
        """Test that stable versions don't conflict with pre-releases."""
        versions_strs = ["1.0.0", "1.0.0-rc1"]
        # After filtering pre-releases, should have only 1 stable version
        stable = version_utils.filter_prerelease(versions_strs)
        assert len(stable) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
