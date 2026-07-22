import { useEffect } from 'react';
import { usePublicSettings } from './hooks';

// Syncs the browser tab's favicon + title from the company settings, so an
// admin-uploaded logo replaces the default tab icon everywhere. Runs app-wide.
function setFavicon(href: string): void {
  let link = document.querySelector<HTMLLinkElement>("link[rel~='icon']");
  if (!link) {
    link = document.createElement('link');
    link.rel = 'icon';
    document.head.appendChild(link);
  }
  link.href = href;
}

export function useDocumentBranding(): void {
  const settings = usePublicSettings();
  const logoUrl = settings.data?.logo_url;
  const companyName = settings.data?.company_name;

  useEffect(() => {
    if (logoUrl) setFavicon(logoUrl);
  }, [logoUrl]);

  useEffect(() => {
    if (companyName) document.title = companyName;
  }, [companyName]);
}
