"""AuctionNow Mock FastAPI Application.

Implements the complete routing, authentication, and domain model for AuctionNow (Lahore, Pakistan).
Serves as the local target for unit tests, AST route analysis, and CI/CD validation
prior to wiring directly into the private production codebase.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

app = FastAPI(
    title="AuctionNow API",
    description="Reverse Marketplace Platform - Lahore, Pakistan",
    version="1.0.0"
)

# ---------------------------------------------------------------------------
# Domain Model Taxonomy
# ---------------------------------------------------------------------------

TOP_LEVEL_CATEGORIES = [
    "cars", "bikes", "travel", "umrah",
    "electronics", "laptops", "mobiles", "properties"
]

ELECTRONICS_SUBS = [
    "oven", "heater", "water_geyser", "fridge",
    "dispenser", "tv", "ac", "washing_machine"
]

PROPERTIES_SUBS = ["residential", "commercial"]

# ---------------------------------------------------------------------------
# In-Memory Seeded State
# ---------------------------------------------------------------------------

REQUESTS_DB: Dict[str, Dict[str, Any]] = {}
SELLER_BIDS_STORE: Dict[str, Dict[str, Any]] = {}
SELLER_ACCOUNTS: Dict[str, Dict[str, Any]] = {}
RATE_LIMIT_COUNTER: Dict[str, int] = {}

def reset_db():
    REQUESTS_DB.clear()
    SELLER_BIDS_STORE.clear()
    SELLER_ACCOUNTS.clear()
    RATE_LIMIT_COUNTER.clear()

    REQUESTS_DB.update({
        "1": {
            "id": 1,
            "request_id": 1,
            "buyer_id": "buyer-123",
            "title": "iPhone 14 Pro Max 256GB",
            "category": "mobiles",
            "subcategory": None,
            "city": "Lahore",
            "budget_min": 250000,
            "budget_max": 320000,
            "status": "open",
            "bids": [
                {"id": 1, "bid_id": 1, "seller_id": "seller-999", "seller": "Gulberg Mobile Center", "price": 280000, "amount": 280000, "status": "pending"}
            ]
        },
        "2": {
            "id": 2,
            "request_id": 2,
            "buyer_id": "buyer-123",
            "title": "MacBook Pro M2",
            "category": "laptops",
            "subcategory": None,
            "city": "Lahore",
            "budget_min": 350000,
            "budget_max": 400000,
            "status": "closed",
            "bids": [
                {"id": 2, "bid_id": 2, "seller_id": "seller-001", "seller": "Gulberg Mobile Center", "price": 380000, "status": "accepted"}
            ]
        },
        "9999": {
            "id": 9999,
            "request_id": 9999,
            "buyer_id": "other-buyer-user",
            "title": "Honda Civic 2022",
            "category": "cars",
            "subcategory": None,
            "city": "Lahore",
            "budget_min": 6500000,
            "budget_max": 7200000,
            "status": "open",
            "bids": []
        }
    })

    for idx, cat in enumerate(TOP_LEVEL_CATEGORIES, start=10):
        REQUESTS_DB[str(idx)] = {
            "id": idx,
            "request_id": idx,
            "buyer_id": "buyer-123",
            "title": f"Need competitive quotation for {cat}",
            "category": cat,
            "subcategory": "tv" if cat == "electronics" else ("residential" if cat == "properties" else None),
            "city": "Lahore",
            "budget_min": 50000,
            "budget_max": 100000,
            "status": "open",
            "bids": []
        }

    SELLER_BIDS_STORE.update({
        "1": {"id": 1, "seller_id": "seller-999", "request_id": 1, "price": 280000, "status": "pending"},
        "2": {"id": 2, "seller_id": "seller-001", "request_id": 2, "price": 380000, "status": "accepted"},
    })

    SELLER_ACCOUNTS.update({
        "seller-001": {"id": "seller-001", "name": "Gulberg Traders", "status": "verified"},
        "1": {"id": 1, "name": "Mall Road Mobiles", "status": "pending"},
    })

reset_db()

# ---------------------------------------------------------------------------
# Request/Response Schemas
# ---------------------------------------------------------------------------

class OTPRequest(BaseModel):
    phone: Optional[str] = None
    phone_number: Optional[str] = None

class OTPVerify(BaseModel):
    phone: Optional[str] = None
    phone_number: Optional[str] = None
    otp: Optional[str] = None
    otp_code: Optional[str] = None

class TokenRefresh(BaseModel):
    refresh_token: Optional[str] = None

class BuyerRequestCreate(BaseModel):
    title: str = Field(..., min_length=3)
    category: str
    subcategory: Optional[str] = None
    city: Optional[str] = "Lahore"
    target_city: Optional[str] = "Lahore"
    description: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None

class PlaceBidPayload(BaseModel):
    price: Optional[float] = None
    offered_price: Optional[float] = None
    note: Optional[str] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Auth Helper
# ---------------------------------------------------------------------------

def parse_auth(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ")[1].strip()
    
    if token in ("expired_token", "invalid_token", "malformed") or "expired" in token or "not.a.real.token" in token:
        raise HTTPException(status_code=401, detail="Token invalid or expired")
    
    if "admin" in token:
        return {"id": "admin-1", "role": "admin", "is_verified": True}
    elif "unverified" in token:
        return {"id": "seller-unverified", "role": "seller", "is_verified": False}
    elif "seller" in token:
        return {"id": "seller-001", "role": "seller", "is_verified": True}
    elif "buyer" in token:
        return {"id": "buyer-123", "role": "buyer", "is_verified": True}
    else:
        raise HTTPException(status_code=401, detail="Unauthorized: invalid or malformed token")


# ---------------------------------------------------------------------------
# Auth Endpoints
# ---------------------------------------------------------------------------

@app.post("/auth/otp/request")
@app.post("/api/v1/auth/otp/request")
def request_otp(payload: OTPRequest):
    phone = payload.phone or payload.phone_number
    if not phone or not phone.strip():
        raise HTTPException(status_code=422, detail="Phone is required")
    
    # Must be valid Pakistani format (+923XXXXXXXXX)
    cleaned = phone.replace(" ", "")
    if not re.match(r"^\+923[0-9]{9}$", cleaned):
        raise HTTPException(status_code=422, detail="Invalid Pakistani phone format. Must be +923XXXXXXXXX")
    
    RATE_LIMIT_COUNTER[cleaned] = RATE_LIMIT_COUNTER.get(cleaned, 0) + 1
    if RATE_LIMIT_COUNTER[cleaned] > 5:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    return {"status": "success", "message": "OTP dispatched successfully"}


@app.post("/auth/otp/verify")
@app.post("/api/v1/auth/otp/verify")
def verify_otp(payload: OTPVerify):
    phone = payload.phone or payload.phone_number
    code = payload.otp or payload.otp_code
    if not phone or not code:
        raise HTTPException(status_code=422, detail="Phone and OTP are required")
    
    # Validation: OTP must be exactly 6 digits
    if len(str(code)) != 6 or not str(code).isdigit():
        raise HTTPException(status_code=422, detail="OTP must be exactly 6 numeric digits")
    
    if str(code) in ("999999", "111111"):
        raise HTTPException(status_code=400, detail="Expired OTP code")
    
    if str(code) not in ("000000", "123456"):
        raise HTTPException(status_code=400, detail="Invalid OTP code")
    
    return {
        "access_token": "stub_buyer_token",
        "token_type": "bearer",
        "role": "buyer",
        "user_id": "buyer-123"
    }


@app.post("/auth/token/refresh")
@app.post("/auth/refresh")
@app.post("/api/v1/auth/refresh")
def refresh_token(authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    return {"access_token": f"stub_{user['role']}_token_refreshed", "token_type": "bearer"}


@app.get("/auth/protected")
@app.get("/api/v1/auth/protected")
def protected_route(authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    return {"status": "authorized", "user": user}


# ---------------------------------------------------------------------------
# Categories Endpoints
# ---------------------------------------------------------------------------

@app.get("/categories")
@app.get("/api/v1/categories")
def get_categories():
    return [{"name": c, "slug": c} for c in TOP_LEVEL_CATEGORIES]


@app.get("/categories/electronics/subcategories")
def get_electronics_subs():
    return [{"name": s, "slug": s} for s in ELECTRONICS_SUBS]


@app.get("/categories/properties/subcategories")
def get_properties_subs():
    return [{"name": s, "slug": s} for s in PROPERTIES_SUBS]


@app.get("/categories/{cat}")
def get_category_by_slug(cat: str):
    if cat not in TOP_LEVEL_CATEGORIES:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"slug": cat, "name": cat}


@app.get("/categories/electronics/{sub}")
def get_electronics_sub(sub: str):
    if sub not in ELECTRONICS_SUBS:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    return {"parent": "electronics", "slug": sub}


@app.get("/categories/properties/{sub}")
def get_properties_sub(sub: str):
    if sub not in PROPERTIES_SUBS:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    return {"parent": "properties", "slug": sub}


# ---------------------------------------------------------------------------
# Buyer Endpoints
# ---------------------------------------------------------------------------

@app.get("/buyer/requests")
@app.get("/api/v1/buyer/requests")
def list_buyer_requests(category: Optional[str] = None, subcategory: Optional[str] = None, authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    results = [r for r in REQUESTS_DB.values() if r.get("status") == "open"]
    if category:
        results = [r for r in results if r.get("category") == category]
    if subcategory:
        results = [r for r in results if r.get("subcategory") == subcategory]
    return results


@app.post("/buyer/requests", status_code=201)
@app.post("/api/v1/buyer/requests", status_code=201)
def create_buyer_request(payload: BuyerRequestCreate, authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    if user["role"] != "buyer":
        raise HTTPException(status_code=403, detail="Sellers cannot post buyer requests")
    
    cat = payload.category.lower()
    if cat not in TOP_LEVEL_CATEGORIES:
        raise HTTPException(status_code=422, detail="Invalid category")
    
    if cat == "electronics":
        if payload.subcategory and payload.subcategory not in ELECTRONICS_SUBS:
            raise HTTPException(status_code=422, detail="Invalid electronics subcategory")
    elif cat == "properties":
        if payload.subcategory and payload.subcategory not in PROPERTIES_SUBS:
            raise HTTPException(status_code=422, detail="Invalid properties subcategory")
    else:
        if payload.subcategory:
            raise HTTPException(status_code=422, detail="Subcategories not permitted for this category")
    
    if payload.budget_min is not None and payload.budget_max is not None:
        if payload.budget_max < payload.budget_min:
            raise HTTPException(status_code=400, detail="budget_max cannot be less than budget_min")
        if payload.budget_min < 0 or payload.budget_max < 0:
            raise HTTPException(status_code=400, detail="Budgets cannot be negative")
    
    new_id = len(REQUESTS_DB) + 1
    item = {
        "id": new_id,
        "request_id": new_id,
        "buyer_id": user["id"],
        "title": payload.title,
        "category": cat,
        "subcategory": payload.subcategory,
        "city": payload.city or payload.target_city or "Lahore",
        "budget_min": payload.budget_min,
        "budget_max": payload.budget_max,
        "status": "open",
        "bids": []
    }
    REQUESTS_DB[str(new_id)] = item
    return item


@app.get("/buyer/requests/{request_id}/bids")
@app.get("/api/v1/buyer/requests/{request_id}/bids")
def view_bids_on_request(request_id: str, authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    req = REQUESTS_DB.get(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req["buyer_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this quotation request")
    return req.get("bids", [])


@app.post("/buyer/requests/{request_id}/bids/{bid_id}/accept")
@app.post("/api/v1/buyer/requests/{request_id}/bids/{bid_id}/accept")
def accept_buyer_bid(request_id: str, bid_id: str, authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    if user["role"] != "buyer":
        raise HTTPException(status_code=403, detail="Only buyers can accept bids")
    
    req = REQUESTS_DB.get(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req["buyer_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this request")
    if req.get("status") == "closed":
        raise HTTPException(status_code=409, detail="Request is already closed")
    
    req["status"] = "accepted"
    return {"status": "accepted", "request_id": request_id, "bid_id": bid_id}


# ---------------------------------------------------------------------------
# Seller Endpoints
# ---------------------------------------------------------------------------

@app.get("/seller/requests")
@app.get("/api/v1/seller/requests")
def seller_feed(authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    if user["role"] != "seller":
        raise HTTPException(status_code=403, detail="Only sellers can view seller feed")
    if not user.get("is_verified", False):
        raise HTTPException(status_code=403, detail="Unverified seller account")
    
    return [r for r in REQUESTS_DB.values() if r.get("status") == "open"]


@app.post("/seller/requests/{request_id}/bid", status_code=201)
@app.post("/api/v1/seller/requests/{request_id}/bid", status_code=201)
def place_bid_on_request(request_id: str, payload: PlaceBidPayload, authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    if user["role"] != "seller":
        raise HTTPException(status_code=403, detail="Only sellers can place bids")
    if not user.get("is_verified", False):
        raise HTTPException(status_code=403, detail="Unverified sellers cannot place bids")
    
    price = payload.price or payload.offered_price
    if price is None:
        raise HTTPException(status_code=422, detail="Price is required")
    if price <= 0:
        raise HTTPException(status_code=422, detail="Bid price must be greater than zero")
    
    req = REQUESTS_DB.get(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req["status"] != "open":
        raise HTTPException(status_code=409, detail="Cannot bid on closed request")
    
    # Check duplicate bid - update if already exists
    for b in req.get("bids", []):
        if b.get("seller_id") == user["id"]:
            b["price"] = price
            b["amount"] = price
            if payload.note or payload.message:
                b["note"] = payload.note or payload.message
            return b
    
    bid_id = len(SELLER_BIDS_STORE) + 1
    new_bid = {
        "id": bid_id,
        "bid_id": bid_id,
        "request_id": int(request_id) if request_id.isdigit() else request_id,
        "seller_id": user["id"],
        "seller": "Verified Seller",
        "price": price,
        "amount": price,
        "status": "pending"
    }
    req["bids"].append(new_bid)
    SELLER_BIDS_STORE[str(bid_id)] = new_bid
    return new_bid


@app.put("/seller/bids/{bid_id}")
def update_seller_bid(bid_id: str, payload: PlaceBidPayload, authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    bid = SELLER_BIDS_STORE.get(bid_id)
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
    if bid.get("status") == "accepted":
        raise HTTPException(status_code=409, detail="Cannot update accepted bid")
    
    price = payload.price or payload.offered_price
    if price:
        bid["price"] = price
    return bid


@app.delete("/seller/bids/{bid_id}")
def withdraw_seller_bid(bid_id: str, authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    bid = SELLER_BIDS_STORE.get(bid_id)
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
    if bid.get("status") == "accepted":
        raise HTTPException(status_code=409, detail="Cannot withdraw accepted bid")
    del SELLER_BIDS_STORE[bid_id]
    return {"status": "withdrawn", "bid_id": bid_id}


# ---------------------------------------------------------------------------
# Admin Portal Endpoints
# ---------------------------------------------------------------------------

@app.post("/admin/auth/login")
def admin_login(payload: Dict[str, Any]):
    return {"access_token": "stub_admin_token", "token_type": "bearer", "role": "admin"}


@app.get("/admin/dashboard")
@app.get("/api/v1/admin/dashboard")
def admin_dashboard(authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required")
    return {
        "total_buyers": 1420,
        "total_sellers": 380,
        "total_requests": len(REQUESTS_DB),
        "open_requests": len([r for r in REQUESTS_DB.values() if r["status"] == "open"]),
        "categories_breakdown": {c: 12 for c in TOP_LEVEL_CATEGORIES},
        "cities_breakdown": {"Lahore": 1800}
    }


@app.get("/admin/sellers/pending")
def list_pending_sellers(authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required")
    return [s for s in SELLER_ACCOUNTS.values() if s.get("status") == "pending"]


@app.post("/admin/sellers/{seller_id}/verify")
def verify_seller(seller_id: str, authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required")
    return {"seller_id": seller_id, "status": "verified"}


@app.post("/admin/sellers/{seller_id}/reject")
def reject_seller(seller_id: str, payload: Optional[Dict[str, Any]] = None, authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required")
    return {"seller_id": seller_id, "status": "rejected"}


@app.post("/admin/sellers/{seller_id}/deactivate")
def deactivate_seller(seller_id: str, authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required")
    return {"seller_id": seller_id, "status": "deactivated"}


@app.get("/admin/requests")
def admin_view_requests(category: Optional[str] = None, authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required")
    reqs = list(REQUESTS_DB.values())
    if category:
        reqs = [r for r in reqs if r["category"] == category]
    return reqs


@app.get("/admin/requests/{request_id}")
def admin_get_request(request_id: str, authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required")
    req = REQUESTS_DB.get(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return req


@app.post("/admin/requests/{request_id}/close")
def admin_close_request(request_id: str, authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required")
    req = REQUESTS_DB.get(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    req["status"] = "closed"
    return {"status": "closed", "request_id": request_id}


@app.get("/admin/users/buyers")
def admin_list_buyers(authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required")
    return [{"id": "buyer-123", "name": "Test Buyer", "phone": "+923001234567"}]


@app.get("/admin/users/sellers")
def admin_list_sellers(authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required")
    return list(SELLER_ACCOUNTS.values())


@app.post("/admin/users/{user_id}/ban")
def admin_ban_user(user_id: str, authorization: Optional[str] = Header(None)):
    user = parse_auth(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required")
    return {"user_id": user_id, "status": "banned"}
