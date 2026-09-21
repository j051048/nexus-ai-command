import { describe, expect, it } from "vitest";

describe("GlobalCommandBar", () => {
  it("loads the growth command registry without runtime reference errors", async () => {
    const commandBar = await import("@/components/layout/GlobalCommandBar");
    const commandBarEvents = await import("@/components/layout/commandBarEvents");

    expect(commandBar.GlobalCommandBar).toBeTypeOf("function");
    // The dispatch helpers live in their own module so the command bar stays
    // out of the entry chunk; both exports must keep working.
    expect(commandBarEvents.dispatchAIChatMessage).toBeTypeOf("function");
    expect(commandBarEvents.dispatchNewChat).toBeTypeOf("function");
  });
});
