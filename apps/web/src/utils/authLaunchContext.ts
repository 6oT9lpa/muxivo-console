export const DISCORD_ACTIVITY_AUTH_SOURCE = "discord-activity";

/**
 * Reads the non-secret launch marker used when Console is opened from
 * Discord Activity. The marker changes presentation only; OAuth state and
 * server-side authorization remain authoritative.
 */
export function isDiscordActivityAuthLaunch(
  url: URL | null = typeof window !== "undefined" ? new URL(window.location.href) : null,
): boolean {
  return url?.searchParams.get("source") === DISCORD_ACTIVITY_AUTH_SOURCE;
}
