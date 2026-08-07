import "server-only";

const API_URL =
  process.env.SPORTSINTEL_INTERNAL_API_URL ?? "http://localhost:8300";

export async function getHome() {
  const response = await fetch(`${API_URL}/api/home`, { cache: "no-store" });
  if (!response.ok) throw new Error("Unable to load SportsIntel data");
  return response.json();
}

export async function getGame(gameId: string) {
  const response = await fetch(`${API_URL}/api/games/${gameId}`, { cache: "no-store" });
  if (!response.ok) throw new Error("Unable to load game data");
  return response.json();
}

export async function getMlb() {
  const response = await fetch(`${API_URL}/api/mlb`, { cache: "no-store" });
  if (!response.ok) throw new Error("Unable to load MLB data");
  return response.json();
}

export async function getMlbGame(gameId: string) {
  const response = await fetch(`${API_URL}/api/mlb/${gameId}`, { cache: "no-store" });
  if (!response.ok) throw new Error("Unable to load MLB game");
  return response.json();
}

export async function getMlbResults(days = 7) {
  const response = await fetch(`${API_URL}/api/mlb/results?days=${days}`, { cache: "no-store" });
  if (!response.ok) throw new Error("Unable to load MLB results");
  return response.json();
}

export async function getSportsCatalog() {
  const response = await fetch(`${API_URL}/api/sports`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Unable to load sports catalog");
  }

  return response.json();
}

export async function getSportCapabilities(sport: string) {
  const response = await fetch(
    `${API_URL}/api/sports/${encodeURIComponent(sport)}/capabilities`,
    { cache: "no-store" },
  );

  if (!response.ok) {
    throw new Error(`Unable to load ${sport} capabilities`);
  }

  return response.json();
}

export async function getSport(sport: string) {
  const response = await fetch(
    `${API_URL}/api/sports/${encodeURIComponent(sport)}`,
    { cache: "no-store" },
  );

  if (!response.ok) {
    throw new Error(`Unable to load ${sport} data`);
  }

  return response.json();
}

export async function getNflReview() {
  const response = await fetch(`${API_URL}/api/sports/nfl/review`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Unable to load NFL readiness review");
  }

  return response.json();
}

export async function getNflCommandCenter() {
  const response = await fetch(`${API_URL}/api/sports/nfl/command-center`, { cache: "no-store" });
  if (!response.ok) throw new Error("Unable to load NFL Command Center");
  return response.json();
}

export async function getNflChanges(gameId: string) {
  try {
    const response = await fetch(
      `${API_URL}/api/sports/nfl/${encodeURIComponent(gameId)}/changes`,
      { cache: "no-store" },
    );

    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

export async function getNflGameContext(gameId: string) {
  try {
    const response = await fetch(
      `${API_URL}/api/sports/nfl/game/${encodeURIComponent(gameId)}/context`,
      { cache: "no-store" },
    );
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}
