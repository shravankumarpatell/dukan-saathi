"""Demo seed data: two tenants (isolation demo), realistic tile/sanitary catalog, opening stock, purchases, sales, receipts."""
from __future__ import annotations

import logging
import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from .db import SessionLocal
from .deps import Ctx
from .models import Batch, Branch, Brand, Category, Company, Godown, Ledger, Party, Product, Role, Tenant, Unit, User
from .schemas import PartyIn, QuickReceiptIn, StockJournalIn, StockJournalLineIn, TradeDocIn, TradeLineIn
from .security import hash_password
from .services import trade as T
from .services.coa import setup_company_defaults
from .services.common import D, audit, money
from .services.posting import LineSpec, allocate, post_voucher

log = logging.getLogger("tileos.seed")

ROLES = {
    "Owner": ["*"],
    "Accountant": ["accounting.*", "reports.view", "gst.view", "audit.view", "parties.manage", "sales.view", "purchase.view", "inventory.view"],
    "Sales": ["sales.*", "parties.manage", "inventory.view", "reports.view", "accounting.view"],
    "Store": ["inventory.*", "purchase.*", "sales.view", "reports.view"],
}

TILES = [
    # sku, name, brand, category, series, design, colour, size, finish, material, sqft/box, pcs/box, purchase, retail, dealer, project, hsn, gst, reorder
    ("KJ-CAR-6060-GL", "Carrara Bianco 600x600 Glossy", "Kajaria", "Vitrified Floor Tiles", "Eternity", "Carrara Bianco", "White", "600x600 mm", "Glossy", "Vitrified", "15.50", "4", "520", "780", "690", "640", "69072100", "18", "40"),
    ("KJ-STA-6060-MT", "Statuario Grey 600x600 Matt", "Kajaria", "Vitrified Floor Tiles", "Eternity", "Statuario", "Grey", "600x600 mm", "Matt", "Vitrified", "15.50", "4", "540", "820", "720", "660", "69072100", "18", "40"),
    ("SM-ONX-6012-PL", "Onyx Beige 600x1200 Polished", "Somany", "Vitrified Floor Tiles", "Duragres", "Onyx", "Beige", "600x1200 mm", "Polished", "Vitrified", "15.50", "2", "890", "1350", "1180", "1090", "69072100", "18", "30"),
    ("SM-WD-2012-MT", "Oakwood Plank 200x1200 Matt", "Somany", "Vitrified Floor Tiles", "Wood Series", "Oakwood", "Brown", "200x1200 mm", "Matt", "Vitrified", "15.50", "6", "760", "1150", "1020", "940", "69072100", "18", "30"),
    ("JN-SLT-3060-RS", "Slate Charcoal 300x600 Rustic", "Johnson", "Ceramic Wall Tiles", "Marbonite", "Slate", "Charcoal", "300x600 mm", "Rustic", "Ceramic", "9.70", "5", "310", "480", "420", "390", "69072100", "18", "50"),
    ("JN-MRB-3060-GL", "Marble Ivory 300x600 Glossy", "Johnson", "Ceramic Wall Tiles", "Marbonite", "Marble Ivory", "Ivory", "300x600 mm", "Glossy", "Ceramic", "9.70", "5", "290", "450", "400", "370", "69072100", "18", "50"),
    ("KJ-SUB-1030-GL", "Subway White 100x300 Glossy", "Kajaria", "Ceramic Wall Tiles", "Kitchen", "Subway", "White", "100x300 mm", "Glossy", "Ceramic", "7.50", "23", "240", "380", "340", "310", "69072300", "18", "60"),
    ("AG-OUT-6060-AS", "Anti-Skid Outdoor 600x600", "AGL", "Outdoor Tiles", "Terrace", "Stone", "Grey", "600x600 mm", "Anti-skid", "Vitrified", "15.50", "4", "480", "720", "640", "590", "69072100", "18", "40"),
    ("AG-PRK-4040-RG", "Parking Tile 400x400 Heavy Duty", "AGL", "Outdoor Tiles", "Parking", "Checkers", "Red", "400x400 mm", "Rough", "Vitrified", "8.60", "5", "210", "330", "290", "270", "69072100", "18", "80"),
    ("OR-MOS-3030-GL", "Glass Mosaic 300x300 Aqua", "Orient Bell", "Mosaic & Decor", "Aqua", "Mosaic", "Aqua Blue", "300x300 mm", "Glossy", "Glass", "10.76", "11", "620", "980", "860", "790", "70169000", "18", "15"),
    ("OR-3D-6012-HL", "3D Highlighter 600x1200 Gold", "Orient Bell", "Mosaic & Decor", "Inspire", "Waves", "Gold", "600x1200 mm", "Matt", "Vitrified", "15.50", "2", "1450", "2200", "1950", "1800", "69072100", "18", "10"),
    ("SM-MRB-8080-PL", "Marble Statuario 800x800 Polished", "Somany", "Vitrified Floor Tiles", "Duragres", "Statuario", "White", "800x800 mm", "Polished", "Vitrified", "20.66", "3", "1280", "1950", "1720", "1590", "69072100", "18", "20"),
]

SANITARY = [
    # sku, name, brand, category, model, colour, warranty, purchase, retail, dealer, project, hsn, gst, set_contents
    ("HW-WC-ONE-W", "One-Piece Water Closet Aurora", "Hindware", "Sanitaryware", "AUR-92001", "White", 120, "6800", "10500", "9200", "8600", "69101000", "18", [{"name": "Seat cover soft-close", "qty": 1}, {"name": "Flush tank fittings", "qty": 1}, {"name": "Installation kit", "qty": 1}]),
    ("CR-WC-WALL-W", "Wall-Hung WC Cera Camry", "Cera", "Sanitaryware", "S1044103", "White", 120, "5400", "8400", "7300", "6800", "69101000", "18", [{"name": "Seat cover", "qty": 1}, {"name": "Wall-hung bolts", "qty": 2}]),
    ("CR-WB-TT-W", "Table-Top Wash Basin Cera Cupid", "Cera", "Sanitaryware", "S2020112", "White", 60, "2100", "3400", "2950", "2700", "69101000", "18", []),
    ("HW-WB-PED-W", "Pedestal Wash Basin Hindware Neo", "Hindware", "Sanitaryware", "NEO-10041", "White", 60, "2600", "4100", "3600", "3300", "69101000", "18", [{"name": "Basin", "qty": 1}, {"name": "Pedestal", "qty": 1}]),
    ("JQ-FL-PLT-CH", "Concealed Flush Plate Jaquar", "Jaquar", "Bath Fittings", "JCP-CHR-152415", "Chrome", 120, "1900", "3100", "2700", "2500", "84818090", "18", []),
    ("JQ-SHR-RAIN-CH", "Rain Shower 8 inch Jaquar", "Jaquar", "Bath Fittings", "OHS-CHR-1979", "Chrome", 120, "1600", "2650", "2300", "2100", "84818090", "18", []),
    ("JQ-MIX-BSN-CH", "Basin Mixer Jaquar Kubix", "Jaquar", "Bath Fittings", "KUB-CHR-35011", "Chrome", 120, "3200", "5200", "4550", "4200", "84818090", "18", []),
    ("GR-CIST-CONC", "Concealed Cistern Grohe Rapid", "Grohe", "Bath Fittings", "38528001", "White", 120, "7800", "12000", "10600", "9800", "69101000", "18", [{"name": "Frame", "qty": 1}, {"name": "Cistern", "qty": 1}]),
]

CUSTOMERS = [
    ("Sharma Builders & Developers", "customer", "27AABCS1234F1Z5", "9822012345", "Pune", "27", "project", "500000", 30),
    ("Rajesh Patil (Home Owner)", "customer", None, "9860011223", "Pune", "27", "retail", "0", 0),
    ("Modern Interiors Studio", "customer", "27AAECM5678K1Z2", "9890044556", "Pune", "27", "dealer", "300000", 15),
    ("Sai Krupa Tiles Depot", "customer", "27AAFCS9012L1Z8", "9970077889", "Solapur", "27", "dealer", "400000", 21),
    ("Green Valley Housing Society", "customer", None, "9922233445", "Mumbai", "27", "project", "1000000", 45),
    ("Kavya Constructions", "customer", "29AAKCK3456M1Z1", "9845566778", "Bengaluru", "29", "project", "600000", 30),
    ("Deepak Hardware & Sanitary", "customer", "24AADCD7890N1Z6", "9825599001", "Surat", "24", "dealer", "250000", 15),
    ("Priya Mehta (Renovation)", "customer", None, "9833344556", "Mumbai", "27", "retail", "0", 0),
]
SUPPLIERS = [
    ("Kajaria Ceramics Ltd", "supplier", "07AAACK1234Q1Z3", "01143000000", "New Delhi", "07", 45),
    ("Somany Ceramics Ltd", "supplier", "06AAACS5678R1Z9", "01244000000", "Gurugram", "06", 45),
    ("Cera Sanitaryware Ltd", "supplier", "24AAACC9012S1Z4", "07926000000", "Ahmedabad", "24", 30),
    ("Jaquar & Company Pvt Ltd", "supplier", "06AAACJ3456T1Z7", "01244600000", "Manesar", "06", 30),
    ("Metro Tiles Distributors", "supplier", "27AAFCM7890U1Z0", "9820011002", "Mumbai", "27", 15),
]


def _ctx(user: User, company: Company, branch: Branch) -> Ctx:
    return Ctx(user=user, tenant_id=user.tenant_id, company_id=company.id, branch_id=branch.id, perms=["*"], ip="seed")


async def seed_if_empty() -> None:
    async with SessionLocal() as db:
        if (await db.execute(select(Tenant.id).limit(1))).first():
            return
        log.info("Seeding demo data ...")
        await seed_demo(db)
        await seed_second_tenant(db)
        await db.commit()
        log.info("Seed complete")


async def _make_tenant(db, name: str, slug: str, company_kwargs: dict, owner_email: str, owner_name: str, password: str) -> tuple[Tenant, Company, Branch, User, dict[str, Role]]:
    tenant = Tenant(name=name, slug=slug)
    db.add(tenant)
    await db.flush()
    roles: dict[str, Role] = {}
    for rname, perms in ROLES.items():
        r = Role(tenant_id=tenant.id, name=rname, permissions=perms, is_system=True, description=f"{rname} role")
        db.add(r)
        roles[rname] = r
    await db.flush()
    company = Company(tenant_id=tenant.id, **company_kwargs)
    db.add(company)
    await db.flush()
    branch = Branch(tenant_id=tenant.id, company_id=company.id, name="Head Office", code="HO", is_default=True, state_code=company.state_code, gstin=company.gstin, address=company.address_line1)
    db.add(branch)
    await db.flush()
    owner = User(tenant_id=tenant.id, email=owner_email, full_name=owner_name, password_hash=hash_password(password), role_id=roles["Owner"].id, default_company_id=company.id, default_branch_id=branch.id, is_owner=True)
    db.add(owner)
    await db.flush()
    await setup_company_defaults(db, tenant.id, company.id, branch.id, company.fy_start_month)
    return tenant, company, branch, owner, roles


async def seed_demo(db) -> None:
    tenant, company, branch, owner, roles = await _make_tenant(
        db,
        "Shree Tiles & Sanitary",
        "demo",
        dict(name="Shree Tiles & Sanitary", legal_name="Shree Tiles & Sanitary Pvt Ltd", gstin="27AAECS1234A1Z5", pan="AAECS1234A", address_line1="Plot 14, Tilak Road", address_line2="Near Swargate", city="Pune", state="Maharashtra", state_code="27", pincode="411002", phone="020-24450000", email="accounts@shreetiles.in"),
        "admin@demo.tileos",
        "Anil Shah (Owner)",
        "Admin@123",
    )
    for email, name, role in (("accounts@demo.tileos", "Meera Kulkarni", "Accountant"), ("sales@demo.tileos", "Rohit Deshmukh", "Sales"), ("store@demo.tileos", "Suresh Yadav", "Store")):
        db.add(User(tenant_id=tenant.id, email=email, full_name=name, password_hash=hash_password("Demo@123"), role_id=roles[role].id, default_company_id=company.id, default_branch_id=branch.id))
    # second branch + godown
    b2 = Branch(tenant_id=tenant.id, company_id=company.id, name="Hadapsar Showroom", code="HDP", state_code="27", address="Magarpatta Road, Hadapsar, Pune")
    db.add(b2)
    await db.flush()
    g2 = Godown(tenant_id=tenant.id, company_id=company.id, branch_id=b2.id, name="Hadapsar Warehouse", code="HDP-WH")
    db.add(g2)
    await db.flush()
    ctx = _ctx(owner, company, branch)
    main_godown = (await db.execute(select(Godown).where(Godown.company_id == company.id, Godown.is_default.is_(True)))).scalar_one()
    units = {u.symbol: u for u in (await db.execute(select(Unit).where(Unit.company_id == company.id))).scalars().all()}

    brands: dict[str, Brand] = {}
    for bn in sorted({t[2] for t in TILES} | {s[2] for s in SANITARY}):
        b = Brand(tenant_id=tenant.id, company_id=company.id, name=bn)
        db.add(b)
        brands[bn] = b
    cats: dict[str, Category] = {}
    for cn, kind in (("Vitrified Floor Tiles", "tile"), ("Ceramic Wall Tiles", "tile"), ("Outdoor Tiles", "tile"), ("Mosaic & Decor", "tile"), ("Sanitaryware", "sanitary"), ("Bath Fittings", "sanitary"), ("Adhesives & Grout", "general")):
        c = Category(tenant_id=tenant.id, company_id=company.id, name=cn, kind=kind)
        db.add(c)
        cats[cn] = c
    await db.flush()

    products: list[Product] = []
    for sku, name, brand, cat, series, design, colour, size, finish, material, sqft, pcs, pp, rp, dp, prp, hsn, gst, reorder in TILES:
        p = Product(
            tenant_id=tenant.id, company_id=company.id, sku=sku, name=name, product_type="tile", brand_id=brands[brand].id, category_id=cats[cat].id, series=series, design=design, colour=colour, size=size, finish=finish, material=material, grade="Premium", application="Outdoor" if "Outdoor" in cat else ("Wall" if "Wall" in cat else "Floor"),
            thickness_mm=D("9") if "Wall" in cat else D("10"), stock_unit_id=units["Box"].id, sqft_per_box=D(sqft), pieces_per_box=D(pcs), sqm_per_box=(D(sqft) / D("10.7639")).quantize(D("0.0001")), boxes_per_pallet=D("48"), weight_kg_per_box=D("28"),
            hsn_code=hsn, gst_rate=D(gst), purchase_price=D(pp), sale_price=D(rp), retail_price=D(rp), dealer_price=D(dp), project_price=D(prp), mrp=(D(rp) * D("1.15")).quantize(D("1")), reorder_level=D(reorder), track_batches=True,
        )
        db.add(p)
        products.append(p)
    for sku, name, brand, cat, model, colour, warranty, pp, rp, dp, prp, hsn, gst, contents in SANITARY:
        p = Product(tenant_id=tenant.id, company_id=company.id, sku=sku, name=name, product_type="sanitary", brand_id=brands[brand].id, category_id=cats[cat].id, model_no=model, colour=colour, warranty_months=warranty, set_contents=contents, stock_unit_id=units["Nos"].id, hsn_code=hsn, gst_rate=D(gst), purchase_price=D(pp), sale_price=D(rp), retail_price=D(rp), dealer_price=D(dp), project_price=D(prp), mrp=(D(rp) * D("1.1")).quantize(D("1")), reorder_level=D("3"), track_batches=False, installation_notes="Requires concealed plumbing; check rough-in before installation.")
        db.add(p)
        products.append(p)
    # adhesive (general)
    adhesive = Product(tenant_id=tenant.id, company_id=company.id, sku="RF-ADH-20KG", name="Tile Adhesive 20kg Bag (Grey)", product_type="general", brand_id=brands["Kajaria"].id, category_id=cats["Adhesives & Grout"].id, stock_unit_id=units["Bag"].id, hsn_code="38245000", gst_rate=D("18"), purchase_price=D("310"), sale_price=D("420"), retail_price=D("420"), dealer_price=D("380"), project_price=D("360"), mrp=D("450"), reorder_level=D("50"), track_batches=False)
    db.add(adhesive)
    products.append(adhesive)
    await db.flush()
    for p in products:
        await db.refresh(p, ["stock_unit", "brand", "category"])

    # batches with shade/calibre for tiles
    batches: dict[uuid.UUID, list[Batch]] = {}
    for p in products:
        if p.product_type != "tile":
            continue
        lst = []
        for i, (shade, cal) in enumerate((("A1", "C1"), ("A2", "C1")), start=1):
            b = Batch(tenant_id=tenant.id, company_id=company.id, product_id=p.id, batch_no=f"B{date.today().year}{i:02d}-{p.sku[-4:]}", shade=shade, calibre=cal, mfg_date=date.today() - timedelta(days=120 - i * 10))
            db.add(b)
            lst.append(b)
        batches[p.id] = lst
    await db.flush()

    # parties
    from .routers.parties import _ensure_ledger

    customers: list[Party] = []
    for name, ptype, gstin, phone, city, state, tier, limit, days in CUSTOMERS:
        pin = PartyIn(party_type=ptype, name=name, gstin=gstin, phone=phone, whatsapp=phone, city=city, state_code=state, price_tier=tier, credit_limit=D(limit), credit_days=days, billing_address=f"{city}, {'Maharashtra' if state == '27' else 'Karnataka' if state == '29' else 'Gujarat'}", whatsapp_opt_in=True, tags=["builder"] if tier == "project" else (["dealer"] if tier == "dealer" else ["walk-in"]))
        p = Party(tenant_id=tenant.id, company_id=company.id, **pin.model_dump(exclude={"opening_balance", "opening_type"}))
        db.add(p)
        await db.flush()
        await _ensure_ledger(db, ctx, p, pin)
        customers.append(p)
    suppliers: list[Party] = []
    for name, ptype, gstin, phone, city, state, days in SUPPLIERS:
        pin = PartyIn(party_type=ptype, name=name, gstin=gstin, phone=phone, city=city, state_code=state, credit_days=days, billing_address=city)
        p = Party(tenant_id=tenant.id, company_id=company.id, **pin.model_dump(exclude={"opening_balance", "opening_type"}))
        db.add(p)
        await db.flush()
        await _ensure_ledger(db, ctx, p, pin)
        suppliers.append(p)
    await db.flush()

    today = date.today()
    start = today - timedelta(days=75)

    # capital introduction + bank
    from .services.posting import get_system_ledger

    cash = await get_system_ledger(db, company.id, "cash")
    bank = await get_system_ledger(db, company.id, "bank")
    capital = await get_system_ledger(db, company.id, "capital")
    await post_voucher(db, ctx, voucher_type="receipt", on=start, lines=[LineSpec(bank.id, debit=D("2500000")), LineSpec(capital.id, credit=D("2500000"))], narration="Capital introduced by owner")
    await post_voucher(db, ctx, voucher_type="contra", on=start, lines=[LineSpec(cash.id, debit=D("100000")), LineSpec(bank.id, credit=D("100000"))], narration="Cash withdrawn for counter")

    # opening stock (stock journal -> Dr Stock-in-Hand, Cr Capital)
    from .services import stock as S
    from .services.common import get_fiscal_year, next_number
    from .models import StockJournal

    fy = await get_fiscal_year(db, company.id, start)
    sj = StockJournal(tenant_id=tenant.id, company_id=company.id, branch_id=branch.id, journal_type="opening", doc_no=await next_number(db, tenant.id, company.id, "opening", fy), date=start, to_godown_id=main_godown.id, reason="Opening stock", created_by=owner.id, lines=[])
    db.add(sj)
    await db.flush()
    total = D("0")
    lines_json = []
    inventory_led = await get_system_ledger(db, company.id, "inventory")
    for p in products:
        q = D(random.choice([60, 80, 100, 120])) if p.product_type == "tile" else D(random.choice([6, 8, 10, 12])) if p.product_type == "sanitary" else D("150")
        if p.product_type == "tile":
            half = (q / 2).quantize(D("1"))
            for b, bq in zip(batches[p.id], (half, q - half)):
                await S.add_movement(db, ctx, product=p, godown_id=main_godown.id, on=start, movement_type="opening", quantity=bq, rate=p.purchase_price, batch_id=b.id, doc_type="stock_journal", doc_id=sj.id, narration="Opening stock")
        else:
            await S.add_movement(db, ctx, product=p, godown_id=main_godown.id, on=start, movement_type="opening", quantity=q, rate=p.purchase_price, doc_type="stock_journal", doc_id=sj.id, narration="Opening stock")
        total += money(q * p.purchase_price)
        lines_json.append({"product_id": str(p.id), "product_name": p.name, "sku": p.sku, "qty": str(q), "unit": p.stock_unit.symbol, "rate": str(p.purchase_price), "value": str(money(q * p.purchase_price))})
    sj.lines = lines_json
    sj.total_value = total
    v = await post_voucher(db, ctx, voucher_type="journal", on=start, lines=[LineSpec(inventory_led.id, debit=total), LineSpec(capital.id, credit=total)], narration=f"Opening stock {sj.doc_no}", reference_type="stock_journal", reference_id=sj.id, number_type="stock_journal")
    sj.voucher_id = v.id

    # purchases (3 bills)
    tiles = [p for p in products if p.product_type == "tile"]
    sanitary = [p for p in products if p.product_type == "sanitary"]
    purchase_plan = [
        (suppliers[0], start + timedelta(days=5), [(tiles[0], 60), (tiles[1], 40), (tiles[6], 50)]),
        (suppliers[1], start + timedelta(days=12), [(tiles[2], 30), (tiles[3], 30), (tiles[11], 20)]),
        (suppliers[2], start + timedelta(days=20), [(sanitary[1], 6), (sanitary[2], 10), (sanitary[3], 8)]),
        (suppliers[3], start + timedelta(days=28), [(sanitary[4], 10), (sanitary[5], 12), (sanitary[6], 6)]),
        (suppliers[4], start + timedelta(days=40), [(adhesive, 200), (tiles[8], 100)]),
    ]
    for sup, on, items in purchase_plan:
        lines = []
        for p, q in items:
            bid = batches[p.id][0].id if p.product_type == "tile" else None
            lines.append(TradeLineIn(product_id=p.id, qty=D(q), rate=p.purchase_price, batch_id=bid))
        doc = await T.build_document(db, ctx, "purchase_bill", TradeDocIn(date=on, party_id=sup.id, supplier_ref_no=f"{sup.name.split()[0].upper()}/{on.strftime('%y%m')}/{random.randint(100, 999)}", lines=lines))
        await T.post_document(db, ctx, doc)
    # a purchase order pending
    po = await T.build_document(db, ctx, "purchase_order", TradeDocIn(date=today - timedelta(days=2), party_id=suppliers[0].id, lines=[TradeLineIn(product_id=tiles[0].id, qty=D("80"), rate=tiles[0].purchase_price), TradeLineIn(product_id=tiles[7].id, qty=D("40"), rate=tiles[7].purchase_price)]))
    await T.post_document(db, ctx, po)

    # sales invoices over the last 60 days
    rng = random.Random(42)
    invoices = []
    for i in range(22):
        on = start + timedelta(days=10 + rng.randint(0, 64))
        if on > today:
            on = today
        cust = rng.choice(customers)
        n_lines = rng.randint(1, 4)
        lines = []
        chosen = rng.sample(products, n_lines)
        for p in chosen:
            if p.product_type == "tile":
                b = batches[p.id][rng.randint(0, 1)]
                avail = await S.balance(db, company.id, p.id, main_godown.id, b.id)
                boxes = min(D(rng.choice([6, 10, 15, 20, 25])), avail)
                if boxes < 1:
                    continue
                bid = b.id
            elif p.product_type == "sanitary":
                avail = await S.balance(db, company.id, p.id, main_godown.id)
                boxes = min(D(rng.choice([1, 2, 3])), avail)
                if boxes < 1:
                    continue
                bid = None
            else:
                boxes = D(rng.choice([5, 10, 20]))
                bid = None
            rate = T._price_for(p, cust, "sales_invoice")
            lines.append(TradeLineIn(product_id=p.id, qty=boxes, rate=rate, batch_id=bid, discount_pct=D(rng.choice([0, 0, 2, 5]))))
        if not lines:
            continue
        paid = D("0")
        pay_ledger = None
        if cust.price_tier == "retail":
            pay_ledger = cash.id if rng.random() < 0.5 else bank.id
        data = TradeDocIn(date=on, party_id=cust.id, lines=lines, paid_amount=paid, payment_ledger_id=pay_ledger, salesman=rng.choice(["Rohit", "Sneha", "Amit"]), notes="Delivery within 2 days. Shade A1 confirmed with customer.")
        try:
            async with db.begin_nested():
                doc = await T.build_document(db, ctx, "sales_invoice", data)
                if cust.price_tier == "retail":
                    doc.paid_amount = doc.grand_total
                    doc.payment_ledger_id = pay_ledger
                await T.post_document(db, ctx, doc)
            invoices.append(doc)
        except Exception as e:  # noqa: BLE001
            log.warning("seed invoice skipped: %s", e)
    # receipts against some credit invoices (partial and full)
    for doc in invoices:
        if doc.paid_amount == 0 and rng.random() < 0.6:
            amt = doc.grand_total if rng.random() < 0.5 else (doc.grand_total * D("0.5")).quantize(D("1"))
            on = min(doc.date + timedelta(days=rng.randint(3, 20)), today)
            party = await db.get(Party, doc.party_id)
            v = await post_voucher(db, ctx, voucher_type="receipt", on=on, lines=[LineSpec(bank.id, debit=amt), LineSpec(party.ledger_id, credit=amt)], narration=f"NEFT received from {party.name}", party_id=party.id)
            await allocate(db, ctx, v, party.id, "receivable", amt, None, True)
    # supplier payment
    sup = suppliers[0]
    v = await post_voucher(db, ctx, voucher_type="payment", on=start + timedelta(days=30), lines=[LineSpec(sup.ledger_id, debit=D("150000")), LineSpec(bank.id, credit=D("150000"))], narration=f"Part payment to {sup.name}", party_id=sup.id)
    await allocate(db, ctx, v, sup.id, "payable", D("150000"), None, True)
    # expenses
    ledgers = {l.name: l for l in (await db.execute(select(Ledger).where(Ledger.company_id == company.id))).scalars().all()}
    await post_voucher(db, ctx, voucher_type="payment", on=today.replace(day=min(today.day, 5)), lines=[LineSpec(ledgers["Rent"].id, debit=D("45000")), LineSpec(bank.id, credit=D("45000"))], narration="Showroom rent")
    await post_voucher(db, ctx, voucher_type="payment", on=today - timedelta(days=3), lines=[LineSpec(ledgers["Electricity"].id, debit=D("8200")), LineSpec(cash.id, credit=D("8200"))], narration="MSEB bill")
    await post_voucher(db, ctx, voucher_type="payment", on=today - timedelta(days=1), lines=[LineSpec(ledgers["Transport & Delivery"].id, debit=D("6500")), LineSpec(cash.id, credit=D("6500"))], narration="Tempo charges for site deliveries")

    # quotations / orders / sales return / transfer
    q1 = await T.build_document(db, ctx, "quotation", TradeDocIn(date=today - timedelta(days=1), party_id=customers[0].id, valid_till=today + timedelta(days=14), lines=[TradeLineIn(product_id=tiles[2].id, qty=D("70"), rate=tiles[2].project_price, area_sqft=D("1070")), TradeLineIn(product_id=tiles[11].id, qty=D("30"), rate=tiles[11].project_price), TradeLineIn(product_id=sanitary[0].id, qty=D("4"), rate=sanitary[0].project_price)], notes="Tower B, 3BHK flats - flooring & master bath. 7% wastage included."))
    await T.post_document(db, ctx, q1)
    q2 = await T.build_document(db, ctx, "quotation", TradeDocIn(date=today, party_id=customers[7].id, valid_till=today + timedelta(days=7), lines=[TradeLineIn(product_id=tiles[5].id, qty=D("22"), rate=tiles[5].retail_price), TradeLineIn(product_id=tiles[6].id, qty=D("8"), rate=tiles[6].retail_price)]))
    so = await T.build_document(db, ctx, "sales_order", TradeDocIn(date=today - timedelta(days=3), party_id=customers[4].id, lines=[TradeLineIn(product_id=tiles[7].id, qty=D("40"), rate=tiles[7].project_price), TradeLineIn(product_id=tiles[8].id, qty=D("60"), rate=tiles[8].project_price)], notes="Terrace + parking, Phase 2"))
    await T.post_document(db, ctx, so)
    # sales return against first invoice
    if invoices:
        inv = invoices[0]
        ln = inv.lines[0]
        ret_data = TradeDocIn(date=today - timedelta(days=1), party_id=inv.party_id, reference_doc_id=inv.id, lines=[TradeLineIn(product_id=ln.product_id, qty=D("2") if ln.qty >= 2 else ln.qty, rate=ln.rate, batch_id=ln.batch_id, discount_pct=ln.discount_pct)], notes=f"Damaged boxes returned against {inv.doc_no}")
        ret = await T.build_document(db, ctx, "sales_return", ret_data)
        await T.post_document(db, ctx, ret)
    # stock transfer to Hadapsar
    sj2 = StockJournal(tenant_id=tenant.id, company_id=company.id, branch_id=branch.id, journal_type="transfer", doc_no=await next_number(db, tenant.id, company.id, "transfer", await get_fiscal_year(db, company.id, today)), date=today - timedelta(days=4), from_godown_id=main_godown.id, to_godown_id=g2.id, reason="Showroom display + stock", created_by=owner.id, lines=[])
    db.add(sj2)
    await db.flush()
    tl = []
    for p in (tiles[0], tiles[4], sanitary[2]):
        q = D("10") if p.product_type == "tile" else D("2")
        rate = await S.avg_cost(db, company.id, p.id)
        bid = batches[p.id][0].id if p.product_type == "tile" else None
        await S.add_movement(db, ctx, product=p, godown_id=main_godown.id, on=sj2.date, movement_type="transfer_out", quantity=-q, rate=rate, batch_id=bid, doc_type="stock_journal", doc_id=sj2.id, narration=sj2.doc_no)
        await S.add_movement(db, ctx, product=p, godown_id=g2.id, on=sj2.date, movement_type="transfer_in", quantity=q, rate=rate, batch_id=bid, doc_type="stock_journal", doc_id=sj2.id, narration=sj2.doc_no)
        tl.append({"product_id": str(p.id), "product_name": p.name, "sku": p.sku, "batch_id": str(bid) if bid else None, "qty": str(q), "unit": p.stock_unit.symbol, "rate": str(rate), "value": str(money(q * rate))})
    sj2.lines = tl
    # project + reservation + sample
    from .models import Project, SampleIssue, StockReservation

    proj = Project(tenant_id=tenant.id, company_id=company.id, party_id=customers[0].id, name="Sharma Heights - Tower B", site_address="Baner Road, Pune", budget=D("2500000"), notes="120 flats; flooring 600x1200 Onyx Beige")
    db.add(proj)
    await db.flush()
    db.add(StockReservation(tenant_id=tenant.id, company_id=company.id, product_id=tiles[2].id, batch_id=batches[tiles[2].id][0].id, godown_id=main_godown.id, party_id=customers[0].id, project_id=proj.id, qty=D("20"), reference=q1.doc_no, expires_on=today + timedelta(days=14)))
    db.add(SampleIssue(tenant_id=tenant.id, company_id=company.id, product_id=tiles[10].id, party_id=customers[2].id, qty=D("1"), issued_on=today - timedelta(days=6), expected_return_on=today + timedelta(days=1), notes="Highlighter sample for client approval"))
    await audit(db, ctx, "seed", "tenant", tenant.id, "Demo data seeded")


async def seed_second_tenant(db) -> None:
    tenant, company, branch, owner, roles = await _make_tenant(
        db,
        "Ganesh Ceramics",
        "ganesh",
        dict(name="Ganesh Ceramics", gstin="24AAACG1111B1Z2", address_line1="Ring Road", city="Surat", state="Gujarat", state_code="24", pincode="395002", phone="0261-2200000"),
        "owner@ganesh.tileos",
        "Ganesh Patel",
        "Admin@123",
    )
    units = {u.symbol: u for u in (await db.execute(select(Unit).where(Unit.company_id == company.id))).scalars().all()}
    db.add(Product(tenant_id=tenant.id, company_id=company.id, sku="GC-001", name="Ganesh Ivory 600x600", product_type="tile", stock_unit_id=units["Box"].id, sqft_per_box=D("15.5"), pieces_per_box=D("4"), hsn_code="69072100", gst_rate=D("18"), purchase_price=D("400"), sale_price=D("600"), retail_price=D("600")))
    await db.flush()
