import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import Sidebar from "../Sidebar";

// Complete sub-component stubbing for Sidebar to isolate its high-level A11y
vi.mock("../SearchPanel", () => ({ default: () => <div>Search</div> }));
vi.mock("../FavoriteAgents", () => ({ default: () => <div>Favorites</div> }));
vi.mock("../RecentAgents", () => ({ default: () => <div>Recent</div> }));
vi.mock("../ProfileSummary", () => ({ default: () => <div>Profile</div> }));
vi.mock("../../auth/AuthContext", () => ({ useAuth: () => ({ profile: {} }) }));
vi.mock("../../../contexts/UserContext", () => ({ useUser: () => ({ user: {} }) }));
vi.mock("lucide-react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("lucide-react")>();
  return { ...actual };
});

describe("Sidebar Accessibility", () => {
  it("should render with correct ARIA roles", () => {
    render(<Sidebar />);
    const nav = screen.getByRole("navigation");
    expect(nav).toBeInTheDocument();
    expect(nav).toHaveAttribute("aria-label", "主导航工具栏");
  });

  it("should have an accessible search region", () => {
    render(<Sidebar />);
    const searchRegion = screen.getByRole("search");
    expect(searchRegion).toBeInTheDocument();
  });
});
