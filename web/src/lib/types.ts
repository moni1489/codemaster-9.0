// Типы ответов публичного API (зеркало pydantic-схем api/app/*/schemas.py)

export type Lang = "kk" | "ru" | "en";
export const LANGS: Lang[] = ["kk", "ru", "en"];
export type FileAccess = "open" | "restricted" | "closed";

export interface TranslationInfo {
  requested_lang: Lang;
  lang: Lang;
  status: "original" | "verified" | "machine" | "missing";
  is_fallback: boolean;
}

export interface Ref {
  id: string;
  number: string;
  cipher: string;
  title: string;
}

export interface BranchRef {
  id: string;
  slug: string;
  name: string;
}

export interface DocPage {
  id: string;
  page_no: number;
  url: string;
  thumb_url: string | null;
  width: number | null;
  height: number | null;
}

export interface DocumentListItem {
  id: string;
  cipher: string;
  title: string;
  summary: string | null;
  period_label: string | null;
  year_from: number | null;
  year_to: number | null;
  date_verified: boolean;
  category: string;
  doc_type: string;
  file_access: FileAccess;
  has_digital_copy: boolean;
  thumb_url: string | null;
  fund_number: string;
  is_personal_fund: boolean;
  is_demo: boolean;
  branch: BranchRef | null;
  translation: TranslationInfo;
}

export interface SearchResponse {
  items: DocumentListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  fuzzy: boolean;
  expanded_terms: string[];
}

export interface DocumentCard {
  id: string;
  cipher: string;
  title: string;
  summary: string | null;
  historical_note: string | null;
  period_label: string | null;
  date_from: string | null;
  date_to: string | null;
  year_from: number | null;
  year_to: number | null;
  date_verified: boolean;
  category: string;
  doc_type: string;
  language: string;
  sheets: string | null;
  sheets_count: number | null;
  storage_location: string | null;
  author_org: string | null;
  place: string | null;
  topic: string | null;
  tags: string[];
  file_access: FileAccess;
  access_conditions: string | null;
  has_digital_copy: boolean;
  pages: DocPage[];
  fund: Ref;
  inventory: Ref;
  case: Ref;
  branch: BranchRef | null;
  is_personal_fund: boolean;
  is_demo: boolean;
  translation: TranslationInfo;
}

export interface ChildItem {
  id: string;
  number: string;
  cipher: string;
  title: string;
  year_from: number | null;
  year_to: number | null;
  count: number | null;
}

export interface HierarchyNode {
  level: "fund" | "inventory" | "case";
  id: string;
  number: string;
  cipher: string;
  title: string;
  summary: string | null;
  historical_note: string | null;
  restricted_note: string | null;
  year_from: number | null;
  year_to: number | null;
  is_personal_fund: boolean;
  is_demo: boolean;
  branch: BranchRef | null;
  parents: Ref[];
  children: ChildItem[];
  documents: DocumentListItem[];
  translation: TranslationInfo;
}

export interface FacetValue {
  value: string;
  count: number;
  label: string | null;
}

export interface Facets {
  categories: FacetValue[];
  doc_types: FacetValue[];
  branches: FacetValue[];
  year_min: number | null;
  year_max: number | null;
  personal_funds: number;
}

export interface Branch {
  id: string;
  slug: string;
  type: "main" | "branch";
  name: string;
  short_name: string;
  locality: string;
  address: string;
  hours: string | null;
  hours_verified: boolean;
  director: string | null;
  phone: string | null;
  phones_extra: Record<string, string> | null;
  email: string | null;
  lat: number | null;
  lon: number | null;
  coords_verified: boolean;
  photo_url: string | null;
  description: string | null;
  translation: TranslationInfo;
}

export interface MemorialDate {
  id: string;
  year: number;
  month: number | null;
  day: number | null;
  date_label: string | null;
  title: string;
  source: string | null;
  translation: TranslationInfo;
}

export interface TodayResponse {
  date: string;
  exact: boolean;
  items: MemorialDate[];
}
