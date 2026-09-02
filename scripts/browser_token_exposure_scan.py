"""Guard browser-facing code against platform credential exposure.

Console may handle first-party browser session cookies, CSRF tokens and password
recovery tokens. It must not expose Discord/Twitch/platform access tokens,
refresh tokens, bot tokens or client secrets through frontend source or public
API contracts.
"""

import re
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCAN_ROOTS = (
    REPOSITORY_ROOT / "apps" / "web" / "src",
    REPOSITORY_ROOT / "apps" / "web" / "public",
    REPOSITORY_ROOT / "apps" / "api" / "src" / "muxivo_console" / "contracts",
    REPOSITORY_ROOT / "apps" / "api" / "src" / "muxivo_console" / "presentation",
)
SCANNED_SUFFIXES = {".json", ".js", ".py", ".ts", ".vue"}
ALLOW_COMMENT = "muxivo-token-exposure-scan: allow"
FORBIDDEN_IDENTIFIER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])("
    r"access_token|refresh_token|bot_token|activity_token|oauth_token|client_secret|"
    r"platform_access_token|platform_refresh_token|discord_access_token|"
    r"discord_refresh_token|twitch_access_token|twitch_refresh_token|"
    r"accessToken|refreshToken|botToken|activityToken|oauthToken|clientSecret|"
    r"platformAccessToken|platformRefreshToken|discordAccessToken|"
    r"discordRefreshToken|twitchAccessToken|twitchRefreshToken"
    r")(?![A-Za-z0-9_])"
)


@dataclass(frozen=True, slots=True)
class TokenExposureFinding:
    path: Path
    line_number: int
    marker: str
    line: str


def scan_browser_facing_sources(
    roots: tuple[Path, ...] = DEFAULT_SCAN_ROOTS,
) -> list[TokenExposureFinding]:
    findings: list[TokenExposureFinding] = []
    for root in roots:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in paths:
            if not path.is_file() or path.suffix not in SCANNED_SUFFIXES:
                continue
            findings.extend(_scan_file(path))
    return findings


def _scan_file(path: Path) -> list[TokenExposureFinding]:
    findings: list[TokenExposureFinding] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if ALLOW_COMMENT in line:
            continue
        for match in FORBIDDEN_IDENTIFIER_PATTERN.finditer(line):
            findings.append(
                TokenExposureFinding(
                    path=path,
                    line_number=line_number,
                    marker=match.group(1),
                    line=line.strip(),
                )
            )
    return findings


def main() -> int:
    findings = scan_browser_facing_sources()
    if findings:
        print("Browser token exposure scan failed:")
        for finding in findings:
            relative_path = finding.path.relative_to(REPOSITORY_ROOT)
            print(
                f"- {relative_path}:{finding.line_number}: "
                f"forbidden marker {finding.marker!r}: {finding.line}"
            )
        return 1
    print("Browser token exposure scan passed: no platform credential fields found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
