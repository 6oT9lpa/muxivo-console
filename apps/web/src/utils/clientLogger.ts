type ClientLogContext = Record<string, string | number | boolean | undefined>;

function write(level: "info" | "warn" | "error", event: string, context: ClientLogContext = {}): void {
  // Keep client telemetry structured and avoid recording visitor message content in the browser log.
  console[level](`[Muxivo Console] ${event}`, context);
}

export const clientLogger = {
  info(event: string, context?: ClientLogContext): void {
    write("info", event, context);
  },
  warn(event: string, context?: ClientLogContext): void {
    write("warn", event, context);
  },
  error(event: string, context?: ClientLogContext): void {
    write("error", event, context);
  },
};
