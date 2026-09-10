import { render, screen } from "@testing-library/react";

import { MarkdownResult } from "./MarkdownResult";

describe("MarkdownResult", () => {
  it("renders a grounded Markdown response and safe external link", () => {
    render(
      <MarkdownResult
        running={false}
        result={"# Finding\n\nSee [source](https://example.test)."}
      />,
    );
    expect(screen.getByRole("heading", { name: "Finding" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "source" })).toHaveAttribute(
      "rel",
      "noreferrer noopener",
    );
  });

  it("does not interpret raw HTML", () => {
    const { container } = render(
      <MarkdownResult running={false} result={'<img src=x onerror="alert(1)">'} />,
    );
    expect(container.querySelector("img")).not.toBeInTheDocument();
    expect(container).toHaveTextContent("<img src=x");
  });
});
