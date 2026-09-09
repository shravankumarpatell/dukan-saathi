#!/usr/bin/env bash
# Quick API smoke test. Usage: bash /app/scripts/smoke.sh [base_url]
BASE="${1:-http://localhost:8001}"
TOKEN=$(curl -s -X POST "$BASE/api/auth/login" -H "Content-Type: application/json" -d '{"email":"admin@demo.tileos","password":"Admin@123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
H="Authorization: Bearer $TOKEN"
check() { # name url
  code=$(curl -s -o /tmp/smoke_body -w "%{http_code}" "$BASE$2" -H "$H")
  if [ "$code" = "200" ]; then echo "OK   $code $1"; else echo "FAIL $code $1 :: $(head -c 200 /tmp/smoke_body)"; fi
}
check "me" "/api/auth/me"
check "dashboard" "/api/reports/dashboard"
check "trial-balance" "/api/reports/trial-balance"
check "profit-loss" "/api/reports/profit-loss"
check "balance-sheet" "/api/reports/balance-sheet"
check "day-book" "/api/reports/day-book?from_date=2026-01-01"
check "outstanding" "/api/reports/outstanding"
check "outstanding-payable" "/api/reports/outstanding?kind=payable"
check "stock-summary" "/api/reports/stock-summary"
check "gst-summary" "/api/reports/gst-summary?from_date=2026-01-01"
check "dead-stock" "/api/reports/dead-stock"
check "ledgers" "/api/accounting/ledgers"
check "groups" "/api/accounting/groups"
check "vouchers" "/api/accounting/vouchers"
check "parties" "/api/parties"
check "products" "/api/inventory/products"
check "godowns" "/api/inventory/godowns"
check "units" "/api/inventory/units"
check "stock-journals" "/api/inventory/stock-journals"
check "reservations" "/api/inventory/reservations"
check "samples" "/api/inventory/samples"
check "invoices" "/api/trade/sales_invoice"
check "quotations" "/api/trade/quotation"
check "purchase_bills" "/api/trade/purchase_bill"
check "types" "/api/trade/types"
check "fiscal-years" "/api/settings/fiscal-years"
check "users" "/api/settings/users"
check "roles" "/api/settings/roles"
check "audit" "/api/settings/audit-log"
check "bi" "/api/bi/overview"
check "sync-status" "/api/sync/status"
check "whatsapp" "/api/whatsapp/messages"
check "tally" "/api/tally/export?what=ledgers"
check "states" "/api/tools/states"
python3 - "$BASE" "$TOKEN" << 'EOF'
import sys, json, urllib.request
base, tok = sys.argv[1], sys.argv[2]
def post(path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:300]}
print("tile calc:", post("/api/tools/tile-calculator", {"area_sqft": 1000, "sqft_per_box": 16, "wastage_pct": 7}))
print("ai:", post("/api/ai/query", {"question": "sales this month"})["answer"])
tb = json.load(urllib.request.urlopen(urllib.request.Request(base + "/api/reports/trial-balance", headers={"Authorization": "Bearer " + tok})))
print("TB balanced:", tb["balanced"], tb["totals"]["closing_dr"], tb["totals"]["closing_cr"])
EOF
