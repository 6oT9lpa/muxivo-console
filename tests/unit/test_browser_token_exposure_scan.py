from pathlib import Path

from scripts.browser_token_exposure_scan import scan_browser_facing_sources


def test_browser_token_exposure_scan_flags_platform_credential_fields(
    tmp_path: Path,
) -> None:
    source = tmp_path / "PlatformConnectionResponse.ts"
    source.write_text(
        "export type PlatformConnectionResponse = {\n"
        "  access_token: string;\n"
        "  refreshToken: string;\n"
        "};\n",
        encoding="utf-8",
    )

    findings = scan_browser_facing_sources((tmp_path,))

    assert {finding.marker for finding in findings} == {"access_token", "refreshToken"}


def test_browser_token_exposure_scan_allows_first_party_browser_tokens(
    tmp_path: Path,
) -> None:
    source = tmp_path / "PasswordRecovery.vue"
    source.write_text(
        "const token = recoveryToken.value;\n"
        "headers.set('X-CSRF-Token', csrfToken());\n"
        "const sessionTokenLabel = 'stored in an HttpOnly cookie';\n",
        encoding="utf-8",
    )

    assert scan_browser_facing_sources((tmp_path,)) == []


def test_browser_token_exposure_scan_supports_explicit_local_allow_comment(
    tmp_path: Path,
) -> None:
    source = tmp_path / "DocumentationSnippet.ts"
    source.write_text(
        "const example = 'access_token'; // muxivo-token-exposure-scan: allow\n",
        encoding="utf-8",
    )

    assert scan_browser_facing_sources((tmp_path,)) == []
