export interface NavItem {
  label: string;
  href: string;
  domain: string;
}

export const DASHBOARD_NAV_ITEMS: readonly NavItem[] = [
  { label: "Dashboard", href: "/", domain: "overview" },
  { label: "Items Catalog", href: "/items", domain: "items" },
  { label: "Equipment Units", href: "/equipment-units", domain: "equipment-units" },
  { label: "Stock Balances", href: "/stock-balances", domain: "stock-balances" },
  { label: "Delivery Orders", href: "/delivery-orders", domain: "delivery-orders" },
  { label: "Collection Orders", href: "/collection-orders", domain: "collection-orders" },
  { label: "Stock Movements", href: "/stock-movements", domain: "stock-movements" },
  { label: "Reconciliation", href: "/reconciliation", domain: "reconciliation" },
  { label: "Projects", href: "/projects", domain: "projects" },
  { label: "Users", href: "/users", domain: "users" },
] as const;

