import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OtpInput } from "../OtpInput";

describe("OtpInput", () => {
  it("renders 6 inputs", () => {
    render(<OtpInput value="" onChange={() => {}} />);
    expect(screen.getAllByRole("textbox")).toHaveLength(6);
  });

  it("calls onChange with concatenated value on typing", async () => {
    const onChange = vi.fn();
    render(<OtpInput value="" onChange={onChange} />);
    const inputs = screen.getAllByRole("textbox");
    await userEvent.type(inputs[0], "1");
    expect(onChange).toHaveBeenLastCalledWith("1");
  });

  it("accepts only digits", async () => {
    const onChange = vi.fn();
    render(<OtpInput value="" onChange={onChange} />);
    const inputs = screen.getAllByRole("textbox");
    await userEvent.type(inputs[0], "a");
    expect(onChange).not.toHaveBeenCalled();
  });
});
