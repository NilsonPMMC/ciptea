<template>
  <v-container class="fill-height justify-center">
    <v-card width="100%" max-width="450" class="pa-8" elevation="8">
      <div class="text-center mb-6 mt-4">
        <img src="/brasao.png" height="60" alt="Brasão Mogi"> 
        <h2 class="text-h5 font-weight-bold text-primary">CIPTEA - PAC</h2>
        <p class="text-caption text-grey">Acesso Restrito</p>
      </div>

      <v-form @submit.prevent="fazerLogin">
        <v-text-field
          v-model="username"
          label="Usuário"
          prepend-inner-icon="mdi-account"
          variant="outlined"
          class="mb-2"
        ></v-text-field>

        <v-text-field
          v-model="password"
          label="Senha"
          type="password"
          prepend-inner-icon="mdi-key"
          variant="outlined"
          class="mb-4"
        ></v-text-field>

        <v-btn 
            block 
            color="primary" 
            size="large" 
            type="submit" 
            :loading="loading"
        >
            Entrar
        </v-btn>
      </v-form>

      <div class="text-center mt-4">
          <v-btn variant="text" size="small" to="/" color="grey">
              Voltar ao Aplicativo
          </v-btn>
      </div>
    </v-card>
  </v-container>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useToastStore } from '@/stores/toast';

const username = ref('');
const password = ref('');
const loading = ref(false);

const router = useRouter();
const authStore = useAuthStore();
const toast = useToastStore();

const fazerLogin = async () => {
    loading.value = true;
    try {
        await authStore.login(username.value, password.value);
        router.push('/admin'); // Redireciona para o Dashboard
        toast.success(`Bem-vindo, ${username.value}!`);
    } catch (error) {
        toast.error('Usuário ou senha inválidos.');
    } finally {
        loading.value = false;
    }
}
</script>