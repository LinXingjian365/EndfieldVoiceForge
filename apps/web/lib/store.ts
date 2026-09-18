"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Character } from "./api";

interface StudioState {
  characterId: string;
  character: Character | null;
  surface: "smoke" | "paper";
  setCharacter: (c: Character) => void;
  setSurface: (s: "smoke" | "paper") => void;
}

export const useStudio = create<StudioState>()(
  persist(
    (set) => ({
      characterId: "typhoea",
      character: null,
      surface: "smoke",
      setCharacter: (c) => set({ character: c, characterId: c.id }),
      setSurface: (s) => set({ surface: s }),
    }),
    { name: "evf-studio", partialize: (s) => ({ characterId: s.characterId, surface: s.surface }) },
  ),
);
