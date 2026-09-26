import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { CodeInput } from "./code-input";

function Harness() {
  const [value, setValue] = useState("");
  return <CodeInput aria-label="Code" value={value} onValueChange={setValue} />;
}

describe("code à 6 cases", () => {
  it("un seul vrai champ : collage du code avec espace, chiffres seulement, 6 au plus", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const input = screen.getByLabelText("Code") as HTMLInputElement;

    await user.click(input);
    await user.paste("876 157");
    expect(input.value).toBe("876157");

    await user.clear(input);
    await user.type(input, "12a3456789");
    expect(input.value).toBe("123456");
    expect(input.autocomplete).toBe("one-time-code");
  });

  it("retour arrière efface le dernier chiffre", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const input = screen.getByLabelText("Code") as HTMLInputElement;

    await user.type(input, "1234{Backspace}");

    expect(input.value).toBe("123");
  });
});
