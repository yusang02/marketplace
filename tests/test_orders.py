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


# --- Race condition tests ---

# One round can miss a race, so repeat it
RACE_ROUNDS = 20


def _post_at_the_same_time(client, requests):
    """Send POST requests at the same time and return their status codes."""
    barrier = threading.Barrier(len(requests))  # all threads start together
    results = []

    def send(path, headers, body):
        barrier.wait()
        response = client.post(path, headers=headers, json=body)
        results.append(response.status_code)

    threads = []
    for path, headers, body in requests:
        threads.append(threading.Thread(target=send, args=(path, headers, body)))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return sorted(results)


def test_two_buyers_cannot_both_take_the_same_stock(client, alice, bob, listing):
    """Two buyers order all stock at once. Only one succeeds."""

    carol = {"X-User-Id": "carol"}
    body = {"listing_id": listing["id"], "quantity": 5}

    for _ in range(RACE_ROUNDS):
        # Refill to 5 so every round fights over the full stock again
        client.patch(f"/listings/{listing['id']}", json={"quantity": 5}, headers=alice)

        results = _post_at_the_same_time(client, [
            ("/orders", bob, body),
            ("/orders", carol, body),
        ])

        assert results == [200, 409]
        assert client.get(f"/listings/{listing['id']}", headers=alice).json()["quantity"] == 0


def test_double_cancel_restores_stock_once(client, alice, bob, listing):
    """Buyer and seller cancel at once. Stock is restored only once."""

    for _ in range(RACE_ROUNDS):
        order = client.post(
            "/orders", json={"listing_id": listing["id"], "quantity": 2}, headers=bob
        ).json()
        cancel = f"/orders/{order['id']}/cancel"

        results = _post_at_the_same_time(client, [
            (cancel, bob, None),
            (cancel, alice, None),
        ])

        assert client.get(f"/listings/{listing['id']}", headers=bob).json()["quantity"] == 5
        assert results == [200, 409]


def test_pay_and_cancel_at_once_ends_cancelled(client, alice, bob, listing):
    """Pay and cancel at once. Never ends PAID with stock already restored."""

    for _ in range(RACE_ROUNDS):
        order = client.post(
            "/orders", json={"listing_id": listing["id"], "quantity": 2}, headers=bob
        ).json()

        _post_at_the_same_time(client, [
            (f"/orders/{order['id']}/pay", bob, None),
            (f"/orders/{order['id']}/cancel", alice, None),
        ])

        # Must end CANCELLED with stock back, never PAID with stock returned
        for row in client.get("/orders", headers=bob).json():
            if row["id"] == order["id"]:
                status = row["status"]
        stock = client.get(f"/listings/{listing['id']}", headers=bob).json()["quantity"]
        assert (status, stock) == ("CANCELLED", 5)