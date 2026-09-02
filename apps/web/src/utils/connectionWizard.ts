export type ConnectablePlatform = "discord" | "twitch";

export type ConnectionWizardCopy = {
  platform: ConnectablePlatform;
  title: string;
  summary: string;
  actionLabel: string;
  resourceLabel: string;
  resourcePlaceholder: string;
  resourceHelp: string;
  preflightSteps: string[];
};

export const connectionWizardOptions: ConnectionWizardCopy[] = [
  {
    platform: "discord",
    title: "Connect Discord server",
    summary: "Verify native server ownership before Console stores the connection.",
    actionLabel: "Connect Discord server",
    resourceLabel: "Discord server ID",
    resourcePlaceholder: "123456789012345678",
    resourceHelp:
      "Use the Discord guild/server ID for a server where your linked Discord identity can administer the bot.",
    preflightSteps: [
      "Confirm you are signed in to Console.",
      "Link the matching Discord identity.",
      "Verify Discord server ownership through the Control API.",
      "Store only non-secret server metadata in Console.",
      "Write a lifecycle audit event for the organization.",
    ],
  },
  {
    platform: "twitch",
    title: "Connect Twitch channel",
    summary: "Verify broadcaster ownership before Console stores the connection.",
    actionLabel: "Connect Twitch channel",
    resourceLabel: "Twitch channel ID",
    resourcePlaceholder: "broadcaster-123",
    resourceHelp:
      "Use the Twitch broadcaster/channel ID for a channel your linked Twitch identity owns or can administer.",
    preflightSteps: [
      "Confirm you are signed in to Console.",
      "Link the matching Twitch identity.",
      "Verify Twitch broadcaster ownership through the Control API.",
      "Store only non-secret channel metadata in Console.",
      "Write a lifecycle audit event for the organization.",
    ],
  },
];

const wizardCopyByPlatform = new Map(
  connectionWizardOptions.map((option) => [option.platform, option]),
);

export function connectionWizardFor(platform: ConnectablePlatform): ConnectionWizardCopy {
  const copy = wizardCopyByPlatform.get(platform);
  if (copy === undefined) {
    throw new Error(`Unsupported connection wizard platform: ${platform}`);
  }
  return copy;
}
