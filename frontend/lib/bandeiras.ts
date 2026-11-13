import * as Flags from "country-flag-icons/react/3x2";
import type { ComponentType, SVGProps } from "react";

// Bandeiras em SVG (pacote country-flag-icons, sem chamada externa), indexadas pelo codigo ISO de 2 letras.
const TODAS = Flags as unknown as Record<string, ComponentType<SVGProps<SVGSVGElement>>>;

export function bandeiraDe(iso2: string | null | undefined): ComponentType<SVGProps<SVGSVGElement>> | undefined {
  return iso2 ? TODAS[iso2.toUpperCase()] : undefined;
}