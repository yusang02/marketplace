import threading


def test_happy_path_create_order_pay_deliver(client, alice, bob, listing):
    response = client.post(
        "/orders", json={"listing_id": listing["id"], "quantity": 2}, headers=bob
    )
    assert response.status_code == 200
    order = response.json()
    assert order["status"] == "PENDING"
    assert order["buyer_id"] == "bob"
    assert order["seller_id"] == "alice"

    # ordering decremented the listing
    assert client.get(f"/listings/{listing['id']}", headers=bob).json()["quantity"] == 3

    paid = client.post(f"/orders/{order['id']}/pay", headers=bob)
    assert paid.status_code == 200
    assert paid.json()["status"] == "PAID"

    delivered = client.post(f"/orders/{order['id']}/deliver", headers=alice)
    assert delivered.status_code == 200
    assert delivered.json()["status"] == "DELIVERED"


def test_cannot_order_your_own_listing(client, alice, listing):
    response = client.post(
        "/orders", json={"listing_id": listing["id"], "quantity": 1}, headers=alice
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SELF_PURCHASE"


def test_ordering_a_missing_listing_is_404(client, bob):
    response = client.post(
        "/orders", json={"listing_id": 999, "quantity": 1}, headers=bob
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LISTING_NOT_FOUND"


def test_acting_on_a_missing_order_is_404(client, bob):
    response = client.post("/orders/999/pay", headers=bob)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"


def test_insufficient_stock_is_409(client, bob, listing):
    response = client.post(
        "/orders", json={"listing_id": listing["id"], "quantity": 10}, headers=bob
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_STOCK"
    # the failed order must not have touched the stock
    assert client.get(f"/listings/{listing['id']}", headers=bob).json()["quantity"] == 5


def test_only_the_buyer_can_pay(client, alice, bob, listing):
    order = client.post(
        "/orders", json={"listing_id": listing["id"], "quantity": 1}, headers=bob
    ).json()

    response = client.post(f"/orders/{order['id']}/pay", headers=alice)  # seller tries
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_only_the_seller_can_deliver(client, bob, listing):
    order = client.post(
        "/orders", json={"listing_id": listing["id"], "quantity": 1}, headers=bob
    ).json()
    client.post(f"/orders/{order['id']}/pay", headers=bob)

    response = client.post(f"/orders/{order['id']}/deliver", headers=bob)  # buyer tries
    assert response.status_code == 403


def test_a_third_party_cannot_cancel(client, bob, listing):
    order = client.post(
        "/orders", json={"listing_id": listing["id"], "quantity": 1}, headers=bob
    ).json()

    response = client.post(f"/orders/{order['id']}/cancel", headers={"X-User-Id": "carol"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_delivering_a_pending_order_is_409(client, alice, bob, listing):
    """PENDING -> DELIVERED skips PAID, so it must be rejected."""
    order = client.post(
        "/orders", json={"listing_id": listing["id"], "quantity": 1}, headers=bob
    ).json()

    response = client.post(f"/orders/{order['id']}/deliver", headers=alice)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_TRANSITION"


def test_delivered_is_final(client, alice, bob, listing):
    order = client.post(
        "/orders", json={"listing_id": listing["id"], "quantity": 1}, headers=bob
    ).json()
    client.post(f"/orders/{order['id']}/pay", headers=bob)
    client.post(f"/orders/{order['id']}/deliver", headers=alice)

    assert client.post(f"/orders/{order['id']}/cancel", headers=bob).status_code == 409
    assert client.post(f"/orders/{order['id']}/pay", headers=bob).status_code == 409


def test_cancel_restores_stock(client, bob, listing):
    order = client.post(
        "/orders", json={"listing_id": listing["id"], "quantity": 2}, headers=bob
    ).json()
    assert client.get(f"/listings/{listing['id']}", headers=bob).json()["quantity"] == 3

    response = client.post(f"/orders/{order['id']}/cancel", headers=bob)
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert client.get(f"/listings/{listing['id']}", headers=bob).json()["quantity"] == 5


def test_seller_can_cancel_a_paid_order(client, alice, bob, listing):
    order = client.post(
        "/orders", json={"listing_id": listing["id"], "quantity": 1}, headers=bob
    ).json()
    client.post(f"/orders/{order['id']}/pay", headers=bob)

    response = client.post(f"/orders/{order['id']}/cancel", headers=alice)
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


def test_orders_are_only_visible_to_buyer_and_seller(client, alice, bob, listing):
    client.post(
        "/orders", json={"listing_id": listing["id"], "quantity": 1}, headers=bob
    )

    assert len(client.get("/orders", headers=bob).json()) == 1      # buyer
    assert len(client.get("/orders", headers=alice).json()) == 1    # seller
    assert client.get("/orders", headers={"X-User-Id": "carol"}).json() == []


def test_role_filter(client, alice, bob, listing):
    client.post(
        "/orders", json={"listing_id": listing["id"], "quantity": 1}, headers=bob
    )

    assert len(client.get("/orders?role=buyer", headers=bob).json()) == 1
    assert client.get("/orders?role=seller", headers=bob).json() == []
    assert len(client.get("/orders?role=seller", headers=alice).json()) == 1


def test_two_buyers_cannot_both_take_the_same_stock(client, listing):
    results = []

    def buy(user):
        response = client.post(
            "/orders",
            json={"listing_id": listing["id"], "quantity": 5},
            headers={"X-User-Id": user},
        )
        results.append(response.status_code)

    bob_thread = threading.Thread(target=buy, args=("bob",))
    carol_thread = threading.Thread(target=buy, args=("carol",))

    bob_thread.start()
    carol_thread.start()
    bob_thread.join()
    carol_thread.join()

    assert sorted(results) == [200, 409]
    assert client.get(f"/listings/{listing['id']}", headers={"X-User-Id": "alice"}).json()["quantity"] == 0


def test_orders_survive_their_listing_being_deleted(client, alice, bob, listing):
    order = client.post(
        "/orders",
        json={"listing_id": listing["id"], "quantity": 1},
        headers=bob,
    ).json()
    client.post(f"/orders/{order['id']}/cancel", headers=bob)

    assert client.delete(f"/listings/{listing['id']}", headers=alice).status_code == 200

    response = client.get("/orders", headers=bob)
    assert response.status_code == 200
    assert response.json()[0]["id"] == order["id"]
    assert response.json()[0]["listing_title"] == "LOL Unranked Smurf Account"


def test_seller_still_sees_an_order_after_deleting_the_listing(client, alice, bob, listing):
    order = client.post(
        "/orders",
        json={"listing_id": listing["id"], "quantity": 1},
        headers=bob,
    ).json()
    client.post(f"/orders/{order['id']}/cancel", headers=bob)
    client.delete(f"/listings/{listing['id']}", headers=alice)

    response = client.get("/orders", headers=alice)
    assert response.status_code == 200
    assert response.json()[0]["seller_id"] == "alice"