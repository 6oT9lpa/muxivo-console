export type DemoChannelId = "general" | "server-logs" | "dev-blog";

export interface DemoMessage {
  id: string;
  channelId: DemoChannelId;
  author: string;
  avatar: string;
  content: string;
  timestamp: string;
  kind: "member" | "bot" | "log" | "dev";
  flagged?: boolean;
  removed?: boolean;
  pending?: boolean;
  classification?: DemoClassification;
  embed?: DemoLogEmbed;
}

export interface DemoClassification {
  labels: ReadonlyArray<string>;
  risk: number;
  action: string;
  executionPlan: ReadonlyArray<string>;
}

export interface DemoLogEmbed {
  accent: "violet" | "cyan" | "amber" | "rose";
  title: string;
  description: string;
  fields: ReadonlyArray<{ label: string; value: string }>;
}

export interface ModerationDemoDecision {
  risk_score: number;
  action: string;
  primary_label: string;
  labels: string[];
  execution_plan: string[];
}

export interface ModerationDemoEffect {
  action: string;
  removesMessage: boolean;
  restriction: "timeout" | "kick" | "ban" | null;
}
