import { render, screen } from "@testing-library/react";

import { FilePanel } from "./FilePanel";

it("renders generated files with an output-scoped download URL", () => {
  render(
    <FilePanel
      loading={false}
      files={[
        {
          name: "research report.md",
          type: "file",
          path: "session_thread-a/research report.md",
          size: 2_048,
          mtime: 1_788_940_800,
        },
      ]}
    />,
  );
  expect(screen.getByText("research report.md")).toBeInTheDocument();
  expect(screen.getByText("2.0 KB")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Download research report.md" })).toHaveAttribute(
    "href",
    expect.stringContaining("path=session_thread-a%2Fresearch+report.md"),
  );
});
