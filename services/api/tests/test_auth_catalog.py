from sqlalchemy import select

from app.models import Membership, Session

from .conftest import catalog, register


def test_auth_csrf_session_revocation(setup):
    c, dbs = setup
    assert c.get("/api/products").status_code == 401
    c.headers.pop("X-OrderMesh")
    assert c.post("/api/auth/logout").status_code == 403
    c.headers["X-OrderMesh"] = "1"
    register(c)
    assert c.get("/api/auth/me").status_code == 200
    with dbs() as db:
        session = db.scalar(select(Session))
        assert session.token_hash != c.cookies.get("ordermesh_session")
    assert (
        c.post(
            "/api/customers",
            json={"name": "X"},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    old = c.cookies.get("ordermesh_session")
    c.post("/api/auth/logout")
    c.cookies.set("ordermesh_session", old)
    assert c.get("/api/auth/me").status_code == 401


def test_login_generic_error_and_success(setup):
    c, _ = setup
    register(c)
    c.post("/api/auth/logout")
    for email in ["one@example.com", "missing@example.com"]:
        r = c.post("/api/auth/login", json={"email": email, "password": "incorrect"})
        assert (
            r.status_code == 401 and r.json()["detail"] == "Invalid email or password"
        )
    assert (
        c.post(
            "/api/auth/login",
            json={"email": "one@example.com", "password": "test-only-password-123"},
        ).status_code
        == 200
    )


def test_tenant_isolation_and_membership_revocation(setup):
    c, dbs = setup
    first = register(c)
    customer, product = catalog(c)
    second = register(c, "two")
    assert c.get("/api/customers").json() == []
    assert (
        c.put(f"/api/customers/{customer['id']}", json={"name": "stolen"}).status_code
        == 404
    )
    assert (
        c.post(
            f"/api/products/{product['id']}/stock", json={"delta": 1, "reason": "steal"}
        ).status_code
        == 404
    )
    assert (
        c.get(
            "/api/products", headers={"X-Organization-ID": first["organization_id"]}
        ).status_code
        == 403
    )
    with dbs() as db:
        member = db.get(Membership, (second["id"], second["organization_id"]))
        db.delete(member)
        db.commit()
    assert c.get("/api/products").status_code == 403


def test_roles_are_checked_live(setup):
    c, dbs = setup
    account = register(c)
    _, product = catalog(c)
    with dbs() as db:
        member = db.get(Membership, (account["id"], account["organization_id"]))
        member.role = "viewer"
        db.commit()
    assert c.get("/api/products").status_code == 200
    assert c.post("/api/customers", json={"name": "Forbidden"}).status_code == 403
    assert c.post("/api/extractions", json={"text": "Rice 2"}).status_code == 403
    assert c.get("/api/audit").status_code == 403


def test_catalog_validation_and_ledger(setup):
    c, _ = setup
    register(c)
    _, p = catalog(c)
    assert (
        c.post(
            "/api/products", json={"name": "Rice", "sku": "RICE-1", "price_minor": 1}
        ).status_code
        == 409
    )
    assert (
        c.post(
            "/api/products", json={"name": "Bad", "sku": "BAD", "price_minor": -1}
        ).status_code
        == 422
    )
    assert (
        c.post(
            f"/api/products/{p['id']}/stock", json={"delta": -31, "reason": "Too much"}
        ).status_code
        == 409
    )
    assert len(c.get("/api/stock-movements").json()) == 1
    assert c.get("/api/products").json()[0]["stock"] == 30


def test_auth_rate_limit(setup):
    c, _ = setup
    for _ in range(10):
        assert (
            c.post(
                "/api/auth/login",
                json={"email": "none@example.com", "password": "wrong"},
            ).status_code
            == 401
        )
    assert (
        c.post(
            "/api/auth/login", json={"email": "none@example.com", "password": "wrong"}
        ).status_code
        == 429
    )
