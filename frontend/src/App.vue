<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { api } from "./api.js";
import "./style.css";

// --- State ---

const currentUser = ref("alice");

const listings = ref([]);
const orders = ref([]);
const allGames = ref([]);

const gameFilter = ref("");
const listingSort = ref("new");
const roleFilter = ref("all");
const orderSort = ref("new");

const error = ref(null);

const modal = ref(null); // "new" | "listing" | "order"
const modalId = ref(null);
const menuOpen = ref(false);
const confirmDelete = ref(false);

const buyQuantity = ref(1);
const editForm = ref({ title: "", price: "", quantity: "" });
const newForm = ref({ title: "", game: "", price: "", quantity: "" });

// --- Loading ---

async function run(action) {
  error.value = null;
  try {
    await action();
  } catch (failure) {
    error.value = failure;
  }
}

async function loadListings() {
  const query = gameFilter.value ? `?game=${gameFilter.value}` : "";
  listings.value = await api(currentUser.value, `/listings${query}`);

  // There is no endpoint that lists games, so the dropdown is built from an
  // unfiltered response. A filtered one would shrink it to a single option.
  if (!gameFilter.value) {
    allGames.value = [
      ...new Set(listings.value.map((listing) => listing.game)),
    ];
  }
}

async function loadOrders() {
  const query = roleFilter.value === "all" ? "" : `?role=${roleFilter.value}`;
  orders.value = await api(currentUser.value, `/orders${query}`);
}

function reload() {
  return run(async () => {
    await loadListings();
    await loadOrders();
  });
}

onMounted(reload);

watch(currentUser, () => {
  closeModal();
  reload();
});
watch(gameFilter, () => run(loadListings));
watch(roleFilter, () => run(loadOrders));

// --- Sorting ---

// The API has no sort parameter, so this reorders what was already fetched.
// With pagination it would have to move to the server.
const sortedListings = computed(() => {
  const rows = [...listings.value];
  if (listingSort.value === "price_asc")
    return rows.sort((a, b) => a.price - b.price);
  if (listingSort.value === "price_desc")
    return rows.sort((a, b) => b.price - a.price);
  if (listingSort.value === "stock")
    return rows.sort((a, b) => b.quantity - a.quantity);
  return rows.sort((a, b) => b.id - a.id);
});

const STATUS_ORDER = { PENDING: 0, PAID: 1, DELIVERED: 2, CANCELLED: 3 };

const sortedOrders = computed(() => {
  const rows = [...orders.value];
  if (orderSort.value === "old") return rows.sort((a, b) => a.id - b.id);
  if (orderSort.value === "status") {
    return rows.sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status]);
  }
  return rows.sort((a, b) => b.id - a.id);
});

// --- Permissions ---

// These mirror the server's rules so the buttons match what is allowed.
// They are a convenience only: the API still answers 403 or 409 by itself.
function canPay(order) {
  return order.status === "PENDING" && order.buyer_id === currentUser.value;
}

function canDeliver(order) {
  return order.status === "PAID" && order.seller_id === currentUser.value;
}

function canCancel(order) {
  const open = order.status === "PENDING" || order.status === "PAID";
  const mine =
    order.buyer_id === currentUser.value ||
    order.seller_id === currentUser.value;
  return open && mine;
}

const FINAL_NOTE = {
  DELIVERED: "Delivered and complete. Nothing left to do.",
  CANCELLED: "Cancelled. The stock went back to the listing.",
};

// --- Formatting ---

function money(amount) {
  return `RM ${amount.toFixed(2)}`;
}

function shortDate(value) {
  return new Date(value).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
  });
}

function longDate(value) {
  return new Date(value).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function capitalise(status) {
  return status[0] + status.slice(1).toLowerCase();
}

// --- Modal ---

// The open row is looked up by id every time instead of being copied into a
// ref, so reloading the lists also refreshes what the modal shows.
const openListing = computed(() =>
  listings.value.find((row) => row.id === modalId.value),
);
const openOrder = computed(() =>
  orders.value.find((row) => row.id === modalId.value),
);

const isMyListing = computed(
  () => openListing.value.owner_id === currentUser.value,
);

const buyTotal = computed(() => openListing.value.price * buyQuantity.value);

function openNew() {
  modal.value = "new";
  newForm.value = { title: "", game: "", price: "", quantity: "" };
}

function openListingModal(listing) {
  modal.value = "listing";
  modalId.value = listing.id;
  menuOpen.value = false;
  confirmDelete.value = false;
  buyQuantity.value = 1;
  editForm.value = {
    title: listing.title,
    price: listing.price.toFixed(2),
    quantity: listing.quantity,
  };
}

function openOrderModal(order) {
  modal.value = "order";
  modalId.value = order.id;
}

function closeModal() {
  modal.value = null;
  modalId.value = null;
  menuOpen.value = false;
  confirmDelete.value = false;
}

// --- Actions ---

function createListing() {
  run(async () => {
    await api(currentUser.value, "/listings", {
      method: "POST",
      body: JSON.stringify({
        title: newForm.value.title,
        game: newForm.value.game,
        price: Number(newForm.value.price),
        quantity: Number(newForm.value.quantity),
      }),
    });
    closeModal();
    await loadListings();
  });
}

function saveListing() {
  const id = modalId.value;
  run(async () => {
    await api(currentUser.value, `/listings/${id}`, {
      method: "PATCH",
      body: JSON.stringify({
        title: editForm.value.title,
        price: Number(editForm.value.price),
        quantity: Number(editForm.value.quantity),
      }),
    });
    closeModal();
    await loadListings();
  });
}

function deleteListing() {
  const id = modalId.value;
  run(async () => {
    await api(currentUser.value, `/listings/${id}`, { method: "DELETE" });
    closeModal();
    await loadListings();
  });
}

function placeOrder() {
  const id = modalId.value;
  run(async () => {
    await api(currentUser.value, "/orders", {
      method: "POST",
      body: JSON.stringify({
        listing_id: id,
        quantity: Number(buyQuantity.value),
      }),
    });
    closeModal();
    await loadListings();
    await loadOrders();
  });
}

// Every action reloads both lists: the server is the only source of truth, so
// the stock number on screen is what the database actually holds.
function orderAction(name) {
  const id = modalId.value;
  run(async () => {
    await api(currentUser.value, `/orders/${id}/${name}`, { method: "POST" });
    await loadListings();
    await loadOrders();
  });
}
</script>

<template>
  <div class="page">
    <!-- --- Header --- -->
    <div class="topbar">
      <h1>Marketplace</h1>
      <div class="switcher">
        <span class="muted">user</span>
        <input v-model="currentUser" class="user-input" />
        <button @click="currentUser = 'alice'">alice</button>
        <button @click="currentUser = 'bob'">bob</button>
      </div>
    </div>

    <div v-if="error" class="banner">
      <span
        ><b>{{ error.code }}</b> · {{ error.message }}</span
      >
      <button class="plain" @click="error = null">&times;</button>
    </div>

    <div class="columns">
      <!-- --- Listings --- -->
      <div class="card">
        <div class="card-head">
          <h2>Listings</h2>
          <button @click="openNew">+ New</button>
        </div>
        <div class="toolbar">
          <select v-model="gameFilter">
            <option value="">All games</option>
            <option v-for="game in allGames" :key="game" :value="game">
              {{ game }}
            </option>
          </select>
          <select v-model="listingSort">
            <option value="new">Newest</option>
            <option value="price_asc">Price up</option>
            <option value="price_desc">Price down</option>
            <option value="stock">Stock</option>
          </select>
        </div>
        <p v-if="sortedListings.length === 0" class="empty">
          {{ gameFilter ? "No listings for that game." : "No listings yet." }}
        </p>
        <div
          v-for="listing in sortedListings"
          :key="listing.id"
          class="row"
          @click="openListingModal(listing)"
        >
          <div class="row-line">
            <span>{{ listing.title }}</span>
            <span class="price">{{ money(listing.price) }}</span>
          </div>
          <div class="row-line">
            <span class="tag game">{{ listing.game }}</span>
            <span class="muted">
              {{ listing.quantity }} in stock ·
              {{ shortDate(listing.created_at) }}
            </span>
          </div>
        </div>
      </div>

      <!-- --- Orders --- -->
      <div class="card">
        <div class="card-head">
          <h2>Orders</h2>
        </div>
        <div class="toolbar">
          <select v-model="roleFilter">
            <option value="all">All</option>
            <option value="buyer">Buying</option>
            <option value="seller">Selling</option>
          </select>
          <select v-model="orderSort">
            <option value="new">Newest</option>
            <option value="old">Oldest</option>
            <option value="status">Status</option>
          </select>
        </div>

        <p v-if="sortedOrders.length === 0" class="empty">No orders yet.</p>
        <div
          v-for="order in sortedOrders"
          :key="order.id"
          class="row"
          @click="openOrderModal(order)"
        >
          <div class="row-line">
            <span
              ><span class="muted">#{{ order.id }}</span>
              {{ order.listing_title }}</span
            >
            <span class="tag" :class="order.status">{{
              capitalise(order.status)
            }}</span>
          </div>
          <div class="row-line muted">
            <span>
              {{ order.quantity }} &times; {{ money(order.unit_price) }} ·
              {{ money(order.unit_price * order.quantity) }}
            </span>
            <span>{{ longDate(order.created_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- --- Modal --- -->
    <div v-if="modal" class="backdrop" @click.self="closeModal">
      <div class="modal">
        <div class="modal-head">
          <button
            v-if="modal === 'listing' && isMyListing && !confirmDelete"
            class="plain"
            @click="menuOpen = !menuOpen"
          >
            &#8943;
          </button>
          <button class="plain" @click="closeModal">&times;</button>
          <div v-if="menuOpen" class="menu">
            <button
              class="danger plain"
              @click="
                menuOpen = false;
                confirmDelete = true;
              "
            >
              Delete listing
            </button>
          </div>
        </div>

        <!-- New listing -->
        <div v-if="modal === 'new'">
          <h3>New listing</h3>
          <label>Title</label>
          <input v-model="newForm.title" placeholder="" />
          <label>Game</label>
          <input v-model="newForm.game" list="games" placeholder="" />
          <datalist id="games">
            <option v-for="game in allGames" :key="game" :value="game" />
          </datalist>
          <div class="two">
            <div>
              <label>Price (RM)</label>
              <input v-model="newForm.price" placeholder="0.00" />
            </div>
            <div>
              <label>Quantity</label>
              <input v-model="newForm.quantity" type="number" placeholder="1" />
            </div>
          </div>
          <hr />
          <div class="buttons">
            <button @click="createListing">Create listing</button>
          </div>
        </div>

        <!-- Delete confirmation -->
        <div v-else-if="modal === 'listing' && confirmDelete">
          <h3>Delete this listing?</h3>
          <p class="muted">
            {{ openListing.title }} will be removed permanently. Orders already
            placed against it stay in your history.
          </p>
          <hr />
          <div class="buttons">
            <button @click="confirmDelete = false">Keep listing</button>
            <button class="danger" @click="deleteListing">
              Delete listing
            </button>
          </div>
        </div>

        <!-- Listing detail -->
        <div v-else-if="modal === 'listing'">
          <h3>{{ openListing.title }}</h3>
          <div class="row-line">
            <span class="tag game">{{ openListing.game }}</span>
            <span class="muted">{{ shortDate(openListing.created_at) }}</span>
          </div>

          <div class="two boxes">
            <div class="box">
              <div class="muted">Unit price</div>
              <div class="big">{{ money(openListing.price) }}</div>
            </div>
            <div class="box">
              <div class="muted">In stock</div>
              <div class="big">{{ openListing.quantity }}</div>
            </div>
          </div>
          <hr />

          <label class="nudge">Seller</label>
          <div class="nudge">
            {{ openListing.owner_id }}
            <span v-if="isMyListing" class="muted">(you)</span>
          </div>
          <hr />

          <!-- Owner sees the edit form, everyone else sees the buy form -->
          <div v-if="isMyListing">
            <label>Title</label>
            <input v-model="editForm.title" />
            <div class="two">
              <div>
                <label>Price (RM)</label>
                <input v-model="editForm.price" />
              </div>
              <div>
                <label>Quantity</label>
                <input v-model="editForm.quantity" type="number" />
              </div>
            </div>
            <hr />
            <div class="buttons">
              <button @click="saveListing">Save changes</button>
            </div>
          </div>

          <div v-else>
            <div class="row-line bottom">
              <div>
                <label>Quantity</label>
                <input
                  v-model="buyQuantity"
                  type="number"
                  min="1"
                  class="qty"
                />
              </div>
              <div class="right">
                <div class="muted">Total</div>
                <div class="big">{{ money(buyTotal) }}</div>
              </div>
            </div>
            <hr />
            <div class="buttons">
              <button @click="placeOrder">Place order</button>
            </div>
          </div>
        </div>

        <!-- Order detail -->
        <div v-else-if="modal === 'order'">
          <div class="row-line">
            <span class="muted">Order #{{ openOrder.id }}</span>
            <span class="tag" :class="openOrder.status">{{
              capitalise(openOrder.status)
            }}</span>
          </div>
          <h3>{{ openOrder.listing_title }}</h3>
          <div class="two boxes">
            <div class="box">
              <div class="muted">Quantity</div>
              <div class="big">
                {{ openOrder.quantity }} &times;
                {{ money(openOrder.unit_price) }}
              </div>
            </div>
            <div class="box">
              <div class="muted">Total</div>
              <div class="big">
                {{ money(openOrder.unit_price * openOrder.quantity) }}
              </div>
            </div>
          </div>
          <hr />

          <div class="two">
            <div>
              <label>Buyer</label>
              <div>{{ openOrder.buyer_id }}</div>
            </div>
            <div>
              <label>Seller</label>
              <div>{{ openOrder.seller_id }}</div>
            </div>
          </div>
          <label class="spaced">Placed</label>
          <div>{{ longDate(openOrder.created_at) }}</div>
          <hr />

          <div
            v-if="
              canPay(openOrder) || canDeliver(openOrder) || canCancel(openOrder)
            "
            class="buttons"
          >
            <button v-if="canPay(openOrder)" @click="orderAction('pay')">
              Pay
            </button>
            <button
              v-if="canDeliver(openOrder)"
              @click="orderAction('deliver')"
            >
              Deliver
            </button>
            <button
              v-if="canCancel(openOrder)"
              class="danger"
              @click="orderAction('cancel')"
            >
              Cancel
            </button>
          </div>
          <p v-else class="muted">{{ FINAL_NOTE[openOrder.status] }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
