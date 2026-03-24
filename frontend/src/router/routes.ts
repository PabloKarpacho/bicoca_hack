import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('layouts/MainLayout.vue'),
    children: [
      {
        path: '',
        name: 'upload',
        component: () => import('pages/UploadPage.vue'),
        meta: {
          title: 'Upload resumes',
        },
      },
      {
        path: 'search',
        name: 'search',
        component: () => import('pages/SearchPage.vue'),
        meta: {
          title: 'Candidate search',
        },
      },
    ],
  },

  {
    path: '/:catchAll(.*)*',
    component: () => import('pages/ErrorNotFound.vue'),
  },
];

export default routes;
