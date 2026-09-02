export type ConnectablePlatform = "discord" | "twitch";

export type ConnectionWizardCopy = {
  platform: ConnectablePlatform;
  title: string;
  summary: string;
  actionLabel: string;
  candidateLabel: string;
  candidateHelp: string;
  preflightSteps: string[];
};

export const connectionWizardOptions: ConnectionWizardCopy[] = [
  {
    platform: "discord",
    title: "Connect Discord server",
    summary: "Verify native server ownership before Console stores the connection.",
    actionLabel: "Connect Discord server",
    candidateLabel: "Available Discord servers",
    candidateHelp:
      "Choose a server discovered through the linked Discord identity. Console never asks you to paste a server ID.",
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
    candidateLabel: "Available Twitch channels",
    candidateHelp:
      "Choose a channel discovered through the linked Twitch identity. Console never asks you to paste a channel ID.",
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
