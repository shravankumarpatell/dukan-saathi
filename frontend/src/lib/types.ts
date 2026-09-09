/** Hand-picked aliases over the generated OpenAPI types (src/lib/api-types.ts). */
import type { components } from "./api-types";

type S = components["schemas"];

export type TokenOut = S["TokenOut"];
export type MeOut = S["MeOut"];
export type CompanyOut = S["CompanyOut"];
export type CompanyIn = S["CompanyIn"];
export type BranchOut = S["BranchOut"];
export type BranchIn = S["BranchIn"];
export type UserOut = S["UserOut"];
export type UserIn = S["UserIn"];
export type RoleOut = S["RoleOut"];
export type RoleIn = S["RoleIn"];
export type FiscalYearOut = S["FiscalYearOut"];
export type AuditOut = S["AuditOut"];
export type AccountGroupOut = S["AccountGroupOut"];
export type LedgerOut = S["LedgerOut"];
export type LedgerIn = S["LedgerIn"];
export type VoucherOut = S["VoucherOut"];
export type VoucherIn = S["VoucherIn"];
export type VoucherLineOut = S["VoucherLineOut"];
export type QuickReceiptIn = S["QuickReceiptIn"];
export type PartyOut = S["PartyOut"];
export type PartyIn = S["PartyIn"];
export type ProjectOut = S["ProjectOut"];
export type ProductOut = S["ProductOut"];
export type ProductIn = S["ProductIn"];
export type UnitOut = S["UnitOut"];
export type BrandOut = S["BrandOut"];
export type CategoryOut = S["CategoryOut"];
export type GodownOut = S["GodownOut"];
export type BatchOut = S["BatchOut"];
export type StockJournalOut = S["StockJournalOut"];
export type StockJournalIn = S["StockJournalIn"];
export type ReservationOut = S["ReservationOut"];
export type SampleOut = S["SampleOut"];
export type TradeDocOut = S["TradeDocOut"];
export type TradeDocIn = S["TradeDocIn"];
export type TradeLineIn = S["TradeLineIn"];
export type TradeLineOut = S["TradeLineOut"];
export type TradeDocListOut = S["TradeDocListOut"];
export type TileCalcIn = S["TileCalcIn"];
export type TileCalcOut = S["TileCalcOut"];

export interface Paged<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  sum_grand_total?: string;
}

export type DocType =
  | "quotation"
  | "sales_order"
  | "delivery_challan"
  | "sales_invoice"
  | "sales_return"
  | "purchase_order"
  | "grn"
  | "purchase_bill"
  | "purchase_return";

export interface DocTypeMeta {
  type: DocType;
  module: "sales" | "purchase";
  slug: string;
  label: string;
  plural: string;
  partyType: "customer" | "supplier";
  accounting: boolean;
  stock: "out" | "in" | null;
  chord: string;
}

export const DOC_TYPES: DocTypeMeta[] = [
  { type: "quotation", module: "sales", slug: "quotations", label: "Quotation", plural: "Quotations", partyType: "customer", accounting: false, stock: null, chord: "G Q" },
  { type: "sales_order", module: "sales", slug: "orders", label: "Sales order", plural: "Sales orders", partyType: "customer", accounting: false, stock: null, chord: "G O" },
  { type: "delivery_challan", module: "sales", slug: "challans", label: "Delivery challan", plural: "Delivery challans", partyType: "customer", accounting: false, stock: null, chord: "" },
  { type: "sales_invoice", module: "sales", slug: "invoices", label: "Sales invoice", plural: "Sales invoices", partyType: "customer", accounting: true, stock: "out", chord: "G S" },
  { type: "sales_return", module: "sales", slug: "returns", label: "Sales return / credit note", plural: "Sales returns", partyType: "customer", accounting: true, stock: "in", chord: "" },
  { type: "purchase_order", module: "purchase", slug: "orders", label: "Purchase order", plural: "Purchase orders", partyType: "supplier", accounting: false, stock: null, chord: "" },
  { type: "grn", module: "purchase", slug: "grn", label: "Goods receipt (GRN)", plural: "Goods receipts", partyType: "supplier", accounting: false, stock: null, chord: "" },
  { type: "purchase_bill", module: "purchase", slug: "bills", label: "Purchase bill", plural: "Purchase bills", partyType: "supplier", accounting: true, stock: "in", chord: "G P" },
  { type: "purchase_return", module: "purchase", slug: "returns", label: "Purchase return / debit note", plural: "Purchase returns", partyType: "supplier", accounting: true, stock: "out", chord: "" },
];

export function docMeta(module: string, slug: string): DocTypeMeta | undefined {
  return DOC_TYPES.find((d) => d.module === module && d.slug === slug);
}
export function docMetaByType(type: string): DocTypeMeta | undefined {
  return DOC_TYPES.find((d) => d.type === type);
}
export function docHref(type: string, id?: string): string {
  const m = docMetaByType(type);
  if (!m) return "/dashboard";
  return `/${m.module}/${m.slug}${id ? `/${id}` : ""}`;
}
