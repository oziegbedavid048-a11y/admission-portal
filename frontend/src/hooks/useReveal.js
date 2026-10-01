import { useEffect } from 'react';

/**
 * Fades each `.reveal` element up into place the first time it scrolls into
 * view. The class that hides them is only added here, once the observer is
 * running, so without JavaScript every section is simply visible. A visitor who
 * asked for reduced motion gets no movement at all.
 */
export default function useReveal() {
  useEffect(() => {
    const root = document.documentElement;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced || !('IntersectionObserver' in window)) return undefined;

    root.classList.add('reveal-ready');
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { rootMargin: '0px 0px -24px 0px', threshold: 0.05 },
    );

    const watch = () =>
      document.querySelectorAll('.reveal:not(.is-visible)').forEach((node) => observer.observe(node));
    watch();
    // Sections that mount later (the reviews widget) are picked up too.
    const mutations = new MutationObserver(watch);
    mutations.observe(document.body, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
      mutations.disconnect();
      root.classList.remove('reveal-ready');
    };
  }, []);
}
