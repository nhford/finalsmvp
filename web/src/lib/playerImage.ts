import available from "@/data/playerImages.json";

const availableSet = new Set(available);

function slugifyPlayer(name: string): string {
  return name
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/['.]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");
}

/** Local headshot path when a cutout exists under /images/players/. */
export function playerImageUrl(
  _year: number,
  _teamAbbr: string,
  player: string,
): string | null {
  const slug = slugifyPlayer(player);
  if (!availableSet.has(slug)) return null;
  return `/images/players/${slug}.png`;
}
