"""End-to-end API flow test for the accounting/inventory effect chain. Run: python3 /app/scripts/flow_test.py [base]"""
import datetime
import json
import sys
import urllib.error
import urllib.request

base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"


def call(method, path, body=None, tok=None):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + tok} if tok else {})})
    try:
        return json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:400]}


tok = call("POST", "/api/auth/login", {"email": "admin@demo.tileos", "password": "Admin@123"})["access_token"]
custs = call("GET", "/api/parties?party_type=customer", tok=tok)
c = custs[0]
print("customer", c["name"], "outstanding", c["outstanding"])
prods = call("GET", "/api/inventory/products?product_type=tile", tok=tok)
p = prods[0]
print("product", p["name"], "stock", p["stock_qty"])
stock_before = call("GET", f"/api/inventory/products/{p['id']}/stock", tok=tok)["total_qty"]
today = datetime.date.today().isoformat()
inv = call("POST", "/api/trade/sales_invoice", {"date": today, "party_id": c["id"], "lines": [{"product_id": p["id"], "qty": "5", "rate": p["project_price"], "discount_pct": "2"}], "post": True}, tok=tok)
print("invoice", inv.get("doc_no"), inv.get("status"), inv.get("grand_total"), inv.get("balance_due"), inv.get("error"), inv.get("body"))
stock_after = call("GET", f"/api/inventory/products/{p['id']}/stock", tok=tok)["total_qty"]
print("stock", stock_before, "->", stock_after)
v = call("GET", f"/api/accounting/vouchers/{inv['voucher_id']}", tok=tok)
print("voucher", v["voucher_no"], [(l["ledger_name"], l["debit"], l["credit"]) for l in v["lines"]])
cash = [l for l in call("GET", "/api/accounting/ledgers?kind=cash_bank", tok=tok) if l["is_cash"]][0]
rc = call("POST", "/api/accounting/quick-entry", {"kind": "receipt", "date": today, "party_id": c["id"], "amount": "1000", "account_ledger_id": cash["id"], "auto_allocate": True}, tok=tok)
print("receipt", rc.get("voucher_no"), rc.get("error"), rc.get("body"))
inv2 = call("GET", f"/api/trade/sales_invoice/{inv['id']}", tok=tok)
print("balance after receipt", inv2["balance_due"])
led = call("GET", "/api/accounting/ledgers?kind=non_party", tok=tok)
bad = call("POST", "/api/accounting/vouchers", {"voucher_type": "journal", "date": today, "lines": [{"ledger_id": led[0]["id"], "debit": "100"}, {"ledger_id": led[1]["id"], "credit": "90"}]}, tok=tok)
print("unbalanced ->", bad.get("error"), bad.get("body"))
tok2 = call("POST", "/api/auth/login", {"email": "owner@ganesh.tileos", "password": "Admin@123"})["access_token"]
x = call("GET", f"/api/trade/sales_invoice/{inv['id']}", tok=tok2)
print("cross-tenant access ->", x.get("error"))
print("tenant2 parties:", len(call("GET", "/api/parties", tok=tok2)), "products:", len(call("GET", "/api/inventory/products", tok=tok2)))
cx = call("POST", f"/api/trade/sales_invoice/{inv['id']}/cancel?reason=test", tok=tok)
print("cancel with receipt ->", cx.get("error"), cx.get("body", "")[:120])
# draft -> edit -> post -> cancel flow
d = call("POST", "/api/trade/sales_invoice", {"date": today, "party_id": c["id"], "lines": [{"product_id": p["id"], "qty": "1", "rate": "500"}]}, tok=tok)
d = call("PUT", f"/api/trade/sales_invoice/{d['id']}", {"date": today, "party_id": c["id"], "lines": [{"product_id": p["id"], "qty": "2", "rate": "500"}]}, tok=tok)
print("draft edited", d.get("doc_no"), d.get("grand_total"), d.get("error"), d.get("body"))
d = call("POST", f"/api/trade/sales_invoice/{d['id']}/post", tok=tok)
print("posted", d.get("status"), d.get("error"))
d = call("POST", f"/api/trade/sales_invoice/{d['id']}/cancel?reason=wrong+party", tok=tok)
print("cancelled", d.get("status"), d.get("error"), d.get("body"))
tb = call("GET", "/api/reports/trial-balance", tok=tok)
print("TB balanced", tb["balanced"])
q = call("GET", "/api/trade/quotation", tok=tok)["items"][0]
conv = call("POST", f"/api/trade/quotation/{q['id']}/convert", {"target_doc_type": "sales_invoice", "post": False}, tok=tok)
print("convert quotation ->", conv.get("doc_no"), conv.get("status"), conv.get("error"), conv.get("body"))
print("bi", call("GET", "/api/bi/overview", tok=tok).get("cashflow"))
# purchase bill + return
sup = call("GET", "/api/parties?party_type=supplier", tok=tok)[0]
pb = call("POST", "/api/trade/purchase_bill", {"date": today, "party_id": sup["id"], "supplier_ref_no": "T-1", "lines": [{"product_id": p["id"], "qty": "10", "rate": p["purchase_price"]}], "post": True}, tok=tok)
print("purchase bill", pb.get("doc_no"), pb.get("grand_total"), pb.get("error"), pb.get("body"))
pr = call("POST", f"/api/trade/purchase_bill/{pb['id']}/convert", {"target_doc_type": "purchase_return", "post": True}, tok=tok)
print("purchase return", pr.get("doc_no"), pr.get("status"), pr.get("error"), pr.get("body"))
# stock adjustment
g = call("GET", "/api/inventory/godowns", tok=tok)
sj = call("POST", "/api/inventory/stock-journals", {"journal_type": "adjustment", "date": today, "reason": "breakage", "lines": [{"product_id": p["id"], "qty": "-1", "godown_id": g[0]["id"]}]}, tok=tok)
print("adjustment", sj.get("doc_no"), sj.get("total_value"), sj.get("error"), sj.get("body"))
sjt = call("POST", "/api/inventory/stock-journals", {"journal_type": "transfer", "date": today, "from_godown_id": g[0]["id"], "to_godown_id": g[1]["id"], "lines": [{"product_id": p["id"], "qty": "1"}]}, tok=tok)
print("transfer", sjt.get("doc_no"), sjt.get("error"), sjt.get("body"))
tb = call("GET", "/api/reports/trial-balance", tok=tok)
print("TB balanced", tb["balanced"], "BS balanced", call("GET", "/api/reports/balance-sheet", tok=tok)["balanced"])
