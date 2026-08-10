import { describe, expect, it } from "vitest";
import { ConsoleApiError } from "../../api/consoleApi";
import {
  type BrowserSession,
  type BrowserSessionGateway,
  useBrowserSession,
} from "./useBrowserSession";

class StubGateway implements BrowserSessionGateway {
  revoked = false;

  constructor(
    private readonly currentResult: BrowserSession | Error,
    private readonly revocationError: Error | null = null,
  ) {}

  async current(): Promise<BrowserSession> {
    if (this.currentResult instanceof Error) throw this.currentResult;
    return this.currentResult;
  }

  async revokeCurrent(): Promise<void> {
    if (this.revocationError) throw this.revocationError;
    this.revoked = true;
  }
}

const session: BrowserSession = {
  user_id: "0198a6a2-7da7-7000-8000-000000000001",
  session_id: "0198a6a2-7da7-7000-8000-000000000002",
  assurance_level: "password",
};

describe("useBrowserSession", () => {
  it("restores an authenticated first-party Console session", async () => {
    const browserSession = useBrowserSession(new StubGateway(session));

    const state = await browserSession.refresh();

    expect(state).toBe("authenticated");
    expect(browserSession.session.value).toEqual(session);
  });

  it("treats a 401 response as an anonymous browser", async () => {
    const browserSession = useBrowserSession(
      new StubGateway(new ConsoleApiError(401, "Authentication required")),
    );

    const state = await browserSession.refresh();

    expect(state).toBe("anonymous");
    expect(browserSession.session.value).toBeNull();
  });

  it("does not turn service failures into a fake signed-out state", async () => {
    const browserSession = useBrowserSession(new StubGateway(new Error("network failure")));

    const state = await browserSession.refresh();

    expect(state).toBe("unavailable");
    expect(browserSession.session.value).toBeNull();
  });

  it("revokes the server session before transitioning to anonymous", async () => {
    const gateway = new StubGateway(session);
    const browserSession = useBrowserSession(gateway);
    await browserSession.refresh();

    const state = await browserSession.signOut();

    expect(gateway.revoked).toBe(true);
    expect(state).toBe("anonymous");
    expect(browserSession.session.value).toBeNull();
  });

  it("fails closed when server-side revocation cannot be confirmed", async () => {
    const browserSession = useBrowserSession(
      new StubGateway(session, new Error("revocation unavailable")),
    );
    await browserSession.refresh();

    const state = await browserSession.signOut();

    expect(state).toBe("unavailable");
    expect(browserSession.session.value).toBeNull();
  });
});
