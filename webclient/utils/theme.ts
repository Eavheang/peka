// ponytail: stored per browser, not per account. Move to the user profile API if it must follow users across devices.
export const THEME_KEY = "peka_theme";

export const THEMES = [
  {
    id: "clay",
    label: "Clay",
    description: "Warm paper, the default",
    swatch: ["#f4f0e8", "#e96243", "#202523"],
  },
  {
    id: "daylight",
    label: "Daylight",
    description: "Bright and neutral",
    swatch: ["#faf9f6", "#6b8fc4", "#23262a"],
  },
  {
    id: "sage",
    label: "Sage",
    description: "Soft green, low glare",
    swatch: ["#f1f2eb", "#7d9a6f", "#222723"],
  },
  {
    id: "midnight",
    label: "Midnight",
    description: "Dark, easy at night",
    swatch: ["#16181a", "#f07a5c", "#0e1011"],
  },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];

export function getTheme(): ThemeId {
  const stored = localStorage.getItem(THEME_KEY);
  return THEMES.some((theme) => theme.id === stored) ? (stored as ThemeId) : "clay";
}

export function setTheme(theme: ThemeId) {
  localStorage.setItem(THEME_KEY, theme);
  document.documentElement.dataset.theme = theme;
}

// Runs before paint so the saved theme never flashes the default.
export const themeBootScript = `try{var t=localStorage.getItem("${THEME_KEY}");if(t)document.documentElement.dataset.theme=t}catch(e){}`;
