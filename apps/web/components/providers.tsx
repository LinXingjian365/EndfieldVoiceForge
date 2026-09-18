"use client";

import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, type Character } from "@/lib/api";
import { useStudio } from "@/lib/store";

function CharacterProvider({ children }: { children: React.ReactNode }) {
  const { characterId, setCharacter, surface } = useStudio();
  const q = useQuery({
    queryKey: ["character", characterId],
    queryFn: () => api<Character>(`/characters/${characterId}`),
  });
  useEffect(() => {
    if (q.data) setCharacter(q.data);
  }, [q.data, setCharacter]);
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.surface = surface;
    if (q.data) {
      root.style.setProperty("--operator-accent", q.data.accent);
      root.style.setProperty("--operator-accent-deep", q.data.accentDeep);
    }
  }, [q.data, surface]);
  return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 5_000, retry: 1, refetchOnWindowFocus: false } } }),
  );
  return (
    <QueryClientProvider client={client}>
      <CharacterProvider>{children}</CharacterProvider>
    </QueryClientProvider>
  );
}
