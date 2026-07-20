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

const DEFAULT_PLAYER_IMAGE = "/images/misc/default_player.png";

/** Local headshot path, or the default silhouette when missing. */
export function playerImageUrl(
  _year: number,
  _teamAbbr: string,
  player: string,
): string {
  const slug = slugifyPlayer(player);
  if (availableSet.has(slug)) return `/images/players/${slug}.png`;
  return DEFAULT_PLAYER_IMAGE;
}
