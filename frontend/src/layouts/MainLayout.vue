<template>
  <q-layout view="lHh Lpr lFf" class="app-layout">
    <q-header bordered class="bg-white text-dark">
      <q-toolbar class="q-px-md">
        <q-btn flat dense round icon="menu" aria-label="Navigation" @click="toggleLeftDrawer" />

        <q-toolbar-title class="row items-center q-gutter-md">
          <div>
            <div class="text-subtitle1 text-weight-bold">Resume Search Console</div>
            <div class="text-caption text-grey-7">
              Upload resumes, monitor processing, and build candidate shortlists
            </div>
          </div>
        </q-toolbar-title>

        <q-chip
          dense
          square
          :color="apiConfigured ? 'positive' : 'warning'"
          :text-color="apiConfigured ? 'white' : 'black'"
        >
          {{ apiConfigured ? 'API connected' : 'API adapter pending' }}
        </q-chip>
      </q-toolbar>
    </q-header>

    <q-drawer v-model="leftDrawerOpen" show-if-above bordered :width="260">
      <div class="drawer-brand q-px-lg q-py-md">
        <div class="text-overline text-primary">Operations</div>
        <div class="text-h6 q-mt-xs">Candidate discovery</div>
      </div>

      <q-list class="q-px-sm">
        <q-item
          v-for="item in navigationItems"
          :key="item.to"
          clickable
          :to="item.to"
          exact
          active-class="bg-primary text-white"
          class="rounded-borders q-mb-xs"
        >
          <q-item-section avatar>
            <q-icon :name="item.icon" />
          </q-item-section>
          <q-item-section>
            <q-item-label>{{ item.label }}</q-item-label>
            <q-item-label caption class="text-inherit">
              {{ item.caption }}
            </q-item-label>
          </q-item-section>
        </q-item>
      </q-list>
    </q-drawer>

    <q-page-container class="bg-grey-1">
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { isApiConfigured } from '../api';

const apiConfigured = isApiConfigured();

const navigationItems = [
  {
    to: '/',
    label: 'Upload',
    caption: 'Send resumes to async processing',
    icon: 'upload_file',
  },
  {
    to: '/search',
    label: 'Search',
    caption: 'Configure filters and review shortlist',
    icon: 'manage_search',
  },
];

const leftDrawerOpen = ref(false);

function toggleLeftDrawer(): void {
  leftDrawerOpen.value = !leftDrawerOpen.value;
}
</script>
