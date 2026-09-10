import { render, screen } from "@testing-library/react";

import type { MonitorEvent } from "../types";
import { ActivityPanel } from "./ActivityPanel";

it("shows public execution metadata without rendering hidden reasoning fields", () => {
  const event: MonitorEvent = {
    type: "monitor_event",
    event: "assistant_call",
    message: "Delegating to assistant",
    data: {
      assistant_name: "network_search_agent",
      chain_of_thought: "private reasoning must stay hidden",
    },
    timestamp: "2026-09-09T08:00:00Z",
  };
  render(<ActivityPanel events={[event]} connectionStatus="connected" />);
  expect(screen.getByText("network_search_agent")).toBeInTheDocument();
  expect(screen.queryByText(/private reasoning/)).not.toBeInTheDocument();
});

