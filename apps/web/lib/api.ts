const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8300";

export async function getHome() {
  const response = await fetch(`${API_URL}/api/home`, { cache: "no-store" });
  if (!response.ok) throw new Error("Unable to load SportsIntel data");
  return response.json();
}
