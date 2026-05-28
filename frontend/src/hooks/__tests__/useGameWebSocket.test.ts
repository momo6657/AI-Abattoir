/**
 * useGameWebSocket hook 基础测试
 *
 * 注意：WebSocket 测试需要 mock 浏览器 WebSocket API
 */

describe("useGameWebSocket", () => {
  let originalWebSocket: typeof global.WebSocket;

  beforeAll(() => {
    originalWebSocket = global.WebSocket;
  });

  afterAll(() => {
    global.WebSocket = originalWebSocket;
  });

  it("exports useGameWebSocket", async () => {
    const mod = await import("../useGameWebSocket");
    expect(mod.useGameWebSocket).toBeDefined();
    expect(typeof mod.useGameWebSocket).toBe("function");
  });

  it("WebSocket class is available in test env", () => {
    // WebSocket is available via jsdom
    expect(typeof WebSocket).toBe("function");
  });
});
