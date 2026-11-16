// Pagefind's default UI ships no type declarations. These cover what src/components/SiteSearch.astro uses.
declare module '@pagefind/default-ui' {
  export class PagefindUI {
    constructor(options: Record<string, unknown>);
  }
}
declare module '@pagefind/default-ui/css/ui.css';
