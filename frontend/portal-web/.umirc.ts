export default {
  npmClient: 'pnpm',
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
    },
  },
  routes: [
    { path: '/login', component: '@/pages/Login' },
    { path: '/', redirect: '/chat' },
    { path: '/chat', component: '@/pages/Chat' },
    { path: '/history', component: '@/pages/History' },
  ],
};
