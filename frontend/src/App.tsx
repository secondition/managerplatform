import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';
import { router } from '@/app/router';
import { useBootstrapAuth } from '@/features/auth/useBootstrapAuth';
import { useDocumentBranding } from '@/features/settings/useDocumentBranding';
import { useApplyTheme } from '@/stores/themeStore';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});

// Bootstraps the session (GET /auth/me) once, then renders the router. The auth
// store starts in 'loading', so RequireAuth shows a spinner until this resolves.
function Root() {
  useBootstrapAuth();
  useDocumentBranding();
  useApplyTheme();
  return <RouterProvider router={router} />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Root />
    </QueryClientProvider>
  );
}
