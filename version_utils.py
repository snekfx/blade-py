"""Version utilities for proper canonicalization and pre-release handling."""

from packaging import version as pkg_version


def canonicalize_version(ver_str):
    """
    Parse and canonicalize a version string.

    Returns a normalized packaging.version.Version object that treats
    equivalent versions like 2.0 and 2.0.0 as equal.

    Args:
        ver_str: Version string (e.g., "2.0", "2.0.0", "1.0.0-rc1")

    Returns:
        packaging.version.Version object or None if parsing fails
    """
    if not ver_str or ver_str == 'path' or 'workspace' in str(ver_str):
        return None

    # Clean up version string
    ver_str = str(ver_str).strip('"').split()[0]

    # Handle leading '='
    if ver_str.startswith('='):
        ver_str = ver_str[1:]

    try:
        # packaging.version.Version automatically normalizes versions
        # so 2.0 and 2.0.0 become the same object
        return pkg_version.parse(ver_str)
    except (pkg_version.InvalidVersion, ValueError):
        return None


def is_prerelease(ver_obj):
    """
    Check if a version is a pre-release (alpha, beta, rc, etc.).

    Args:
        ver_obj: packaging.version.Version object or version string

    Returns:
        True if pre-release, False otherwise
    """
    if isinstance(ver_obj, str):
        parsed = canonicalize_version(ver_obj)
        if not parsed:
            return False
        ver_obj = parsed

    if ver_obj is None:
        return False

    return ver_obj.is_prerelease


def filter_prerelease(versions):
    """
    Filter out pre-release versions from a list.

    Args:
        versions: List of packaging.version.Version objects or version strings

    Returns:
        List of stable versions only
    """
    stable = []
    for ver in versions:
        if isinstance(ver, str):
            parsed = canonicalize_version(ver)
            if parsed and not parsed.is_prerelease:
                stable.append(parsed)
        else:
            if ver and not ver.is_prerelease:
                stable.append(ver)
    return stable


def get_latest_stable(versions):
    """
    Get the latest stable (non-prerelease) version from a list.

    Args:
        versions: List of packaging.version.Version objects or version strings

    Returns:
        Latest stable version or None if no stable versions found
    """
    stable = filter_prerelease(versions)
    if not stable:
        return None

    # packaging.version.Version objects support comparison operators
    return max(stable)


def parse_version_metadata(ver_str):
    """
    Parse version metadata (e.g., v2.0.0-deprecated).

    Args:
        ver_str: Version string possibly with metadata

    Returns:
        Dict with 'version' (Version object) and 'metadata' (string) keys
    """
    if not ver_str:
        return {'version': None, 'metadata': None}

    ver_str = str(ver_str).strip()

    # Handle leading 'v'
    if ver_str.startswith('v'):
        ver_str = ver_str[1:]

    # Check for metadata after hyphen (outside of pre-release markers)
    # e.g., "2.0.0-deprecated" -> version="2.0.0", metadata="deprecated"
    # BUT "2.0.0-rc1" -> this is a pre-release, not metadata

    try:
        parsed = pkg_version.parse(ver_str)

        # If there's a local version identifier, that's our metadata
        if parsed.local:
            return {
                'version': parsed,
                'metadata': parsed.local
            }

        return {
            'version': parsed,
            'metadata': None
        }
    except (pkg_version.InvalidVersion, ValueError):
        return {'version': None, 'metadata': None}


def versions_equal(ver1, ver2):
    """
    Check if two versions are equivalent.

    Args:
        ver1, ver2: Version strings or packaging.version.Version objects

    Returns:
        True if versions are equal, False otherwise
    """
    # Parse if strings
    if isinstance(ver1, str):
        parsed1 = canonicalize_version(ver1)
    else:
        parsed1 = ver1

    if isinstance(ver2, str):
        parsed2 = canonicalize_version(ver2)
    else:
        parsed2 = ver2

    # Handle None cases
    if parsed1 is None or parsed2 is None:
        return parsed1 == parsed2

    # Use packaging's built-in equality (handles 2.0 == 2.0.0)
    return parsed1 == parsed2
