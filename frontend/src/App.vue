<script setup>
import { ref, onMounted } from "vue";

const result = ref("");

async function check() {
  const response = await fetch("http://localhost:8000/listings", {
    headers: { "X-User-Id": "alice" },
  });
  const body = await response.json();
  result.value = `${body.length} listings`;
}

onMounted(check);
</script>

<template>
  <h1>{{ result }}</h1>
</template>
