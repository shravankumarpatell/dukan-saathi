import {
  ArrowLeftRight,
  BarChart3,
  BookOpen,
  Boxes,
  Building2,
  Calculator,
  ClipboardList,
  FileText,
  Landmark,
  LayoutDashboard,
  type LucideIcon,
  MessageSquare,
  Package,
  Receipt,
  RefreshCw,
  Scale,
  Settings,
  ShoppingCart,
  Sparkles,
  Truck,
  Users,
  Warehouse,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon?: LucideIcon;
  chord?: string; // "g s"
  perm?: string;
  keywords?: string[];
}

export interface NavGroup {
  label: string;
  icon: LucideIcon;
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  {
    label: "Overview",
    icon: LayoutDashboard,
    items: [{ label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, chord: "g d", keywords: ["home", "overview"] }],
  },
  {
    label: "Sales",
    icon: Receipt,
    items: [
      { label: "Invoices", href: "/sales/invoices", icon: Receipt, chord: "g s", perm: "sales.view", keywords: ["bill", "sale"] },
      { label: "Quotations", href: "/sales/quotations", icon: FileText, chord: "g q", perm: "sales.view", keywords: ["estimate", "proforma"] },
      { label: "Sales orders", href: "/sales/orders", icon: ClipboardList, chord: "g o", perm: "sales.view" },
      { label: "Delivery challans", href: "/sales/challans", icon: Truck, perm: "sales.view" },
      { label: "Sales returns", href: "/sales/returns", icon: ArrowLeftRight, perm: "sales.view", keywords: ["credit note"] },
    ],
  },
  {
    label: "Purchase",
    icon: ShoppingCart,
    items: [
      { label: "Purchase bills", href: "/purchase/bills", icon: ShoppingCart, chord: "g p", perm: "purchase.view" },
      { label: "Purchase orders", href: "/purchase/orders", icon: ClipboardList, perm: "purchase.view" },
      { label: "Goods receipts", href: "/purchase/grn", icon: Truck, perm: "purchase.view", keywords: ["grn"] },
      { label: "Purchase returns", href: "/purchase/returns", icon: ArrowLeftRight, perm: "purchase.view", keywords: ["debit note"] },
    ],
  },
  {
    label: "Accounting",
    icon: Landmark,
    items: [
      { label: "Vouchers", href: "/accounting/vouchers", icon: BookOpen, chord: "g v", perm: "accounting.view", keywords: ["journal", "payment", "receipt", "contra"] },
      { label: "Ledgers", href: "/accounting/ledgers", icon: Landmark, chord: "g l", perm: "accounting.view", keywords: ["chart of accounts"] },
      { label: "Outstanding", href: "/accounting/outstanding", icon: Scale, chord: "g u", perm: "reports.view", keywords: ["receivable", "payable", "ageing"] },
      { label: "Day book", href: "/accounting/day-book", icon: FileText, perm: "accounting.view" },
      { label: "Trial balance", href: "/accounting/reports/trial-balance", icon: Scale, chord: "g t", perm: "reports.view" },
      { label: "Profit & loss", href: "/accounting/reports/profit-loss", icon: BarChart3, perm: "reports.view" },
      { label: "Balance sheet", href: "/accounting/reports/balance-sheet", icon: Landmark, perm: "reports.view" },
    ],
  },
  {
    label: "Inventory",
    icon: Package,
    items: [
      { label: "Products", href: "/inventory/products", icon: Package, chord: "g i", perm: "inventory.view", keywords: ["items", "tiles", "sanitary"] },
      { label: "Stock summary", href: "/inventory/stock", icon: Boxes, chord: "g k", perm: "inventory.view" },
      { label: "Adjustments & transfers", href: "/inventory/journals", icon: ArrowLeftRight, perm: "inventory.view", keywords: ["stock journal"] },
      { label: "Godowns", href: "/inventory/godowns", icon: Warehouse, perm: "inventory.view", keywords: ["warehouse"] },
      { label: "Reservations & samples", href: "/inventory/reservations", icon: ClipboardList, perm: "inventory.view" },
      { label: "Dead stock", href: "/inventory/dead-stock", icon: BarChart3, perm: "inventory.view" },
    ],
  },
  {
    label: "Parties",
    icon: Users,
    items: [
      { label: "Customers", href: "/parties/customers", icon: Users, chord: "g c", keywords: ["debtors"] },
      { label: "Suppliers", href: "/parties/suppliers", icon: Building2, chord: "g e", keywords: ["vendors", "creditors"] },
      { label: "Projects & sites", href: "/parties/projects", icon: ClipboardList },
    ],
  },
  {
    label: "Compliance & tools",
    icon: Calculator,
    items: [
      { label: "GST summary", href: "/gst", icon: Scale, chord: "g g", perm: "gst.view", keywords: ["gstr", "tax"] },
      { label: "Tile calculator", href: "/tools/tile-calculator", icon: Calculator, chord: "g x", keywords: ["sqft", "boxes", "wastage"] },
      { label: "Business intelligence", href: "/more/bi", icon: BarChart3, perm: "reports.view", keywords: ["forecast", "margin"] },
      { label: "Ask TileOS (AI)", href: "/more/ai", icon: Sparkles, chord: "g a", perm: "reports.view" },
      { label: "WhatsApp", href: "/more/whatsapp", icon: MessageSquare, perm: "sales.view" },
      { label: "Sync & Tally", href: "/more/sync", icon: RefreshCw, perm: "accounting.view", keywords: ["offline", "export", "tally"] },
    ],
  },
  {
    label: "Settings",
    icon: Settings,
    items: [
      { label: "Company & branches", href: "/settings/company", icon: Building2, chord: "g ,", perm: "settings.manage" },
      { label: "Users & roles", href: "/settings/users", icon: Users, perm: "settings.manage" },
      { label: "Fiscal years & locks", href: "/settings/fiscal-years", icon: Landmark, perm: "settings.manage" },
      { label: "Audit log", href: "/settings/audit-log", icon: BookOpen, perm: "audit.view" },
    ],
  },
];

export interface ActionCommand {
  label: string;
  href: string;
  shortcut?: string; // "alt+n"
  perm?: string;
  keywords?: string[];
}

export const ACTIONS: ActionCommand[] = [
  { label: "New sales invoice", href: "/sales/invoices/new", shortcut: "alt+n", perm: "sales.write", keywords: ["new sale", "bill", "create invoice"] },
  { label: "New quotation", href: "/sales/quotations/new", shortcut: "alt+q", perm: "sales.write", keywords: ["estimate"] },
  { label: "New sales order", href: "/sales/orders/new", perm: "sales.write" },
  { label: "New purchase bill", href: "/purchase/bills/new", shortcut: "alt+p", perm: "purchase.write" },
  { label: "New purchase order", href: "/purchase/orders/new", perm: "purchase.write" },
  { label: "New receipt (money in)", href: "/accounting/vouchers/new?type=receipt", shortcut: "alt+r", perm: "accounting.post", keywords: ["collect", "payment in"] },
  { label: "New payment (money out)", href: "/accounting/vouchers/new?type=payment", shortcut: "alt+y", perm: "accounting.post" },
  { label: "New journal voucher", href: "/accounting/vouchers/new?type=journal", shortcut: "alt+j", perm: "accounting.post" },
  { label: "New contra (cash/bank)", href: "/accounting/vouchers/new?type=contra", perm: "accounting.post" },
  { label: "New customer", href: "/parties/customers?new=1", shortcut: "alt+c", perm: "parties.manage" },
  { label: "New supplier", href: "/parties/suppliers?new=1", perm: "parties.manage" },
  { label: "New product", href: "/inventory/products?new=1", shortcut: "alt+i", perm: "inventory.manage" },
  { label: "Stock adjustment", href: "/inventory/journals?new=adjustment", perm: "inventory.post" },
  { label: "Stock transfer", href: "/inventory/journals?new=transfer", perm: "inventory.post" },
  { label: "Tile calculator", href: "/tools/tile-calculator", keywords: ["sqft to boxes"] },
];

export const GLOBAL_SHORTCUTS: { keys: string; label: string }[] = [
  { keys: "mod+k", label: "Command palette" },
  { keys: "?", label: "Shortcut cheatsheet" },
  { keys: "esc", label: "Close dialog / cancel" },
  { keys: "mod+s", label: "Save draft (editors)" },
  { keys: "mod+enter", label: "Save & post (editors)" },
  { keys: "mod+p", label: "Print (document view)" },
  { keys: "/", label: "Focus search / filter on list pages" },
  { keys: "j / k", label: "Move down / up in lists" },
  { keys: "enter", label: "Open highlighted row" },
  { keys: "n", label: "New record on list pages" },
  { keys: "mod+d", label: "Toggle dark mode" },
];

export const GRID_SHORTCUTS: { keys: string; label: string }[] = [
  { keys: "↑ ↓ ← →", label: "Move between cells" },
  { keys: "enter", label: "Commit cell, move to next row (adds a row at the end)" },
  { keys: "shift+enter", label: "Move up a row" },
  { keys: "tab / shift+tab", label: "Next / previous field" },
  { keys: "mod+↑ / mod+↓", label: "Jump to first / last row" },
  { keys: "mod+backspace", label: "Delete current row" },
  { keys: "type to search", label: "Product/party/ledger pickers open on first keystroke" },
  { keys: "alt+t", label: "Open tile area→box calculator on the current line" },
];
