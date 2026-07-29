"""
versioning.py  Semantic version management.

Reads / writes a .version file (plain text, e.g. "1.0.0").
Supports bump strategies: major, minor, patch (default).
Also stamps version into generated docs at build time.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


BumpType = Literal["major", "minor", "patch"]


@dataclass
class Version:
      major: int
      minor: int
      patch: int

    def __str__(self) -> str:
              return f"{self.major}.{self.minor}.{self.patch}"

    def bumped(self, bump: BumpType = "patch") -> "Version":
              if bump == "major":
                            return Version(self.major + 1, 0, 0)
                        if bump == "minor":
                                      return Version(self.major, self.minor + 1, 0)
                                  return Version(self.major, self.minor, self.patch + 1)


def read_version(version_file: str) -> Version:
      """Read version from file. Returns 0.0.0 if file absent."""
    path = Path(version_file)
    if not path.exists():
              return Version(0, 0, 0)
    text = path.read_text(encoding="utf-8").strip()
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", text)
    if not m:
              raise ValueError(f"Invalid version format in {version_file!r}: {text!r}")
    return Version(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def write_version(version_file: str, version: Version) -> None:
      """Persist version back to file."""
    Path(version_file).write_text(str(version) + "\n", encoding="utf-8")


def resolve_version(
      version_file: str,
      bump: BumpType = "patch",
      explicit: str = None,
      logger=None,
) -> Version:
      """
          Determine the next version:
                - If --version X.Y.Z supplied, use it (validates format).
                      - Otherwise bump the stored version.
                          """
    if explicit:
              m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", explicit.strip())
        if not m:
                      raise ValueError(f"--version must be in X.Y.Z format, got: {explicit!r}")
                  v = Version(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if logger:
                      logger.info(f"Using explicit version: {v}")
                  return v

    current = read_version(version_file)
    next_v  = current.bumped(bump)
    if logger:
              logger.info(f"Version bump ({bump}): {current} -> {next_v}")
    return next_v
