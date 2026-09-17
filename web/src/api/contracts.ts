/** Backend list/detail contracts (Task 2). */
import type { MixListItem } from '../types';

/** Paginated backend shape: GET /mixes returns { items, total }. */
export interface MixListResponse {
  items: MixListItem[];
  total: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

/** True for the canonical paginated DTO { items: [], total: n }. */
export function isMixListResponse(raw: unknown): raw is MixListResponse {
  if (!isRecord(raw)) return false;
  return Array.isArray(raw.items) && typeof raw.total === 'number';
}

/**
 * Accept every known list shape:
 * - legacy flat array (older payloads + current e2e fixtures)
 * - paginated DTO { items, total }
 * - anything else -> honest empty page (never fabricated mixes)
 */
export function normalizeMixListResponse(raw: unknown): MixListResponse {
  if (Array.isArray(raw)) {
    return { items: raw as MixListItem[], total: raw.length };
  }
  if (isRecord(raw) && Array.isArray(raw.items)) {
    const items = raw.items as MixListItem[];
    const total = typeof raw.total === 'number' ? raw.total : items.length;
    return { items, total };
  }
  return { items: [], total: 0 };
}
