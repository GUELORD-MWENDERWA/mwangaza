// Cycle d'un appel d'IA fait pour une personne (IA.3 à IA.5) : un clic = une demande avec son
// `request_id` (rejouée, elle ne refait pas l'appel), puis lecture toutes les 2 s jusqu'à la fin ;
// la personne garde ou abandonne (`settle`), une fois. Rien n'est écrit par l'IA.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { uuidv7 } from "../../lib/ids";

const POLL_MS = 2000;
const WORKING = ["queued", "running"];

type Call = { id: string; state: string; refusal: string };

type Options<Read extends Call> = {
  name: string;
  start: (requestId: string) => Promise<Call>;
  read: (id: string) => Promise<Read>;
  settle?: (id: string, kept: boolean) => Promise<unknown>;
};

export function useAiCall<Read extends Call>({ name, start, read, settle }: Options<Read>) {
  const requestId = useRef(uuidv7());
  const [id, setId] = useState<string | null>(null);
  const ask = useMutation({
    mutationFn: () => start(requestId.current),
    onSuccess: (started) => setId(started.id),
  });
  const reading = useQuery({
    enabled: id !== null,
    queryKey: ["ai-call", name, id],
    queryFn: () => read(id!),
    // La réponse d'une question ne se lit qu'une fois : jamais de relecture au retour sur l'onglet.
    refetchOnWindowFocus: false,
    staleTime: Infinity,
    refetchInterval: (query) =>
      WORKING.includes(query.state.data?.state ?? "queued") ? POLL_MS : false,
  });
  const closing = useMutation({
    mutationFn: (kept: boolean) => settle!(id!, kept),
  });
  const state = reading.data?.state;
  return {
    ask,
    reading,
    closing,
    id,
    state,
    data: reading.data,
    waiting: ask.isPending || (id !== null && (state === undefined || WORKING.includes(state))),
    failed: state === "error" || state === "refused",
    /** Prépare une nouvelle demande (nouveau `request_id`). */
    reset: () => {
      requestId.current = uuidv7();
      setId(null);
      ask.reset();
    },
  };
}
