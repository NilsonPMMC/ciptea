<template>
  <v-app>
    <v-main>
      <RouterView />
    </v-main>
    <GlobalToast />
  </v-app>
</template>

<script setup>
import GlobalToast from '@/components/GlobalToast.vue';
</script>