import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router";

import { createQueryClient } from "../lib/queryClient";
import { routes } from "../routes";

/** Toute l'application à une adresse (`/login`, `/account`…), avec le faux serveur de `mockApi`. */
export function renderApp(path = "/") {
  const queryClient = createQueryClient();
  // Nouvel essai sans attendre (pas de réseau) ; sinon les réglages de l'application.
  queryClient.setDefaultOptions({
    queries: { ...queryClient.getDefaultOptions().queries, retryDelay: 0 },
  });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const user = userEvent.setup();
  const view = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { ...view, user, router, queryClient };
}
