<template>
  <v-snackbar
    v-model="store.show"
    :color="store.color"
    :timeout="store.timeout"
    location="top right" 
    elevation="4"
  >
    <div class="d-flex align-center">
        <v-icon v-if="store.color === 'success'" icon="mdi-check-circle" start></v-icon>
        <v-icon v-if="store.color === 'error'" icon="mdi-alert-circle" start></v-icon>
        <v-icon v-if="store.color === 'warning'" icon="mdi-alert" start></v-icon>
        
        <span class="font-weight-medium">{{ store.message }}</span>
    </div>

    <template v-slot:actions>
      <v-btn
        icon="mdi-close"
        variant="text"
        size="small"
        @click="store.show = false"
      ></v-btn>
    </template>
  </v-snackbar>
</template>

<script setup>
import { useToastStore } from '@/stores/toast';

const store = useToastStore();
</script>