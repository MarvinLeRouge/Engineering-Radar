export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export function extractRepositoryId(idSlug: string): number | null {
  const match = /(\d+)$/.exec(idSlug)
  return match ? Number(match[1]) : null
}
