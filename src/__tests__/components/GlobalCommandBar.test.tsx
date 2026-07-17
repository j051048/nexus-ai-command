import { describe, expect, it } from "vitest";

describe("GlobalCommandBar", () => {
  it("loads the growth command registry without runtime reference errors", async () => {
    const commandBar = await import("@/components/layout/GlobalCommandBar");

    expect(commandBar.GlobalCommandBar).toBeTypeOf("function");
    expect(commandBar.dispatchAIChatMessage).toBeTypeOf("function");
  });
});
