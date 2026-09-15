def test_create_listing_sets_owner_from_header(client, alice):
    response = client.post(
        "/listings",
        json={"title": "LOL Account", "game": "LOL", "price": "300.50", "quantity": 5},
        headers=alice,
    )
    assert response.status_code == 200
    assert response.json()["owner_id"] == "alice"


def test_missing_user_header_is_401(client):
    response = client.post(
        "/listings",
        json={"title": "LOL Account", "game": "LOL", "price": "300.50", "quantity": 5},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_blank_user_header_is_401(client):
    response = client.get("/listings", headers={"X-User-Id": "   "})
    assert response.status_code == 401


def test_create_listing_trims_title(client, alice):
    response = client.post(
        "/listings",
        json={"title": "  LOL Account  ", "game": "LOL", "price": "300.50", "quantity": 5},
        headers=alice,
    )
    assert response.json()["title"] == "LOL Account"


def test_empty_title_is_rejected(client, alice):
    response = client.post(
        "/listings",
        json={"title": "", "game": "LOL", "price": "300.50", "quantity": 5},
        headers=alice,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
 
 
def test_blank_title_is_rejected(client, alice):
    response = client.post(
        "/listings",
        json={"title": "   ", "game": "LOL", "price": "300.50", "quantity": 5},
        headers=alice,
    )
    assert response.status_code == 422
 
 
def test_too_long_title_is_rejected(client, alice):
    response = client.post(
        "/listings",
        json={"title": "x" * 101, "game": "LOL", "price": "300.50", "quantity": 5},
        headers=alice,
    )
    assert response.status_code == 422
 
 
def test_empty_game_is_rejected(client, alice):
    response = client.post(
        "/listings",
        json={"title": "LOL Account", "game": "", "price": "300.50", "quantity": 5},
        headers=alice,
    )
    assert response.status_code == 422
 
 
def test_zero_price_is_rejected(client, alice):
    response = client.post(
        "/listings",
        json={"title": "LOL Account", "game": "LOL", "price": "0", "quantity": 5},
        headers=alice,
    )
    assert response.status_code == 422
 
 
def test_negative_price_is_rejected(client, alice):
    response = client.post(
        "/listings",
        json={"title": "LOL Account", "game": "LOL", "price": "-5.00", "quantity": 5},
        headers=alice,
    )
    assert response.status_code == 422
 
 
def test_price_with_three_decimals_is_rejected(client, alice):
    response = client.post(
        "/listings",
        json={"title": "LOL Account", "game": "LOL", "price": "300.555", "quantity": 5},
        headers=alice,
    )
    assert response.status_code == 422
 
 
def test_zero_quantity_is_rejected(client, alice):
    response = client.post(
        "/listings",
        json={"title": "LOL Account", "game": "LOL", "price": "300.50", "quantity": 0},
        headers=alice,
    )
    assert response.status_code == 422
 
 
def test_fractional_quantity_is_rejected(client, alice):
    response = client.post(
        "/listings",
        json={"title": "LOL Account", "game": "LOL", "price": "300.50", "quantity": 1.5},
        headers=alice,
    )
    assert response.status_code == 422


def test_list_filters_by_game(client, alice):
    client.post(
        "/listings",
        json={"title": "LOL Account", "game": "LOL", "price": "300.50", "quantity": 5},
        headers=alice,
    )
    client.post(
        "/listings",
        json={"title": "Elden Ring DLC", "game": "Elden Ring", "price": "199.99", "quantity": 5},
        headers=alice,
    )
 
    everything = client.get("/listings", headers=alice).json()
    assert len(everything) == 2
 
    lol_only = client.get("/listings?game=LOL", headers=alice).json()
    assert len(lol_only) == 1
    assert lol_only[0]["title"] == "LOL Account"


def test_sold_out_listings_are_hidden(client, alice, bob, listing):
    # bob buys every unit, dropping the listing to quantity 0
    client.post(
        "/orders", json={"listing_id": listing["id"], "quantity": 5}, headers=bob
    )
    # quantity is 0, so it drops out of the list for everyone
    assert client.get("/listings", headers=bob).json() == []
    # still reachable directly by id
    assert client.get(f"/listings/{listing['id']}", headers=bob).status_code == 200


def test_missing_listing_is_404(client, alice):
    response = client.get("/listings/999", headers=alice)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LISTING_NOT_FOUND"


def test_owner_can_patch(client, alice, listing):
    response = client.patch(
        f"/listings/{listing['id']}",
        json={"title": "Cheap LOL Account", "price": "250.00", "quantity": 10},
        headers=alice,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Cheap LOL Account"
    assert body["price"] == 250.00
    assert body["quantity"] == 10


def test_patch_only_changes_price_sent(client, alice, listing):
    response = client.patch(
        f"/listings/{listing['id']}", json={"price": "250.00"}, headers=alice
    )
    body = response.json()
    assert body["price"] == 250.00
    assert body["title"] == "LOL Unranked Smurf Account" 
    assert body["quantity"] == 5   


def test_patch_by_non_owner_is_403(client, bob, listing):
    response = client.patch(
        f"/listings/{listing['id']}", json={"price": "1.00"}, headers=bob
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

def test_patch_with_a_blank_title_is_rejected(client, alice, listing):
    response = client.patch(
        f"/listings/{listing['id']}", json={"title": "   "}, headers=alice
    )
    assert response.status_code == 422


def test_patch_with_a_null_title_leaves_it_unchanged(client, alice, listing):
    response = client.patch(
        f"/listings/{listing['id']}", json={"title": None, "price": "250.00"}, headers=alice
    )
    assert response.status_code == 200
    assert response.json()["title"] == "LOL Unranked Smurf Account"


def test_delete_by_non_owner_is_403(client, bob, listing):
    response = client.delete(f"/listings/{listing['id']}", headers=bob)
    assert response.status_code == 403


def test_delete_is_blocked_while_an_order_is_active(client, alice, bob, listing):
    order = client.post(
        "/orders", json={"listing_id": listing["id"], "quantity": 1}, headers=bob
    ).json()
 
    blocked = client.delete(f"/listings/{listing['id']}", headers=alice)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "LISTING_HAS_ACTIVE_ORDERS"
 
    # CANCELLED is final, so the listing can go once the order is cancelled
    client.post(f"/orders/{order['id']}/cancel", headers=bob)
    assert client.delete(f"/listings/{listing['id']}", headers=alice).status_code == 200